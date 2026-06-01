## ADDED Requirements

### Requirement: Containernet activated by presence of container config on any node
`MininetPlugin` in `cornet/plugins/network/mininet_plugin.py` SHALL detect whether any node in the config has a non-None `container` field. When containers are present, the plugin SHALL use `from containernet.net import Containernet` as the network class. When no containers are present, the plugin SHALL use `mn_wifi.net.Mininet_wifi` as before. The import of `containernet` SHALL be deferred (inside the method) so that the base `cornet` install does not fail if Containernet is not installed.

#### Scenario: Container config activates Containernet
- **WHEN** any node in `config.network.nodes` has `container.image` set
- **THEN** `MininetPlugin` SHALL instantiate `containernet.net.Containernet` as the network object
- **THEN** each node with a container config SHALL be added via `net.addDocker(name, dimage=image, cpu_quota=quota, mem_limit=mem)`

#### Scenario: No containers uses Mininet-WiFi
- **WHEN** no node in config has a `container` field set
- **THEN** `MininetPlugin` SHALL instantiate `mn_wifi.net.Mininet_wifi` as before
- **THEN** all existing WiFi experiment configs SHALL continue to work unchanged

#### Scenario: Containernet import error gives actionable message
- **WHEN** Containernet is not installed and a container config is present
- **THEN** `MininetPlugin.configure()` SHALL raise `ImportError` with the message: `"containernet not installed. Install with: pip install containernet or see INSTALL.md"`

### Requirement: Docker container resource constraints from device config
When using Containernet, `MininetPlugin` SHALL apply `cpu_quota` and `mem_limit` from the node's container config to each `addDocker()` call. The `cpu_quota` SHALL be passed as a fraction of one CPU core (e.g., 0.5 = 50% of one core). The `mem_limit` SHALL be passed in bytes.

#### Scenario: CPU and memory limits applied to container
- **WHEN** `node.container = {image: "ubuntu:22.04", cpu_quota: 0.5, mem_limit_mb: 512}`
- **THEN** `net.addDocker(name, dimage="ubuntu:22.04", cpu_quota=0.5, mem_limit="512m")` SHALL be called

#### Scenario: Container without resource limits uses defaults
- **WHEN** `node.container = {image: "ubuntu:22.04"}` with no cpu_quota or mem_limit
- **THEN** `net.addDocker()` SHALL be called without `cpu_quota` or `mem_limit` arguments (Containernet defaults apply)

### Requirement: WiFi-only path unchanged by this change
The existing Mininet-WiFi topology setup, `net.socketServer()` call, and wmediumd configuration in `MininetPlugin` SHALL be unchanged when no container config is present. All existing `MininetPlugin` tests SHALL continue to pass.

#### Scenario: Existing mininet task config unaffected
- **WHEN** an existing task config with WiFi nodes but no containers is loaded
- **THEN** `MininetPlugin` SHALL behave identically to its behavior before this change
- **THEN** all unit and integration tests for `MininetPlugin` SHALL pass
