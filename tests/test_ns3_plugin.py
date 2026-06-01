from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cornet.config.loader import load_unified
from cornet.context import ExperimentContext
from cornet.plugins.network import ns3_plugin as ns3_module
from cornet.plugins.network.ns3_plugin import Ns3Plugin, PluginConfigError


def _write_config(tmp_path: Path, network_lines: list[str]):
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "_schema: unified-v1",
                "network:",
                *network_lines,
                "robot:",
                "  plugin: gazebo",
                "  robots: []",
                "experiment:",
                "  name: ns3-test",
                "  duration: 0.0",
                f"  output_dir: {tmp_path / 'results'}",
            ]
        )
    )
    return load_unified(path)


class _FakeTunManager:
    def __init__(self, ip_list):
        self.ip_list = ip_list
        self.teardown_calls = 0

    def setup(self):
        return {f"cornet{i}": ip for i, ip in enumerate(self.ip_list)}

    def teardown(self):
        self.teardown_calls += 1


class _FakeClockServer:
    def __init__(self, *args, **kwargs):
        self.on_tick = kwargs.get("on_tick")
        self.start_calls = 0
        self.stop_calls = 0
        self.physics_time = 0.0

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1


class _FakePositionServer:
    def __init__(self, *args, **kwargs):
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1


class _FakeDispatcher:
    def __init__(self, *args, **kwargs):
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1

    def update_physics_time(self, t: float):
        pass


class _FakeAoITracker:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self.exported = None

    def update_physics_time(self, t: float):
        pass

    def sample(self):
        return {}

    def record_update(self, flow_id: str, physics_time: float):
        pass

    def close(self):
        self.closed = True

    def export_json(self, path: Path):
        self.exported = path


class _RunningProc:
    def __init__(self, args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.returncode = None
        self.stderr = None
        self.terminated = False

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired(cmd=self.args, timeout=timeout)

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class _FailedProc:
    def __init__(self, args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.returncode = 1
        self.stderr = type("Stderr", (), {"read": lambda self: "bad tun args"})()

    def wait(self, timeout=None):
        return 1

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 1

    def kill(self):
        self.returncode = -9


def _prepare_ns3(monkeypatch, tmp_path: Path) -> Path:
    ns3_dir = tmp_path / "ns3"
    ns3_dir.mkdir()
    (ns3_dir / "ns3").write_text("#!/bin/sh\n")
    monkeypatch.setattr(ns3_module, "_find_ns3_dir", lambda: ns3_dir)
    monkeypatch.setattr("cornet.middleware.TunManager", _FakeTunManager)
    monkeypatch.setattr("cornet.middleware.ClockServer", _FakeClockServer)
    monkeypatch.setattr("cornet.middleware.PositionServer", _FakePositionServer)
    monkeypatch.setattr("cornet.middleware.PacketDispatcher", _FakeDispatcher)
    monkeypatch.setattr("cornet.middleware.AoITracker", _FakeAoITracker)
    return ns3_dir


def test_ns3_plugin_passes_tun_args_and_collects_aoi(monkeypatch, tmp_path: Path) -> None:
    _prepare_ns3(monkeypatch, tmp_path)
    launched = {}

    def fake_popen(args, **kwargs):
        launched["args"] = args
        return _RunningProc(args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    cfg = _write_config(
        tmp_path,
        [
            "  plugin: ns3",
            "  type: ns3",
            "  nodes:",
            "    - name: ue1",
            "      type: UE",
            "      ip: 10.0.0.1",
            "    - name: gnb1",
            "      type: GNB",
            "      ip: 10.0.0.2",
            "  middleware:",
            "    enabled: true",
            "    ip_list: [10.0.0.1, 10.0.0.2]",
            "  scenario:",
            "    profile: 5g_nr_urllc",
        ],
    )

    plugin = Ns3Plugin()
    context = ExperimentContext(variant_id="test")
    plugin.configure(cfg, context)
    plugin.start()

    assert any(arg.startswith("--tun0=cornet0,10.0.0.1") for arg in launched["args"])
    assert any(arg.endswith("cornet/scenarios/5g_nr_urllc/run.py") for arg in launched["args"])

    out_dir = tmp_path / "results"
    plugin.collect(out_dir)
    assert plugin._aoi_tracker.exported == out_dir / "aoi_summary.json"
    plugin.stop()


def test_ns3_plugin_tears_down_tun_on_early_launch_failure(monkeypatch, tmp_path: Path) -> None:
    _prepare_ns3(monkeypatch, tmp_path)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: _FailedProc(args, **kwargs))

    cfg = _write_config(
        tmp_path,
        [
            "  plugin: ns3",
            "  type: ns3",
            "  nodes:",
            "    - name: ue1",
            "      type: UE",
            "      ip: 10.0.0.1",
            "  middleware:",
            "    enabled: true",
            "    ip_list: [10.0.0.1]",
            "  scenario:",
            "    profile: 5g_nr_urllc",
        ],
    )

    plugin = Ns3Plugin()
    plugin.configure(cfg, ExperimentContext(variant_id="test"))
    with pytest.raises(RuntimeError, match="bad tun args"):
        plugin.start()
    assert plugin._tun_manager.teardown_calls == 1


def test_6g_thz_requires_module(monkeypatch, tmp_path: Path) -> None:
    ns3_dir = tmp_path / "ns3"
    ns3_dir.mkdir()
    (ns3_dir / "ns3").write_text("#!/bin/sh\n")
    monkeypatch.setattr(ns3_module, "_find_ns3_dir", lambda: ns3_dir)

    cfg = _write_config(
        tmp_path,
        [
            "  plugin: ns3",
            "  type: ns3",
            "  nodes: []",
            "  scenario:",
            "    profile: 6g_thz",
        ],
    )

    plugin = Ns3Plugin()
    with pytest.raises(PluginConfigError, match="ns3-thz"):
        plugin.configure(cfg, ExperimentContext(variant_id="test"))