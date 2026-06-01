## ADDED Requirements

### Requirement: Ns3Plugin wires full middleware stack during experiment lifecycle
`Ns3Plugin` in `cornet/plugins/network/ns3_plugin.py` SHALL initialize a `TunManager`, `ClockServer`, `PositionServer`, `PacketDispatcher`, and `AoITracker` when `middleware.enabled: true` is set in config. The middleware SHALL be started in `Ns3Plugin.start()` after NS-3 is launched and SHALL be stopped in `Ns3Plugin.stop()` before NS-3 is terminated.

#### Scenario: Middleware stack started after NS-3 launch
- **WHEN** `Ns3Plugin.start()` is called with middleware enabled
- **THEN** `TunManager.setup()` SHALL be called before the NS-3 subprocess is launched
- **THEN** the NS-3 subprocess SHALL be started with TUN interface names passed as CLI arguments
- **THEN** `ClockServer.start()` and `PacketDispatcher.start()` SHALL be called after NS-3 is running

#### Scenario: Middleware stack stopped cleanly on experiment end
- **WHEN** `Ns3Plugin.stop()` is called
- **THEN** `PacketDispatcher.stop()` SHALL be called first (drains remaining packets)
- **THEN** `TunManager.teardown()` SHALL be called after the NS-3 subprocess is terminated
- **THEN** `TunManager.teardown()` SHALL be called even if NS-3 exits with a non-zero code

### Requirement: NS-3 receives TUN interface names and IPs as CLI arguments
When launching the NS-3 subprocess, `Ns3Plugin` SHALL pass TUN configuration via CLI arguments in the format `--tunX=<ifname>,<ip>` for each node. NS-3 script templates SHALL read these arguments to configure `TapBridge` attachment points.

#### Scenario: NS-3 launched with correct TUN arguments
- **WHEN** config has `nodes: [{name: ue1, ip: 10.0.0.1}, {name: gnb1, ip: 10.0.0.2}]`
- **THEN** the NS-3 subprocess SHALL be launched with `--tun0=tun0,10.0.0.1 --tun1=tun1,10.0.0.2`

#### Scenario: NS-3 script missing TUN arguments logged as error
- **WHEN** the NS-3 subprocess exits within 2 seconds of start with code != 0
- **THEN** `Ns3Plugin.start()` SHALL raise `RuntimeError` with the NS-3 script's stderr output
- **THEN** `TunManager.teardown()` SHALL still be called (via guaranteed cleanup)

### Requirement: AoI results collected in collect()
`Ns3Plugin.collect(output_dir)` SHALL call `AoITracker.close()` and then `AoITracker.export_json(output_dir)` to write per-flow CSVs and `aoi_summary.json`. These files SHALL be written before the orchestrator gathers results.

#### Scenario: AoI files present in output directory after experiment
- **WHEN** an experiment with 2 UE nodes completes and `collect(output_dir)` is called
- **THEN** `aoi_summary.json` SHALL exist in `output_dir`
- **THEN** per-flow CSV files (`aoi_<src>_<dst>.csv`) SHALL exist for each observed flow
- **THEN** the JSON summary SHALL contain `mean_s` and `p95_s` for each flow

### Requirement: Middleware disabled path is zero-overhead
When `middleware.enabled` is absent or `false`, `Ns3Plugin` SHALL NOT import or instantiate any middleware classes. The plugin SHALL launch NS-3 directly as before (subprocess only). All existing NS-3 plugin tests SHALL pass without middleware configuration.

#### Scenario: Middleware absent does not affect launch
- **WHEN** config has no `middleware` section
- **THEN** `Ns3Plugin.start()` SHALL launch NS-3 without creating TUN interfaces
- **THEN** no `TunManager` or `PacketDispatcher` SHALL be instantiated
