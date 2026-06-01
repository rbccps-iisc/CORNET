"""Unit tests for unified config schema and loader."""

import textwrap
from pathlib import Path

import pytest
import yaml

from cornet.config.loader import load_unified
from cornet.config.schema import ConfigValidationError


# ── Fixtures ─────────────────────────────────────────────────────────────────

VALID_YAML = textwrap.dedent("""
    _schema: unified-v1
    network:
      plugin: ns3
      type: ns3
      nodes:
        - name: ue1
          type: UE
    robot:
      plugin: gazebo
      robots:
        - name: pendulum
          model:
            type: urdf
            path: models/pendulum.urdf
    experiment:
      name: test_run
      duration: 30.0
      output_dir: results/test
""").strip()


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_valid_load(tmp_path: Path) -> None:
    cfg = load_unified(write_yaml(tmp_path, VALID_YAML))
    assert cfg.experiment.name == "test_run"
    assert cfg.network.plugin == "ns3"
    assert cfg.robot.robots[0].name == "pendulum"


def test_missing_required_field(tmp_path: Path) -> None:
    broken = VALID_YAML.replace("duration: 30.0", "")
    with pytest.raises(ConfigValidationError):
        load_unified(write_yaml(tmp_path, broken))


def test_unknown_network_type(tmp_path: Path) -> None:
    broken = VALID_YAML.replace("type: ns3", "type: unknown_backend")
    with pytest.raises(ConfigValidationError):
        load_unified(write_yaml(tmp_path, broken))


def test_legacy_fallback_raises(tmp_path: Path) -> None:
    legacy = textwrap.dedent("""
        network:
          type: lte
        duration: 60
    """).strip()
    with pytest.raises(ConfigValidationError, match="unified-v1"):
        load_unified(write_yaml(tmp_path, legacy))


def test_sweep_config(tmp_path: Path) -> None:
    with_sweep = VALID_YAML + textwrap.dedent("""
        experiment:
          name: sweep_run
          duration: 10.0
          sweep:
            axes:
              network.numerology: [2, 4]
              network.bandwidth: [20, 40]
            repeats: 2
    """)
    # The top-level experiment key is overridden by the appended block
    content = VALID_YAML.replace(
        "experiment:\n  name: test_run\n  duration: 30.0\n  output_dir: results/test",
        textwrap.dedent("""
            experiment:
              name: sweep_run
              duration: 10.0
              sweep:
                axes:
                  network.numerology: [2, 4]
                  network.bandwidth: [20, 40]
                repeats: 2
        """).strip(),
    )
    cfg = load_unified(write_yaml(tmp_path, content))
    assert cfg.experiment.sweep is not None
    assert cfg.experiment.sweep.repeats == 2
