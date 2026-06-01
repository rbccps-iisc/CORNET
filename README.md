# CORNET — Generic Co-Simulation Framework for Networked Robots

[![CI](https://github.com/rbccps-iisc/CORNET/actions/workflows/test.yml/badge.svg)](https://github.com/rbccps-iisc/CORNET/actions)

**CORNET** is a task-driven, plugin-based co-simulation framework that lets you run network-robotics experiments with a single config file and one command:

```bash
python -m cornet tasks/pendulum_nr_control
```

## Features

- **Unified config schema** — one YAML covers network (NS-3 5G NR or Mininet-WiFi) + robot (Gazebo + ROS 2)
- **Plugin architecture** — swap network or robot backends without touching orchestration code
- **Task-folder convention** — each experiment is fully self-contained under `tasks/<name>/`
- **Parameter sweep** — declare axes in config; framework runs all combinations automatically
- **EvalTool interface** — standardized metric extraction per task
- **Experiment leaderboard** — append-only JSON + `rich` terminal viewer across runs

## Quickstart

```bash
pip install cornet-framework
# System prerequisites: NS-3 (with 5G NR), Mininet-WiFi, Gazebo Classic 11, ROS 2 Humble
python -m cornet tasks/pendulum_nr_control
python -m cornet view tasks/pendulum_nr_control
```

See [docs/INSTALL.md](docs/INSTALL.md) for system prerequisites and [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for a walkthrough.

## Development

CORNET changes are tracked with OpenSpec (`/opsx:propose → /opsx:discuss → /opsx:apply → /opsx:archive`). The optional discuss phase (`/opsx:discuss`) runs adversarial critique and generates a `discussion.md` with binding implementation constraints before apply. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#openspec-workflow).

## CORNET Family

| Version | Repo | Publication |
|---------|------|-------------|
| 1.0 | [srikrishna3118/CORNET](https://github.com/srikrishna3118/CORNET) | COMSNETS 2020 |
| 2.0 | [rbccps-iisc/CORNET2.0](https://github.com/rbccps-iisc/CORNET2.0) | arXiv:2109.06979, COMSNETS 2022 |
| 3.0 | [rbccps-iisc/CORNET3.0](https://github.com/rbccps-iisc/CORNET3.0) | PhD thesis (IISc, 2025) |
| Flagship | **this repo** | — |

See [docs/LINEAGE.md](docs/LINEAGE.md) for the full family history and BibTeX citations.

## License

MIT — see [LICENSE](LICENSE).
