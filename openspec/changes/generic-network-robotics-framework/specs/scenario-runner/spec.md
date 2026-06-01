## MODIFIED Requirements

### Requirement: run_scenario.py delegates to framework orchestrator
`run_scenario.py` SHALL remain the CLI entry point for backward compatibility but SHALL delegate all orchestration logic to `framework/orchestrator.py`. When invoked with an existing `scenarios/*.yaml` file, it SHALL call the orchestrator in legacy mode (bypassing unified config validation). When invoked with a `tasks/<name>` path or a unified-schema YAML, it SHALL call the orchestrator in task mode.

#### Scenario: Existing scenario YAML still works unchanged
- **WHEN** the user runs `python3 run_scenario.py scenarios/pendulum_5g_nr_urllc_control.yaml`
- **THEN** the experiment SHALL run identically to the pre-framework behavior
- **THEN** no error SHALL be raised due to the legacy config format

#### Scenario: New task folder path accepted
- **WHEN** the user runs `python3 run_scenario.py tasks/pendulum_nr_control`
- **THEN** `run_scenario.py` SHALL detect the argument is a directory
- **THEN** it SHALL call `framework.orchestrator.run(task_dir="tasks/pendulum_nr_control")`

#### Scenario: Unified YAML accepted directly
- **WHEN** the user runs `python3 run_scenario.py tasks/my_exp/config.yaml`
- **THEN** `run_scenario.py` SHALL detect `_schema: unified-v1` in the file
- **THEN** it SHALL call `framework.orchestrator.run(config_path=...)` using unified mode
