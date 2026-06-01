## ADDED Requirements

### Requirement: Mininet-WiFi topology with Docker container nodes
The framework SHALL instantiate a Mininet-WiFi network topology where each node in the `network.nodes` config list can be backed by a Docker container image. Docker containers SHALL be started before Mininet stations are created and stopped after Mininet is torn down. The plugin SHALL expose IP addresses of instantiated nodes to other plugins via the shared experiment context.

#### Scenario: Docker container nodes start before simulation
- **WHEN** a task config specifies `network.type: mininet` and one or more nodes with `container.image` set
- **THEN** the orchestrator SHALL pull (if not cached) and start each Docker container before calling `mininet_plugin.start()`
- **THEN** each container SHALL be connected to the Mininet topology at the IP address specified in `network.nodes[*].ip`

#### Scenario: Access point and mobile station co-exist
- **WHEN** a node has `type: STATIC` in the config
- **THEN** the plugin SHALL create a Mininet-WiFi access point + host pair at the configured position
- **WHEN** a node has `type: MOBILE`
- **THEN** the plugin SHALL create a Mininet-WiFi station with mobility model enabled

#### Scenario: Topology teardown on experiment stop
- **WHEN** the orchestrator calls `mininet_plugin.stop()`
- **THEN** all Mininet stations, access points, and Docker containers SHALL be stopped and removed
- **THEN** the plugin SHALL not leave orphaned network namespaces or container processes

#### Scenario: wmediumd interference modeling enabled by config
- **WHEN** the config includes `network.mininet.wmediumd: true`
- **THEN** the plugin SHALL start wmediumd before the Mininet topology
- **WHEN** `network.mininet.wmediumd` is absent or false
- **THEN** the plugin SHALL skip wmediumd without error

#### Scenario: Plugin exposes node IPs to shared context
- **WHEN** Mininet topology is up
- **THEN** the plugin SHALL write `context.network.node_ips` as a dict `{node_name: ip_address}` accessible to the robot plugin
