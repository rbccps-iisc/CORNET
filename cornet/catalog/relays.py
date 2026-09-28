"""UDP relays for catalogue network flows.

Each declared flow is one datagram socket. ``processing_delay_ms`` is a
wall-time hold before the datagram is forwarded, so a slower target computer
can be emulated. The default is 0 and adds no extra wait.
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import yaml


class UdpRelay:
    """Forward one UDP flow, optionally holding each datagram on the wall clock."""

    def __init__(
        self,
        listen: tuple[str, int],
        forward: tuple[str, int],
        *,
        delay_s: float = 0.0,
    ) -> None:
        self._forward = forward
        self._delay_s = max(0.0, delay_s)
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(listen)
        self._sock.settimeout(0.05)
        self._thread: threading.Thread | None = None

    @property
    def listen_address(self) -> tuple[str, int]:
        return self._sock.getsockname()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="cornet-udp-relay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._sock.close()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _addr = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            if self._delay_s and self._stop.wait(self._delay_s):
                return
            try:
                self._sock.sendto(data, self._forward)
            except OSError:
                return


def relays_from_file(path: Path, forward_host: str = "127.0.0.1") -> list[UdpRelay]:
    """Build one relay per flow in a compiled ``relays.yaml``."""
    data = yaml.safe_load(path.read_text()) or {}
    relays = []
    for flow in data.get("flows") or []:
        port = int(flow["port"])
        delay_ms = float(flow.get("processing_delay_ms") or 0.0)
        relays.append(
            UdpRelay(
                ("0.0.0.0", port),
                (forward_host, port),
                delay_s=delay_ms / 1000.0,
            )
        )
    return relays
