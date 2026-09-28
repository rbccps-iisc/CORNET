# CORNET

CORNET runs a network simulator and a robot simulator from one task config.

```bash
python -m cornet tasks/pendulum_nr_control
python -m cornet view tasks/pendulum_nr_control
```

| | |
|---|---|
| [Getting started](GETTING_STARTED.md) | Install the package, run a task, read the leaderboard |
| [Installation](INSTALL.md) | NS-3 lanes, Gazebo, ROS 2, Mininet, PX4 |
| [Architecture](ARCHITECTURE.md) | Orchestrator, plugins, and the OpenSpec workflow |
| [Research session](guides/research-session.md) | Question through report, including the 28 September 2026 pendulum check |
| [CLI](reference/cli.md) | `run`, `view`, `ui`, `bench`, `research` |
| [Config schema](reference/config-schema.md) | Fields of `_schema: unified-v1` |
| [Leaderboard format](reference/leaderboard-format.md) | Entry fields, including provenance |
