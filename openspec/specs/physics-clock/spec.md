## ADDED Requirements

### Requirement: UDS clock server endpoint
The system SHALL implement `ClockServer` in `cornet/middleware/clock.py` that listens on a Unix Domain Socket at a configurable path (default: `/tmp/cornet_clock.sock`). The server SHALL accept newline-delimited JSON messages of the form `{"type":"clock","physics_time":<float>}`. On each valid message, `ClockServer.get_physics_time()` SHALL return the most recently received `physics_time` value.

#### Scenario: Clock updated via UDS message
- **WHEN** a client connects to `/tmp/cornet_clock.sock` and sends `{"type":"clock","physics_time":1.2345}\n`
- **THEN** `ClockServer.get_physics_time()` SHALL return `1.2345`
- **THEN** the server SHALL continue accepting new connections and messages

#### Scenario: Old socket file cleaned up on start
- **WHEN** `/tmp/cornet_clock.sock` already exists from a previous run
- **THEN** `ClockServer.start()` SHALL remove the stale socket file before binding
- **THEN** `ClockServer.start()` SHALL NOT raise `OSError: Address already in use`

#### Scenario: Malformed JSON message ignored
- **WHEN** a client sends `not-valid-json\n`
- **THEN** the server SHALL log a WARNING and continue processing the next message
- **THEN** `get_physics_time()` SHALL return the last valid value unchanged

### Requirement: UDS position server endpoint
The system SHALL implement `PositionServer` in `cornet/middleware/clock.py` that listens on a Unix Domain Socket at a configurable path (default: `/tmp/cornet_positions.sock`). The server SHALL accept newline-delimited JSON messages of the form `{"type":"positions","nodes":{"<name>":{"x":<f>,"y":<f>,"z":<f>},...}}`. On each valid message, `PositionServer.get_positions()` SHALL return the most recently received positions dict.

#### Scenario: Positions updated via UDS message
- **WHEN** a client sends `{"type":"positions","nodes":{"robot1":{"x":5.1,"y":0.2,"z":0.5}}}\n`
- **THEN** `PositionServer.get_positions()` SHALL return `{"robot1": {"x":5.1,"y":0.2,"z":0.5}}`

#### Scenario: Position update is atomic
- **WHEN** a new positions message arrives while the previous positions are being read
- **THEN** `get_positions()` SHALL return either the complete old dict or the complete new dict, never a partial mix

### Requirement: Wall-clock fallback when no physics source connects
When `physics.connector: none` is configured, or when no client connects within `clock_timeout_s` seconds after `ClockServer.start()`, `get_physics_time()` SHALL return `time.monotonic()` (wall-clock time). A WARNING SHALL be logged: `"No physics clock connected after <timeout>s. Using wall clock."`.

#### Scenario: No bridge connected falls back to wall clock
- **WHEN** `ClockServer` is started and no client connects within `clock_timeout_s = 5.0`
- **THEN** `get_physics_time()` SHALL return a value equal to `time.monotonic()` within 0.1 seconds
- **THEN** a WARNING log line SHALL contain `"wall clock"`

#### Scenario: Physics connector: none uses wall clock immediately
- **WHEN** `physics.connector` is configured as `none`
- **THEN** `ClockServer` SHALL NOT start the UDS listener
- **THEN** `get_physics_time()` SHALL return `time.monotonic()` from the first call

### Requirement: PhysicsConnector abstraction for ROS2 and ROS1 bridges
The package SHALL ship CLI bridge scripts installable as extras. `cornet[ros2]` SHALL install `cornet-bridge-ros2` which subscribes to `/clock` (ROS2 `rosgraph_msgs/Clock`) and `/robot_positions` topic and pushes to the UDS endpoints. `cornet[ros1]` SHALL install `cornet-bridge-ros1` equivalently. These scripts SHALL be the ONLY files in the `cornet` package that import `rclpy` or `rospy`; the base `cornet` package SHALL have no ROS dependency.

#### Scenario: Base package installs without ROS
- **WHEN** `pip install cornet` is run on a system without ROS2
- **THEN** all `cornet` imports SHALL succeed without `ImportError`
- **THEN** `from cornet.middleware.clock import ClockServer` SHALL work without rclpy present

#### Scenario: ROS2 bridge pushes to clock endpoint
- **WHEN** `cornet-bridge-ros2` is running and Gazebo publishes `/clock` at 100 Hz
- **THEN** the bridge SHALL push one `{"type":"clock","physics_time":<t>}` message per `/clock` message to the UDS socket
- **THEN** `ClockServer.get_physics_time()` in CORNET SHALL update at approximately 100 Hz
