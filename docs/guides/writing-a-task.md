# Writing a Task

This guide walks through creating a new CORNET experiment task from scratch.
A task is a directory under `tasks/` containing a `config.yaml` and optionally
an `eval/eval_tool.py`.

---

## 1. Directory layout

```
tasks/
  my_task/
    config.yaml          ← required: experiment configuration
    eval/
      eval_tool.py       ← optional: metric extractor (enables leaderboard)
    launch.py            ← optional: custom ROS 2 launch file (auto-discovered)
    world.sdf            ← optional: custom Gazebo world (auto-discovered)
```

CORNET auto-discovers `launch.py` and `world.sdf` if present. If absent, the
Gazebo plugin generates them from `config.yaml`.

---

## 2. Minimal `config.yaml`

```yaml
# tasks/my_task/config.yaml
network:
  plugin: ns3
  type: ns3
  # simulation_script: name of the NS-3 scratch script to run.
  # Use the shortcut name (strip ALL "-default" occurrences from the binary
  # name — e.g. ns3.38-my_script-default-default → shortcut: my_script).
  simulation_script: my_script
  # All other flat keys under network: are forwarded as --key=val NS-3 CLI args.
  networkPreset: 5g_nr_urllc    # --networkPreset
  numerology: 2                  # --numerology
  bandwidth: 20000000            # --bandwidth in Hz (20 MHz)
  schedulerType: edf             # --schedulerType
  nodes:
    - name: ue0
      type: UE
      ip: 10.0.0.1
    - name: gnb0
      type: GNB

robot:
  plugin: gazebo
  robots:
    - name: robot0
      model:
        type: urdf
        path: models/pendulum.urdf
      pose:
        x: 0.0
        y: 0.0
        z: 0.1

experiment:
  name: my_task
  duration: 60.0
  output_dir: results
  primary_metric: mean_latency_ms
  higher_is_better: false
```

**NS-3 script shortcut name**: The `simulation_script` value must match the NS-3
program shortcut, not the `.cc` filename. NS-3 strips **all** `-default`
occurrences when building shortcuts: a binary
`ns3.38-my_script-default-default` becomes shortcut `my_script`.

**Alternative — built-in scenario templates**: Instead of `simulation_script`
and flat CLI keys, you can use the nested `scenario:` block to select one of
CORNET's bundled scenario scripts:

```yaml
network:
  plugin: ns3
  type: ns3
  scenario:
    profile: 5g_nr_urllc   # 5g_nr_urllc | 5g_nr_embb | 5g_nr_mmtc | 6g_thz
    numerology: 2           # forwarded as --numerology
    bandwidth_mhz: 20       # forwarded as --bandwidth (value in MHz)
    scheduler: edf          # forwarded as --scheduler
  nodes: [...]
```

See [config-schema.md](../reference/config-schema.md) for the full field reference.

---

## 3. Run the task

```bash
python -m cornet tasks/my_task
# equivalent:
python -m cornet run tasks/my_task
```

CORNET will:
1. Load and validate `config.yaml` against `UnifiedConfig` schema
2. Start the NS-3 network plugin (launches the `5g_nr_urllc` scenario script)
3. Start the Gazebo robot plugin (spawns robot0 in the auto-generated world)
4. Run for `experiment.duration` seconds
5. Call `eval/eval_tool.py` if present
6. Write an entry to `tasks/my_task/leaderboard.json`

---

## 4. Add an EvalTool

Create `tasks/my_task/eval/eval_tool.py`:

```python
# tasks/my_task/eval/eval_tool.py
from __future__ import annotations

import json
from pathlib import Path
from cornet.eval.base import EvalTool as BaseEvalTool


class EvalTool(BaseEvalTool):
    """Compute mean round-trip latency from NS-3 CSV output."""

    def run_evaluation(self, results_dir: str) -> str:
        csv_path = Path(results_dir) / "latency.csv"
        if not csv_path.exists():
            return "FAILURE,\nmissing latency.csv"

        rows = csv_path.read_text().strip().splitlines()[1:]  # skip header
        if not rows:
            return "FAILURE,\nempty latency.csv"

        values = [float(r.split(",")[1]) for r in rows]
        mean_ms = sum(values) / len(values)

        return self.format_result(mean_ms)
```

**EvalTool contract:**
- `run_evaluation(results_dir)` receives the path where the network plugin wrote its output files
- Return value must be `"SUCCESS, <float>"` (use `self.format_result(value)`) or `"FAILURE,\n<detail>"`
- `format_result` raises `ValueError` for non-finite floats — always validate your metric

The leaderboard entry written to `leaderboard.json` will contain a flat `metric` field with the returned value, e.g. `{"status": "SUCCESS", "metric": 42.7, "primary_metric": "mean_latency_ms", ...}`.

---

## 5. View the leaderboard

After one or more runs:

```bash
python -m cornet view tasks/my_task
```

Prints a ranked table sorted by `primary_metric` (ascending by default; pass `--higher-is-better` to reverse).

```bash
python -m cornet view tasks/my_task --higher-is-better
```

---

## 6. Use the web UI

```bash
python -m cornet ui tasks/my_task
```

Opens the leaderboard in a browser with live-reloading charts. Useful for monitoring a sweep.

---

## 7. Run a parameter sweep

Add a `sweep` block to `experiment:`:

```yaml
experiment:
  name: My Task Sweep
  duration: 60.0
  output_dir: results
  primary_metric: mean_latency_ms
  sweep:
    axes:
      network.numerology: [1, 2, 3]         # dot-path into config fields
      network.bandwidth: [20000000, 40000000]  # NS-3 flat extra key (Hz)
    repeats: 3
```

CORNET expands the cartesian product (6 variants × 3 repeats = 18 runs) and writes each to:

```
results/
  numerology=1+bandwidth=20000000/run_0/
  numerology=1+bandwidth=20000000/run_1/
  ...
```

See [parameter-sweep.md](parameter-sweep.md) for full details.

---

## 8. Existing tasks as examples

| Task | Network | Robot | Notes |
|---|---|---|---|
| `tasks/pendulum_nr_control/` | NS-3 (URLLC) | Gazebo pendulum | AoI eval tool |
| `tasks/uav_wifi_control/` | Mininet-WiFi | Gazebo UAV | Docker containers |
| `tasks/aoi_5phase_eval/` | NS-3 (URLLC) | — | Sweep over 5 AoI phases |

---

## 9. NS-3 capability levels and lane selection

CORNET maintains a capability registry at `scripts/patches/ns3/CAPABILITY_MATRIX.yaml`.
Every CORNET-exposed NS-3 feature is classified at one of three levels:

| Level | Meaning |
|---|---|
| `upstream-available` | Feature exists in NR upstream source. No CORNET patches, config fields, or scratch script support yet. Manual integration required. |
| `cornet-integrated` | CORNET patches or config fields expose the feature. Not yet exercised end-to-end in a leaderboard run. |
| `cornet-validated` | Feature has been exercised end-to-end under `make validate-*` with a real leaderboard entry. Results are reproducible. |

**Lane guarantee**: The stable lane (`v2.4-ns3.38`) provides `cornet-validated` for all
exposed features. The latest lane (`v4.2-ns3.47`) is `cornet-integrated` for most features
until `make validate-v47` produces a real leaderboard entry.

### Declaring required capabilities (optional)

Tasks may declare which NS-3 capabilities they need:

```yaml
network:
  plugin: ns3
  simulation_script: my_experiment-default
  requires_nr_capability: custom_edf_scheduler   # or a list: [custom_edf_scheduler, pdcp_aoi_timestamps]
```

If the installed NS-3 lane does not provide the declared capability at the required
validation level, the orchestrator exits with a clear error explaining which lane to install.

### Which lane for which experiment type

| Experiment type | Recommended lane | Patches needed |
|---|---|---|
| AoI measurement, EDF/AoI scheduling | Stable (`v2.4-ns3.38`) | `ns3_lte_pdcp.patch` + `nr_schedulers.patch` |
| Pendulum control, UAV control | Stable (`v2.4-ns3.38`) | `ns3_lte_pdcp.patch` + `nr_schedulers.patch` |
| CSI-RS, beamforming, MIMO | Latest (`v4.2-ns3.47`) | `ns3_lte_pdcp.patch` only (`nr_schedulers.patch` is inert but present) |
| Sub-band CSI, Kronecker beamforming | Latest (`v4.2-ns3.47`) | No CORNET patches required |

---

## 10. Writing a custom NS-3 scratch script

If `simulation_script` points to a custom `.cc` file, it must implement the
**CORNET virtual-port contract** to work with `middleware.enabled: true`.

### The `--tun{i}` contract

When `middleware.enabled: true`, the CORNET plugin creates Linux TUN interfaces
(`cornet0`, `cornet1`, ...) and passes their names and IPs to NS-3 via CLI args:

```
--tun0=cornet0,10.0.0.1  --tun1=cornet1,10.0.0.2  ...
```

Your scratch script **must**:
1. Parse `--tun{i}=name,ip` args for `i = 0..N`.
2. Create one `TapBridgeHelper` per arg using the provided `name`.
3. The TAP bridge count must equal the `--tun{i}` arg count — **not** `numUes`.

```cpp
// CORNET virtual-port contract
const uint32_t CORNET_MAX_TUNS = 8;
std::vector<std::string> cornetTunArgs(CORNET_MAX_TUNS, "");
for (uint32_t k = 0; k < CORNET_MAX_TUNS; k++)
    cmd.AddValue("tun" + std::to_string(k), "CORNET TUN interface: name,ip", cornetTunArgs[k]);
cmd.Parse(argc, argv);

// ... (after NS-3 node/device setup) ...
TapBridgeHelper tapBridge;
tapBridge.SetAttribute("Mode", StringValue("UseLocal"));
uint32_t tapCount = 0;
for (uint32_t i = 0; i < CORNET_MAX_TUNS && tapCount < ueNodes.GetN(); i++) {
    if (cornetTunArgs[i].empty()) break;
    std::string tapName = cornetTunArgs[i].substr(0, cornetTunArgs[i].find(','));
    tapBridge.SetAttribute("DeviceName", StringValue(tapName));
    tapBridge.Install(ueNodes.Get(tapCount), ueDevices.Get(tapCount));
    tapCount++;
}
```

> **Important**: Scripts that hard-code TAP names (e.g. `"tap-robot"`) are
> **incompatible with `middleware.enabled: true`**. The CORNET plugin creates
> `cornet0`, `cornet1`, etc. — not `tap-robot`.

### Port number args

Sensor and control port numbers are forwarded from `MiddlewareConfig`:

```yaml
network:
  middleware:
    enabled: true
    ip_list: [10.0.0.1, 10.0.0.2]
    sensor_port: 5001    # forwarded as --sensorPort
    control_port: 5002   # forwarded as --controlPort
```

Declare them in your `CommandLine`:
```cpp
uint16_t sensorPort = 5001;
uint16_t controlPort = 5002;
cmd.AddValue("sensorPort", "UDP port for robot sensor data", sensorPort);
cmd.AddValue("controlPort", "UDP port for robot control commands", controlPort);
```

Use `scripts/ns3/scratch/scratch_template-default.cc` as the starting point for
any new scratch script — it implements the full contract with inline comments.
