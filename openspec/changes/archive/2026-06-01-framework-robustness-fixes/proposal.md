## Why

The adversarial discussion of `generic-network-robotics-framework` (archived 2026-06-01) surfaced four correctness and integration risks in the implemented framework that are silent in normal operation: a YAML config fallback that masks mis-typed unified configs, a parallel sweep mode where `ROS_DOMAIN_ID` isolation does not protect Gazebo's fixed port, an `EvalTool` return-string contract loose enough to cause leaderboard sort failures, and a generated launch file that accumulates on disk when the orchestrator is killed before `stop()`. All four are small, targeted fixes with no architectural impact.

## What Changes

- **`cornet/config/loader.py`** — `load_unified()` fallback detection: before silencing a Pydantic `ValidationError`, check whether the YAML contains any unified-schema sentinel key (`robot`, `experiment`, `sweep`); if so, surface the full error instead of falling back
- **`cornet/orchestrator.py`** — parallel sweep: assign `GAZEBO_MASTER_URI` and `GAZEBO_MODEL_DATABASE_URI` with per-variant port offsets alongside the existing `ROS_DOMAIN_ID` assignment; add a stale `generated_launch_*.py` cleanup call at orchestrator startup
- **`cornet/eval/base.py`** — `EvalTool.collect()`: cast the parsed metric to `float` and raise `ValueError` if it fails; add a `format_result(value: float, status="SUCCESS") -> str` class method that enforces the format
- **`.gitignore`** — add `tasks/**/generated_launch_*.py`

## Capabilities

### New Capabilities

- `eval-tool-metric-validation`: `EvalTool` base class gains a `format_result()` class method and a `float`-cast guard in `collect()`; malformed metric strings now raise `ValueError` at record time with a descriptive message

### Modified Capabilities

- `unified-config-schema`: fallback detection logic changed — YAMLs containing `robot:`, `experiment:`, or `sweep:` keys are treated as attempted unified configs and surface `ConfigValidationError` instead of silently falling back to the legacy loader
- `gazebo-ros-auto-launch`: spec updated to require `GAZEBO_MASTER_URI` port assignment in parallel sweep mode and to document gitignore protection for generated launch files
- `parameter-sweep`: spec updated to require per-variant `GAZEBO_MASTER_URI` assignment (port = base + variant index) when `parallel: true`

## Impact

- **`cornet/config/loader.py`**: ~10 lines changed in `load_unified()`
- **`cornet/orchestrator.py`**: ~15 lines added — port-offset logic in parallel sweep setup, startup cleanup call
- **`cornet/eval/base.py`**: ~10 lines added — `format_result()` classmethod, `float()` cast guard
- **`.gitignore`**: 1 line added
- **No breaking changes**: all existing task configs and tests remain valid; the fallback change only affects YAMLs that contain sentinel keys AND have a Pydantic error, which no existing task config does
