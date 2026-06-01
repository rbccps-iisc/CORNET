from __future__ import annotations

import json
from pathlib import Path

from cornet.config.loader import load_unified
from cornet.orchestrator import Orchestrator


TASK_ROOT = Path("/home/acharya/simulation/CORNET_Research/tasks")


def test_example_tasks_write_leaderboard_entries(tmp_path: Path) -> None:
    pendulum_task = TASK_ROOT / "pendulum_nr_control"
    uav_task = TASK_ROOT / "uav_wifi_control"

    pendulum_results = tmp_path / "pendulum_results"
    (pendulum_results / "analysis").mkdir(parents=True)
    (pendulum_results / "analysis" / "aoi_statistics.json").write_text(
        json.dumps({"flow1": {"mean": 11.0}, "flow2": {"mean": 13.0}})
    )

    uav_results = tmp_path / "uav_results"
    (uav_results / "analysis").mkdir(parents=True)
    (uav_results / "analysis" / "control_statistics.json").write_text(
        json.dumps({"control": {"position": {"rms": 0.25}}})
    )

    orchestrator = Orchestrator()
    pendulum_cfg = load_unified(pendulum_task / "config.yaml")
    uav_cfg = load_unified(uav_task / "config.yaml")

    orchestrator._eval_and_record(pendulum_cfg, pendulum_task, pendulum_results)
    orchestrator._eval_and_record(uav_cfg, uav_task, uav_results)

    pendulum_leaderboard = json.loads((pendulum_task / "leaderboard.json").read_text())
    uav_leaderboard = json.loads((uav_task / "leaderboard.json").read_text())

    assert pendulum_leaderboard[-1]["status"] == "SUCCESS"
    assert pendulum_leaderboard[-1]["metric"] == 12.0
    assert uav_leaderboard[-1]["status"] == "SUCCESS"
    assert uav_leaderboard[-1]["metric"] == 0.25
