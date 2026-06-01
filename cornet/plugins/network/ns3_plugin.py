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
    - ``simulation_script``: name of the scratch script to run (required)
    - ``numerology``, ``bandwidth``, ``scheduler``, etc.: forwarded as CLI args
    """

    def __init__(self) -> None:
        self._config = None
        self._context = None
        self._ns3_proc: subprocess.Popen | None = None
        self._middleware_proc: subprocess.Popen | None = None
        self._ns3_dir: Path | None = None

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

    def start(self) -> None:
        cfg = self._config
        ns3_dir = self._ns3_dir

        # Extract simulation script name from extra config keys
        extra = cfg.network.model_extra if hasattr(cfg.network, "model_extra") else {}
        script = extra.get("simulation_script")
        if not script:
            logger.warning("No 'simulation_script' in network config; skipping NS-3 launch")
            return

        # Build CLI argument list from extra numeric/string keys
        args = [str(ns3_dir / "ns3"), "run", script, "--"]
        for key, val in extra.items():
            if key == "simulation_script":
                continue
            args.append(f"--{key}={val}")

        logger.info("Launching NS-3: %s", " ".join(args))
        self._ns3_proc = subprocess.Popen(
            args,
            cwd=str(ns3_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # Populate stub IPs (real IPs come from middleware TUN/TAP after setup)
        for node in cfg.network.nodes:
            self._context.network.node_ips[node.name] = f"10.0.0.{len(self._context.network.node_ips) + 1}"

    def run(self) -> None:
        pass

    def stop(self) -> None:
        for proc_attr in ("_ns3_proc", "_middleware_proc"):
            proc: subprocess.Popen | None = getattr(self, proc_attr, None)
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                setattr(self, proc_attr, None)
        logger.info("NS-3 plugin stopped")

    def collect(self, output_dir: Path) -> None:
        pass


# Register
from cornet.plugins import register as _register
_register("ns3", Ns3Plugin)
