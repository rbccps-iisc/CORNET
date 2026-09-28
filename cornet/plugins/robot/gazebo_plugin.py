"""Gazebo Classic + ROS 2 robot plugin for CORNET."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cornet.plugins.base import Plugin

if TYPE_CHECKING:
    from cornet.config.schema import UnifiedConfig
    from cornet.context import ExperimentContext

logger = logging.getLogger(__name__)

_CLOCK_TOPIC_TIMEOUT = 60  # seconds to wait for /clock to appear


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError):
        if proc.poll() is None:
            proc.send_signal(sig)


class GazeboPlugin(Plugin):
    """Launches Gazebo Classic via ros2 launch; spawns robots per config.

    If ``robot.launch_file`` is set, that file is used directly.
    Otherwise, a launch file is auto-generated from ``robot.robots``.
    """

    def __init__(self) -> None:
        self._config = None
        self._context = None
        self._launch_path: Path | None = None
        self._launch_dir: Path | None = None
        self._launch_proc: subprocess.Popen | None = None
        self._auto_generated = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def configure(self, config: "UnifiedConfig", context: "ExperimentContext") -> None:
        self._config = config
        self._context = context

        if config.robot.launch_file:
            self._launch_path = Path(config.robot.launch_file)
            self._auto_generated = False
        else:
            # Will be set in start() once we know task_dir — we need task_dir
            # The Orchestrator sets launch_file via auto-discovery before configure(),
            # so if we get here launch_file is truly absent.
            self._auto_generated = True

    def start(self) -> None:
        cfg = self._config

        if self._auto_generated:
            # Generate from robot config — use a temp dir
            import tempfile
            self._launch_dir = Path(tempfile.mkdtemp(prefix="cornet_launch_"))
            from cornet.gazebo.generic_launch import generate
            self._launch_path = generate(cfg.robot, self._launch_dir)
            logger.info("Auto-generated launch file: %s", self._launch_path)

        if self._launch_path is None or not self._launch_path.exists():
            raise FileNotFoundError(f"Launch file not found: {self._launch_path}")

        logger.info("Launching Gazebo via: ros2 launch %s", self._launch_path)
        env = os.environ.copy()
        robot = getattr(cfg, "robot", None)
        repo_root = Path(__file__).resolve().parents[3]
        model_paths = []
        for path in getattr(robot, "model_paths", None) or []:
            if not path:
                continue
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = repo_root / path
            model_paths.append(str(candidate))
        if model_paths:
            existing = env.get("GAZEBO_MODEL_PATH", "")
            prefix = os.pathsep.join(model_paths)
            env["GAZEBO_MODEL_PATH"] = f"{prefix}{os.pathsep}{existing}" if existing else prefix
        plugin_dir = Path(__file__).resolve().parents[3] / "scripts" / "gazebo" / "actor_collisions" / "build"
        if plugin_dir.is_dir():
            existing = env.get("GAZEBO_PLUGIN_PATH", "")
            env["GAZEBO_PLUGIN_PATH"] = f"{plugin_dir}{os.pathsep}{existing}" if existing else str(plugin_dir)
        self._launch_proc = subprocess.Popen(
            ["ros2", "launch", str(self._launch_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            env=env,
        )

        self._wait_for_clock()

    def run(self) -> None:
        pass

    def stop(self) -> None:
        proc = self._launch_proc
        self._launch_proc = None
        if proc is not None:
            self._stop_process_group(proc)
            logger.info("Gazebo launch process stopped")

        if self._auto_generated and self._launch_dir is not None:
            shutil.rmtree(self._launch_dir, ignore_errors=True)
            self._launch_dir = None
        elif self._auto_generated and self._launch_path and self._launch_path.exists():
            self._launch_path.unlink(missing_ok=True)

    @staticmethod
    def _stop_process_group(proc: subprocess.Popen) -> None:
        """Stop ros2 launch and the gzserver/gzclient processes it spawned.

        SIGTERM on the launch parent leaves gzserver running. The launch
        process is started in its own session, so the group id is its pid
        even after the parent has already exited.
        """
        if proc.poll() is None:
            _signal_group(proc, signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        _signal_group(proc, signal.SIGKILL)
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def collect(self, output_dir: Path) -> None:
        pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _wait_for_clock(self) -> None:
        """Poll until Gazebo /clock topic appears or timeout."""
        deadline = time.monotonic() + _CLOCK_TOPIC_TIMEOUT
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["ros2", "topic", "list"],
                capture_output=True,
                text=True,
            )
            if "/clock" in result.stdout:
                logger.info("Gazebo /clock topic available — simulation running")
                return
            if self._launch_proc and self._launch_proc.poll() is not None:
                output = ""
                if self._launch_proc.stdout is not None:
                    output = self._launch_proc.stdout.read() or ""
                detail = f"\n{output}" if output else ""
                raise RuntimeError(
                    f"ros2 launch exited early (code {self._launch_proc.returncode}){detail}"
                )
            time.sleep(2)
        raise TimeoutError(
            f"Gazebo /clock not available after {_CLOCK_TOPIC_TIMEOUT} s. "
            "Check Gazebo installation and ROS 2 environment."
        )


# Register
from cornet.plugins import register as _register
_register("gazebo", GazeboPlugin)
