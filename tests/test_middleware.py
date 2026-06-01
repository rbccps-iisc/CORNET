from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest

from cornet.middleware.aoi import AoITracker
from cornet.middleware.clock import ClockServer, PositionServer
from cornet.middleware.dispatcher import PacketDispatcher
from cornet.middleware.tun import TunManager


def test_packet_dispatcher_ordering_and_epsilon() -> None:
    dispatched: list[tuple[str, bytes]] = []
    dispatcher = PacketDispatcher(
        rtf=0.0,
        on_dispatch=lambda flow_id, payload: dispatched.append((flow_id, payload)),
    )
    dispatcher.start()
    dispatcher.enqueue("flow2", 2.0, b"two")
    dispatcher.enqueue("flow1", 1.0, b"one")
    dispatcher.update_physics_time(0.9995)
    time.sleep(0.02)
    dispatcher.update_physics_time(2.0)
    time.sleep(0.02)
    dispatcher.stop()

    assert dispatched == [("flow1", b"one"), ("flow2", b"two")]
    assert dispatcher.stats()["dispatched"] == 2


def test_packet_dispatcher_deadline_and_ber_drop() -> None:
    dispatcher = PacketDispatcher(rtf=0.0, deadline_s=0.5, ber=1.0)
    dispatcher.update_physics_time(2.0)
    dispatcher.enqueue("late", 1.0, b"late")
    dispatcher.enqueue("drop", 2.0, b"drop")
    dispatcher.start()
    time.sleep(0.02)
    dispatcher.stop()

    stats = dispatcher.stats()
    assert stats["deadline_drop"] == 1
    assert stats["ber_drop"] == 1


def test_packet_dispatcher_rtf_sleep(monkeypatch) -> None:
    slept: list[float] = []
    real_sleep = time.sleep
    dispatcher = PacketDispatcher(rtf=2.0, on_dispatch=lambda flow_id, payload: None)

    def fake_sleep(duration: float) -> None:
        slept.append(duration)
        dispatcher.update_physics_time(1.0)

    monkeypatch.setattr("cornet.middleware.dispatcher.time.sleep", fake_sleep)

    dispatcher.start()
    dispatcher.enqueue("flow", 1.0, b"payload")
    real_sleep(0.01)
    dispatcher.stop()

    assert slept
    assert slept[0] == pytest.approx((1.0 + 0.001) / 2.0, rel=1e-3)


def test_aoi_tracker_summary_and_export(tmp_path: Path) -> None:
    tracker = AoITracker()
    tracker.record_update("ue1-gnb1", 0.0)
    tracker.update_physics_time(1.0)
    tracker.sample()
    tracker.record_update("ue1-gnb1", 1.0)
    tracker.update_physics_time(1.5)
    tracker.sample()
    tracker.close()
    tracker.export_json(tmp_path / "aoi_summary.json")

    summary = json.loads((tmp_path / "aoi_summary.json").read_text())
    assert summary["ue1-gnb1"]["mean_s"] == pytest.approx(0.75)
    assert summary["ue1-gnb1"]["p95_s"] >= 0.5
    assert (tmp_path / "aoi_ue1-gnb1.csv").exists()


def test_tun_manager_setup_teardown_and_context(monkeypatch) -> None:
    commands: list[list[str]] = []
    closed: list[int] = []
    next_fd = iter([10, 11])

    monkeypatch.setattr("cornet.middleware.tun._require_net_admin", lambda: None)
    monkeypatch.setattr("cornet.middleware.tun.os.open", lambda path, flags: next(next_fd))
    monkeypatch.setattr("cornet.middleware.tun.fcntl.ioctl", lambda fd, code, req: 0)
    monkeypatch.setattr("cornet.middleware.tun.os.close", lambda fd: closed.append(fd))

    def fake_run(args, capture_output=True, text=False):
        commands.append(args)
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr("cornet.middleware.tun.subprocess.run", fake_run)

    with TunManager(["10.0.0.1", "10.0.0.2"]) as manager:
        mapping = manager.if_names()
        assert mapping == ["cornet0", "cornet1"]
        assert manager.get_fd("cornet0") == 10

    assert any(cmd[:4] == ["ip", "rule", "add", "from"] for cmd in commands)
    assert closed == [10, 11]


def test_clock_server_fallback_and_stale_socket(tmp_path: Path) -> None:
    socket_path = tmp_path / "clock.sock"
    socket_path.write_text("stale")
    server = ClockServer(socket_path=str(socket_path), clock_timeout_s=0.05)
    server.start()
    time.sleep(0.15)
    assert server.physics_time > 0.0
    server._process_clock_line(b"not json")
    server.stop()
    assert not socket_path.exists()


def test_position_server_updates_over_socket(tmp_path: Path) -> None:
    socket_path = tmp_path / "positions.sock"
    server = PositionServer(socket_path=str(socket_path))
    server.start()

    deadline = time.time() + 1.0
    while not socket_path.exists() and time.time() < deadline:
        time.sleep(0.01)

    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
                client.sendall(b'{"name":"robot0","x":1.0,"y":2.0,"z":3.0}\n')
            break
        except ConnectionRefusedError:
            if time.time() >= deadline:
                raise
            time.sleep(0.01)

    deadline = time.time() + 1.0
    while server.get_position("robot0") is None and time.time() < deadline:
        time.sleep(0.01)

    assert server.get_position("robot0") == {"x": 1.0, "y": 2.0, "z": 3.0}
    server.stop()