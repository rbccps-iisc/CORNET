# Parameter Sweep

CORNET's built-in sweep engine expands a cartesian product of parameter axes
across one or more runs, writing each variant to its own output directory and
leaderboard entry.

---

## 1. Add a `sweep` block

In your task's `config.yaml`, add a `sweep` key under `experiment`:

```yaml
experiment:
  name: my_sweep
  duration: 60.0
  output_dir: results
  primary_metric: mean_aoi_ms
  higher_is_better: false

  sweep:
    axes:
      network.scenario.numerology: [1, 2, 3]
      network.scenario.bandwidth_mhz: [20, 40]
    repeats: 2
```

This expands to **3 × 2 × 2 = 12** runs.

---

## 2. Axis key format

Axis keys are dot-path references to fields in `UnifiedConfig`. Examples:

| Key | Field |
|---|---|
| `network.scenario.numerology` | `config.network.scenario.numerology` |
| `network.scenario.bandwidth_mhz` | `config.network.scenario.bandwidth_mhz` |
| `experiment.duration` | `config.experiment.duration` |
| `middleware.rtf` | `config.middleware.rtf` |

The key must resolve to a scalar field (int, float, str, bool). Nested objects
and lists are not supported as sweep values.

---

## 3. Variant ID naming

CORNET generates a `variant_id` string for each expanded variant:

| Axes | Repeats | Example variant ID |
|---|---|---|
| 1 axis | 1 | `"2"` (the value itself) |
| 2+ axes | 1 | `"numerology=2_bandwidth_mhz=40"` |
| any | > 1 | `"numerology=2_bandwidth_mhz=40_run1"` |

Variant IDs are used as:
- `output_dir` suffix: `results/numerology=2_bandwidth_mhz=40_run1/`
- `variant_id` field in `leaderboard.json`

---

## 4. Output directory layout

```
results/
  numerology=1_bandwidth_mhz=20_run1/
    analysis/
      aoi_statistics.json
  numerology=1_bandwidth_mhz=20_run2/
    analysis/
      aoi_statistics.json
  numerology=1_bandwidth_mhz=40_run1/
  ...
tasks/my_task/leaderboard.json    ← one entry per variant
```

---

## 5. Running a sweep

```bash
python -m cornet tasks/my_task
```

The sweep runner calls `expand_sweep(config)` then iterates through each
variant sequentially. Failed variants are logged and skipped; the sweep
continues.

---

## 6. Viewing sweep results

```bash
python -m cornet view tasks/my_task
```

The leaderboard table shows one row per variant, sorted by primary metric.
Use the web UI for charts across sweep dimensions:

```bash
python -m cornet ui tasks/my_task
```

---

## 7. Programmatic sweep expansion

```python
from cornet.config.loader import load_config
from cornet.sweep.expander import expand_sweep

config = load_config("tasks/my_task/config.yaml")
variants = expand_sweep(config)
for v in variants:
    print(v.experiment.name, v.network.scenario.numerology)
```

`expand_sweep` returns a single-element list (original config, name = "default")
when no sweep is defined.

---

## 8. Reference: SweepConfig schema

| Field | Type | Default | Description |
|---|---|---|---|
| `axes` | `dict[str, list]` | `{}` | Mapping from dot-path key to list of values. |
| `repeats` | `int` | `1` | Number of repeated runs per parameter combination. |

See [config-schema.md](../reference/config-schema.md) for the full schema.
