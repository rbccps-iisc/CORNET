"""NS-3 5G NR network plugin for CORNET.

Wraps the network_manager.py and cornet_middleware.py logic from CORNET3.0.
The NS-3 simulation binary is expected to be built at $NS3_DIR or ~/ns-3-dev/.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from cornet.plugins.base import Plugin

if TYPE_CHECKING:
    from cornet.config.schema import UnifiedConfig
    from cornet.context import ExperimentContext

logger = logging.getLogger(__name__)


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
            self._dispatcher = PacketDispatcher(
                rtf=mw.rtf,
                deadline_s=mw.deadline_s,
                ber=mw.ber,
                on_dispatch=self._on_packet_dispatch,
            )
            self._aoi_tracker = AoITracker()

        self._validate_scenario(sc)

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

        # ── Build NS-3 command ────────────────────────────────────────
        args = [str(ns3_dir / "ns3"), "run", script, "--"]
        for key, val in extra.items():
            if key == "simulation_script":
                continue
            args.append(f"--{key}={val}")

        # Forward scenario parameters as CLI args
        if sc is not None:
            if sc.numerology is not None:
                args.append(f"--numerology={sc.numerology}")
            if sc.bandwidth_mhz is not None:
                args.append(f"--bandwidth={sc.bandwidth_mhz}")
            if sc.scheduler is not None:
                args.append(f"--scheduler={sc.scheduler}")

        # Pass TUN interface names to NS-3
        for i, (if_name, ip) in enumerate(tun_map.items()):
            args.append(f"--tun{i}={if_name},{ip}")

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
            logger.info("AoI summary written to %s", output_dir / "aoi_summary.json")


# Register
from cornet.plugins import register as _register
_register("ns3", Ns3Plugin)
