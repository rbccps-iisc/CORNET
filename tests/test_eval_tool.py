from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from cornet.eval.base import EvalTool


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

    _TASKS = Path(__file__).parent.parent / "tasks"
    tool_cls = _load_eval_tool(_TASKS / "pendulum_nr_control" / "eval" / "eval_tool.py")
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

    _TASKS = Path(__file__).parent.parent / "tasks"
    tool_cls = _load_eval_tool(_TASKS / "uav_wifi_control" / "eval" / "eval_tool.py")
    assert tool_cls().run_evaluation(str(results_dir)) == "SUCCESS, 0.123456"


# ── EvalTool.format_result() ──────────────────────────────────────────────────

def test_format_result_success_default(tmp_path: Path) -> None:
    assert EvalTool.format_result(14.3) == "SUCCESS, 14.3"


def test_format_result_failure_status(tmp_path: Path) -> None:
    assert EvalTool.format_result(0.0, "FAILURE") == "FAILURE, 0.0"


def test_format_result_rejects_non_numeric_string(tmp_path: Path) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvalTool.format_result("14.3 ms")  # type: ignore[arg-type]


def test_format_result_rejects_nan(tmp_path: Path) -> None:
    import math
    with pytest.raises(ValueError, match="finite"):
        EvalTool.format_result(math.nan)


def test_format_result_rejects_inf(tmp_path: Path) -> None:
    import math
    with pytest.raises(ValueError, match="finite"):
        EvalTool.format_result(math.inf)


# ── Orchestrator metric validation ────────────────────────────────────────────

def _make_eval_tool_module(tmp_path: Path, return_str: str) -> Path:
    """Write a minimal eval_tool.py returning a fixed string."""
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_tool.py").write_text(
        f"from cornet.eval.base import EvalTool\n"
        f"class EvalTool(EvalTool):\n"
        f"    def run_evaluation(self, results_dir):\n"
        f"        return {return_str!r}\n"
    )
    return tmp_path


def test_orchestrator_raises_on_non_float_metric(tmp_path: Path) -> None:
    """_eval_and_record must raise ValueError when metric string is not a float."""
    import textwrap
    from cornet.config.loader import load_unified
    from cornet.orchestrator import Orchestrator

    (tmp_path / "config.yaml").write_text(textwrap.dedent("""
        _schema: unified-v1
        network:
          plugin: ns3
          type: ns3
          nodes: []
        robot:
          plugin: gazebo
          robots: []
        experiment:
          name: bad_metric
          duration: 0.0
          output_dir: tmp/results
    """).strip())
    _make_eval_tool_module(tmp_path, "SUCCESS, 14.3 ms")

    config = load_unified(tmp_path / "config.yaml")
    orch = Orchestrator()
    with pytest.raises(ValueError, match="non-float"):
        orch._eval_and_record(config, tmp_path, tmp_path / "results")


def test_orchestrator_records_valid_metric(tmp_path: Path) -> None:
    """_eval_and_record writes a leaderboard entry when metric is a valid float."""
    import json
    import textwrap
    from cornet.config.loader import load_unified
    from cornet.orchestrator import Orchestrator

    (tmp_path / "config.yaml").write_text(textwrap.dedent("""
        _schema: unified-v1
        network:
          plugin: ns3
          type: ns3
          nodes: []
        robot:
          plugin: gazebo
          robots: []
        experiment:
          name: good_metric
          duration: 0.0
          output_dir: tmp/results
    """).strip())
    _make_eval_tool_module(tmp_path, "SUCCESS, 14.3")

    config = load_unified(tmp_path / "config.yaml")
    orch = Orchestrator()
    orch._eval_and_record(config, tmp_path, tmp_path / "results")

    lb = json.loads((tmp_path / "leaderboard.json").read_text())
    assert lb[-1]["metric"] == 14.3
    assert lb[-1]["status"] == "SUCCESS"
