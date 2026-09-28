from __future__ import annotations

import json
from pathlib import Path

from cornet.plugins.base import Plugin
from cornet.telemetry import (
    build_timing_report,
    parse_gz_stats_factors,
    parse_ns3_timing_log,
    timing_warning,
)


def test_timing_report_schema_and_unavailable() -> None:
    report = build_timing_report(
        wall_s=1.0,
        rtf_samples=[],
        lag_samples=[],
        cpu_percent={"ns3": 0.0, "gzserver": 0.0, "ros_nodes": 0.0, "other": 0.0},
        rtf_min=0.95,
        lag_budget_ms=1.0,
    )
    for key in ("wall_s", "gazebo_rtf", "ns3_lag_ms", "cpu_percent", "thresholds", "timing_ok"):
        assert key in report
    assert report["gazebo_rtf"] == "unavailable"
    assert report["ns3_lag_ms"] == "unavailable"
    assert report["timing_ok"] == "unavailable"
    assert timing_warning(report) is None


def test_gazebo_overload_fails_rtf_min() -> None:
    report = build_timing_report(
        wall_s=10,
        rtf_samples=[0.6, 0.6, 0.6],
        lag_samples=[],
        cpu_percent={"ns3": 0, "gzserver": 0, "ros_nodes": 0, "other": 0},
        rtf_min=0.95,
        lag_budget_ms=1.0,
    )
    assert report["gazebo_rtf"]["mean"] == 0.6
    assert report["timing_ok"] is False
    warning = timing_warning(report)
    assert warning is not None and "rtf_min" in warning


def test_lag_budget_exceeded() -> None:
    report = build_timing_report(
        wall_s=10,
        rtf_samples=[],
        lag_samples=[4.0] * 20,
        cpu_percent={"ns3": 1, "gzserver": 0, "ros_nodes": 0, "other": 0},
        rtf_min=0.95,
        lag_budget_ms=1.0,
    )
    assert report["ns3_lag_ms"]["p99"] == 4.0
    assert report["timing_ok"] is False
    warning = timing_warning(report)
    assert warning is not None and "lag_budget_ms" in warning


def test_parse_helpers(tmp_path: Path) -> None:
    log = tmp_path / "ns3_timing.log"
    log.write_text("# sim_s,lag_ms\n0.01,0.2\n0.02,1.5\nbad\n")
    assert parse_ns3_timing_log(log) == [0.2, 1.5]
    assert parse_ns3_timing_log(tmp_path / "missing.log") == []
    assert parse_gz_stats_factors("Factor,SimTime,RealTime\n0.98,1,1\n") == [0.98]


def test_orchestrator_writes_timing_json(monkeypatch, tmp_path: Path) -> None:
    class _Quiet(Plugin):
        def configure(self, config, context) -> None:
            return None

        def start(self) -> None:
            return None

        def run(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def collect(self, output_dir: Path) -> None:
            return None

    from cornet.orchestrator import Orchestrator

    monkeypatch.setattr(Orchestrator, "_load_plugins", lambda self, config: [_Quiet()])
    monkeypatch.setattr(Orchestrator, "_preflight", lambda self, config: None)
    cfg = tmp_path / "task"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(
        "\n".join(
            [
                "_schema: unified-v1",
                "network:",
                "  plugin: ns3",
                "  type: ns3",
                "  nodes: []",
                "robot:",
                "  plugin: none",
                "  robots: []",
                "experiment:",
                "  name: timing-test",
                "  duration: 0",
                f"  output_dir: {tmp_path / 'results'}",
            ]
        )
    )
    Orchestrator().run(task_dir=cfg)
    report = json.loads((tmp_path / "results" / "timing.json").read_text())
    assert report["gazebo_rtf"] == "unavailable"
    assert report["timing_ok"] == "unavailable"
