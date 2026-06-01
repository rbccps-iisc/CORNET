## Why

The CORNET lineage now spans three generations across two GitHub organizations:
- `srikrishna3118/CORNET` (1.0) — NS-3 + Ardupilot SITL, COMSNETS 2020
- `rbccps-iisc/CORNET2.0` — Mininet-WiFi + Containernet + ROS, arXiv:2109.06979, COMSNETS 2022 (cited in ≥2 papers)
- `rbccps-iisc/CORNET3.0` — NS-3 5G NR + AoI + pendulum control (PhD thesis, 8GB results)

Each generation was a self-contained research artifact but they are architecturally disconnected silos. There is no unified entry point, no shared config schema, no interoperable plugin layer. Researchers who want Mininet-WiFi AND NS-3 5G NR in the same experiment must manually wire two codebases.

The solution is a new flagship repository — `rbccps-iisc/CORNET` — that synthesizes all three generations into a single, task-driven, plugin-based co-simulation framework for networked robots, analogous to NVlabs/the-ai-telco-engineer for wireless algorithms. CORNET2.0 and CORNET3.0 remain permanently archived at their existing URLs (preserving citations and PhD thesis provenance); their plugin code is ported — not migrated — into the new flagship.

## What Changes

**New repository: `rbccps-iisc/CORNET`** (clean, pip-installable, no NS-3 source tree)

- **New repo file**: `pyproject.toml` — `pip install cornet-framework`; declares dependencies (`pydantic`, `rich`); NS-3, Mininet-WiFi, Gazebo/ROS 2 are system-level prerequisites documented in `docs/INSTALL.md`
- **New**: `cornet/` package (top-level Python package name) — plugin registry, lifecycle manager, component loader
- **New**: `cornet/orchestrator.py` — single entry-point `python -m cornet tasks/<name>`; reads task YAML, resolves plugins, runs lifecycle
- **New**: `cornet/plugins/network/mininet_plugin.py` — Mininet-WiFi + Docker container instantiation; code ported from `rbccps-iisc/CORNET2.0/network/`
- **New**: `cornet/plugins/network/ns3_plugin.py` — NS-3 5G NR integration; code ported from `rbccps-iisc/CORNET3.0/network/`
- **New**: `cornet/plugins/robot/gazebo_plugin.py` — launches Gazebo world, spawns robots; auto-generates ROS 2 launch if none provided
- **New**: `cornet/plugins/robot/ros2_bridge_plugin.py` — ROS 2 ↔ UDP bridges; ported from `rbccps-iisc/CORNET3.0/robot/`
- **New**: `cornet/config/schema.py` — Pydantic v2 `UnifiedConfig`; `network`, `robot`, `experiment` sections
- **New**: `cornet/gazebo/generic_launch.py` — ROS 2 Python launch file generator
- **New**: `cornet/eval/base.py` — `EvalTool` base class; per-task `eval/eval_tool.py`
- **New**: `cornet/sweep/expander.py` — cartesian product sweep over config axes
- **New**: `cornet/leaderboard/` — append-only `leaderboard.json` + `rich` terminal viewer
- **New**: `tasks/` — two example tasks: `pendulum_nr_control/` (NS-3 5G NR) and `uav_wifi_control/` (Mininet-WiFi + Docker)
- **New**: `docs/LINEAGE.md` — documents CORNET 1.0 → 2.0 → 3.0 → CORNET (flagship) history with citations
- **Unchanged**: `rbccps-iisc/CORNET2.0` — archived at existing URL; citations intact
- **Unchanged**: `rbccps-iisc/CORNET3.0` — archived at existing URL; PhD thesis results intact; `run_scenario.py` continues to work as-is

## Capabilities

### New Capabilities

- `mininet-docker-integration`: Mininet-WiFi topology instantiation with Docker container nodes, ported from CORNET2.0; configurable via YAML
- `unified-config-schema`: Single YAML config covering network deployment (NS-3, Mininet, or both) and robot deployment (Gazebo + ROS 2), with schema validation
- `gazebo-ros-auto-launch`: Auto-generation of a generic ROS 2 Gazebo launch file when the user does not provide one; spawns robots at YAML-specified poses using `robot_state_publisher` + `spawn_entity`
- `plugin-orchestrator`: Lifecycle-managed plugin system (init → configure → start → run → stop → collect) that composes network and robot plugins from config
- `task-folder-convention`: `tasks/<name>/config.yaml` layout (inspired by NVlabs/the-ai-telco-engineer) enabling self-contained, portable experiments
- `eval-tool-interface`: Standardized `EvalTool` base class and per-task `eval/eval_tool.py`; `collect()` calls `run_evaluation(results_dir)` and records `SUCCESS, <metric>` into the leaderboard; primary metric declared in config (`experiment.primary_metric`, `experiment.higher_is_better`)
- `parameter-sweep`: `experiment.sweep` block in config declares axes and values; orchestrator expands into N variant configs, runs each, and feeds all results to the leaderboard; replaces all bespoke `run_aoi_multiue_evaluation.py`-style batch runners
- `experiment-leaderboard`: Per-task `leaderboard.json` accumulating every run's metric; `python -m framework view tasks/<name>` renders a sorted terminal table; supersedes the ad-hoc `compare_aoi_phases.py`, `compare_baseline_experiments.py` family

### Modified Capabilities

- `scenario-runner`: `run_scenario.py` shim updated to delegate to new orchestrator while preserving CLI interface

## Impact

- **New repository**: `rbccps-iisc/CORNET` — clean slate, ~20 Python modules, no NS-3 source tree, no results data; `git clone` is fast
- **No files modified**: `rbccps-iisc/CORNET2.0` and `rbccps-iisc/CORNET3.0` are untouched; their plugin code is *ported* (copied and adapted), not moved
- **New dependencies**: `pydantic>=2.0`, `rich`; NS-3, Mininet-WiFi, Gazebo/ROS 2 are system prerequisites
- **Citation safety**: All existing paper citations to `rbccps-iisc/CORNET2.0` and `srikrishna3118/CORNET` remain valid forever
- **Thesis safety**: 8GB of results and full git history of `rbccps-iisc/CORNET3.0` are untouched
- **Forward path**: `srikrishna3118/CORNET` (CORNET 1.0) gets a README update pointing to the new flagship at `rbccps-iisc/CORNET`
