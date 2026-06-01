# Writing a Custom Plugin

CORNET uses a plugin system for network and robot backends. If the built-in
`ns3`, `mininet`, and `gazebo` plugins don't cover your use case, you can
write a custom plugin.

---

## 1. Plugin interface

All plugins implement `cornet.plugins.base.Plugin`:

```python
class Plugin(abc.ABC):
    def configure(self, config: UnifiedConfig, context: ExperimentContext) -> None: ...
    def start(self) -> None: ...
    def run(self) -> None: ...          # optional — default is a no-op
    def stop(self) -> None: ...
    def collect(self, output_dir: Path) -> None: ...  # optional
```

**Lifecycle order** (called by the Orchestrator):

| Step | Method | Purpose |
|---|---|---|
| 1 | `configure(config, context)` | Read config; prepare state. Must NOT start processes. |
| 2 | `start()` | Launch subprocesses, create topology, etc. |
| 3 | `run()` | Block for experiment duration (optional; Orchestrator handles timing). |
| 4 | `stop()` | Tear down all processes. Called even on error — must be idempotent. |
| 5 | `collect(output_dir)` | Copy metrics/logs to `output_dir`. |

---

## 2. ExperimentContext fields

The `context` object is shared across all plugins in a single run:

```python
@dataclass
class ExperimentContext:
    network: NetworkContext       # context.network.node_ips: dict[str, str]
    robot: RobotContext           # context.robot.robot_namespaces: dict[str, str]
    variant_id: str               # "default" or "param=val+param=val" for sweeps
```

Network plugins populate `context.network.node_ips` during `start()`.
Robot plugins read those IPs to configure ROS 2 namespaces or launch files.

---

## 3. Minimal custom network plugin skeleton

```python
# cornet/plugins/network/my_plugin.py
from __future__ import annotations

from pathlib import Path
from cornet.config.schema import UnifiedConfig
from cornet.context import ExperimentContext
from cornet.plugins.base import Plugin


class MyNetworkPlugin(Plugin):
    def configure(self, config: UnifiedConfig, context: ExperimentContext) -> None:
        self._nodes = config.network.nodes
        self._duration = config.experiment.duration
        self._context = context
        self._proc = None

    def start(self) -> None:
        # Start your network simulator
        import subprocess
        self._proc = subprocess.Popen(["my-simulator", "--nodes", str(len(self._nodes))])
        # Populate node IPs so robot plugin can use them
        for i, node in enumerate(self._nodes):
            self._context.network.node_ips[node.name] = f"10.0.{i}.1"

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=10)
            self._proc = None

    def collect(self, output_dir: Path) -> None:
        # Copy your simulator's output to output_dir
        import shutil
        sim_output = Path("/tmp/my-simulator-output")
        if sim_output.exists():
            shutil.copytree(sim_output, output_dir / "network", dirs_exist_ok=True)
```

---

## 4. Register the plugin

Add an entry to the plugin registry in `cornet/plugins/__init__.py` (or wherever your project resolves plugin names):

```python
NETWORK_PLUGINS = {
    "ns3": "cornet.plugins.network.ns3_plugin.NS3Plugin",
    "mininet": "cornet.plugins.network.mininet_plugin.MininetPlugin",
    "my-network": "cornet.plugins.network.my_plugin.MyNetworkPlugin",  # add this
}
```

Then use `plugin: my-network` in `config.yaml`:

```yaml
network:
  plugin: my-network
  type: ns3   # keep a valid type for schema validation; your plugin ignores it
```

---

## 5. Testing your plugin

Write unit tests that call the lifecycle methods directly:

```python
def test_my_plugin_lifecycle(tmp_path):
    from cornet.config.schema import UnifiedConfig
    from cornet.context import ExperimentContext
    from cornet.plugins.network.my_plugin import MyNetworkPlugin

    config = UnifiedConfig.model_validate({...})
    context = ExperimentContext()
    plugin = MyNetworkPlugin()

    plugin.configure(config, context)
    plugin.start()
    plugin.stop()
    plugin.collect(tmp_path)
    assert (tmp_path / "network").exists()
```

<!-- TODO: expand — document how to write robot plugins, bridge plugins, and how to use context.variant_id for sweep-aware output paths. -->
