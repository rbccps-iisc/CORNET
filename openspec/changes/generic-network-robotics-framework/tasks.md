## 0. New Repository Bootstrap

- [ ] 0.1 Create `rbccps-iisc/CORNET` on GitHub via the rbccps-iisc org (public, MIT license, no template)
- [ ] 0.2 Clone locally to `/home/acharya/simulation/CORNET_Research/` (distinct from existing CORNET 1.0 clone)
- [ ] 0.3 Create `pyproject.toml` with package name `cornet`, version `0.1.0`, dependencies `pydantic>=2.0` and `rich`; entry points `cornet = cornet.__main__:main`
- [ ] 0.4 Create top-level directory structure: `cornet/`, `tasks/`, `docs/`, `tests/`, `.github/workflows/`
- [ ] 0.5 Create `docs/LINEAGE.md` documenting CORNET 1.0 → 2.0 → 3.0 → CORNET (flagship) with citations and URLs for each generation
- [ ] 0.6 Add `docs/INSTALL.md` listing system prerequisites (NS-3 build, Mininet-WiFi, Gazebo, ROS 2 Humble) with install commands
- [ ] 0.7 Add CI workflow `.github/workflows/test.yml`: `pip install -e .[dev]` + `pytest tests/` on ubuntu-latest
- [ ] 0.8 Update `srikrishna3118/CORNET` README.md header to: "⚠️ This is CORNET 1.0 (archived). The current flagship is [rbccps-iisc/CORNET](https://github.com/rbccps-iisc/CORNET)." — submit as a PR to that repo
- [ ] 0.9 Initialize OpenSpec in the new repo: `cd /home/acharya/simulation/CORNET_Research && openspec init` (selects GitHub Copilot); copy the `openspec/changes/generic-network-robotics-framework/` artifacts from CORNET3.0 into the new repo's OpenSpec so the change history travels with the code

## 1. Framework Package Skeleton

- [ ] 1.1 Create `cornet/` package with `__init__.py` and `__main__.py` (entry point: `python -m cornet tasks/<name>`)
- [ ] 1.2 Create `cornet/plugins/base.py` — abstract `Plugin` class with lifecycle methods: `configure(config, context)`, `start()`, `run()`, `stop()`, `collect(output_dir)`
- [ ] 1.3 Create `cornet/plugins/__init__.py` — plugin registry dict mapping string names to classes; `PluginNotFoundError` exception
- [ ] 1.4 Create `cornet/context.py` — `ExperimentContext` dataclass with `network` and `robot` sub-contexts

## 2. Unified Config Schema

- [ ] 2.1 Create `cornet/config/schema.py` — Pydantic v2 `UnifiedConfig` model with `network`, `robot`, `experiment` sections; `ConfigValidationError` exception
- [ ] 2.2 Define `NetworkConfig`: `plugin` (str), `type` (Literal["ns3","mininet","ns3+mininet"]), `nodes` (list), `mininet` (optional sub-model with `wmediumd: bool`)
- [ ] 2.3 Define `RobotConfig`: `plugin` (str), `launch_file` (optional path), `world` (optional path), `robots` (list of `RobotEntry` with `name`, `model.type`, `model.path`, `pose`)
- [ ] 2.4 Define `ExperimentConfig`: `name`, `duration`, `output_dir`
- [ ] 2.5 Extend `config_manager.py`: add `load_unified(path) -> UnifiedConfig`; update `load(path)` to detect `_schema: unified-v1` and route to `load_unified()`, otherwise use legacy loader
- [ ] 2.6 Write unit tests in `tests/test_unified_config.py` covering valid load, missing field error, unknown network type error, and legacy fallback

## 3. Plugin Orchestrator

- [ ] 3.1 Create `cornet/orchestrator.py` — `Orchestrator` class; `load_plugins(config)` resolves plugin names from registry; `run(task_dir=None, config_path=None)` entry point
- [ ] 3.2 Implement lifecycle loop: `configure → start → run → stop → collect`; wrap in try/finally so `stop()` always called; call `stop()` on already-started plugins in reverse order on exception
- [ ] 3.3 Add preflight check: if any loaded plugin is `MininetPlugin` and `os.getuid() != 0`, log error and `sys.exit(1)`
- [ ] 3.4 Implement task-folder auto-discovery: if `tasks/<name>/launch.py` exists and `robot.launch_file` is null, set `config.robot.launch_file` to that path before plugins configure; same for `world.sdf`

## 4. Mininet-WiFi + Docker Plugin

- [ ] 4.1 Create `cornet/plugins/network/mininet_plugin.py` — `MininetPlugin(Plugin)`; port topology-building logic from `CORNET2.0/network/network_config.py`
- [ ] 4.2 Port `MOBILE`/`STATIC` node-type handling: MOBILE → Mininet-WiFi station; STATIC → host + access-point pair
- [ ] 4.3 Add Docker container lifecycle: `configure()` pulls images listed in `node.container.image`; `start()` runs containers; `stop()` removes containers and Mininet topology
- [ ] 4.4 Implement wmediumd toggle: if `config.network.mininet.wmediumd: true`, start wmediumd before `net.start()`
- [ ] 4.5 After topology is up, write `{node.name: node.ip}` to `context.network.node_ips`
- [ ] 4.6 Register plugin in `cornet/plugins/__init__.py` under key `"mininet"`

## 5. NS-3 Plugin Wrapper

- [ ] 5.1 Create `cornet/plugins/network/ns3_plugin.py` — `Ns3Plugin(Plugin)`; wrap existing `network/network_manager.py` and `network/cornet_middleware.py` logic
- [ ] 5.2 Move NS-3 build/setup validation (currently inline in `run_scenario.py`) into `Ns3Plugin.configure()`
- [ ] 5.3 Expose TUN/TAP bridge IP in `context.network.node_ips` keyed by UE name after middleware starts
- [ ] 5.4 Register plugin under key `"ns3"`

## 6. Gazebo + ROS 2 Plugin

- [ ] 6.1 Create `cornet/plugins/robot/gazebo_plugin.py` — `GazeboPlugin(Plugin)`; `configure()` reads `robot.robots` list and sets `self._launch_path`
- [ ] 6.2 In `configure()`: if `robot.launch_file` is set, use it; else call `generic_launch.generate()` and store the returned temp path in `self._launch_path`
- [ ] 6.3 `start()`: invoke `ros2 launch <self._launch_path>` as a subprocess; poll until Gazebo `/clock` topic is available (or timeout)
- [ ] 6.4 `stop()`: send SIGTERM to the launch subprocess; wait for clean exit (timeout 10 s, then SIGKILL); delete generated temp launch file if it was auto-generated
- [ ] 6.5 Register plugin under key `"gazebo"`

## 7. Generic Gazebo Launch Generator

- [ ] 7.1 Create `cornet/gazebo/generic_launch.py` — `generate(config: RobotConfig, task_dir: Path) -> Path` function
- [ ] 7.2 Implement using ROS 2 `launch` + `launch_ros` Python API: build `LaunchDescription` with `ExecuteProcess` for gzserver and `Node` for each robot's spawn
- [ ] 7.3 For each robot with `model.type: urdf`: add `robot_state_publisher` node loading the URDF with `xacro.process_file()` if xacro extension; plain `open()` otherwise
- [ ] 7.4 For each robot with `model.type: sdf`: add `ExecuteProcess` calling `ros2 run gazebo_ros spawn_entity.py` with the SDF path and pose args
- [ ] 7.5 Write generated file to `task_dir / f"generated_launch_{int(time.time())}.py"`; return the `Path`
- [ ] 7.6 Handle missing `robot.world`: use empty world string `""` so Gazebo starts with an empty environment

## 8. run_scenario.py Shim Update

- [ ] 8.1 Update `run_scenario.py`: add directory-argument detection — if `sys.argv[1]` is a directory, call `cornet.orchestrator.run(task_dir=sys.argv[1])`
- [ ] 8.2 Add unified-YAML detection — if `sys.argv[1]` ends in `.yaml` and file contains `_schema: unified-v1`, call `cornet.orchestrator.run(config_path=sys.argv[1])`
- [ ] 8.3 Keep existing code path for legacy `scenarios/*.yaml` unchanged below both new branches

## 9. Example Tasks

- [ ] 9.1 Create `tasks/pendulum_nr_control/config.yaml` — unified schema; `network.plugin: ns3`; `robot.plugin: gazebo`; `robot.robots` with one pendulum URDF; mirrors `scenarios/pendulum_5g_nr_urllc_control.yaml` parameters
- [ ] 9.2 Create `tasks/uav_wifi_control/config.yaml` — unified schema; `network.plugin: mininet`; Docker container node with `image: ros:humble`; `robot.plugin: gazebo`; UAV SDF model; `network.mininet.wmediumd: true`
- [ ] 9.3 Verify both example configs pass `config_manager.load_unified()` validation (add to CI smoke test)

## 10. EvalTool Interface

- [ ] 10.1 Create `cornet/eval/base.py` — abstract `EvalTool` base class with `run_evaluation(results_dir: str) -> str`; document return format (`SUCCESS, <metric>` or `FAILURE,`)
- [ ] 10.2 Update `ExperimentConfig` schema (task 2.4) to add `primary_metric: str | None` and `higher_is_better: bool = False`
- [ ] 10.3 Update `Orchestrator.collect()` to: import `eval.eval_tool.EvalTool` from the task directory if present; call `run_evaluation(output_dir)`; parse first-line metric; write entry to leaderboard
- [ ] 10.4 Create example `eval/eval_tool.py` for `tasks/pendulum_nr_control/`: reads `analysis/aoi_statistics.json`, returns `SUCCESS, <mean_aoi_ms>`
- [ ] 10.5 Create example `eval/eval_tool.py` for `tasks/uav_wifi_control/`: reads `analysis/control_statistics.json`, returns `SUCCESS, <rmse>`
- [ ] 10.6 Add `tests/test_eval_tool.py`: mock results dir with fixture JSONs; assert `run_evaluation()` returns correct `SUCCESS, <value>` string

## 11. Parameter Sweep Engine

- [ ] 11.1 Create `cornet/sweep/expander.py` — `expand_sweep(config: UnifiedConfig) -> list[UnifiedConfig]`; uses `itertools.product` over `experiment.sweep` axes; assigns `variant_id` strings
- [ ] 11.2 Update `ExperimentConfig` schema to add `sweep: dict[str, list] | None` and `sweep.parallel: bool = False` and `sweep.repeats: int = 1`
- [ ] 11.3 Update `Orchestrator.run()`: if `config.experiment.sweep` is present, call `expander.expand_sweep()` and loop over variants; pass `variant_id` and per-variant `output_dir` into each run
- [ ] 11.4 Implement ROS_DOMAIN_ID isolation for parallel sweep: assign `ROS_DOMAIN_ID = base_domain + variant_index`; validate all IDs ≤ 101; log assigned IDs at start
- [ ] 11.5 Convert the 5-phase AoI evaluation into `tasks/aoi_5phase_eval/config.yaml` using `experiment.sweep` over `network.scheduler`; verify it produces the same 5 result directories as the old `run_aoi_multiue_evaluation.py`
- [ ] 11.6 Add `tests/test_sweep_expander.py`: assert 3×2 grid produces 6 variants with correct `variant_id` strings; assert `repeats: 3` produces 18 variants; assert empty sweep returns single `default` variant

## 12. Experiment Leaderboard

- [ ] 12.1 Create `cornet/leaderboard/writer.py` — `append_entry(task_dir, entry: dict)`; reads existing JSON array, appends, writes atomically (write to `.tmp` then `os.rename`)
- [ ] 12.2 Implement corrupt-file recovery: if `leaderboard.json` parse fails, rename to `leaderboard.json.bak.<timestamp>`, log warning, start fresh
- [ ] 12.3 Create `cornet/leaderboard/viewer.py` — `show(task_dir, higher_is_better: bool)`; reads `leaderboard.json`, builds `rich.table.Table` sorted by metric; FAILURE rows at bottom; best row in bold green
- [ ] 12.4 Wire `python -m cornet view tasks/<name>` subcommand in `cornet/__main__.py` (add `view` subparser alongside the existing run subparser)
- [ ] 12.5 Update `tasks/pendulum_nr_control/` and `tasks/uav_wifi_control/` example tasks to include `experiment.primary_metric` and verify leaderboard entries are written after a dry-run
- [ ] 12.6 Add `tests/test_leaderboard.py`: assert append creates file; assert second append has 2 entries; assert corrupt file produces `.bak` and resets; assert viewer output contains correct sorted order

## 13. Documentation and Smoke Tests

- [ ] 13.1 Update `docs/GETTING_STARTED.md`: add "Task-based workflow" section explaining `tasks/` layout, sweep config, and `python -m cornet view`
- [ ] 13.2 Update `docs/ARCHITECTURE.md`: add full diagram showing Orchestrator → SweepExpander → [PluginLifecycle × N variants] → EvalTool → Leaderboard
- [ ] 13.3 Add `tests/test_plugin_lifecycle.py`: mock plugin records call order; assert `configure → start → run → stop → collect`; assert `stop()` called on exception in `start()`
- [ ] 13.4 Add `tests/test_generic_launch.py`: call `generate()` with two-robot config; assert output file exists, is valid Python, contains both robot names
- [ ] 13.5 Run existing `tests/test_aoi_tracker.py` and confirm it still passes (regression guard)
