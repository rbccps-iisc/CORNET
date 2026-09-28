# Leaderboard File Format

<!-- auto-generated marker: DO NOT remove — checked by docs-check CI -->

## Overview

Each task directory contains a `leaderboard.json` file that accumulates one entry per experiment run. The file is written atomically (write-to-tmp, then `os.replace`) so concurrent reads always see a complete JSON document.

## File location

```
tasks/<name>/leaderboard.json
```

## JSON structure

The root of `leaderboard.json` is a JSON **array**. Each element is a leaderboard entry object.

```json
[
  {
    "timestamp": "2026-06-01T14:32:00.123456",
    "variant_id": "my_task",
    "status": "SUCCESS",
    "metric": 42.7,
    "output_dir": "tasks/my_task/results",
    "primary_metric": "mean_aoi_ms"
  },
  {
    "timestamp": "2026-06-01T14:40:11.000000",
    "variant_id": "my_task@ns3-v24",
    "status": "FAILURE",
    "metric": null,
    "output_dir": "tasks/my_task/results",
    "primary_metric": "mean_aoi_ms",
    "error": "NS-3 exited before startup completed: ..."
  }
]
```

## Entry fields

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | ✓ | UTC wall-clock time when the entry was written. |
| `variant_id` | string | ✓ | Experiment name, optionally suffixed with `@<tag>` when `CORNET_NS3_TAG` is set (e.g. `my_task@ns3-v24`). For sweep runs the sweep axis values are appended: `my_task+numerology=2+bandwidth=20000000`. |
| `status` | string | ✓ | `"SUCCESS"` when the EvalTool returned a valid metric; `"FAILURE"` when the lifecycle raised an exception or the EvalTool reported failure. |
| `metric` | number \| null | ✓ | Scalar metric value returned by `EvalTool.run_evaluation()`. `null` for `FAILURE` entries. |
| `output_dir` | string | ✓ | Path to the results directory written by the network/robot plugins. |
| `primary_metric` | string \| null | ✓ | Name of the metric (from `experiment.primary_metric` in `config.yaml`). Used by `cornet view` for sorting. |
| `error` | string | | Present only in `FAILURE` entries. Contains the exception message or EvalTool failure detail. |
| `config_hash` | string | | SHA-256 of the resolved variant config. Older entries may omit it. |
| `git_sha` | string \| null | | Repository HEAD at run time, or `null` outside a git checkout. |
| `seed` | number | | Variant seed. Sweep repeats use `experiment.seed`, then `seed+1`, and so on. |
| `hypothesis_id` | string \| null | | Research hypothesis id, or `null` outside a research session. |
| `lane` | string | | `CORNET_NS3_TAG`, or `none` when that variable is unset. |
| `standard` | boolean | | `true` for a catalogue-standard scenario. Defaults to `true`. |
| `timing_ok` | boolean \| string | | `true`, `false`, or `unavailable`. Taken from `timing.json` only when this run started telemetry. A launch that exits before that leaves `unavailable` even if an older `timing.json` is in the output directory. |
| `rtf_mean` | number | | Gazebo real-time factor mean, present only when `timing.json` recorded `gazebo_rtf.mean`. |

## Atomic write guarantee

The writer (`cornet.leaderboard.writer.append_entry`) uses the following sequence:

1. Read existing `leaderboard.json` (or start with `[]` if absent).
2. Append the new entry.
3. Write the full updated list to `leaderboard.json.tmp`.
4. Call `os.replace("leaderboard.json.tmp", "leaderboard.json")` — atomic on POSIX.

If the process is killed between steps 3 and 4, the `.tmp` file is left on disk. A subsequent run detects the valid `.json` and overwrites the stale `.tmp`. If `leaderboard.json` is corrupted, the writer renames it to `leaderboard.json.bak.<timestamp>` and starts fresh.

## Viewing the leaderboard

```bash
python -m cornet view tasks/<name>
```

See [cli.md](cli.md) for full options.

## Programmatic access

```python
import json
from pathlib import Path

entries = json.loads(Path("tasks/pendulum_nr_control/leaderboard.json").read_text())
successes = [e for e in entries if e["status"] == "SUCCESS"]
best = min(successes, key=lambda e: e["metric"])
print(best["variant_id"], best["metric"])
```
