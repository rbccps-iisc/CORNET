from __future__ import annotations

import json
from pathlib import Path

from cornet.eval.base import EvalTool as BaseEvalTool


class EvalTool(BaseEvalTool):
    """Return the mean AoI across all recorded flows."""

    def run_evaluation(self, results_dir: str) -> str:
        stats_path = Path(results_dir) / "analysis" / "aoi_statistics.json"
        if not stats_path.exists():
            return "FAILURE,\nmissing analysis/aoi_statistics.json"

        try:
            data = json.loads(stats_path.read_text())
            if not isinstance(data, dict) or not data:
                return "FAILURE,\nempty AoI statistics"

            means = []
            for flow_stats in data.values():
                if isinstance(flow_stats, dict) and "mean" in flow_stats:
                    means.append(float(flow_stats["mean"]))

            if not means:
                return "FAILURE,\nno per-flow mean AoI values found"

            metric = sum(means) / len(means)
            return f"SUCCESS, {metric:.6f}"
        except Exception as exc:
            return f"FAILURE,\n{exc}"
