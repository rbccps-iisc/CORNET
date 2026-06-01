# Writing a Custom EvalTool

An EvalTool is a Python class that extracts scalar metrics from a completed
experiment output directory. CORNET calls it after every run and appends the
result to `leaderboard.json`.

---

## 1. EvalTool interface

```python
# cornet/eval/base.py
class EvalTool(abc.ABC):
    @abc.abstractmethod
    def run_evaluation(self, results_dir: str) -> str:
        """Evaluate one completed run directory and return the status string."""

    @classmethod
    def format_result(cls, value: float, status: str = "SUCCESS") -> str:
        """Returns 'SUCCESS, <value>'. Raises ValueError if value is not finite."""
```

**Return value format:**
- `"SUCCESS, <float>"` — run succeeded; float is the primary metric value
- `"FAILURE,\n<details>"` — run failed; details written to logs; no leaderboard entry written

---

## 2. File location

Place your eval tool at `tasks/<name>/eval/eval_tool.py`. The class must be
named `EvalTool` and subclass `cornet.eval.base.EvalTool`.

```
tasks/
  my_task/
    eval/
      eval_tool.py     ← your class
      __init__.py      ← empty, required for import
```

---

## 3. Minimal example

```python
# tasks/my_task/eval/eval_tool.py
from __future__ import annotations

import json
from pathlib import Path
from cornet.eval.base import EvalTool as BaseEvalTool


class EvalTool(BaseEvalTool):
    """Compute mean round-trip latency from NS-3 output."""

    def run_evaluation(self, results_dir: str) -> str:
        stats_path = Path(results_dir) / "rtt_stats.json"
        if not stats_path.exists():
            return "FAILURE,\nmissing rtt_stats.json"

        data = json.loads(stats_path.read_text())
        mean_ms = data["mean_rtt_ms"]

        # format_result validates the value and returns "SUCCESS, <value>"
        return self.format_result(mean_ms)
```

---

## 4. Multi-metric example

If your task has multiple metrics, include them all in the return string:

```python
def run_evaluation(self, results_dir: str) -> str:
    data = json.loads((Path(results_dir) / "stats.json").read_text())
    mean_aoi = data["aoi"]["mean_ms"]
    loss_pct = data["loss_percent"]
    primary = self.format_result(mean_aoi)
    # Additional lines are recorded as debug metadata:
    return f"{primary}\naoi_mean={mean_aoi:.2f}ms loss={loss_pct:.1f}%"
```

Only the first line (`SUCCESS, <value>`) is parsed as the leaderboard metric.
Additional lines are stored in the leaderboard entry's `meta.eval_details`.

---

## 5. Error handling guidelines

| Condition | Recommended response |
|---|---|
| Missing expected output file | `"FAILURE,\nmissing <filename>"` |
| Empty / zero-row data | `"FAILURE,\nempty data"` |
| Non-finite computed value | `self.format_result(...)` will raise; catch and return `"FAILURE,\n..."` |
| Exception in external lib | Catch and return `"FAILURE,\n<traceback excerpt>"` |

---

## 6. Testing your EvalTool

```python
def test_eval_tool(tmp_path):
    import json
    from tasks.my_task.eval.eval_tool import EvalTool

    # Arrange: write fake output files
    stats = {"mean_rtt_ms": 12.5}
    (tmp_path / "rtt_stats.json").write_text(json.dumps(stats))

    # Act
    result = EvalTool().run_evaluation(str(tmp_path))

    # Assert
    assert result.startswith("SUCCESS")
    assert "12.5" in result
```

---

## 7. Real-world reference

See `tasks/pendulum_nr_control/eval/eval_tool.py` for a production example
that reads per-flow AoI statistics and computes a weighted mean.

<!-- TODO: expand — document how to report multiple named metrics and how the leaderboard writer maps them to leaderboard entry fields. -->
