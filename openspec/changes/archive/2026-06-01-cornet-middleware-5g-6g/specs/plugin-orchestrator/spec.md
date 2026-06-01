## MODIFIED Requirements

### Requirement: Plugin lifecycle contract
Every network and robot plugin SHALL implement the `Plugin` abstract base class defined in `cornet/plugins/base.py` with the following lifecycle methods: `configure(config, context)`, `start()`, `run()`, `stop()`, `collect(output_dir)`. The orchestrator SHALL call these in order and SHALL NOT call a later step if an earlier step raises an exception. The `output_dir` argument to `collect()` SHALL be the same directory passed to the orchestrator's `run()` call, and SHALL be created by the orchestrator before `collect()` is invoked.

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

## ADDED Requirements

### Requirement: output_dir created before collect() is called
The orchestrator SHALL create `output_dir` (with `os.makedirs(output_dir, exist_ok=True)`) before calling any plugin's `collect(output_dir)`. Plugins SHALL be able to write files into `output_dir` from within `collect()` without creating the directory themselves.

#### Scenario: output_dir exists when collect() is called
- **WHEN** the orchestrator calls `collect(output_dir)` on a plugin
- **THEN** `os.path.isdir(output_dir)` SHALL be `True` at the time `collect()` is entered
- **THEN** the plugin SHALL be able to write `open(os.path.join(output_dir, "results.json"), "w")` without raising `FileNotFoundError`

#### Scenario: output_dir creation is idempotent
- **WHEN** `output_dir` already exists
- **THEN** the orchestrator SHALL NOT raise an exception (uses `exist_ok=True`)

### Requirement: Preflight CAP_NET_ADMIN check for NS-3 plugin with middleware
When `network.plugin: ns3` and `middleware.enabled: true`, the orchestrator SHALL verify that the process has root privileges (UID = 0) or `CAP_NET_ADMIN` capability before calling `Ns3Plugin.configure()`. If the check fails, the orchestrator SHALL print `"ERROR: NS-3 middleware requires root or CAP_NET_ADMIN. Run with sudo."` and exit with code 1. Experiments without middleware SHALL NOT require elevated privileges.

#### Scenario: NS-3 + middleware without root exits cleanly
- **WHEN** `middleware.enabled: true` and the process UID is not 0
- **THEN** the orchestrator SHALL print the root error message and exit with code 1
- **THEN** no TUN interfaces SHALL be created
- **THEN** no NS-3 subprocess SHALL be launched
