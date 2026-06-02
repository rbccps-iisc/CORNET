"""CORNET Orchestrator — loads plugins, drives lifecycle, manages sweep variants."""

from __future__ import annotations

import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Optional

from cornet.config.loader import load_unified
from cornet.config.schema import UnifiedConfig
from cornet.context import ExperimentContext
from cornet.plugins.base import Plugin
import cornet.plugins as _registry

logger = logging.getLogger(__name__)


def _has_cap_net_admin() -> bool:
    """Return True if the process has CAP_NET_ADMIN (bit 12 of CapEff)."""
    if os.geteuid() == 0:
        return True
    try:
        from pathlib import Path as _Path
        status = _Path("/proc/self/status").read_text()
        for line in status.splitlines():
            if line.startswith("CapEff:"):
                cap_eff = int(line.split(":")[1].strip(), 16)
                return bool(cap_eff & (1 << 12))
    except Exception:
        pass
    return False


class Orchestrator:
    """Drives the full CORNET experiment lifecycle.

    Usage::

        orch = Orchestrator()
        orch.run(task_dir="tasks/pendulum_nr_control")
    """

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        *,
        task_dir: Optional[str | Path] = None,
        config_path: Optional[str | Path] = None,
    ) -> None:
        """Run an experiment from a task directory or explicit config path."""
        config, resolved_task_dir = self._resolve_config(task_dir, config_path)
        self._cleanup_stale_launch_files(resolved_task_dir)

        # Sweep expansion
        from cornet.sweep.expander import expand_sweep
        variants = expand_sweep(config)

        previous_ros_domain = os.environ.get("ROS_DOMAIN_ID")
        previous_gazebo_uri = os.environ.get("GAZEBO_MASTER_URI")
        try:
            for variant_index, variant_cfg in enumerate(variants):
                self._apply_ros_domain(variant_cfg, variant_index)
                self._run_variant(variant_cfg, resolved_task_dir)
        finally:
            if previous_ros_domain is None:
                os.environ.pop("ROS_DOMAIN_ID", None)
            else:
                os.environ["ROS_DOMAIN_ID"] = previous_ros_domain
            if previous_gazebo_uri is None:
                os.environ.pop("GAZEBO_MASTER_URI", None)
            else:
                os.environ["GAZEBO_MASTER_URI"] = previous_gazebo_uri

    # ── Internal ─────────────────────────────────────────────────────────────

    def _resolve_config(
        self,
        task_dir: Optional[str | Path],
        config_path: Optional[str | Path],
    ) -> tuple[UnifiedConfig, Path | None]:
        """Return (UnifiedConfig, task_dir_path)."""
        if task_dir is not None:
            td = Path(task_dir)
            cfg_file = td / "config.yaml"
            if not cfg_file.exists():
                logger.error("No config.yaml found in task directory: %s", td)
                sys.exit(1)
            return load_unified(cfg_file), td

        if config_path is not None:
            p = Path(config_path)
            return load_unified(p), p.parent

        logger.error("Either task_dir or config_path must be provided.")
        sys.exit(1)

    def _run_variant(self, config: UnifiedConfig, task_dir: Path | None) -> None:
        """Run a single variant through the full lifecycle."""
        # Inject NS-3 version tag into variant_id before ExperimentContext is built
        # so that every downstream consumer (context, leaderboard, logs) sees the tag.
        # Controlled by CORNET_NS3_TAG env var (e.g. "ns3-v24"). No-op when unset.
        ns3_tag = os.environ.get("CORNET_NS3_TAG")
        if ns3_tag:
            config.experiment.name = f"{config.experiment.name}@{ns3_tag}"

        context = ExperimentContext(variant_id=config.experiment.name)
        output_dir = Path(config.experiment.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Auto-discover launch.py and world.sdf from task dir
        if task_dir is not None:
            self._auto_discover(config, task_dir)

        # Preflight check
        self._preflight(config)

        plugins = self._load_plugins(config)

        started: list[Plugin] = []
        try:
            for p in plugins:
                p.configure(config, context)
            for p in plugins:
                p.start()
                started.append(p)

            logger.info("Running experiment '%s' for %.1f s …", config.experiment.name, config.experiment.duration)
            self._run_plugins(plugins, config.experiment.duration)

        except Exception:
            logger.exception("Error during experiment run")
            raise
        finally:
            # Stop in reverse order
            for p in reversed(started):
                try:
                    p.stop()
                except Exception:
                    logger.exception("Error stopping plugin %s", type(p).__name__)

        # Collect phase (after stop, no rollback on error)
        for p in plugins:
            try:
                p.collect(output_dir)
            except Exception:
                logger.exception("Error collecting from plugin %s", type(p).__name__)

        try:
            self._eval_and_record(config, task_dir, output_dir)
        except ValueError as exc:
            logger.error(
                "EvalTool metric error for variant '%s': %s",
                config.experiment.name,
                exc,
            )
            if task_dir is not None:
                import datetime
                from cornet.leaderboard.writer import append_entry
                append_entry(
                    task_dir=str(task_dir),
                    entry={
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "variant_id": config.experiment.name,
                        "status": "FAILURE",
                        "metric": None,
                        "output_dir": str(output_dir),
                        "primary_metric": config.experiment.primary_metric,
                        "error": str(exc),
                    },
                )

    def _apply_ros_domain(self, config: UnifiedConfig, variant_index: int) -> None:
        """Assign per-variant ROS_DOMAIN_ID when sweep.parallel is enabled."""
        sweep = config.experiment.sweep
        if sweep is None or not sweep.parallel:
            return

        base_domain = int(os.environ.get("ROS_DOMAIN_ID", "0"))
        domain_id = base_domain + variant_index
        if domain_id > 101:
            raise ValueError(
                f"ROS_DOMAIN_ID {domain_id} exceeds ROS 2 limit (101). "
                "Reduce sweep width or lower the base ROS_DOMAIN_ID."
            )

        os.environ["ROS_DOMAIN_ID"] = str(domain_id)
        logger.info(
            "Assigned ROS_DOMAIN_ID=%s for variant '%s'",
            domain_id,
            config.experiment.name,
        )

        if config.robot is not None:
            gazebo_port = 11345 + variant_index
            os.environ["GAZEBO_MASTER_URI"] = f"http://localhost:{gazebo_port}"
            logger.info(
                "Assigned GAZEBO_MASTER_URI=http://localhost:%s for variant '%s'",
                gazebo_port,
                config.experiment.name,
            )

    def _auto_discover(self, config: UnifiedConfig, task_dir: Path) -> None:
        """Set robot.launch_file and robot.world from task_dir if not explicitly provided."""
        if config.robot.launch_file is None:
            for candidate in ("launch.py", "launch.xml"):
                if (task_dir / candidate).exists():
                    config.robot.launch_file = str(task_dir / candidate)
                    logger.debug("Auto-discovered launch file: %s", config.robot.launch_file)
                    break
        if config.robot.world is None:
            if (task_dir / "world.sdf").exists():
                config.robot.world = str(task_dir / "world.sdf")
                logger.debug("Auto-discovered world: %s", config.robot.world)

    def _preflight(self, config: UnifiedConfig) -> None:
        """Abort early if required privileges or capabilities are missing."""
        mininet_plugins = {"mininet", "ns3+mininet"}
        if config.network.plugin in mininet_plugins and os.getuid() != 0:
            logger.error(
                "Plugin '%s' requires root. Re-run with sudo.", config.network.plugin
            )
            sys.exit(1)

        # NS-3 with middleware enabled requires CAP_NET_ADMIN for TUN creation
        mw = config.network.middleware
        if (
            config.network.plugin in {"ns3", "ns3+mininet"}
            and mw is not None
            and mw.enabled
        ):
            if not _has_cap_net_admin():
                logger.error(
                    "NS-3 middleware requires CAP_NET_ADMIN to create TUN interfaces. "
                    "Re-run with sudo, or grant the capability:\n"
                    "  sudo setcap cap_net_admin+ep $(which python3)"
                )
                sys.exit(1)

    def _load_plugins(self, config: UnifiedConfig) -> list[Plugin]:
        """Instantiate network and robot plugins from the registry."""
        plugins: list[Plugin] = []
        for name in (config.network.plugin, config.robot.plugin):
            cls = _registry.get(name)
            plugins.append(cls())
        return plugins

    def _run_plugins(self, plugins: list[Plugin], duration: float) -> None:
        """Call run() on all plugins (non-blocking), then sleep for duration."""
        for p in plugins:
            p.run()
        time.sleep(duration)

    def _eval_and_record(
        self,
        config: UnifiedConfig,
        task_dir: Path | None,
        output_dir: Path,
    ) -> None:
        """Call EvalTool if present and write leaderboard entry."""
        if task_dir is None:
            return

        eval_module_path = task_dir / "eval" / "eval_tool.py"
        if not eval_module_path.exists():
            return

        import importlib.util
        spec = importlib.util.spec_from_file_location("eval_tool", eval_module_path)
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        eval_tool = mod.EvalTool()
        result_str = eval_tool.run_evaluation(str(output_dir))

        parts = result_str.strip().split(",", 1)
        status = parts[0].strip()
        metric_str = parts[1].strip() if len(parts) > 1 else ""

        try:
            metric = float(metric_str)
        except ValueError:
            raise ValueError(
                f"EvalTool returned non-float metric: {metric_str!r}. "
                "Use EvalTool.format_result() to construct the return string."
            )
        if not math.isfinite(metric):
            raise ValueError(
                f"EvalTool returned non-finite metric: {metric_str!r} (got {metric}). "
                "Use EvalTool.format_result() to construct the return string."
            )

        from cornet.leaderboard.writer import append_entry
        import datetime
        append_entry(
            task_dir=str(task_dir),
            entry={
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "variant_id": config.experiment.name,
                "status": status,
                "metric": metric,
                "output_dir": str(output_dir),
                "primary_metric": config.experiment.primary_metric,
            },
        )
        logger.info("Leaderboard entry written: %s, metric=%s", status, metric)

    def _cleanup_stale_launch_files(self, task_dir: Path) -> None:
        """Remove generated_launch_*.py files older than 1 hour from task_dir."""
        now = time.time()
        for stale_file in task_dir.glob("generated_launch_*.py"):
            age = now - stale_file.stat().st_mtime
            if age > 3600:
                stale_file.unlink()
                logger.debug("Removed stale launch file: %s (age %.0fs)", stale_file, age)
