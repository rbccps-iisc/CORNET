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
    "variant_id": "default",
    "metrics": {
      "mean_aoi_ms": 42.7,
      "packet_loss_pct": 1.2
    },
    "config_snapshot": {
      "network.numerology": 2,
      "network.bandwidth_mhz": 20
    },
    "meta": {
      "duration_s": 60.0,
      "cornet_version": "0.1.0"
    }
  }
]
```

## Entry fields

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | ✓ | UTC wall-clock time when the entry was written. |
| `variant_id` | string | ✓ | Sweep variant identifier. `"default"` for non-sweep runs. For sweep runs, constructed as `param1=val1+param2=val2` from the axis values. |
| `metrics` | object | ✓ | Key–value map of scalar metric values produced by the task's `EvalTool`. Keys are strings; values are numbers or strings. |
| `config_snapshot` | object | | Dot-path key–value map of config parameters for this variant. Included automatically for sweep runs. |
| `meta` | object | | Additional metadata (duration, version, etc.). |

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
best = min(entries, key=lambda e: e["metrics"]["mean_aoi_ms"])
print(best["variant_id"], best["metrics"])
```
