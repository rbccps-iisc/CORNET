# Writing a Task

This guide walks through creating a new CORNET experiment task from scratch.
A task is a directory under `tasks/` containing a `config.yaml` and optionally
an `eval/eval_tool.py`.

---

## 1. Directory layout

```
tasks/
  my_task/
    config.yaml          ← required: experiment configuration
    eval/
      eval_tool.py       ← optional: metric extractor (enables leaderboard)
    launch.py            ← optional: custom ROS 2 launch file (auto-discovered)
    world.sdf            ← optional: custom Gazebo world (auto-discovered)
```

CORNET auto-discovers `launch.py` and `world.sdf` if present. If absent, the
Gazebo plugin generates them from `config.yaml`.

---

## 2. Minimal `config.yaml`

```yaml
# tasks/my_task/config.yaml
network:
  plugin: ns3
  type: ns3
  nodes:
    - name: ue0
      type: UE
      ip: 10.0.0.1
    - name: gnb0
      type: GNB
  scenario:
    profile: 5g_nr_urllc
    numerology: 2
    bandwidth_mhz: 20

robot:
  plugin: gazebo
  robots:
    - name: robot0
      model:
        type: urdf
        path: models/pendulum.urdf
      pose:
        x: 0.0
        y: 0.0
        z: 0.1

experiment:
  name: My Task
  duration: 60.0
  output_dir: results
  primary_metric: mean_latency_ms
  higher_is_better: false
```

**Valid scenario profiles**: `5g_nr_urllc`, `5g_nr_embb`, `5g_nr_mmtc`, `6g_thz` (experimental).

See [config-schema.md](../reference/config-schema.md) for the full field reference.

---

## 3. Run the task

```bash
python -m cornet tasks/my_task
# equivalent:
python -m cornet run tasks/my_task
```

CORNET will:
1. Load and validate `config.yaml` against `UnifiedConfig` schema
2. Start the NS-3 network plugin (launches the `5g_nr_urllc` scenario script)
3. Start the Gazebo robot plugin (spawns robot0 in the auto-generated world)
4. Run for `experiment.duration` seconds
5. Call `eval/eval_tool.py` if present
6. Write an entry to `tasks/my_task/leaderboard.json`

---

## 4. Add an EvalTool

Create `tasks/my_task/eval/eval_tool.py`:

```python
# tasks/my_task/eval/eval_tool.py
from __future__ import annotations

import json
from pathlib import Path
from cornet.eval.base import EvalTool as BaseEvalTool


class EvalTool(BaseEvalTool):
    """Compute mean round-trip latency from NS-3 CSV output."""

    def run_evaluation(self, results_dir: str) -> str:
        csv_path = Path(results_dir) / "latency.csv"
        if not csv_path.exists():
            return "FAILURE,\nmissing latency.csv"

        rows = csv_path.read_text().strip().splitlines()[1:]  # skip header
        if not rows:
            return "FAILURE,\nempty latency.csv"

        values = [float(r.split(",")[1]) for r in rows]
        mean_ms = sum(values) / len(values)

        return self.format_result(mean_ms)
```

**EvalTool contract:**
- `run_evaluation(results_dir)` receives the path where the network plugin wrote its output files
- Return value must be `"SUCCESS, <float>"` (use `self.format_result(value)`) or `"FAILURE,\n<detail>"`
- `format_result` raises `ValueError` for non-finite floats — always validate your metric

The leaderboard entry's `metrics` dict will contain `{"primary_metric_name": <value>}`.

---

## 5. View the leaderboard

After one or more runs:

```bash
python -m cornet view tasks/my_task
```

Prints a ranked table sorted by `primary_metric` (ascending by default; pass `--higher-is-better` to reverse).

```bash
python -m cornet view tasks/my_task --higher-is-better
```

---

## 6. Use the web UI

```bash
python -m cornet ui tasks/my_task
```

Opens the leaderboard in a browser with live-reloading charts. Useful for monitoring a sweep.

---

## 7. Run a parameter sweep

Add a `sweep` block to `experiment:`:

```yaml
experiment:
  name: My Task Sweep
  duration: 60.0
  output_dir: results
  primary_metric: mean_latency_ms
  sweep:
    axes:
      network.scenario.numerology: [1, 2, 3]
      network.scenario.bandwidth_mhz: [20, 40]
    repeats: 3
```

CORNET expands the cartesian product (6 variants × 3 repeats = 18 runs) and writes each to:

```
results/
  numerology=1+bandwidth_mhz=20/run_0/
  numerology=1+bandwidth_mhz=20/run_1/
  ...
```

See [parameter-sweep.md](parameter-sweep.md) for full details.

---

## 8. Existing tasks as examples

| Task | Network | Robot | Notes |
|---|---|---|---|
| `tasks/pendulum_nr_control/` | NS-3 (URLLC) | Gazebo pendulum | AoI eval tool |
| `tasks/uav_wifi_control/` | Mininet-WiFi | Gazebo UAV | Docker containers |
| `tasks/aoi_5phase_eval/` | NS-3 (URLLC) | — | Sweep over 5 AoI phases |
