from __future__ import annotations

import time
from pathlib import Path

from cornet.config.loader import load_unified
from cornet.gazebo.generic_launch import generate
from cornet.orchestrator import Orchestrator


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


def test_cleanup_removes_stale_launch_file_and_keeps_recent(tmp_path: Path) -> None:
    """Files older than 1 hour are removed; recently created files are kept."""
    old_file = tmp_path / "generated_launch_old.py"
    new_file = tmp_path / "generated_launch_new.py"
    old_file.write_text("# old")
    new_file.write_text("# new")

    # Back-date old_file by 2 hours
    two_hours_ago = time.time() - 7200
    import os
    os.utime(old_file, (two_hours_ago, two_hours_ago))

    Orchestrator()._cleanup_stale_launch_files(tmp_path)

    assert not old_file.exists(), "stale file should have been removed"
    assert new_file.exists(), "recent file must not be removed"
