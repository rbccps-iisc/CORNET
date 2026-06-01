## 1. Config Error Messaging (D2)

- [x] 1.1 In `cornet/config/loader.py`, `load_unified()`: after checking `schema_tag != "unified-v1"`, detect whether `raw` contains any key in `{"robot", "experiment", "sweep"}` and append `"Did you forget to add '_schema: unified-v1' at the top?"` to the `ConfigValidationError` message when true
- [x] 1.2 Add a test in `tests/test_unified_config.py` for the new hint message: load a YAML with `robot:` but no `_schema` tag and assert `"Did you forget"` appears in the exception string

## 2. Parallel Sweep — GAZEBO_MASTER_URI (D3)

- [x] 2.1 In `cornet/orchestrator.py`, `_apply_ros_domain()`: when `sweep.parallel` is true and `config.robot is not None`, set `os.environ["GAZEBO_MASTER_URI"] = f"http://localhost:{11345 + variant_index}"`
- [x] 2.2 Save and restore the previous `GAZEBO_MASTER_URI` value in `Orchestrator.run()` alongside the existing `ROS_DOMAIN_ID` save/restore pattern
- [x] 2.3 Add a test in `tests/test_plugin_lifecycle.py` or a new `tests/test_sweep_expander.py` entry that mocks the parallel sweep path and asserts `GAZEBO_MASTER_URI` is set with a port offset per variant

## 3. EvalTool Metric Validation (D4)

- [x] 3.1 In `cornet/eval/base.py`: add `format_result(cls, value: float, status: str = "SUCCESS") -> str` as a `@classmethod` returning `f"{status}, {float(value)}"`
- [x] 3.2 In `cornet/orchestrator.py`, `_eval_and_record()`: replace `except ValueError: metric = None` with `raise ValueError(f"EvalTool returned non-float metric: {metric_str!r}. Use EvalTool.format_result() to construct the return string.")`
- [x] 3.3 Add tests in `tests/test_eval_tool.py`:
  - `format_result(14.3)` → `"SUCCESS, 14.3"`
  - `format_result(0.0, "FAILURE")` → `"FAILURE, 0.0"`
  - `_eval_and_record` with metric string `"14.3 ms"` raises `ValueError`
  - `_eval_and_record` with metric string `"14.3"` writes leaderboard entry normally (regression)

## 4. Stale Launch File Cleanup (D5)

- [x] 4.1 In `cornet/orchestrator.py`: add `_cleanup_stale_launch_files(task_dir: Path) -> None` that globs `generated_launch_*.py` in `task_dir`, checks `mtime`, and unlinks files older than 3600 seconds; log each deletion at DEBUG level
- [x] 4.2 Call `_cleanup_stale_launch_files(resolved_task_dir)` in `Orchestrator.run()` immediately after `_resolve_config()` returns, guarded by `if resolved_task_dir is not None`
- [x] 4.3 Add a test in `tests/test_generic_launch.py` using `tmp_path`: create a `generated_launch_old.py` with mtime set 2 hours in the past and a `generated_launch_new.py` with current mtime; call `_cleanup_stale_launch_files`; assert old file removed and new file still present
