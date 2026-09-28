"""NS-3 5G NR network plugin for CORNET.

Wraps the network_manager.py and cornet_middleware.py logic from CORNET3.0.
The NS-3 simulation binary is expected to be built at $NS3_DIR or ~/ns-3-dev/.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cornet.plugins.base import Plugin

from cornet.config.schema import UnifiedConfig

if TYPE_CHECKING:
    from cornet.context import ExperimentContext

logger = logging.getLogger(__name__)


def append_experiment_args(args: list[str], cfg: UnifiedConfig) -> None:
    """Append duration and the variant seed when the caller has not set them."""
    if not any(arg.startswith("--simTime=") for arg in args):
        args.append(f"--simTime={cfg.experiment.duration}")
    if not any(arg.startswith("--rngRun=") for arg in args):
        args.append(f"--rngRun={cfg.experiment.seed}")

# Scratch scripts in this repository that accept --timingLog / --timingPeriodMs.
_TIMING_SCRIPTS = {
    "remote_robot_control-default",
    "scratch_template-default",
    "bench_nr_multicell-default",
    "nr_multicell-default",
    "lte_multicell-default",
    "wifi_basic-default",
}


def nodes_payload(previous: dict, current: dict, dt: float) -> dict:
    """Constant-velocity snapshot. The first sample for a name has zero velocity."""
    step = dt if dt > 0 else 1.0
    nodes = {}
    for name, pos in current.items():
        prev = previous.get(name)
        if prev is None:
            vx = vy = vz = 0.0
        else:
            vx = (float(pos["x"]) - float(prev["x"])) / step
            vy = (float(pos["y"]) - float(prev["y"])) / step
            vz = (float(pos["z"]) - float(prev["z"])) / step
        nodes[name] = [float(pos["x"]), float(pos["y"]), float(pos["z"]), vx, vy, vz]
    return {"nodes": nodes}


def script_supports_timing(script: str) -> bool:
    """True when *script* is a bundled CORNET scratch program."""
    name = Path(script).name
    if name.endswith(".cc"):
        name = name[:-3]
    if name in _TIMING_SCRIPTS:
        return True
    # ns-3's runnable shortcut drops the CORNET "-default" profile suffix.
    return f"{name}-default" in _TIMING_SCRIPTS


def _scratch_lane(ns3_dir: Path | None) -> str:
    """Patch-set directory that matches the installed NS-3 tree."""
    if ns3_dir is not None:
        nr = ns3_dir / "contrib" / "nr"
        if (nr / ".cornet-patched-v5.1").is_file():
            return "v5.1-ns3.48"
        if (nr / ".cornet-patched-v4.2").is_file():
            return "v4.2-ns3.47"
        if (nr / ".cornet-patched-v2.4").is_file():
            return "v2.4-ns3.38"
    return "v2.4-ns3.38"


def bundled_script_source(script: str, ns3_dir: Path | None = None) -> Path | None:
    """Return the repository ``.cc`` for a bundled script name, if it exists."""
    name = Path(script).name
    stem = name[:-3] if name.endswith(".cc") else name
    if stem not in _TIMING_SCRIPTS:
        return None
    root = Path(__file__).resolve().parents[3]
    lane = _scratch_lane(ns3_dir)
    candidates = [
        root / "scripts" / "ns3" / "scratch" / lane / f"{stem}.cc",
        root / "scripts" / "ns3" / "scratch" / "v2.4-ns3.38" / f"{stem}.cc",
        root / "scripts" / "ns3" / "scratch" / f"{stem}.cc",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def install_bundled_script(ns3_dir: Path, script: str) -> str:
    """Copy a bundled script into the NS-3 scratch directory and return its run target.

    ``./ns3 run`` only resolves programs inside that tree, not arbitrary ``.cc`` paths.
    """
    source = bundled_script_source(script, ns3_dir)
    if source is None or ns3_dir is None:
        return script
    dest_dir = ns3_dir / "scratch"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    if not dest.is_file() or dest.read_bytes() != source.read_bytes():
        shutil.copy2(source, dest)
        # copy2 keeps the source mtime. An older source would not rebuild.
        os.utime(dest, None)
    # Filename suffix "-default" is the CORNET profile tag. ns-3 also appends
    # "-<build-profile>" and then strips every "-default", so the runnable
    # shortcut is the stem without that suffix.
    stem = source.stem
    if stem.endswith("-default"):
        stem = stem[: -len("-default")]
    return stem


class PluginConfigError(RuntimeError):
    """Raised when plugin configuration is structurally valid but unsupported."""

# Map ScenarioConfig.profile to the cornet/scenarios/ template path
_SCENARIO_TEMPLATES: dict[str, str] = {
    "5g_nr_urllc": "5g_nr_urllc/run.py",
    "5g_nr_embb":  "5g_nr_embb/run.py",
    "5g_nr_mmtc":  "5g_nr_mmtc/run.py",
    "6g_thz":      "6g_thz/run.py",
}


def _find_ns3_dir() -> Path | None:
    """Return NS-3 build directory from $NS3_DIR or default locations."""
    env_dir = os.environ.get("NS3_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p
    for candidate in [Path.home() / "ns-3-dev", Path("/usr/local/ns-3")]:
        if candidate.exists():
            return candidate
    return None


class Ns3Plugin(Plugin):
    """NS-3 5G NR network plugin.

    Reads NS-3-specific keys from ``config.network`` (passed through ``extra``):
    - ``simulation_script``: name of the scratch script to run (required unless
      ``scenario`` profile is set, in which case the built-in template is used)
    - ``numerology``, ``bandwidth``, ``scheduler``, etc.: forwarded as CLI args

    When ``config.network.middleware.enabled`` is True, the plugin additionally:
    - Creates TUN interfaces via TunManager
    - Starts ClockServer, PositionServer, PacketDispatcher
    - Passes ``--tunX=<ifname>,<ip>`` args to NS-3
    - Collects AoI statistics on stop
    """

    def __init__(self) -> None:
        self._config = None
        self._context = None
        self._ns3_proc: subprocess.Popen | None = None
        self._middleware_proc: subprocess.Popen | None = None
        self._ns3_dir: Path | None = None

        # Middleware components (only populated when middleware.enabled)
        self._tun_manager = None
        self._clock_server = None
        self._pos_server = None
        self._positions_socket: str | None = None
        self._forward_stop = threading.Event()
        self._forward_thread: threading.Thread | None = None
        self._dispatcher = None
        self._aoi_tracker = None

    def _on_clock_tick(self, physics_time: float) -> None:
        if self._dispatcher is not None:
            self._dispatcher.update_physics_time(physics_time)
        if self._aoi_tracker is not None:
            self._aoi_tracker.update_physics_time(physics_time)
            self._aoi_tracker.sample()

    def _on_packet_dispatch(self, flow_id: str, payload: bytes) -> None:
        if self._aoi_tracker is not None and self._clock_server is not None:
            self._aoi_tracker.record_update(flow_id, self._clock_server.physics_time)

    def _scenario_script(self, profile: str) -> Path:
        template_rel = _SCENARIO_TEMPLATES[profile]
        return Path(__file__).parent.parent.parent / "scenarios" / template_rel

    def _validate_scenario(self, scenario) -> None:
        if scenario is None:
            return
        if scenario.profile == "6g_thz":
            logger.warning("Scenario profile 6g_thz is experimental. Behavior may change.")
            thz_paths = [self._ns3_dir / "src" / "thz", self._ns3_dir / "src" / "ns3-thz"]
            if not any(path.exists() for path in thz_paths):
                logger.warning("6g_thz profile requires ns3-thz module. See docs/INSTALL.md#ns3-thz.")
                raise PluginConfigError(
                    "6g_thz profile requires ns3-thz module. See docs/INSTALL.md#ns3-thz."
                )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _ensure_mobility_positions(self, net) -> None:
        """Start a PositionServer for mobile scenarios even when middleware is off."""
        mob = getattr(net, "mobility", None)
        if not mob or not mob.enabled or self._pos_server is not None:
            return
        from cornet.middleware.clock import PositionServer

        mw = getattr(net, "middleware", None)
        path = mw.positions_socket if mw else "/tmp/cornet_positions.sock"
        self._positions_socket = path
        self._pos_server = PositionServer(socket_path=path)

    def _start_position_forwarder(self, update_hz: float) -> None:
        """Publish constant-velocity snapshots at ``network.mobility.update_hz``."""
        period = 1.0 / update_hz if update_hz and update_hz > 0 else 0.1
        self._forward_stop.clear()

        def loop() -> None:
            previous: dict = {}
            previous_t = time.monotonic()
            while not self._forward_stop.wait(period):
                now = time.monotonic()
                current = self._pos_server.all_positions() if self._pos_server else {}
                payload = nodes_payload(previous, current, now - previous_t)
                previous = current
                previous_t = now
                if payload["nodes"] and self._pos_server is not None:
                    self._pos_server.broadcast(payload)

        self._forward_thread = threading.Thread(target=loop, name="cornet-position-forwarder", daemon=True)
        self._forward_thread.start()

    def configure(self, config: "UnifiedConfig", context: "ExperimentContext") -> None:
        self._config = config
        self._context = context

        self._ns3_dir = _find_ns3_dir()
        if self._ns3_dir is None:
            logger.error(
                "NS-3 directory not found. Set $NS3_DIR or install to ~/ns-3-dev/. "
                "See docs/INSTALL.md."
            )
            sys.exit(1)

        ns3_bin = self._ns3_dir / "ns3"
        if not ns3_bin.exists():
            logger.error("NS-3 binary not found at %s", ns3_bin)
            sys.exit(1)

        logger.info("NS-3 found at %s", self._ns3_dir)

        # Eagerly read middleware and scenario configs
        net = config.network
        mw = net.middleware
        sc = net.scenario

        if mw and mw.enabled:
            from cornet.middleware import (  # noqa: PLC0415
                AoITracker,
                ClockServer,
                PacketDispatcher,
                PositionServer,
                TunManager,
            )
            self._tun_manager = TunManager(ip_list=mw.ip_list)
            self._clock_server = ClockServer(
                socket_path=mw.clock_socket,
                clock_timeout_s=mw.clock_timeout_s,
                on_tick=self._on_clock_tick,
            )
            self._pos_server = PositionServer(socket_path=mw.positions_socket)
            self._positions_socket = mw.positions_socket
            self._dispatcher = PacketDispatcher(
                rtf=mw.rtf,
                deadline_s=mw.deadline_s,
                ber=mw.ber,
                on_dispatch=self._on_packet_dispatch,
            )
            self._aoi_tracker = AoITracker()

        self._ensure_mobility_positions(net)
        self._validate_scenario(sc)

    def _guard_lane_flags(self, ns3_dir: Path, extra: dict) -> None:
        """Reject flags the installed lane cannot provide before NS-3 starts."""
        from cornet.capabilities import capability_level, installed_patch_set

        lane = installed_patch_set(ns3_dir) or "unknown"
        wrap = str(extra.get("wraparound", "")).lower()
        if wrap in {"1", "true", "yes"} and capability_level("hex_wraparound", lane) is None:
            logger.error(
                "hex_wraparound is not available on %s. --wraparound=true requires a lane "
                "that lists hex_wraparound (v4.2-ns3.47 or v5.1-ns3.48).",
                lane,
            )
            sys.exit(1)
        block = str(extra.get("blockage", "")).lower()
        if block in {"1", "true", "yes"} and capability_level("blockage_model_a", lane) is None:
            logger.error(
                "blockage_model_a is not available on %s. --blockage=true requires that capability.",
                lane,
            )
            sys.exit(1)

    def _write_aerial_provenance(self, cfg, extra: dict) -> None:
        aerial = {"UMa-AV", "UMi-AV", "RMa-AV"}
        used = [str(value) for value in extra.values() if str(value) in aerial]
        if not used:
            return
        path = Path(cfg.experiment.output_dir).resolve() / "provenance.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"caveat": "aerial path loss only", "scenarios": ['
            + ", ".join(f'"{name}"' for name in used)
            + "]}\n"
        )

    def start(self) -> None:
        cfg = self._config
        ns3_dir = self._ns3_dir
        mw = cfg.network.middleware
        sc = cfg.network.scenario

        tun_map: dict[str, str] = {}
        if mw and mw.enabled:
            tun_map = self._tun_manager.setup()
            logger.info("TUN interfaces created: %s", tun_map)

        extra = cfg.network.model_extra if hasattr(cfg.network, "model_extra") else {}
        script = extra.get("simulation_script")

        if script is None and sc is not None:
            template_path = self._scenario_script(sc.profile)
            if template_path.exists():
                script = str(template_path)
                logger.info("Using built-in scenario template: %s", template_path)
            else:
                logger.warning("Scenario template not found: %s", template_path)

        if not script:
            logger.warning("No 'simulation_script' in network config; skipping NS-3 launch")
            return

        # NS-3 only runs scratch programs that live in its own tree.
        script = install_bundled_script(ns3_dir, str(script))

        # ── Build NS-3 command ────────────────────────────────────────
        args = [str(ns3_dir / "ns3"), "run", script, "--"]
        for key, val in extra.items():
            if key in {"simulation_script", "timing_log", "layoutFile"}:
                continue
            args.append(f"--{key}={val}")
        append_experiment_args(args, cfg)

        layout_file = extra.get("layoutFile")
        if layout_file:
            layout_path = Path(str(layout_file))
            if not layout_path.is_absolute():
                base = Path(getattr(self._context, "task_dir", "") or ".")
                layout_path = (base / layout_path).resolve()
            args.append(f"--layoutFile={layout_path}")

        forward_timing = script_supports_timing(script) or bool(getattr(cfg.network, "timing_log", False))
        if forward_timing:
            log_path = Path(cfg.experiment.output_dir).resolve() / "ns3_timing.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            args.append(f"--timingLog={log_path}")
            args.append("--timingPeriodMs=10")
        lane = _scratch_lane(ns3_dir)
        if lane in {"v4.2-ns3.47", "v5.1-ns3.48"} and script_supports_timing(script):
            stats_path = Path(cfg.experiment.output_dir).resolve() / "analysis" / "aoi_statistics.json"
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            args.append(f"--aoiStats={stats_path}")

        # Forward scenario parameters as CLI args
        if sc is not None:
            if sc.numerology is not None:
                args.append(f"--numerology={sc.numerology}")
            if sc.bandwidth_mhz is not None:
                args.append(f"--bandwidth={sc.bandwidth_mhz}")
            if sc.scheduler is not None:
                args.append(f"--scheduler={sc.scheduler}")

        # Pass TUN interface names to NS-3 (design D14: plugin owns naming)
        for i, (if_name, ip) in enumerate(tun_map.items()):
            args.append(f"--tun{i}={if_name},{ip}")

        # Pass port numbers from schema fields (design D16)
        if mw and mw.enabled:
            args.append(f"--sensorPort={mw.sensor_port}")
            args.append(f"--controlPort={mw.control_port}")
            args.append(f"--positionsSocket={mw.positions_socket}")
        elif cfg.network.mobility and cfg.network.mobility.enabled and self._positions_socket:
            args.append(f"--positionsSocket={self._positions_socket}")

        self._guard_lane_flags(ns3_dir, extra)
        self._write_aerial_provenance(cfg, extra)

        logger.info("Launching NS-3: %s", " ".join(args))
        try:
            self._ns3_proc = subprocess.Popen(
                args,
                cwd=str(ns3_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self._ns3_proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass
            else:
                if self._ns3_proc.returncode != 0:
                    stderr = self._ns3_proc.stderr.read() if self._ns3_proc.stderr else ""
                    raise RuntimeError(stderr.strip() or "NS-3 exited before startup completed")
        except Exception:
            if mw and mw.enabled and self._tun_manager is not None:
                self._tun_manager.teardown()
            raise

        if mw and mw.enabled:
            self._clock_server.start()
            self._pos_server.start()
            self._dispatcher.start()
        elif self._pos_server is not None:
            self._pos_server.start()

        mob = cfg.network.mobility
        if mob and mob.enabled and self._pos_server is not None:
            self._start_position_forwarder(mob.update_hz)

        # Populate node IPs from TUN map or fallback stubs
        tun_ips = list(tun_map.values())
        for i, node in enumerate(cfg.network.nodes):
            ip = node.ip or (tun_ips[i] if i < len(tun_ips) else f"10.0.0.{i + 1}")
            self._context.network.node_ips[node.name] = ip

    def run(self) -> None:
        pass

    def stop(self) -> None:
        if self._dispatcher is not None:
            self._dispatcher.stop()

        for proc_attr in ("_ns3_proc", "_middleware_proc"):
            proc: subprocess.Popen | None = getattr(self, proc_attr, None)
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                setattr(self, proc_attr, None)

        self._forward_stop.set()
        if self._forward_thread is not None:
            self._forward_thread.join(timeout=2.0)
            self._forward_thread = None
        if self._clock_server is not None:
            self._clock_server.stop()
        if self._pos_server is not None:
            self._pos_server.stop()
        if self._tun_manager is not None:
            self._tun_manager.teardown()

        logger.info("NS-3 plugin stopped")

    def collect(self, output_dir: Path) -> None:
        if self._aoi_tracker is not None:
            self._aoi_tracker.close()
            self._aoi_tracker.export_json(output_dir / "aoi_summary.json")
            self._aoi_tracker.export_eval_statistics(output_dir / "analysis" / "aoi_statistics.json")
            logger.info("AoI summary written to %s", output_dir / "aoi_summary.json")


# Register
from cornet.plugins import register as _register
_register("ns3", Ns3Plugin)
