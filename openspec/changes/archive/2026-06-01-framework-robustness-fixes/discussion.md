# Discussion: framework-robustness-fixes

## Challenge Report

### Challenge 1: GAZEBO_MASTER_URI save/restore is split across two separately-checkable tasks
- **Source**: tasks.md §2, tasks 2.1 and 2.2; cornet/orchestrator.py `run()` (actual code)
- **Assumption**: Task 2.1 (set `GAZEBO_MASTER_URI` in `_apply_ros_domain()`) and task 2.2 (add save/restore in `run()`) will be implemented together and consistently. The `run()` method currently has a single `previous_ros_domain` save/restore in a `try/finally` block around the variant loop.
- **Failure mode**: If task 2.2 is not implemented or is implemented in a separate subtask, `GAZEBO_MASTER_URI` will be written to `os.environ` and never restored. The parent process (and any subsequent test runs in the same process) will inherit the last variant's Gazebo URI. In CI where multiple test invocations share a process, this leaks a stale port into unrelated tests.
- **Risk category**: `correctness`
- **Mitigation**: Merge tasks 2.1 and 2.2 into a single implementation unit. Specifically, save `previous_gazebo_uri = os.environ.get("GAZEBO_MASTER_URI")` immediately before the variant loop (alongside the existing `previous_ros_domain` line) and restore it in the same `finally` block. Both saves and both restores should be in the same contiguous code block to make the pair visually obvious.

---

### Challenge 2: `format_result()` allows `float("nan")` and `float("inf")` to enter the leaderboard silently
- **Source**: specs/eval-tool-interface/spec.md §ADDED "format_result rejects non-float value"; Design §D3
- **Assumption**: The only invalid inputs to `format_result()` are non-numeric types (e.g. strings). The spec scenario "format_result rejects non-float value" shows `TypeError` for `"14.3 ms"` (a string), not for IEEE 754 special values.
- **Failure mode**: `format_result(float("nan"))` returns `"SUCCESS, nan"`. `float("nan")` parses successfully at collect time, so no `ValueError` is raised. A `nan` metric enters the leaderboard. The viewer sorts against it; Python's float comparison with `nan` is always `False`, breaking sort stability for the entire leaderboard.
- **Risk category**: `correctness`
- **Mitigation**: In `format_result()`, after casting to float, call `math.isfinite(value)` and raise `ValueError("EvalTool.format_result() value must be a finite float; got {value!r}")` if it returns False. Also add an analogous check in `_eval_and_record()` after `metric = float(metric_str)`.

---

### Challenge 3: `resolved_task_dir is not None` guard in task 4.2 is dead code
- **Source**: tasks.md §4, task 4.2; cornet/orchestrator.py `_resolve_config()` (actual code)
- **Assumption**: `resolved_task_dir` can be `None` when `Orchestrator.run()` proceeds past `_resolve_config()`.
- **Failure mode**: Inspection of `_resolve_config()` shows it either returns `(cfg, td)`, `(cfg, p.parent)`, or calls `sys.exit(1)` — it never returns `None` for `resolved_task_dir` when execution continues. The guard `if resolved_task_dir is not None:` is always `True`. Dead code is harmless but misleads future readers into thinking `None` is a valid state, possibly causing them to skip the cleanup call in refactors where they see the guard and assume it's optional.
- **Risk category**: `correctness` (minor)
- **Mitigation**: Remove the guard; call `_cleanup_stale_launch_files(resolved_task_dir)` unconditionally after `_resolve_config()`. If the code ever gains a genuine `None`-return path in the future, the guard should be re-added then with a comment explaining the invariant.

---

### Challenge 4: `ValueError` from `_eval_and_record()` aborts all remaining sweep variants
- **Source**: tasks.md §3, task 3.2; Design §D3; cornet/orchestrator.py `run()` variant loop (actual code)
- **Assumption**: A raised `ValueError` from a malformed metric string should be visible to the researcher immediately and can abort the run.
- **Failure mode**: `_eval_and_record()` is called from `_run_variant()` which is called inside `run()`'s `for variant_index, variant_cfg in enumerate(variants):` loop. The loop has no per-variant exception handling (only the outer `finally` for env-var restoration). A `ValueError` from variant 1 of a 5-variant parallel sweep will abort variants 2–5 entirely, losing hours of experiment data silently. The researcher sees a traceback from the *evaluation phase* but no output from incomplete variants.
- **Risk category**: `integration`
- **Mitigation**: Catch `ValueError` from `_eval_and_record()` in `_run_variant()` (or in the variant loop in `run()`). Log it at `ERROR` level and write a `FAILURE` leaderboard entry with `metric: null` and an `error` field containing the malformed string. This preserves the signal (the bad return value) without silently continuing (which the current `metric = None` does), and without aborting the entire sweep.

---

### Challenge 5: Sentinel-key hint misleads when `_schema` has a version mismatch rather than a missing tag
- **Source**: Design §D1; tasks.md §1.1
- **Assumption**: Any YAML that contains `robot:`, `experiment:`, or `sweep:` keys AND has a wrong or absent `_schema` tag is a case of a missing tag (researcher forgot to add it), not a case of version incompatibility.
- **Failure mode**: A user who upgrades task configs to a hypothetical `_schema: unified-v2` and runs them against this v1 framework will receive the message `"Did you forget to add '_schema: unified-v1' at the top?"`. The user has explicitly set a schema tag; the hint actively misleads them. The correct message in that case is a version mismatch error, not a missing-tag hint.
- **Risk category**: `ux`
- **Mitigation**: Narrow the hint: only append `"Did you forget to add '_schema: unified-v1' at the top?"` when `schema_tag == ""` (tag is absent entirely), not when `schema_tag` is a non-empty wrong value. For non-empty wrong values, surface the mismatch: `f"Unsupported schema version '{schema_tag}'. This framework requires '_schema: unified-v1'."`.

---

## Counter-Designs

### Option 1: Centralised env-var lifecycle manager (context manager)
Replace the ad-hoc `previous_ros_domain` / `previous_gazebo_uri` save-restore pattern with a reusable `_IsolatedEnv` context manager that accepts a `dict[str, str]` of env overrides, applies them on `__enter__`, and restores the previous state on `__exit__`.

```python
class _IsolatedEnv:
    def __init__(self, overrides: dict[str, str]) -> None:
        self._overrides = overrides
        self._saved: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for k, v in self._overrides.items():
            self._saved[k] = os.environ.get(k)
            os.environ[k] = v

    def __exit__(self, *_) -> None:
        for k, prev in self._saved.items():
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev
```

`_apply_ros_domain()` becomes a pure function that returns `dict[str, str]` instead of mutating env directly. The variant loop wraps each iteration in `with _IsolatedEnv(env_for_variant):`.

**Pros**: Eliminates the Challenge 1 split-task coordination risk entirely; future env vars (e.g., `GAZEBO_MODEL_DATABASE_URI`) need only be added to `_apply_ros_domain()`'s return dict with no changes to `run()`; restores are always paired with sets.
**Cons**: Larger surface area than required for just two env vars; changes the signature of `_apply_ros_domain()`, affecting any tests that mock it; more abstraction than the change's "localized fixes" charter.
**Trade-offs**: Correctness-by-construction vs scope discipline. The proposal explicitly scopes to ≤3 functions per fix.

---

### Option 2: Subprocess-per-variant isolation (no in-process env mutation)
Run each sweep variant as a child process with its own env dict:

```python
subprocess.run(
    [sys.executable, "-m", "cornet", "--config", serialized_variant_cfg_path],
    env={**os.environ, "ROS_DOMAIN_ID": str(domain_id), "GAZEBO_MASTER_URI": gazebo_uri},
    check=True,
)
```

**Pros**: True process-level isolation; env never leaks between variants or into test state; solves Challenge 1, 3, and 4 simultaneously; correct by construction.
**Cons**: Requires serializing `UnifiedConfig` to disk (or passing via tempfile); fundamentally changes the variant execution model; plugins would be re-initialized from scratch per process; error recovery requires inter-process communication; far larger scope than the four targeted bug fixes.
**Trade-offs**: Architectural correctness vs scope explosion. Suitable as a future refactor target, not for this change.

---

**Recommendation**: Endorse the original proposal with the modification from Challenge 4's mitigation — catch `ValueError` from `_eval_and_record()` per-variant and record a `FAILURE` entry rather than propagating to abort the sweep. This is the only challenge that changes observable behaviour for multi-variant sweeps; the others are hardening improvements that can be addressed in-line during apply.

---

## Decisions Made

- **D1**: Keep task 2.1 and 2.2 as a single implementation unit. Save `previous_gazebo_uri = os.environ.get("GAZEBO_MASTER_URI")` immediately adjacent to `previous_ros_domain` in `run()`, and restore both in the same `finally` block. — *Prevents env-var leakage from split-task implementation order.*

- **D2**: In `format_result()`, after casting value to float, call `math.isfinite()` and raise `ValueError` if the value is `nan` or `inf`. Mirror this check in `_eval_and_record()` after the initial `float()` cast. — *Prevents IEEE 754 special values from entering the leaderboard and breaking sort.*

- **D3**: Remove the `if resolved_task_dir is not None:` guard from task 4.2. Call `_cleanup_stale_launch_files(resolved_task_dir)` unconditionally. — *Dead code removal; `_resolve_config()` always returns a non-None path when execution continues.*

- **D4**: In `_run_variant()` (or the variant loop in `run()`), catch `ValueError` from `_eval_and_record()`, log at ERROR level, and write a `FAILURE` leaderboard entry with `metric: null` and an `error` key containing the malformed string. Do not re-raise. — *Prevents a single bad EvalTool return value from aborting remaining sweep variants.*

- **D5**: Narrow the sentinel-key hint to fire only when `schema_tag == ""` (tag absent). When `schema_tag` is a non-empty wrong value, emit a version-mismatch message instead: `f"Unsupported schema version '{schema_tag}'. This framework requires '_schema: unified-v1'."` — *Avoids actively misleading users who have a valid-but-different version tag.*
