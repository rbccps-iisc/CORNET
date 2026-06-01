## ADDED Requirements

### Requirement: MiddlewareConfig added to NetworkConfig
`NetworkConfig` SHALL accept an optional `middleware: MiddlewareConfig | None` field (default `None`). `MiddlewareConfig` SHALL have fields: `enabled: bool = False`, `ip_list: list[str] = []`, `rtf: float = 1.0`, `deadline_s: float = 0.5`, `ber: float = 0.0`, `clock_timeout_s: float = 5.0`, `clock_socket: str = "/tmp/cornet_clock.sock"`, `positions_socket: str = "/tmp/cornet_positions.sock"`. When `middleware.enabled` is absent or `False`, the field SHALL be ignored by all plugins.

#### Scenario: MiddlewareConfig loads from YAML
- **WHEN** config YAML contains `network.middleware.enabled: true` and `network.middleware.ip_list: ["10.0.0.1"]`
- **THEN** `config.network.middleware.enabled` SHALL be `True`
- **THEN** `config.network.middleware.ip_list` SHALL equal `["10.0.0.1"]`

#### Scenario: MiddlewareConfig absent defaults to disabled
- **WHEN** config YAML has no `middleware` key under `network`
- **THEN** `config.network.middleware` SHALL be `None`
- **THEN** no middleware SHALL be activated by any plugin

### Requirement: MobilityConfig added to NetworkConfig
`NetworkConfig` SHALL accept an optional `mobility: MobilityConfig | None` field (default `None`). `MobilityConfig` SHALL have fields: `enabled: bool = False`, `source: str = "socket"`, `update_hz: float = 10.0`, `update_mode: Literal["periodic","threshold","step_aligned"] = "periodic"`, `position_threshold_m: float = 0.5`. When `mobility.enabled` is `False` (default), no position updates SHALL be sent to plugins after startup.

#### Scenario: MobilityConfig defaults to disabled
- **WHEN** config has no `mobility` key
- **THEN** `config.network.mobility` SHALL be `None`
- **THEN** `PositionBroadcaster` SHALL NOT be started

#### Scenario: MobilityConfig validates update_mode
- **WHEN** `mobility.update_mode: invalid_mode` is in the config
- **THEN** `load_unified()` SHALL raise `ConfigValidationError` listing valid modes

### Requirement: ScenarioConfig added as optional NetworkConfig field
`NetworkConfig` SHALL accept an optional `scenario: ScenarioConfig | None` field (default `None`). `ScenarioConfig` SHALL have fields: `profile: Literal["5g_nr_urllc","5g_nr_embb","5g_nr_mmtc","6g_thz"]`, `numerology: int | None = None`, `bandwidth_mhz: float | None = None`, `scheduler: str | None = None`, `experimental: bool = False`.

#### Scenario: ScenarioConfig profile validated at load
- **WHEN** `scenario.profile: 5g_nr_urllc` is set
- **THEN** `config.network.scenario.profile` SHALL equal `"5g_nr_urllc"`
- **THEN** no `ConfigValidationError` SHALL be raised

### Requirement: NodeConfig gains first-class ip, position, and model_name fields
`NodeConfig` SHALL add: `ip: str | None = None`, `x: float | None = None`, `y: float | None = None`, `z: float | None = None`, `model_name: str | None = None`. The `model_name` field SHALL identify nodes that are tracked by `PositionBroadcaster` for live position updates. Nodes without `model_name` SHALL use static `(x, y, z)` sent once at startup. The `extra="allow"` policy SHALL remain so legacy fields continue to work.

#### Scenario: NodeConfig loads ip and position fields
- **WHEN** node config is `{name: ue1, type: UE, ip: "10.0.0.1", x: 5.0, y: 3.0, z: 0.0}`
- **THEN** `node.ip` SHALL equal `"10.0.0.1"`
- **THEN** `node.x` SHALL equal `5.0`

#### Scenario: NodeConfig without model_name is treated as static
- **WHEN** a node has `x: 5.0, y: 3.0` but no `model_name`
- **THEN** `PositionBroadcaster` SHALL use the static `(x, y, z)` values
- **THEN** no dynamic position subscription SHALL be made for this node
