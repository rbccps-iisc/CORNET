# Middleware

CORNET's middleware layer bridges the NS-3 simulated network and the ROS 2
robot simulation. It provides four components: **AoI Tracker**, **Clock
Server**, **Packet Dispatcher**, and **TUN Manager**.

---

## 1. Overview

```
NS-3 simulation                    ROS 2 / Gazebo
       │                                  │
       │  simulated packets               │
       ▼                                  │
  PacketDispatcher ──(on_dispatch)──► TUN interface
       │                                  │
       └──(physics time)──► ClockServer
                                   │
                              AoITracker
                           (per-flow AoI CSV)
```

All middleware components run in the CORNET process. They have no ROS 2
imports and work at the Python level.

---

## 2. Clock Server

`cornet.middleware.clock.ClockServer` accepts physics-time ticks over a Unix
domain socket and notifies registered listeners.

```python
from cornet.middleware.clock import ClockServer

def on_tick(t: float) -> None:
    print(f"physics time: {t:.3f}s")

clock = ClockServer(
    socket_path="/tmp/cornet_clock.sock",
    clock_timeout_s=5.0,
    on_tick=on_tick,
)
clock.start()
# ...
clock.stop()
```

The NS-3 scenario sends JSON messages over the socket:

```json
{"t": 12.345}
```

If no client connects within `clock_timeout_s` seconds, the server falls back
to `time.monotonic()` advancing the clock at the real-time rate.

There is also a `PositionServer` for robot position updates:

```json
{"name": "robot0", "x": 1.0, "y": 2.0, "z": 0.0}
```

---

## 3. Packet Dispatcher

`cornet.middleware.dispatcher.PacketDispatcher` implements a physics-time
priority queue. Packets enqueued with a simulated release timestamp are
dispatched via `on_dispatch` when `wall_clock >= release_time / rtf`.

```python
from cornet.middleware.dispatcher import PacketDispatcher

def on_dispatch(flow_id: str, payload: bytes) -> None:
    # forward payload to the TUN interface or application
    print(f"dispatching {len(payload)} bytes for flow {flow_id}")

dispatcher = PacketDispatcher(
    rtf=1.0,           # real-time factor (1.0 = wall time matches sim time)
    deadline_s=0.5,    # discard packets that are >0.5 s late
    ber=0.0,           # bit-error rate (0 = lossless)
    on_dispatch=on_dispatch,
)
dispatcher.start()
dispatcher.enqueue(flow_id="ue0->gnb0", payload=b"hello", physics_time=5.0)
# ...
dispatcher.stop()
```

**BER modelling**: When `ber > 0`, the dispatcher applies a geometric
distribution to each packet to simulate bit-level losses (stdlib only, no
numpy).

**RTF = 0**: Setting `rtf=0` disables sleep and dispatches as fast as
possible (useful for non-real-time replay).

---

## 4. AoI Tracker

`cornet.middleware.aoi.AoITracker` tracks per-flow Age of Information (AoI):

$$\text{AoI}_f(t) = t - u_f$$

where $u_f$ is the physics timestamp of the last received update from flow $f$.

```python
from cornet.middleware.aoi import AoITracker

tracker = AoITracker(
    trace_path="/tmp/aoi_trace.csv",
    sample_hz=1.0,          # how often sample() records an AoI snapshot
)

# Called by the network plugin each time a status update is received:
tracker.record_update(flow_id="ue0->gnb0", physics_time=5.0)

# Called by the ClockServer on_tick callback:
tracker.sample(physics_time=5.1)

# At the end of the experiment:
stats = tracker.close()
# stats["ue0->gnb0"] = {"mean": 0.12, "max": 0.5, "p95": 0.3, ...}
```

The `close()` method writes the CSV trace and returns percentile statistics.
The EvalTool in `tasks/pendulum_nr_control/eval/eval_tool.py` reads these
statistics from `analysis/aoi_statistics.json`.

---

## 5. TUN Manager

`cornet.middleware.tun.TunManager` creates Linux TUN interfaces (one per node
IP) and configures policy routing so that NS-3 tap traffic is steered to the
correct interface.

```python
from cornet.middleware.tun import TunManager

mgr = TunManager(ip_list=["10.0.0.1", "10.0.0.2"])
mgr.setup()   # requires CAP_NET_ADMIN (root or ambient capability)
# ... run experiment ...
mgr.teardown()  # idempotent — safe to call on error
```

**Interface naming**: `cornet0`, `cornet1`, … per the IP list order.

**Routing tables**: outbound table `i+1`, loopback table `i+101` for each
interface `i`.

**Teardown**: `teardown()` is idempotent. Call it in a `finally` block to
ensure cleanup even on experiment failure.

---

## 6. Wiring the components

In a typical plugin, all four components are wired together:

```python
# inside MyPlugin.start():
def on_tick(t):
    self._tracker.sample(t)

self._clock = ClockServer(on_tick=on_tick)
self._dispatcher = PacketDispatcher(rtf=config.middleware.rtf, on_dispatch=self._forward)
self._tracker = AoITracker(trace_path=output_dir / "aoi.csv")
self._tun = TunManager(ip_list=list(context.network.node_ips.values()))

self._tun.setup()
self._clock.start()
self._dispatcher.start()
```

See `cornet/middleware/` for the full implementation details.

<!-- TODO: expand — document middleware config schema fields (rtf, deadline_s, ber, clock_socket_path, position_socket_path) and show how they map to config.yaml. -->
