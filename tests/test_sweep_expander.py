from __future__ import annotations

from pathlib import Path

from cornet.config.loader import load_unified
from cornet.sweep.expander import expand_sweep


def test_three_by_two_grid_produces_six_variants(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  numerology: 2
  bandwidth: 20
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: base
  duration: 1.0
  output_dir: results/base
  sweep:
    axes:
      network.numerology: [1, 2, 3]
      network.bandwidth: [20, 40]
    repeats: 1
""".strip()
    )
    variants = expand_sweep(load_unified(config_path))
    assert len(variants) == 6
    names = {variant.experiment.name for variant in variants}
    assert "numerology=1_bandwidth=20" in names
    assert "numerology=3_bandwidth=40" in names


def test_repeats_expand_variant_count(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  numerology: 2
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: base
  duration: 1.0
  output_dir: results/base
  sweep:
    axes:
      network.numerology: [1, 2, 3]
      network.bandwidth: [20, 40]
    repeats: 3
""".strip()
    )
    variants = expand_sweep(load_unified(config_path))
    assert len(variants) == 18
    assert any(variant.experiment.name.endswith("_run3") for variant in variants)


def test_no_sweep_returns_single_default_variant(tmp_path: Path) -> None:
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
  name: default
  duration: 1.0
  output_dir: results/default
""".strip()
    )
    variants = expand_sweep(load_unified(config_path))
    assert len(variants) == 1
    assert variants[0].experiment.name == "default"
