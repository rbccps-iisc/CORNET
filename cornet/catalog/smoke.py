"""Per-flow packet check for a compiled catalogue task.

Each flow in ``relays.yaml`` gets one datagram. The datagram has to come
back out of the UDP relay that the compiler declared for that flow.
"""

from __future__ import annotations

import socket
from pathlib import Path

import yaml

from cornet.catalog.relays import UdpRelay


def smoke_test(task_dir: Path, *, timeout_s: float = 1.0) -> None:
    """Raise AssertionError if any declared flow does not pass a datagram."""
    path = Path(task_dir) / "relays.yaml"
    data = yaml.safe_load(path.read_text()) or {}
    flows = list(data.get("flows") or [])
    if not flows:
        raise AssertionError(f"no flows in {path}")
    missing: list[str] = []
    for flow in flows:
        name = str(flow.get("name") or flow.get("port"))
        payload = f"cornet:{name}".encode()
        delay_s = float(flow.get("processing_delay_ms") or 0.0) / 1000.0
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        relay = UdpRelay(("127.0.0.1", 0), receiver.getsockname(), delay_s=delay_s)
        relay.start()
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sender.sendto(payload, relay.listen_address)
            receiver.settimeout(timeout_s + delay_s)
            try:
                got, _addr = receiver.recvfrom(256)
            except socket.timeout:
                missing.append(name)
                continue
            if got != payload:
                missing.append(name)
        finally:
            sender.close()
            relay.stop()
            receiver.close()
    if missing:
        raise AssertionError("flows without a traversed packet: " + ", ".join(missing))
