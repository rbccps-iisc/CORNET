## Context

The CORNET lineage spans three published research artifacts: CORNET 1.0 (`srikrishna3118/CORNET`, COMSNETS 2020), CORNET 2.0 (`rbccps-iisc/CORNET2.0`, arXiv:2109.06979, COMSNETS 2022), and CORNET 3.0 (`rbccps-iisc/CORNET3.0`, current PhD thesis with 8GB of results data). Each is a citable artifact and must not be modified.

The new flagship is `rbccps-iisc/CORNET` — a clean, pip-installable repository that synthesizes the best of all three generations. Its Python package is named `cornet`. It carries no NS-3 source tree, no accumulated results data, and no legacy experiment scripts. It is a *framework*, not a research notebook.

The target architecture is inspired by NVlabs/the-ai-telco-engineer: a **task-folder convention** where each experiment lives in `tasks/<name>/config.yaml`, a **single orchestrator entry-point** (`python -m cornet tasks/<name>`) resolves and drives plugins, and a **plugin registry** decouples network backends (NS-3, Mininet-WiFi) and robot backends (Gazebo) from the core lifecycle.

Stakeholders: researchers running network-robotics experiments who currently maintain three separate codebases and write bespoke shell scripts per experiment.

## Goals / Non-Goals

**Goals:**
- Create `rbccps-iisc/CORNET` as a clean, standalone repository; Python package `cornet`; pip-installable
- Synthesize CORNET 1.0/2.0/3.0 plugin code into the new framework without modifying any original repo
- Provide a unified YAML config schema covering both `network` and `robot` sections; validate it at load time
- Auto-generate a generic ROS 2 + Gazebo launch file when the user's config does not supply one
- Expose a plugin lifecycle (`configure → start → run → stop → collect`) that any network or robot backend implements
- Introduce `tasks/<name>/config.yaml` convention so experiments are fully self-contained and portable
- Standardized `EvalTool` + per-task primary metric + append-only leaderboard
- Parameter sweep engine replacing all bespoke batch runner scripts

**Non-Goals:**
- Modifying `rbccps-iisc/CORNET2.0`, `rbccps-iisc/CORNET3.0`, or `srikrishna3118/CORNET` in any way
- Backward compatibility shim for `run_scenario.py` (CORNET3.0 keeps working as-is; the new framework is additive)
- AI/LLM agent orchestration

## Decisions

### D1: Plugin architecture over monolithic runner

**Decision**: Introduce `framework/plugins/` with an abstract `Plugin` base class defining the lifecycle interface. Network and robot backends each implement this interface. The orchestrator loads plugins by name from config.

**Rationale**: The current `run_scenario.py` is ~400 lines with NS-3-specific logic hardcoded. Adding Mininet-Docker support inline would make it unmaintainable. A plugin model lets each backend evolve independently and lets researchers add new simulators without touching the core.

**Alternatives considered**:
- *Subclassing run_scenario.py*: simpler short-term, but creates a deep inheritance tree that makes cross-cutting concerns (logging, error recovery) hard to manage.
- *Subprocess-per-backend*: isolates crashes but makes shared state (e.g. network bridge IPs that the robot plugin needs) complex to pass around.

### D2: Port CORNET2.0 Mininet code, do not symlink

**Decision**: Copy the relevant modules from `/home/acharya/simulation/CORNET2.0/network/` into `framework/plugins/network/` and refactor them to implement the Plugin interface. The original CORNET2.0 repo is left untouched.

**Rationale**: Symlinks break when the repo is cloned to another machine. A hard copy gives CORNET3.0 full ownership of the code and avoids cross-repo dependency management.

**Alternatives considered**:
- *Git submodule*: adds CI complexity and forces users to init submodules.
- *pip-installable package from CORNET2.0*: CORNET2.0 is not packaged; would require significant upstream work.

### D3: Auto-generate Gazebo launch via Python, not a static template

**Decision**: `framework/gazebo/generic_launch.py` uses `launch` and `launch_ros` Python APIs (ROS 2 launch framework) to generate a `LaunchDescription` programmatically. It emits a temporary `.launch.py` file written to `tasks/<name>/generated_launch.py` and invokes it via `ros2 launch`.

**Rationale**: A static Jinja/XML template cannot express conditional logic (e.g. "if URDF is provided, use robot_state_publisher; otherwise use a bare SDF spawn"). The Python launch API supports this natively. The generated file is written to disk for auditability.

**Alternatives considered**:
- *Xacro + XML*: standard for ROS 1; in ROS 2 the Python API is canonical and more flexible.
- *Always require user to supply a launch file*: removes a major usability barrier; rejected.

### D4: Unified schema as a Pydantic model

**Decision**: `framework/config/schema.py` defines the config as a Pydantic v2 model. `config_manager.py` gains a `load_unified()` function that attempts Pydantic validation and falls back to the legacy loader for plain scenario YAMLs.

**Rationale**: Pydantic gives free JSON Schema generation, IDE autocomplete, and clear error messages. The fallback ensures backward compatibility without a flag.

**Alternatives considered**:
- *jsonschema + plain dicts*: less ergonomic, no IDE support.
- *dataclasses*: no built-in YAML/JSON parsing or nested validation.

### D5: Task folder mirrors the-ai-telco-engineer convention, adapted for robotics

**Decision**: `tasks/<name>/` contains `config.yaml` (required), optional `world.sdf`, optional `launch.xml` or `launch.py`, optional `eval/` for post-run analysis scripts. The orchestrator discovers tasks by scanning `tasks/`.

**Rationale**: Researchers familiar with the-ai-telco-engineer immediately understand the layout. Keeping the analogy close lowers the learning curve for the AI-networking community.

## Risks / Trade-offs

- **[Risk] ROS 2 version drift** — `generic_launch.py` uses the `launch_ros` API which differs between Humble, Iron, and Jazzy. → *Mitigation*: pin to Humble (current CORNET3.0 target); add a `ros_distro` config field that adjusts import paths.
- **[Risk] Mininet-WiFi root requirement** — all Mininet operations require `sudo`. The orchestrator must detect if it lacks root and warn clearly rather than silently failing inside a plugin. → *Mitigation*: preflight check in `orchestrator.py` before plugin init.
- **[Risk] Generated launch file path collisions** — two concurrent runs could overwrite `generated_launch.py`. → *Mitigation*: write to `tasks/<name>/generated_launch_<timestamp>.py`; clean up on stop.
- **[Risk] Config schema backward compatibility** — existing scenario YAMLs use flat `network:` keys without `type:`. → *Mitigation*: the fallback loader in `config_manager.py` handles legacy format; no migration required.

### D9: New standalone repository, not an extension of CORNET3.0

**Decision**: The generic framework lives in a brand-new `rbccps-iisc/CORNET` repository. Python package name is `cornet`. The existing CORNET2.0 and CORNET3.0 repos are left completely untouched. Plugin code is ported (copy + adapt) into the new repo. The new repo has no NS-3 source tree (`git clone` takes seconds, not minutes), no accumulated results data, and no legacy experiment scripts.

**Rationale**: CORNET3.0 carries 8GB of PhD thesis data that must stay permanently at `rbccps-iisc/CORNET3.0`. CORNET2.0 is cited in ≥2 published papers at its current URL. A new repo gives the flagship a clean git narrative, a fast clone, and the institutional identity (`rbccps-iisc`) consistent with 2.0 and 3.0. It also allows pip-installability — impossible if NS-3's 6GB source tree is in the same repo.

**Alternatives considered**:
- *Extend CORNET3.0 in-place*: Would contaminate thesis results archive; 16GB clone for new users.
- *Revamp `srikrishna3118/CORNET` (1.0)*: Breaks CORNET 1.0 citation URL; mixes personal and institutional identity.
- *Monorepo with all three*: Adds 16GB+ to clone; complicates versioning and citation provenance.

### D6: Standardized eval_tool interface per task (mirrors NVlabs)

**Decision**: Each task supplies `eval/eval_tool.py` defining a `EvalTool` class with `run_evaluation(results_dir: str) -> str`. The return string follows the NVlabs convention: first line `SUCCESS, <metric>` or `FAILURE, <optional_metric>`. The orchestrator's `collect()` phase calls `eval_tool.run_evaluation(output_dir)`, parses the metric, and appends an entry to `tasks/<name>/leaderboard.json`. If no `eval/eval_tool.py` exists, `collect()` skips metric recording without error.

**Rationale**: Makes every run's output comparable with a single scalar. Existing `analysis/` scripts continue to work — `EvalTool` simply calls them internally and reads the JSON they produce (e.g. reads `aoi_statistics.json` and extracts `mean_aoi_ms`). No duplication of analysis logic.

**Alternatives considered**:
- *Declare metric path in config (e.g. `primary_metric: aoi_statistics.json#mean_aoi_ms`)*: simpler but fragile (path-based JSON pointer); doesn't handle FAILURE cases or non-JSON outputs.

### D7: Parameter sweep as config-level axis expansion

**Decision**: If `experiment.sweep` is present, the orchestrator calls `framework/sweep/expander.py` which uses `itertools.product` to enumerate all combinations, produces one `UnifiedConfig` per combination with a `variant_id` (e.g. `numerology=2_bandwidth=40`), and feeds them to the main run loop sequentially. Each variant's results go to `output_dir/<variant_id>/`. Parallel execution is opt-in via `experiment.sweep.parallel: true` and uses `ROS_DOMAIN_ID` isolation (auto-assigned integer per variant) to prevent ROS node collisions.

**Rationale**: Eliminates all bespoke `run_aoi_multiue_evaluation.py`-style batch scripts. The existing 5-phase AoI evaluation becomes a 5-entry sweep. Sequen­tial is the safe default because NS-3 + Mininet both use host networking; parallel requires root + careful port isolation.

**Alternatives considered**:
- *Shell-loop wrapper calling `python -m framework` N times*: works, but doesn't integrate with the leaderboard automatically.
- *GNU Parallel / Ray*: overkill for the typical ≤20 variant sweeps in this research context.

### D8: Leaderboard as append-only JSON + `rich` terminal table

**Decision**: `tasks/<name>/leaderboard.json` is an append-only list of dicts: `{timestamp, variant_id, metric, status, output_dir}`. The `python -m framework view tasks/<name>` subcommand reads it and renders a `rich.table.Table` sorted by metric (respecting `higher_is_better`). The JSON file is human-readable and git-trackable, providing a durable record across sessions.

**Rationale**: The existing `compare_aoi_phases.py`, `compare_baseline_experiments.py` etc. solve the same problem ad hoc. A single structured file + one viewer replaces 6+ compare scripts. `rich` is a single lightweight dependency; no web server required unlike NVlabs' `view_leaderboard.py`.

**Alternatives considered**:
- *SQLite database*: better for large runs but adds tooling overhead; JSON is sufficient for typical study sizes (< 1000 rows).
- *NVlabs-style web server*: unnecessary — researchers here work in terminal-heavy SSH environments.

## Open Questions

- Should `tasks/` live at the repo root (mirrors the-ai-telco-engineer) or under a subdirectory like `experiments/tasks/`? (Current plan: repo root, but open to team preference.)
- Which Gazebo version is the target? Gazebo Classic (11) vs. Ignition/Harmonic affects the `spawn_entity` service name and SDF conventions.
- Should the plugin lifecycle expose an async API to allow NS-3 simulation and Gazebo to run concurrently in event loops, or is subprocess-based parallelism sufficient?
- For sweep parallel mode: should each variant get its own Mininet network namespace, or is port-offset isolation sufficient?
