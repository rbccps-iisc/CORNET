## Why

CORNET's flagship repo has a fully functional orchestration layer (plugin lifecycle, config, sweep, leaderboard) but is missing the co-simulation middleware that gives the framework its scientific value: time-synchronized packet dispatch, physics-clock-driven routing of robot traffic through network simulators, and Age of Information tracking. Three generations of CORNET (1.0–3.0) each implemented pieces of this middleware; this change consolidates the proven design from all three into the flagship, then extends it to enable frontier 5G NR and 6G THz robotic simulations.

## What Changes

- **New**: `cornet/middleware/` package — portable, simulator-agnostic co-simulation engine extracted from CORNET3.0
- **New**: `PacketDispatcher` implementing Algorithm 1 (thesis) — physics-time priority queue, rtf-scaled sleep, deadline discard
- **New**: `AoITracker` — per-flow Age of Information measurement, CSV export, statistics (mean/std/percentiles)
- **New**: `TunManager` — TUN interface lifecycle + source-based policy routing (tables 1…N, 101…N+100)
- **New**: `PhysicsClockSubscriber` — subscribes to ROS2 `/clock` topic; falls back to wall-clock when ROS2 unavailable
- **New**: `cornet/scenarios/` package — 5G NR (URLLC, eMBB, mMTC) and 6G THz scenario configs + NS-3 script templates
- **Modified**: `Ns3Plugin` — wired to full middleware stack (TUN setup, dispatcher start/stop, clock subscription)
- **Modified**: `MininetPlugin` — upgraded to Containernet for true Docker-in-Mininet co-simulation
- **New**: `Ns3MininetPlugin` — hybrid plugin using the aydeger/mininet-lte TapBridge approach (NS-3 in-process via Python bindings)
- **Modified**: `cornet/config/schema.py` — adds `MiddlewareConfig` (time_sync, aoi, ip_list) and `ScenarioConfig` (standard, numerology, bandwidth, QoS)
- **New**: `tests/test_middleware.py` — unit tests for dispatcher ordering, AoI statistics, TUN teardown

## Capabilities

### New Capabilities

- `packet-dispatcher`: Physics-time priority queue implementing Algorithm 1 — enqueue with dt=pt+Δt, rtf-scaled sleep, ε-tolerance release, deadline discard
- `aoi-tracker`: Per-flow Age of Information tracking — CSV trace per flow, JSON summary, statistics (mean, std, p50/p95/p99)
- `tun-manager`: TUN interface lifecycle — create/destroy tun0…tunN, assign IPs, configure per-node source-based policy routing tables
- `physics-clock`: Physics simulator clock subscription — ROS2 `/clock` subscriber with monotonic wall-clock fallback, feeds `update_physics_time()` on PacketDispatcher
- `ns3-middleware-integration`: Full middleware wiring in Ns3Plugin — TUN setup before NS-3 launch, dispatcher running during experiment, clock subscription active, AoI results collected
- `containernet-integration`: MininetPlugin upgrade — uses Containernet (Docker-as-Mininet-host) when container config present, veth pairs connect Docker containers to Mininet nodes
- `5g-6g-scenarios`: Scenario config templates for 5G NR URLLC/eMBB/mMTC and 6G THz — YAML configs that translate to NS-3 CLI arguments, pre-built NS-3 Python script templates for each standard

### Modified Capabilities

- `unified-config-schema`: Adds `middleware` and `scenario` sections to `NetworkConfig`; `NodeConfig` gains `ip` as first-class field (not `model_extra`)
- `plugin-orchestrator`: Orchestrator passes `output_dir` to plugin `collect()` earlier so middleware can write AoI traces before results are gathered

## Impact

- **`cornet/middleware/`**: New package, no existing code changed
- **`cornet/config/schema.py`**: Additive — new optional fields, no breaking changes to existing configs
- **`cornet/plugins/network/ns3_plugin.py`**: Ns3Plugin gains TUN lifecycle; requires root when middleware enabled
- **`cornet/plugins/network/mininet_plugin.py`**: Containernet import replaces `mn_wifi` when containers present; existing WiFi-only path unchanged
- **`cornet/plugins/network/ns3_mininet_plugin.py`**: New file
- **`cornet/scenarios/`**: New package
- **Dependencies**: `numpy` removed from middleware (replaced with stdlib `statistics`); optional `rclpy` for ROS2 clock
- **Tests**: New `tests/test_middleware.py`; all 19 existing tests must continue to pass
