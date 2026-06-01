## ADDED Requirements

### Requirement: Task folder structure convention
Each self-contained experiment SHALL live in `tasks/<name>/` containing at minimum a `config.yaml`. Optional files are `world.sdf`, `launch.py` or `launch.xml`, and an `eval/` directory for analysis scripts. The orchestrator SHALL accept a task folder path as its first argument: `python -m framework tasks/<name>`.

#### Scenario: Orchestrator accepts task folder path
- **WHEN** the user runs `python -m framework tasks/my_experiment`
- **THEN** the orchestrator SHALL look for `tasks/my_experiment/config.yaml`
- **WHEN** `config.yaml` is not found
- **THEN** the orchestrator SHALL exit with a descriptive error listing the expected path

#### Scenario: Optional files are used when present
- **WHEN** `tasks/<name>/launch.py` exists and `config.yaml` does not set `robot.launch_file`
- **THEN** the orchestrator SHALL use `tasks/<name>/launch.py` as the robot launch file automatically
- **WHEN** `tasks/<name>/world.sdf` exists and `config.yaml` does not set `robot.world`
- **THEN** the orchestrator SHALL use `tasks/<name>/world.sdf` as the Gazebo world automatically

#### Scenario: Task folder is fully self-contained
- **WHEN** a task folder is copied to a different machine with the framework installed
- **THEN** the orchestrator SHALL be able to run the experiment using only the files in the task folder plus system-level simulators (NS-3, Gazebo, ROS 2)
- **THEN** no paths outside the task folder or framework package SHALL be hard-coded in `config.yaml`

### Requirement: Example tasks bundled with the framework
The repository SHALL include at least two example tasks under `tasks/` demonstrating different configurations.

#### Scenario: NS-3 + Gazebo example task present
- **WHEN** the repository is cloned
- **THEN** `tasks/pendulum_nr_control/config.yaml` SHALL exist and be valid according to the unified schema
- **THEN** running `python -m framework tasks/pendulum_nr_control` SHALL start the NS-3 network and Gazebo pendulum simulation

#### Scenario: Mininet-WiFi + Gazebo example task present
- **WHEN** the repository is cloned
- **THEN** `tasks/uav_wifi_control/config.yaml` SHALL exist and be valid according to the unified schema
- **THEN** it SHALL demonstrate Mininet-WiFi with Docker container nodes and a UAV spawned in Gazebo
