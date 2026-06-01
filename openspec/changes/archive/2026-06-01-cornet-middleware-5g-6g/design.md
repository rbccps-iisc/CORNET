## Context

CORNET's flagship repo has a working orchestration layer (plugin lifecycle, sweep, leaderboard, 19/19 tests passing) but is missing the co-simulation middleware that makes it scientifically useful. Three prior CORNET generations each implemented pieces:

- **CORNET v1 (2017)**: ArduPilot SITL + NS-3 as ZMQ relay. Delay injection was application-level — the UAV control script slept until `t_send + network_delay` elapsed. NS-3 stamped packets with simulation timestamps; the application extracted the delta. Static positions from XML at launch.
- **CORNET 2.0 (2020)**: Gazebo + Mininet-WiFi + Containernet/Docker. Introduced live position sync: `gz model -m <robot> -p` (CLI poll at 1 Hz) → TCP socket → `net.socketServer()` → wmediumd. The network coordinator was stubbed in Python 2 and never finished.
- **CORNET 3.0 (2022)**: ROS2 + Gazebo + NS-3 NR. Ported ros-net-sim's NetworkCoordinator. Added `PacketDispatcher` (Algorithm 1 from thesis) — moving delay injection from application code into transparent middleware. Dropped live position sync (not needed for inverted pendulum thesis experiments). `cornet_middleware.py` has no ROS2 imports; the ROS2 clock bridge lives in a separate `cornet_bridge_node.py`.

**Related frameworks explored during design:**

- **ROS-NetSim** (alelab-upenn): The direct ancestor of CORNET3.0's middleware. Identical TUN setup, policy routing, `_read_from_tuns`. Uses `threading.Barrier(2)` for BEGIN/END step-sync between physics and network simulators. Has BER injection (`numpy.random.geometric`), packet buffering by `(pkt_id, src_ip, dst_ip)`, and a driver process for MAC-layer requests.
- **DANCERS** (Chroma-CITI, SIMPAR 2025): ROS2 + Gazebo + NS-3. "Decoupled time-stepped" synchronization — a central Coordinator sends BEGIN to both simulators, waits for END from both, advances clock. Sends robot positions to NS-3 at each sync window for mobility-aware channel modeling. Uses Connector abstraction (PhysicsConnector + NetworkConnector) for simulator-agnostic design.

**Key observation from code genealogy:** CORNET3.0's `cornet_middleware.py` already has the right boundary — `update_physics_time(pt)` is a plain Python method call with no ROS imports. The coupling to ROS2 lives in a separate bridge node. The flagship formalizes this boundary and generalizes it.

## Goals / Non-Goals

**Goals:**

- Port `PacketDispatcher`, `AoITracker`, and `TunManager` from CORNET3.0 into the flagship as `cornet/middleware/`
- Add a `PhysicsConnector` abstraction decoupling the middleware from any specific physics simulator middleware (ROS2, ROS1, Gazebo transport, custom)
- Add a `PositionBroadcaster` for configurable robot position sync to network simulators — disabled by default, configurable frequency and mode
- Wire the full middleware stack into `Ns3Plugin` and `MininetPlugin`
- Add `NodeConfig.x/y/z` and `MobilityConfig` to the unified config schema
- Ship NS-3 script templates for 5G NR URLLC, eMBB, mMTC, and 6G THz scenarios
- Keep `cornet` base package free of ROS dependencies; provide `cornet[ros2]` and `cornet[ros1]` extras

**Non-Goals:**

- Implementing DANCERS-style locked-step (barrier) synchronization — CORNET's async dispatch is the thesis differentiation and must be preserved
- Real-time position-aware beam-steering or handover simulation in v1 — channel model updates from positions are best-effort, not step-aligned
- 6G semantic communication or O-RAN AI scheduler — ns3-thz extreme NR params for 6G, not custom semantic coding layers
- Windows or macOS support — TUN/TAP and policy routing are Linux-specific
- Replacing Mininet-WiFi's wmediumd with NS-3 WiFi — they serve different use cases; both are supported

## Decisions

### Decision 1: Keep Async Physics-Clock Dispatch (Algorithm 1), Not Barrier-Based Sync

**Chosen:** CORNET's existing model — sender stamps packet with physics time `pt`, receiver (PacketDispatcher) releases when `physics_time >= pt + network_delay`.

**Rejected:** DANCERS/ROS-NetSim barrier model — Coordinator sends BEGIN, both simulators run one step, both send END, Coordinator advances clock.

**Rationale:** CORNET's research question is how network-induced delay affects robot control performance (AoI, control quality, stability margin). The async model preserves the delay as a real independent variable experienced by the control loop. The barrier model collapses delay into discrete quantized steps, hiding the delay distribution from the experiment. For inverted pendulum and URLLC studies, a packet arriving 0.3ms late vs 0.7ms late has different control consequences — the barrier model would round both to the same sync window.

The barrier model is better when consistent cross-simulator state is required (e.g., collision detection across simulators). That is not CORNET's use case in v1.

```
ASYNC (CORNET):                        BARRIER (DANCERS):
────────────────────────────           ────────────────────────────
Gazebo runs freely at rtf              Coordinator: BEGIN ──► all
/clock → update_physics_time           Gazebo runs for step_size
                                       NS-3 runs for step_size
Robot TUN → annotate(pt)               Both send END
→ NS-3 adds delay Δt                   Coordinator advances clock
→ dispatcher enqueues (pt+Δt, pkt)
→ sleep until physics_time ≥ pt+Δt    Delay ≤ 1 sync_window
→ release pkt to controller            Delay preserved as continuous
```

### Decision 2: PhysicsConnector as Decoupled Push Endpoint

**Chosen:** CORNET exposes two UDS server endpoints. Any physics middleware bridge pushes to them. The middleware core has no ROS imports.

```
Clock endpoint:     /tmp/cornet_clock.sock
Protocol:           newline-delimited JSON
Message:            {"type":"clock","physics_time":1.234567}

Position endpoint:  /tmp/cornet_positions.sock
Protocol:           newline-delimited JSON
Message:            {"type":"positions","nodes":{"robot1":{"x":5.1,"y":0.2,"z":0.5}}}
```

**Connector types** (`physics.connector` config key):

| Connector | Mechanism | ROS dependency |
|-----------|-----------|----------------|
| `ros2` | rclpy subscriber to `/clock` and position topic | `cornet[ros2]` extra |
| `ros1` | rospy subscriber to `/clock` and `/gazebo/model_states` | `cornet[ros1]` extra |
| `socket` | CORNET runs the UDS servers; bridge script pushes | none |
| `none` | Wall clock mode; no physics sync | none |

**Why push model over pull (subscriber) model:** CORNET3.0 already used this pattern — `update_physics_time(pt)` was always called externally. Making it a socket endpoint means: (a) any language can bridge (MATLAB, Bash, C++); (b) cornet base has zero optional deps; (c) integration tests use the same socket path without mocking rclpy; (d) researchers on ROS1 Melodic can use CORNET without any code changes.

**Bridge scripts** ship with the package as optional CLI tools: `cornet-bridge-ros2`, `cornet-bridge-ros1`, `cornet-bridge-gz`. These are the modernized replacement for CORNET2.0's `gz_robot_position.py`.

### Decision 3: Mobility is Disabled by Default, Fully Configurable

**Chosen:** `mobility.enabled: false` by default (CORNET3.0 thesis behav zero overhead). When enabled, three update modes at configurable frequency.ior,

**Rationale:** Not all experiments need mobility. Inverted pendulum, robotic arm, and fixed-sensor-array experiments don't need channel model updates — adding overhead for them would be wrong. The framework must be a zero-cost abstraction when features are off.

**Three update modes:**

```
PERIODIC:  update every 1/update_hz seconds regardless of movement
           Best for: UAV experiments, unknown movement patterns

THRESHOLD: update only when any tracked node moved > position_threshold_m
           Best for: slow ground robots, saves IPC to wmediumd/NS-3
           Example: 0.5m threshold at 2 m/s → ~4 updates/s naturally

STEP_ALIGNED: update at each PacketDispatcher sync window boundary
           Best for: experiments needing consistent channel state per packet
           Higher coupling; requires sync_window_ms config
```

**Per-node configuration:** Nodes with `model_name` set are tracked via the position source. Nodes without `model_name` use static `x/y/z` from config (sent once at startup). This supports mixed topologies: fixed gNB + mobile UE + static controller host.

**Position source for Mininet-WiFi (restoring CORNET 2.0):** PositionBroadcaster sends `set.{model_name}.setPosition("{x},{y},{z}")` to Mininet-WiFi's built-in `net.socketServer()` via TCP. This updates wmediumd in real time — the same mechanism as CORNET2.0's `gz_robot_position.py`, modernized with ROS2 subscriber instead of `gz model -m` CLI polling.

**Position source for NS-3:** NS-3 script templates include a position update UDS server. PositionBroadcaster sends JSON position batch. NS-3 script calls `node->GetObject<MobilityModel>()->SetPosition(Vector(x,y,z))`. This is new vs CORNET3.0.

### Decision 4: TUN Open via fcntl.ioctl, Policy Routing via subprocess

**Chosen:** Open `/dev/net/tun` with `open('/dev/net/tun', 'r+b', buffering=0)` + `fcntl.ioctl(tun, TUNSETIFF, struct.pack('16sH', name, IFF_TUN|IFF_NO_PI))`. Policy routing configured via `subprocess.call(["sudo", "ip", ...])`.

**Rationale:** Confirmed from both CORNET3.0 and ros-net-sim source. `fcntl.ioctl` keeps the TUN fd as a Python file object (readable with `os.read`), avoiding `/dev/net/tun` fd management complexity. The policy routing tables (1…N for outbound per-IP, 101…N+100 for loopback interception) are identical in CORNET3.0 and ros-net-sim — proven pattern.

**Table structure:**
```
Table i+1    (i=node index): outbound from ip_i via tun_i
Table i+101:                  loopback interception for ip_i
"ip rule del pref 0" + "ip rule add pref 10" for local lookup ordering
```
This allows the same host to appear as multiple network endpoints, each with its own TUN.

### Decision 5: Remove numpy from Middleware, Use stdlib statistics

**Chosen:** Replace `numpy.random.geometric` and `numpy.percentile` with stdlib equivalents.

**Rationale:** numpy is a heavy dependency. CORNET base should install in any Python 3.10+ environment without numpy. The AoI statistics (mean, std, p50/p95/p99) use `statistics.mean`, `statistics.stdev`, and a simple sorted-list percentile:

```
p-th percentile of list xs:
  sorted_xs = sorted(xs)
  idx = (p/100) * (len(sorted_xs) - 1)
  lo, hi = int(idx), min(int(idx)+1, len-1)
  return sorted_xs[lo] + (idx - lo) * (sorted_xs[hi] - sorted_xs[lo])
```

For BER injection (from ros-net-sim): geometric distribution `P(X=k) = (1-p)^(k-1) * p` implemented as `math.ceil(math.log(random.random()) / math.log(1-p))`. Validated against numpy results in tests.

### Decision 6: 5G/6G via NS-3 Script Templates (Not Runtime Generation)

**Chosen:** Pre-built NS-3 Python script templates per scenario profile. Templates use TapBridge to CORNET TUN interfaces. YAML `profile` key selects the template; other keys (`numerology`, `bandwidth`, `scheduler`) become CLI arguments.

**Profiles:**

| Profile | NS-3 module | Key params | Use case |
|---------|-------------|------------|----------|
| `5g_nr_urllc` | nr (CTTC) | numerology 3, 100 MHz, OFDM symbol scheduling | 1ms latency budget, robot control |
| `5g_nr_embb` | nr (CTTC) | numerology 1, 100 MHz, large MIMO | High-throughput robot data |
| `5g_nr_mmtc` | nr (CTTC) | numerology 0, 20 MHz, NB-IoT-like | Many sensors, low power |
| `6g_thz` | thz (NIST ns3-thz) | 300 GHz, 2 GHz BW, ~10m range | THz close-range robot-to-robot |

**Rejected: Runtime script generation.** Generating NS-3 C++/Python scripts at runtime from YAML is over-engineered for v1. Researchers need to understand and modify the NS-3 scripts for custom experiments; templates are better than opaque generation.

**NS-3 script interface:** Every template connects to CORNET via TapBridge on the TUN interfaces. The script reads node IPs and TUN names from CLI arguments that CORNET passes. Position update UDS server is built into each template.

### Decision 7: BER Injection as Optional Middleware Feature

**Chosen:** Port `_apply_ber` from ros-net-sim. Disabled by default (`middleware.ber: false`). When enabled, applied by PacketDispatcher on received packets before release.

**Mechanism:** On packet release, if BER > 0: generate geometric-distributed bit-flip positions (using stdlib math, no numpy), flip bits in IP payload only (skip IP header — drop if header bit would flip). BER = 0 → pass through. BER = 1 → always drop. `0 < BER < 1` → stochastic bit errors.

**Rationale:** ROS-NetSim's `_apply_ber` is well-tested and directly applicable. Disabled by default keeps the pendulum experiment behavior unchanged. Useful for 5G URLLC reliability studies.

### Decision 8: MininetPlugin → Containernet when Containers Present

**Chosen:** Import `from containernet.net import Containernet` when any node in config has `container` set; otherwise fall back to `mn_wifi.net.Mininet_wifi`.

**Rejected:** Always use Containernet. Containernet has additional Docker dependencies that WiFi-only experiments don't need.

**Rationale:** Preserves backward compatibility. The `container` field in `NodeConfig` is the opt-in signal. Existing tasks without containers continue to use Mininet-WiFi unchanged.

## Risks / Trade-offs

**[Risk] TUN setup requires root** → Mitigation: Document this clearly. `TunManager.setup()` raises `PermissionError` with a descriptive message if not root. Tests mock the subprocess calls; CI does not require root.

**[Risk] wmediumd position update rate vs. experiment fidelity** → Mitigation: `mobility.update_hz` defaults to 10 Hz. For fast UAVs (>10 m/s), 10 Hz means ~1m position error per update interval; log-distance path loss change ≈1–2 dB. Acceptable for most experiments. Document the tradeoff; users can set higher Hz.

**[Risk] NS-3 position update server adds coupling to script templates** → Mitigation: The position server in NS-3 templates is optional — if CORNET doesn't start the position broadcaster, the NS-3 server just idles. The UDS socket path is configurable.

**[Risk] PhysicsConnector socket endpoint — bridge not running when CORNET starts** → Mitigation: ClockServer and PositionServer use `SO_REUSEADDR` and accept connections lazily. If no bridge connects within a configurable `clock_timeout_s`, CORNET falls back to wall clock and logs a warning. This preserves test-without-bridge usability.

**[Risk] stdlib percentile differs from numpy for small sample sizes** → Mitigation: Validate against numpy in unit tests with synthetic AoI data (>100 samples). Document: p99 is unreliable below ~100 packets/flow.

**[Risk] 6G THz (ns3-thz) module is experimental** → Mitigation: Ship the `6g_thz` template as `experimental` with a config warning. Requires manually installing ns3-thz. Falls back gracefully if module not found at NS-3 build time.

**[Risk] Coordinate frame mismatch between Gazebo ENU and Mininet-WiFi/NS-3** → Mitigation: Default `physics.coordinate_frame: gazebo_enu` is identity (Gazebo meters = NS-3 meters). Mininet-WiFi positions use the same scale. Document that the Gazebo world origin and Mininet grid origin must match (or use `coordinate_offset` config).

**[Risk] Removing numpy breaks CORNET3.0 experiment reproducibility** → Mitigation: The BER bit-flip positions from stdlib geometric will differ from numpy's — but BER is disabled by default and not used in any current task configs. The AoI statistics differences are in the 5th decimal place for >100 samples.

## Open Questions

1. **NS-3 position update protocol for step-aligned mode:** In `update_mode: step_aligned`, CORNET needs a round-trip confirmation from NS-3 that the position was applied before the next packet is dispatched. Current design assumes best-effort (fire-and-forget). Is this sufficient for v1, or does step-aligned require a synchronous response?

2. **`physics.connector: none` fallback rate:** When no physics clock is available, PacketDispatcher uses wall clock. What RTF should be assumed? Default 1.0. Is there a use case where a researcher explicitly wants `rtf: 2.0` without a physics simulator (e.g., replaying a trace at double speed)?

3. **AoI tracker per-flow key definition:** Should flows be keyed by `(src_ip, dst_ip)` (current CORNET3.0) or `(src_ip, dst_ip, app_port)` (finer granularity for multi-app experiments)? The `(src_ip, dst_ip)` key merges all applications between a robot pair.

4. **`cornet-bridge-ros2` process lifecycle:** Should CORNET start the bridge as a subprocess (automatic, simpler UX) or require the user to start it separately (decoupled, more debuggable)? Automatic launch couples CORNET to the ROS2 environment; separate launch is more explicit.
