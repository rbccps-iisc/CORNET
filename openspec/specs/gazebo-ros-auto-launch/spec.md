## ADDED Requirements

### Requirement: Auto-generate ROS 2 Gazebo launch when no launch file is configured
When a task config includes a `robot` section but does not specify `robot.launch_file`, the framework SHALL auto-generate a ROS 2 Python launch file that: (1) starts the Gazebo simulator with the configured world, (2) spawns each robot listed in `robot.robots` at its configured pose, and (3) starts `robot_state_publisher` for robots with a URDF/xacro path. The generated file SHALL be written to `tasks/<name>/generated_launch_<timestamp>.py` and invoked via `ros2 launch`.

#### Scenario: Launch file auto-generated when absent
- **WHEN** `robot.launch_file` is null or not present in config
- **THEN** `framework/gazebo/generic_launch.py` SHALL generate a valid `launch.py` file in the task directory
- **THEN** the generated file SHALL be parseable by `ros2 launch` without error
- **THEN** the orchestrator SHALL invoke it and wait for Gazebo to report ready before proceeding

#### Scenario: Each robot spawned at configured pose
- **WHEN** the generated launch file runs
- **THEN** each entry in `robot.robots` SHALL result in a `spawn_entity` call with the entity name, SDF/URDF model path, and `x`, `y`, `z`, `yaw` from config
- **WHEN** a robot entry omits `pose`
- **THEN** the robot SHALL be spawned at the origin (0, 0, 0, 0)

#### Scenario: URDF robot gets robot_state_publisher
- **WHEN** a robot entry has `model.type: urdf` and a valid `model.path`
- **THEN** the generated launch SHALL include a `robot_state_publisher` node for that robot with the URDF content loaded
- **WHEN** `model.type: sdf`
- **THEN** `robot_state_publisher` SHALL NOT be included for that robot

#### Scenario: User-supplied launch file takes precedence
- **WHEN** `robot.launch_file` is set to a valid path
- **THEN** the orchestrator SHALL invoke the user-supplied file directly
- **THEN** `generic_launch.py` SHALL NOT generate a new file

#### Scenario: World file configured
- **WHEN** `robot.world` is set to a path ending in `.sdf` or `.world`
- **THEN** the generated launch SHALL pass `-world <path>` to `gzserver`
- **WHEN** `robot.world` is absent
- **THEN** the generated launch SHALL start an empty Gazebo world

#### Scenario: Generated launch file cleaned up after experiment
- **WHEN** the orchestrator calls `gazebo_plugin.stop()`
- **THEN** the generated `generated_launch_<timestamp>.py` file SHALL be deleted from disk
