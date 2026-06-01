"""Mininet-WiFi + Docker plugin for CORNET.

Requires root (sudo) and mininet-wifi installed on the host.

Port of CORNET2.0 network/network_config.py topology-building logic, adapted
to the CORNET Plugin lifecycle interface.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from cornet.plugins.base import Plugin

if TYPE_CHECKING:
    from cornet.config.schema import NodeConfig, UnifiedConfig
    from cornet.context import ExperimentContext

logger = logging.getLogger(__name__)


class MininetPlugin(Plugin):
    """Mininet-WiFi network plugin with Docker container support.

    Supported node types (``network.nodes[].type``):
    - ``MOBILE``  → Mininet-WiFi station (802.11)
    - ``STATIC``  → Mininet-WiFi host + access-point pair
    - ``UE``      → alias for MOBILE
    - ``GNB``     → alias for STATIC (treated as AP)
    """

    def __init__(self) -> None:
        self._net = None          # mininet_wifi.net.Mininet_wifi instance
        self._config = None
        self._context = None
        self._container_ids: list[str] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def configure(self, config: "UnifiedConfig", context: "ExperimentContext") -> None:
        self._config = config
        self._context = context

        # Pre-pull Docker images for container nodes
        for node in config.network.nodes:
            if node.container and node.container.image:
                logger.info("Pulling Docker image: %s", node.container.image)
                try:
                    subprocess.run(
                        ["docker", "pull", node.container.image],
                        check=True,
                        capture_output=True,
                    )
                except subprocess.CalledProcessError as exc:
                    logger.warning("Failed to pull %s: %s", node.container.image, exc.stderr.decode())

    def start(self) -> None:
        try:
            from mn_wifi.net import Mininet_wifi  # type: ignore[import]
            from mn_wifi.link import wmediumd, adhoc  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "mininet-wifi is not installed. Install it with: "
                "git clone https://github.com/intrig-unicamp/mininet-wifi && "
                "cd mininet-wifi && sudo util/install.sh -Wlnfv"
            ) from exc

        cfg = self._config
        use_wmediumd = cfg.network.mininet and cfg.network.mininet.wmediumd

        if use_wmediumd:
            self._net = Mininet_wifi(link=wmediumd)
        else:
            self._net = Mininet_wifi()

        self._build_topology(cfg.network.nodes)

        if use_wmediumd:
            self._net.setPropagationModel(model="logDistance", exp=3)

        self._net.build()
        self._net.start()

        # Populate context with node IPs
        for node in cfg.network.nodes:
            mn_node = self._net.get(node.name)
            if mn_node is not None:
                ip = mn_node.IP()
                self._context.network.node_ips[node.name] = ip
                logger.debug("Node %s IP: %s", node.name, ip)

        logger.info("Mininet-WiFi topology started (%d nodes)", len(cfg.network.nodes))

    def run(self) -> None:
        pass  # topology runs passively; duration controlled by Orchestrator

    def stop(self) -> None:
        if self._net is not None:
            try:
                self._net.stop()
                logger.info("Mininet-WiFi topology stopped")
            except Exception:
                logger.exception("Error stopping Mininet topology")
            self._net = None

        for cid in self._container_ids:
            try:
                subprocess.run(["docker", "rm", "-f", cid], check=False, capture_output=True)
            except Exception:
                pass
        self._container_ids.clear()

    def collect(self, output_dir: Path) -> None:
        pass  # no artefacts to collect for basic topology

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_topology(self, nodes: list["NodeConfig"]) -> None:
        """Add stations, APs, and links to self._net based on node configs."""
        for node in nodes:
            ntype = node.type.upper() if node.type else "MOBILE"

            if ntype in ("MOBILE", "UE"):
                self._net.addStation(
                    node.name,
                    **({"ip": node.model_extra.get("ip")} if hasattr(node, "model_extra") and node.model_extra.get("ip") else {}),
                )
            elif ntype in ("STATIC", "GNB"):
                self._net.addAP(node.name, ssid=self._config.network.mininet.ssid if self._config.network.mininet else "cornet-net")
            else:
                logger.warning("Unknown node type '%s' for node '%s'; adding as host", ntype, node.name)
                self._net.addHost(node.name)

        # Default: connect all to first AP if present
        aps = [n for n in nodes if n.type.upper() in ("STATIC", "GNB")]
        if aps:
            self._net.addController("c0")


# Register
from cornet.plugins import register as _register
_register("mininet", MininetPlugin)
