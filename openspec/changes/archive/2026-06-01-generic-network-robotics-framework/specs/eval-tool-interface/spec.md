## ADDED Requirements

### Requirement: EvalTool base class and per-task implementation
The framework SHALL provide `framework/eval/base.py` defining an abstract `EvalTool` class with a single required method `run_evaluation(results_dir: str) -> str`. The return value SHALL follow the format: first line `SUCCESS, <metric>` or `FAILURE,` optionally followed by `FAILURE, <metric>`, with additional detail lines permitted after the first. The `<metric>` SHALL be a numeric float string.

#### Scenario: EvalTool called by collect() after experiment
- **WHEN** the orchestrator's `collect()` phase runs
- **THEN** it SHALL import `eval.eval_tool.EvalTool` from the task directory
- **THEN** call `eval_tool.run_evaluation(output_dir)` and parse the first line
- **THEN** write `{timestamp, variant_id, status, metric, output_dir}` to `tasks/<name>/leaderboard.json`

#### Scenario: Missing eval_tool is silently skipped
- **WHEN** the task directory has no `eval/eval_tool.py`
- **THEN** `collect()` SHALL complete successfully without error
- **THEN** no leaderboard entry SHALL be written for that run

#### Scenario: EvalTool wraps existing analysis scripts
- **WHEN** a task's `eval/eval_tool.py` calls `analysis/aoi_pendulum_analysis.py` internally and reads the produced `aoi_statistics.json`
- **THEN** the primary metric extracted (e.g. `mean_aoi_ms`) SHALL be returned as `SUCCESS, <value>`
- **THEN** the full analysis outputs (PNG plots, report.txt) SHALL remain in `output_dir/analysis/`

### Requirement: Primary metric declared in config
Each task config SHALL optionally declare `experiment.primary_metric` (string key matching a field in `aoi_statistics.json` or `control_statistics.json`) and `experiment.higher_is_better` (bool, default false). These SHALL be passed to the `EvalTool` constructor and used by the leaderboard viewer for sort order.

#### Scenario: Primary metric controls leaderboard sort order
- **WHEN** `experiment.higher_is_better: false` and two runs have metrics `12.5` and `8.3`
- **THEN** the leaderboard SHALL rank the `8.3` run first (lower is better)

#### Scenario: FAILURE run still written to leaderboard
- **WHEN** `run_evaluation()` returns a line starting with `FAILURE,`
- **THEN** the leaderboard SHALL record `status: "FAILURE"` for that run
- **THEN** FAILURE runs SHALL appear last regardless of sort order
