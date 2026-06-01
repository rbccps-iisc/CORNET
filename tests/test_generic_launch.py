from __future__ import annotations

from pathlib import Path

from cornet.config.loader import load_unified
from cornet.gazebo.generic_launch import generate


def test_generate_launch_with_two_robots(tmp_path: Path) -> None:
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
  robots:
    - name: robot_a
      model:
        type: urdf
        path: models/a.urdf
    - name: robot_b
      model:
        type: sdf
        path: models/b.sdf
      pose:
        x: 1.0
        y: 2.0
        z: 3.0
experiment:
  name: launch
  duration: 1.0
  output_dir: results/launch
""".strip()
    )

    cfg = load_unified(config_path)
    launch_path = generate(cfg.robot, tmp_path)

    assert launch_path.exists()
    source = launch_path.read_text()
    compile(source, str(launch_path), "exec")
    assert "robot_a" in source
    assert "robot_b" in source
