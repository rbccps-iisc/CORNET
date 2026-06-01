from __future__ import annotations

import json
from pathlib import Path

from cornet.eval.base import EvalTool as BaseEvalTool


class EvalTool(BaseEvalTool):
    """Return pendulum/control position RMS from control_statistics.json."""

    def run_evaluation(self, results_dir: str) -> str:
        stats_path = Path(results_dir) / "analysis" / "control_statistics.json"
        if not stats_path.exists():
            return "FAILURE,\nmissing analysis/control_statistics.json"

        try:
            data = json.loads(stats_path.read_text())
            metric = float(data["control"]["position"]["rms"])
            return f"SUCCESS, {metric:.6f}"
        except Exception as exc:
            return f"FAILURE,\n{exc}"
