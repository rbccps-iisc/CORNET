# Discussion: generic-network-robotics-framework
> Retroactive adversarial review (change archived 2026-06-01; discussion generated post-archive)

## Challenge Report

### Challenge 1: Silent Pydantic fallback masks mis-typed unified configs
- **Source**: Design §D4 — "load_unified() attempts Pydantic validation and falls back to the legacy loader for plain scenario YAMLs"
- **Assumption**: A YAML that fails Pydantic validation is always a legacy plain-scenario YAML, never a malformed unified config.
- **Failure mode**: A unified config with a typo (e.g., `netwrok:` instead of `network:`) fails Pydantic silently, falls back to the legacy loader, and is interpreted as a plain scenario dict. The experiment runs against wrong or partially-ignored config fields without any error surface. The researcher is left debugging behavior rather than config syntax.
- **Risk category**: correctness
- **Mitigation**: Distinguish "schema unknown" from "schema valid but wrong version." If the YAML contains any top-level key that only appears in the unified schema (`robot:`, `experiment:`, `sweep:`), treat it as an attempted unified config and surface the full Pydantic ValidationError rather than silencing it. The fallback should only activate for YAMLs with none of those keys.

### Challenge 2: Parallel sweep — Gazebo port collision not resolved by ROS_DOMAIN_ID
- **Source**: Design §D7 — "Parallel execution is opt-in via `experiment.sweep.parallel: true` and uses `ROS_DOMAIN_ID` isolation (auto-assigned integer per variant) to prevent ROS node collisions"
- **Assumption**: ROS_DOMAIN_ID isolation is sufficient to prevent inter-variant interference when running multiple Gazebo instances in parallel on a single host.
- **Failure mode**: Gazebo Classic uses a fixed port (`11345` for the master, `11346` for simulation) that is completely independent of ROS_DOMAIN_ID. Two parallel Gazebo instances will fight for port 11345. The second instance will fail to start (or silently shadow the first). The robot plugin receives no error; it connects to the wrong Gazebo instance and spawns robots into the wrong world.
- **Risk category**: integration
- **Mitigation**: For parallel sweeps with Gazebo, auto-assign `GAZEBO_MASTER_URI` (e.g., `http://localhost:1134{variant_index+5}`) per variant, analogous to ROS_DOMAIN_ID assignment. Add a preflight check that detects parallel Gazebo conflicts and aborts with a clear message if port allocation fails. Document that NS-3-only sweeps (no robot plugin) are safe to parallelize without this mitigation.

### Challenge 3: EvalTool return string format is under-specified
- **Source**: Design §D6 — "The return string follows the NVlabs convention: first line `SUCCESS, <metric>` or `FAILURE, <optional_metric>`"
- **Assumption**: `<metric>` is a single parseable scalar (float or int) and tasks will not need to return multiple metrics.
- **Failure mode**: If a task returns `"SUCCESS, 14.3 ms"` (with units), `"SUCCESS, 14.3, 22.1"` (two values), or `"SUCCESS, throughput=14.3"` (key=value), the orchestrator's string split on `", "` produces a non-numeric metric value that cannot be sorted in the leaderboard. The leaderboard silently stores the raw string, and the `higher_is_better` sort breaks or raises a TypeError on the first comparison.
- **Risk category**: correctness
- **Mitigation**: Specify the metric format precisely in the `EvalTool` base class docstring and raise a `ValueError` at record time if `metric` cannot be cast to `float`. Provide a `EvalTool.format_result(value: float, status="SUCCESS") -> str` helper that enforces the format. For multi-metric tasks, document that only the declared `primary_metric` is parsed; secondary metrics belong in a separate JSON artifact.

### Challenge 4: Generated launch files accumulate without gitignore protection
- **Source**: Design §D3 — "write to `tasks/<name>/generated_launch_<timestamp>.py`; clean up on stop"
- **Assumption**: The `stop()` lifecycle method is reliably called, so generated launch files are always cleaned up.
- **Failure mode**: If the orchestrator receives SIGKILL, the Python process exits mid-run without calling `stop()`. Generated `generated_launch_<timestamp>.py` files accumulate in `tasks/<name>/`. Without a `.gitignore` entry for `tasks/**/generated_launch_*.py`, these files get staged and committed, polluting the task directory and potentially leaking machine-specific paths in the generated launch content.
- **Risk category**: integration
- **Mitigation**: Add `tasks/**/generated_launch_*.py` to the repo's `.gitignore` at creation time. As a secondary guard, add a `cleanup_stale_generated_files(task_dir)` call at orchestrator startup (before plugin init) that removes any `generated_launch_*.py` older than 1 hour.

### Challenge 5: Per-variant NS-3 cold-start dominates sequential sweep wall-clock time
- **Source**: Design §D7 — "produces one `UnifiedConfig` per combination… feeds them to the main run loop sequentially"
- **Assumption**: Sequential variant execution has acceptable wall-clock time for typical sweep sizes (≤20 variants).
- **Failure mode**: NS-3 5G NR simulation startup (CMake configuration loading, channel model init, RAN layer setup) takes 30–90 seconds per run on typical hardware. A 20-variant sweep (4 numerologies × 5 bandwidths) accumulates 10–30 minutes of pure initialization overhead before any RAN traffic flows. The researcher may not realize this until the first sweep run and attribute the slowness to simulation time rather than cold-start overhead.
- **Risk category**: performance
- **Mitigation**: Document expected cold-start overhead in `docs/GETTING_STARTED.md` alongside the sweep example. Consider a future `experiment.sweep.warm_start: true` option that reuses the NS-3 process across variants by passing parameter overrides via the ns3 `--ns3::ConfigStore` mechanism rather than restarting the binary. For the current design, add a progress bar via `rich.progress` to make cold-start wait time visible.

## Counter-Designs

### Option 1: Event-bus architecture with loose plugin coupling
Rather than a fixed 6-phase lifecycle (`configure → start → run → stop → collect`), plugins subscribe to experiment lifecycle events (`EXPERIMENT_CONFIGURE`, `EXPERIMENT_START`, `EXPERIMENT_RUN`, `EXPERIMENT_STOP`, `EXPERIMENT_COLLECT`) via an async event bus. Each plugin independently handles the events it cares about. The orchestrator becomes a thin event emitter.

**Pros**: Plugins are fully decoupled — a new plugin type (e.g., a monitoring plugin) can subscribe to any event without touching the orchestrator. Async event handling makes parallel initialization natural.
**Cons**: Debugging becomes harder — execution order is implicit rather than explicit. Error recovery (the current design's "stop in reverse order" guarantee) requires careful event priority logic. Substantially more complex to implement correctly.
**Trade-offs**: High flexibility ceiling, high implementation risk for a research framework where debuggability matters more than extensibility.

### Option 2: Config-as-code Python API, no YAML schema
Replace the YAML + Pydantic approach with a Python fluent API for building experiment configs:
```python
from cornet import Experiment, NS3Plugin, GazeboPlugin
exp = Experiment("pendulum_nr_control")
exp.network = NS3Plugin(numerology=2, bandwidth=20)
exp.robot = GazeboPlugin(world="pendulum.sdf")
exp.run()
```
No YAML parser, no fallback loader, no schema validation — Python's own type system enforces correctness at definition time.

**Pros**: Eliminates the silent-fallback challenge entirely. Full Python tooling (IDE autocomplete, `mypy`, refactoring). Tasks become Python scripts, not YAML + script pairs.
**Cons**: YAML configs are language-agnostic and human-readable without Python knowledge. Existing NS-3 `config.yaml` files from CORNET3.0 would need rewriting. Loses the "declarative experiment" aesthetic that aligns with NVlabs convention.
**Trade-offs**: Better developer ergonomics, worse migration path and community familiarity.

### Option 3: Current design — YAML + lifecycle plugin + Pydantic validation (proposed approach)
Retain the YAML-first, lifecycle-managed design as proposed. Apply mitigations from the Challenge Report (D4 fallback disambiguation, EvalTool format helper, generated-file gitignore, Gazebo port assignment for parallel mode).

**Pros**: Declarative configs are portable and language-agnostic. Lifecycle gives explicit execution order and reliable reverse-stop semantics. Pydantic gives free JSON Schema and error messages. Closest to CORNET3.0's `config.yaml` convention — lowest migration barrier.
**Cons**: YAML fallback ambiguity (Challenge 1) requires care to fix. Parallel mode Gazebo conflicts need port-assignment work (Challenge 2).
**Trade-offs**: Best balance of familiarity, debuggability, and research usability for the target audience.

**Recommendation**: Endorse **Option 3** (current design) with the five mitigations from the Challenge Report applied. The lifecycle plugin model and YAML config are the right choices for a research framework; the identified risks are all fixable at the implementation level without architectural change.

## Decisions Made

- **D1**: Retain the YAML-first lifecycle plugin architecture. — *The target audience (robotics researchers) expects declarative YAML configs; config-as-code adds a Python learning curve that reduces accessibility.*
- **D2**: Fix the Pydantic fallback to distinguish "attempted unified config with errors" from "genuine legacy YAML" by checking for unified-schema sentinel keys (`robot:`, `experiment:`, `sweep:`). — *Silent fallback is the highest-impact correctness risk; a key-presence check is a one-line fix.*
- **D3**: Assign per-variant `GAZEBO_MASTER_URI` (port offset by variant index) in addition to `ROS_DOMAIN_ID` when parallel sweep mode is active. — *Gazebo port 11345 is not ROS-domain-aware; without this, parallel Gazebo spawns silently conflict.*
- **D4**: Enforce float-castable metric in `EvalTool.collect()` and provide a `format_result()` helper in the base class. — *Prevents leaderboard sort failures from unit-suffixed or multi-value metric strings.*
- **D5**: Add `tasks/**/generated_launch_*.py` to `.gitignore` at repo creation and add a stale-file cleanup call at orchestrator startup. — *SIGKILL cannot be caught; gitignore is the only reliable protection against launch file accumulation.*
