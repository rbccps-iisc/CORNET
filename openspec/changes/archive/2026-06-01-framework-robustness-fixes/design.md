## Context

Four risks were identified in the adversarial review of `generic-network-robotics-framework`. Code inspection confirms:

- **D2 (config error messaging)**: `load_unified()` in `cornet/config/loader.py` already requires `_schema: unified-v1` — there is no silent fallback. However, when a YAML contains unified-schema sentinel keys (`robot:`, `experiment:`, `sweep:`) but omits `_schema: unified-v1`, the current error message is generic: `"Expected '_schema: unified-v1', got ''. This loader only handles unified configs."` A researcher who mistakenly omits the schema tag gets no hint to add it.
- **D3 (parallel Gazebo ports)**: `_apply_ros_domain()` in `orchestrator.py` sets `ROS_DOMAIN_ID` per variant but does **not** set `GAZEBO_MASTER_URI`. Two parallel Gazebo instances will conflict on port 11345.
- **D4 (EvalTool metric)**: `_eval_and_record()` in `orchestrator.py` silently sets `metric = None` when `float(metric_str)` raises `ValueError` (e.g. `"14.3 ms"`, `"14.3, 22.1"`). The leaderboard records a null metric without any error. The `EvalTool` base class has no `format_result()` helper to prevent malformed strings.
- **D5 (generated launch cleanup)**: `.gitignore` already covers `tasks/*/generated_launch_*.py`. Missing: a startup cleanup call that removes stale files left by a previous SIGKILL-terminated run.

All four fixes are localized to ≤3 functions each; no architectural change.

## Goals / Non-Goals

**Goals:**
- Improve `load_unified()` error message for YAMLs that look like unified configs but are missing `_schema: unified-v1`
- Set `GAZEBO_MASTER_URI` per variant when `sweep.parallel: true` and a robot plugin is active
- Raise `ValueError` (instead of silently `None`) when `EvalTool` returns an unparseable metric string
- Add `EvalTool.format_result(value, status)` classmethod to the base class
- Purge stale `generated_launch_*.py` files at orchestrator startup

**Non-Goals:**
- Changing the `_schema: unified-v1` sentinel mechanism (it works correctly)
- Full async/parallel isolation beyond Gazebo port assignment
- Changing the leaderboard JSON schema

## Decisions

### D1: Sentinel-key detection in load_unified() error path

**Decision**: In `load_unified()`, when the `_schema` tag is missing or wrong, check whether the raw dict contains any of `{"robot", "experiment", "sweep"}`. If so, append `"Did you forget to add '_schema: unified-v1' at the top?"` to the error message.

**Rationale**: One-line addition to the existing error path. No behavior change for valid configs or genuine legacy YAMLs (which won't have `robot:`, `experiment:`, or `sweep:` keys). Directly addresses the "no hint" problem without any fallback logic.

---

### D2: GAZEBO_MASTER_URI port assignment in _apply_ros_domain()

**Decision**: When `sweep.parallel: true`, set `GAZEBO_MASTER_URI=http://localhost:{11345 + variant_index}` in `_apply_ros_domain()`. Only apply when the config has a robot plugin (check `config.robot is not None`).

**Rationale**: Gazebo Classic's master process binds to `GAZEBO_MASTER_URI` (default `http://localhost:11345`). Per-variant port offset is the same pattern already used for `ROS_DOMAIN_ID` and requires no additional dependencies. Base port 11345 + variant_index is safe for typical sweep sizes (≤20 variants = ports 11345–11364).

**Alternative considered**: Detect and kill stale Gazebo processes at startup. Rejected: too invasive and masks the root cause.

---

### D3: ValueError in _eval_and_record(), format_result() on EvalTool

**Decision**: Replace `except ValueError: metric = None` with a re-raise that includes the malformed string. Add `EvalTool.format_result(value: float, status: str = "SUCCESS") -> str` as a classmethod that returns `f"{status}, {float(value)}"`.

**Rationale**: Silent `None` means the leaderboard silently stores a broken entry with no feedback to the researcher. A raised `ValueError` surfaces at collect time. `format_result()` gives task implementors a canonical way to construct the return string correctly.

**Impact on existing tasks**: `pendulum_nr_control` and `uav_wifi_control` both return `f"SUCCESS, {value}"` with a plain float — they will be unaffected.

---

### D4: Stale generated launch file cleanup at orchestrator startup

**Decision**: Add a `_cleanup_stale_launch_files(task_dir: Path)` call in `Orchestrator.run()` before `_resolve_config()`. It removes `generated_launch_*.py` files in the task directory that are older than 1 hour.

**Rationale**: SIGKILL cannot be caught; `stop()` is not called. The `.gitignore` already covers the pattern so files won't be committed, but they accumulate on disk. A 1-hour age threshold avoids deleting files from a concurrently running experiment. Called before config load so it runs even if config validation subsequently fails.

## Risks / Trade-offs

- **[Risk] GAZEBO_MASTER_URI port exhaustion** — variant_index ≥ 1000 would overflow to privileged ports. → Not a realistic concern for research sweeps; the existing `ROS_DOMAIN_ID > 101` guard already caps parallel sweep width.
- **[Risk] ValueError surfacing breaks existing task code that returns non-float metrics** — unlikely given existing tasks use plain floats, but possible for third-party tasks. → The error message names the malformed string, so task authors can fix it quickly. `format_result()` makes the contract explicit.
- **[Risk] 1-hour stale threshold too conservative** — a very slow experiment might still be running when cleanup runs for a subsequent invocation. → Cleanup is guarded by file age: files from the currently running experiment are minutes old, not hours. Safe in practice.
