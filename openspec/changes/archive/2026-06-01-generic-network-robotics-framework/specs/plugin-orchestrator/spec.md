## ADDED Requirements

### Requirement: Plugin lifecycle contract
Every network and robot plugin SHALL implement the `Plugin` abstract base class defined in `framework/plugins/base.py` with the following lifecycle methods: `configure(config, context)`, `start()`, `run()`, `stop()`, `collect(output_dir)`. The orchestrator SHALL call these in order and SHALL NOT call a later step if an earlier step raises an exception.

#### Scenario: Lifecycle methods called in order
- **WHEN** the orchestrator runs an experiment
- **THEN** `configure()` SHALL be called first for all loaded plugins
- **THEN** `start()` SHALL be called after all plugins configure successfully
- **THEN** `run()` SHALL be called and SHALL block until the experiment duration elapses or a plugin signals completion
- **THEN** `stop()` SHALL be called even if `run()` raises an exception (guaranteed cleanup)
- **THEN** `collect()` SHALL be called after `stop()` to gather result artifacts

#### Scenario: Plugin exception in start() halts experiment cleanly
- **WHEN** any plugin's `start()` raises an exception
- **THEN** the orchestrator SHALL call `stop()` on all already-started plugins in reverse order
- **THEN** the orchestrator SHALL NOT call `run()` or `collect()`
- **THEN** the exception message SHALL be logged with the plugin name

### Requirement: Plugin registry and config-driven loading
The orchestrator SHALL load plugins by names declared in the config (`network.plugin` and `robot.plugin` fields). The plugin registry in `framework/plugins/__init__.py` SHALL map string names to plugin classes. Unknown plugin names SHALL raise `PluginNotFoundError` at config-validation time, before any process is started.

#### Scenario: NS-3 network plugin loaded by name
- **WHEN** config sets `network.plugin: ns3`
- **THEN** the orchestrator SHALL instantiate `Ns3Plugin` and pass the `network` config section to its `configure()` method

#### Scenario: Mininet network plugin loaded by name
- **WHEN** config sets `network.plugin: mininet`
- **THEN** the orchestrator SHALL instantiate `MininetPlugin`

#### Scenario: Unknown plugin raises error before start
- **WHEN** config sets `network.plugin: unknown_backend`
- **THEN** `orchestrator.load_plugins()` SHALL raise `PluginNotFoundError` before calling any lifecycle method

### Requirement: Shared experiment context passed between plugins
The orchestrator SHALL maintain an `ExperimentContext` dataclass and pass it to every plugin's `configure()`. Plugins SHALL write outputs (e.g. IP addresses, bridge names, socket paths) into `context` and SHALL read from it to obtain inputs from sibling plugins.

#### Scenario: Network plugin writes IPs, robot plugin reads them
- **WHEN** the Mininet plugin completes `start()` and writes `context.network.node_ips`
- **THEN** the Gazebo robot plugin's `configure()` (called after network configure) SHALL be able to read `context.network.node_ips` to configure robot-to-node IP bindings

### Requirement: Preflight root check for Mininet plugin
The orchestrator SHALL detect whether the process has root privileges before calling `MininetPlugin.configure()`. If root is not available, the orchestrator SHALL log a clear error message and exit without starting any plugins.

#### Scenario: No root raises descriptive error
- **WHEN** `network.plugin: mininet` and the process UID is not 0
- **THEN** the orchestrator SHALL print `"ERROR: Mininet plugin requires root. Run with sudo."` and exit with code 1
- **THEN** no plugins SHALL be started
