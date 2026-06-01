## 1. Config Schema Extensions

- [x] 1.1 Add `MiddlewareConfig` Pydantic model to `cornet/config/schema.py` (enabled, ip_list, rtf, deadline_s, ber, clock_timeout_s, clock_socket, positions_socket)
- [x] 1.2 Add `MobilityConfig` Pydantic model to `cornet/config/schema.py` (enabled, source, update_hz, update_mode, position_threshold_m)
- [x] 1.3 Add `ScenarioConfig` Pydantic model to `cornet/config/schema.py` (profile as Literal, numerology, bandwidth_mhz, scheduler, experimental)
- [x] 1.4 Extend `NodeConfig` with `ip`, `x`, `y`, `z`, `model_name` fields (all optional, preserve `extra="allow"`)
- [x] 1.5 Add `middleware`, `mobility`, `scenario` optional fields to `NetworkConfig`
- [x] 1.6 Verify all 19 existing tests still pass after schema changes

## 2. Middleware Package Skeleton

- [x] 2.1 Create `cornet/middleware/__init__.py` exporting `PacketDispatcher`, `AoITracker`, `TunManager`, `ClockServer`, `PositionServer`
- [x] 2.2 Create `cornet/middleware/dispatcher.py` — min-heap priority queue with `enqueue()`, `update_physics_time()`, `start()`, `stop()`, `stats`
- [x] 2.3 Implement rtf-scaled sleep and ε-tolerance (0.001s) release logic in `PacketDispatcher`
- [x] 2.4 Implement deadline discard with stats counting in `PacketDispatcher`
- [x] 2.5 Implement optional BER injection using stdlib geometric distribution in `PacketDispatcher`
- [x] 2.6 Create `cornet/middleware/aoi.py` — `AoITracker` with per-flow `update()`, CSV trace writer, `close()`, `summary()`, `export_json()`
- [x] 2.7 Implement `AoITracker` percentile statistics using stdlib `statistics` (no numpy)
- [x] 2.8 Create `cornet/middleware/tun.py` — `TunManager` with `setup()`, `teardown()`, `get_fd()`, context manager protocol
- [x] 2.9 Implement `TunManager.setup()`: `/dev/net/tun` + `fcntl.ioctl(TUNSETIFF)`, `ip addr add`, policy routing tables
- [x] 2.10 Implement `TunManager.teardown()` as idempotent cleanup of routing rules and TUN fds

## 3. Physics Clock and Position Servers

- [x] 3.1 Create `cornet/middleware/clock.py` — `ClockServer` UDS server at configurable socket path
- [x] 3.2 Implement `ClockServer`: newline-delimited JSON accept loop, stale socket cleanup on start, wall-clock fallback after timeout
- [x] 3.3 Implement `PositionServer` UDS server with atomic position dict update on each message
- [x] 3.4 Ensure `cornet/middleware/clock.py` has zero ROS imports; add `ClockServer` and `PositionServer` to `cornet/middleware/__init__.py`

## 4. Bridge Scripts (Optional Extras)

- [x] 4.1 Create `cornet/bridges/ros2_bridge.py` — subscribe to `/clock` and position topic, push to UDS endpoints (only file with `rclpy` import)
- [x] 4.2 Create `cornet/bridges/ros1_bridge.py` — subscribe to `/clock` and `/gazebo/model_states`, push to UDS endpoints (only file with `rospy` import)
- [x] 4.3 Register `cornet-bridge-ros2` and `cornet-bridge-ros1` as console scripts in `pyproject.toml`
- [x] 4.4 Add `[ros2]` and `[ros1]` optional dependency extras to `pyproject.toml`

## 5. NS-3 Plugin Middleware Integration

- [x] 5.1 Update `Ns3Plugin.configure()` to read `MiddlewareConfig` and `ScenarioConfig` from `NetworkConfig`
- [x] 5.2 Update `Ns3Plugin.start()`: call `TunManager.setup()` before NS-3 subprocess launch; pass `--tunX=<ifname>,<ip>` args to NS-3
- [x] 5.3 Update `Ns3Plugin.start()`: start `ClockServer`, `PositionServer`, `PacketDispatcher` after NS-3 is running
- [x] 5.4 Update `Ns3Plugin.stop()`: call `PacketDispatcher.stop()`, terminate NS-3, then `TunManager.teardown()` (guaranteed order)
- [x] 5.5 Update `Ns3Plugin.collect(output_dir)`: call `AoITracker.close()` and `AoITracker.export_json(output_dir)`
- [x] 5.6 Guard entire middleware path behind `if middleware and middleware.enabled:` so middleware-disabled path is zero-overhead

## 6. Orchestrator Updates

- [x] 6.1 Update `cornet/orchestrator.py`: call `os.makedirs(output_dir, exist_ok=True)` before calling any plugin's `collect()`
- [x] 6.2 Add preflight CAP_NET_ADMIN check in `Orchestrator.run()` when `middleware.enabled: true` for ns3 plugin
- [x] 6.3 Update `Plugin` base class `collect()` signature in `cornet/plugins/base.py` to accept `output_dir: str`

## 7. Containernet Integration in MininetPlugin

- [x] 7.1 Add detection logic in `MininetPlugin.configure()`: check if any node has `container` field set
- [x] 7.2 Add deferred import of `containernet.net.Containernet` with `ImportError` guard and actionable error message
- [x] 7.3 Update `MininetPlugin._build_topology()` to call `net.addDocker()` with `cpu_quota` and `mem_limit` for container nodes
- [x] 7.4 Ensure WiFi-only path (no containers) remains unchanged; run existing Mininet tests to verify

## 8. 5G/6G NS-3 Script Templates

- [x] 8.1 Create `cornet/scenarios/__init__.py` and `cornet/scenarios/README.md`
- [x] 8.2 Create `cornet/scenarios/5g_nr_urllc/run.py` — NS-3 CTTC `nr` module, numerology 3, TapBridge, CLI args
- [x] 8.3 Create `cornet/scenarios/5g_nr_embb/run.py` — NS-3 CTTC `nr` module, numerology 1, TapBridge
- [x] 8.4 Create `cornet/scenarios/5g_nr_mmtc/run.py` — NS-3 CTTC `nr` module, numerology 0, 20 MHz, up to 32 UEs
- [x] 8.5 Create `cornet/scenarios/6g_thz/run.py` — ns3-thz module, 300 GHz, experimental flag
- [x] 8.6 Update `Ns3Plugin` to resolve scenario profile to template path and launch it

## 9. Tests

- [x] 9.1 Create `tests/test_middleware.py` — unit tests for `PacketDispatcher` ordering, ε release, deadline discard, BER=0 pass-through
- [x] 9.2 Add `PacketDispatcher` RTF sleep and stats tests to `tests/test_middleware.py`
- [x] 9.3 Add `AoITracker` tests: per-flow tracking, CSV output, `summary()` statistics, empty-flow returns None
- [x] 9.4 Add `TunManager` tests: mock `fcntl.ioctl` and subprocess calls; verify routing table commands; verify idempotent teardown
- [x] 9.5 Add `ClockServer` tests: wall-clock fallback, malformed JSON ignored, stale socket cleanup
- [x] 9.6 Add `MininetPlugin` Containernet tests: container config activates Containernet; no-container config uses Mininet-WiFi
- [x] 9.7 Add `ScenarioConfig` validation tests: valid profiles pass, invalid profile raises `ConfigValidationError`
- [x] 9.8 Verify all 19 original tests still pass (`pytest tests/ -x`)
