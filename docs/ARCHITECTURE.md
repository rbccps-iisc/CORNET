# Architecture

## High-level flow

```text
                 python -m cornet tasks/<name>
                               |
                               v
                        +---------------+
                        | Orchestrator   |
                        +---------------+
                               |
                    +----------+-----------+
                    |                      |
                    v                      v
             +-------------+        +-------------+
             | SweepExpander|       | Task Loader |
             +-------------+        +-------------+
                    |                      |
                    +----------+-----------+
                               |
                               v
                   [PluginLifecycle x N variants]
                               |
      +------------------------+------------------------+
      |                         |                        |
      v                         v                        v
+--------------+        +---------------+        +---------------+
| NetworkPlugin|        | RobotPlugin   |        | EvalTool      |
| ns3/mininet  |        | gazebo        |        | per-task      |
+--------------+        +---------------+        +---------------+
      |                         |                        |
      +-----------+-------------+                        |
                  |                                      |
                  v                                      v
            +------------------+                 +---------------+
            | ExperimentContext|                 | leaderboard   |
            | node IPs, etc.   |                 | append-only   |
            +------------------+                 +---------------+
```

## Key pieces

- `cornet/orchestrator.py`: task resolution, lifecycle, sweep dispatch, EvalTool hook
- `cornet/plugins/`: network and robot backends
- `cornet/config/`: Pydantic schema + loader for `unified-v1`
- `cornet/sweep/`: cartesian product expansion of parameter sweeps
- `cornet/leaderboard/`: atomic writer + `rich` terminal viewer
- `tasks/<name>/`: portable experiment definitions

## Plugin lifecycle

1. `configure(config, context)`
2. `start()`
3. `run()`
4. `stop()`
5. `collect(output_dir)`

The orchestrator always calls `stop()` in reverse order for already-started plugins if any later phase raises.
