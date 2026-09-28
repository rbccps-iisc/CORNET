from __future__ import annotations

import json
from pathlib import Path

from cornet.config.loader import load_unified
from cornet.leaderboard.viewer import show
from cornet.leaderboard.writer import provenance_fields
from cornet.plugins.network.ns3_plugin import append_experiment_args
from cornet.sweep.expander import expand_sweep
from rich.console import Console


def _config(tmp_path: Path, body: str):
    path = tmp_path / "config.yaml"
    path.write_text(body.strip())
    return load_unified(path)


def test_identical_configs_share_a_hash(tmp_path: Path, monkeypatch) -> None:
    cfg = _config(
        tmp_path,
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
  name: default
  duration: 1.0
  seed: 7
  output_dir: results
""",
    )
    monkeypatch.delenv("CORNET_NS3_TAG", raising=False)
    monkeypatch.delenv("CORNET_HYPOTHESIS_ID", raising=False)
    first = provenance_fields(cfg)
    second = provenance_fields(cfg)
    assert first["config_hash"] == second["config_hash"]
    assert first["seed"] == 7
    assert first["hypothesis_id"] is None
    assert first["lane"] == "none"
    assert first["standard"] is True
    assert first["timing_ok"] == "unavailable"
    assert "rtf_mean" not in first


def test_timing_file_fills_rtf_and_timing_ok(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
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
  name: default
  duration: 1.0
  output_dir: results
""",
    )
    out = tmp_path / "results"
    out.mkdir()
    (out / "timing.json").write_text(
        json.dumps({"gazebo_rtf": {"mean": 0.8}, "timing_ok": False})
    )
    fields = provenance_fields(cfg, out)
    assert fields["rtf_mean"] == 0.8
    assert fields["timing_ok"] is False


def test_viewer_renders_entries_without_provenance(tmp_path: Path) -> None:
    (tmp_path / "leaderboard.json").write_text(
        json.dumps(
            [
                {
                    "variant_id": "old",
                    "status": "SUCCESS",
                    "metric": 1.0,
                    "output_dir": "r",
                    "timestamp": "t",
                }
            ]
        )
    )
    console = Console(record=True, width=140)
    show(str(tmp_path), console=console)
    text = console.export_text()
    assert "old" in text


def test_repeats_use_distinct_seeds(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  numerology: 1
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: base
  duration: 1.0
  seed: 10
  output_dir: results
  sweep:
    axes:
      network.numerology: [1]
    repeats: 3
""",
    )
    variants = expand_sweep(cfg)
    seeds = [variant.experiment.seed for variant in variants]
    assert seeds == [10, 11, 12]
    assert len(set(seeds)) == 3


def test_ns3_args_include_rng_run(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
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
  name: default
  duration: 4.0
  seed: 15
  output_dir: results
""",
    )
    args: list[str] = []
    append_experiment_args(args, cfg)
    assert "--simTime=4.0" in args
    assert "--rngRun=15" in args
