from __future__ import annotations

import os
from pathlib import Path

from cornet.config.loader import load_unified
from cornet.context import ExperimentContext
from cornet.orchestrator import Orchestrator
from cornet.plugins.base import Plugin


class RecordingPlugin(Plugin):
    def __init__(self, events: list[str], fail_in_start: bool = False) -> None:
        self.events = events
        self.fail_in_start = fail_in_start

    def configure(self, config, context) -> None:
        self.events.append("configure")

    def start(self) -> None:
        self.events.append("start")
        if self.fail_in_start:
            raise RuntimeError("boom")

    def run(self) -> None:
        self.events.append("run")

    def stop(self) -> None:
        self.events.append("stop")

    def collect(self, output_dir: Path) -> None:
        self.events.append("collect")


def _minimal_config(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: lifecycle
  duration: 0.0
  output_dir: tmp/results
""".strip()
    )
    return load_unified(config_path)


def test_plugin_lifecycle_order(monkeypatch, tmp_path: Path) -> None:
    events: list[str] = []
    orchestrator = Orchestrator()
    config = _minimal_config(tmp_path)

    monkeypatch.setattr(orchestrator, "_preflight", lambda config: None)
    monkeypatch.setattr(orchestrator, "_auto_discover", lambda config, task_dir: None)
    monkeypatch.setattr(orchestrator, "_eval_and_record", lambda config, task_dir, output_dir: None)
    monkeypatch.setattr(
        orchestrator,
        "_load_plugins",
        lambda config: [RecordingPlugin(events), RecordingPlugin(events)],
    )

    orchestrator._run_variant(config, tmp_path)
    assert events == [
        "configure",
        "configure",
        "start",
        "start",
        "run",
        "run",
        "stop",
        "stop",
        "collect",
        "collect",
    ]


def test_stop_called_when_start_fails(monkeypatch, tmp_path: Path) -> None:
    events: list[str] = []
    orchestrator = Orchestrator()
    config = _minimal_config(tmp_path)

    monkeypatch.setattr(orchestrator, "_preflight", lambda config: None)
    monkeypatch.setattr(orchestrator, "_auto_discover", lambda config, task_dir: None)
    monkeypatch.setattr(orchestrator, "_eval_and_record", lambda config, task_dir, output_dir: None)
    monkeypatch.setattr(
        orchestrator,
        "_load_plugins",
        lambda config: [RecordingPlugin(events), RecordingPlugin(events, fail_in_start=True)],
    )

    try:
        orchestrator._run_variant(config, tmp_path)
    except RuntimeError:
        pass

    assert events == ["configure", "configure", "start", "start", "stop"]


def _parallel_sweep_config(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: base
  duration: 0.0
  output_dir: tmp/results
  sweep:
    axes:
      network.numerology: [1, 2]
    parallel: true
""".strip()
    )
    return load_unified(config_path)


def test_parallel_sweep_assigns_gazebo_master_uri(monkeypatch, tmp_path: Path) -> None:
    """Each parallel variant must receive a unique GAZEBO_MASTER_URI port."""
    orchestrator = Orchestrator()
    config = _parallel_sweep_config(tmp_path)

    captured: list[str] = []

    def fake_run_variant(variant_cfg, task_dir):
        captured.append(os.environ.get("GAZEBO_MASTER_URI", ""))

    monkeypatch.setattr(orchestrator, "_run_variant", fake_run_variant)

    orchestrator.run(config_path=tmp_path / "config.yaml")

    assert len(captured) == 2
    assert captured[0] == "http://localhost:11345"
    assert captured[1] == "http://localhost:11346"
    # env var must be restored after run
    assert os.environ.get("GAZEBO_MASTER_URI") != "http://localhost:11346"
