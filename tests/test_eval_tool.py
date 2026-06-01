from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_eval_tool(path: Path):
    spec = importlib.util.spec_from_file_location("eval_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.EvalTool


def test_pendulum_eval_tool_returns_mean_aoi(tmp_path: Path) -> None:
    results_dir = tmp_path / "pendulum"
    analysis_dir = results_dir / "analysis"
    analysis_dir.mkdir(parents=True)
    (analysis_dir / "aoi_statistics.json").write_text(
        json.dumps(
            {
                "flow1": {"mean": 10.0},
                "flow2": {"mean": 14.0},
            }
        )
    )

    tool_cls = _load_eval_tool(
        Path("/home/acharya/simulation/CORNET_Research/tasks/pendulum_nr_control/eval/eval_tool.py")
    )
    assert tool_cls().run_evaluation(str(results_dir)) == "SUCCESS, 12.000000"


def test_uav_eval_tool_returns_position_rms(tmp_path: Path) -> None:
    results_dir = tmp_path / "uav"
    analysis_dir = results_dir / "analysis"
    analysis_dir.mkdir(parents=True)
    (analysis_dir / "control_statistics.json").write_text(
        json.dumps(
            {
                "control": {
                    "position": {"rms": 0.123456},
                }
            }
        )
    )

    tool_cls = _load_eval_tool(
        Path("/home/acharya/simulation/CORNET_Research/tasks/uav_wifi_control/eval/eval_tool.py")
    )
    assert tool_cls().run_evaluation(str(results_dir)) == "SUCCESS, 0.123456"
