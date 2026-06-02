# Discussion: cornet-ns3-self-contained

## Challenge Report

### Challenge 1: `CORNET_NS3_TAG` mutation must precede `ExperimentContext` creation
- **Source**: Design §D3, Task 3.1 ("`append @{tag} to config.experiment.name before writing the leaderboard entry`")
- **Assumption**: Appending the tag "before writing the leaderboard entry" is equivalent to appending it anywhere early in `_run_variant()`.
- **Failure mode**: In `cornet/orchestrator.py`, `_run_variant()` opens with `context = ExperimentContext(variant_id=config.experiment.name)`. If the tag is injected after this line (e.g., just before the `append_entry` call), the `ExperimentContext` object carries the un-tagged variant_id. Any code that reads `context.variant_id` — including plugin logging, AoI tracker correlation, and the success-path leaderboard write — will use the wrong identifier. Only the error-path leaderboard write at the bottom of `_run_variant()` would see the tagged name. The result: success entries are filed as `pendulum_nr_control`, error entries as `pendulum_nr_control@ns3-v24`. The two variants are indistinguishable in success runs.
- **Risk category**: correctness
- **Mitigation**: The mutation `config.experiment.name += f"@{tag}"` must be the first statement in `_run_variant()`, before `ExperimentContext` is constructed. Task 3.1 must be amended to read "inject at the top of `_run_variant()`, before the ExperimentContext line."

---

### Challenge 2: `make validate` skip condition uses directory existence, not install sentinel
- **Source**: Task 3.3 ("checks `~/ns-3-dev-v47` exists before running v4.2 (skip with warning if absent)"), Spec §dual-run-validation §make-validate-target (partial install)
- **Assumption**: If `~/ns-3-dev-v47/` exists as a directory, the v4.2 install is functional.
- **Failure mode**: The directory can exist in at least three non-functional states: (1) NS-3 was cloned but the build failed, (2) the NR patch was never applied (`.cornet-patched-v4.2` absent), (3) a previous run left a stale checkout. The Makefile would proceed to `make validate-v47`, which would fail mid-run with a cryptic NS-3 build error rather than the expected "v4.2 not installed, skipping" warning. Additionally, the check `test -d ~/ns-3-dev-v47` is hardcoded. A user who set `NS3_DIR=~/ns3-custom` when installing v4.2 will always see the skip warning even with a valid install.
- **Risk category**: integration
- **Mitigation**: The skip guard should test for the sentinel file `~/ns-3-dev-v47/.cornet-built` (both sentinels required: `.cornet-built` AND `~/ns-3-dev-v47/contrib/nr/.cornet-patched-v4.2`). This matches the idempotency gate already used in `install_ns3.sh` (D1 in the existing compat-check design). Optionally expose `NS3_DIR_V47` as an overridable Makefile variable to avoid the hardcoded path.

---

### Challenge 3: Bundled scratch script diverges silently from CORNET3.0
- **Source**: Spec §ns3-scratch-bundle §versioned-scratch-layout, Design §D1
- **Assumption**: Copying `remote_robot_control.cc` once at change-authoring time is sufficient; the file is stable.
- **Failure mode**: CORNET3.0 is a separate repository. Bug fixes, parameter changes, or ROS interface updates made there will not propagate to `scripts/ns3/scratch/v2.4-ns3.38/remote_robot_control-default.cc`. The drift is invisible — both repos build cleanly, but the bundled script silently runs old logic. This is particularly dangerous for performance-sensitive research results: a bug fix in CORNET3.0 would show as a result discrepancy between runs, with no obvious cause.
- **Risk category**: correctness
- **Mitigation**: Add an origin comment block at the top of the bundled `.cc` file identifying the source repo, path, and git commit hash at copy time (e.g., `// Origin: CORNET3.0@<commit> network/ns-3/scratch/remote_robot_control.cc`). This makes drift detectable via `git log` on CORNET3.0. A lightweight `make check-scratch-sync` target (diffs the bundled copy against CORNET3.0 if `CORNET3_DIR` is set) is optional but recommended.

---

### Challenge 4: Substring filter creates false positives and a blank option for legacy entries
- **Source**: Design §D4, Spec §dual-run-validation §ui-variant-filter
- **Assumption**: Filtering `variant_id` by substring `ns3-v24` reliably distinguishes all past and future entries, and the UI `<select>` can be populated cleanly from unique tags in the data.
- **Failure mode**: Two problems. First, substring match: `?variant=ns3-v24` would also match a future entry named `pendulum_ns3-v247_test` or a task named `ns3-v24-extended`. This is low-probability today but grows as the task library expands. Second, and more immediately: the leaderboard already contains 12 synthetic entries with `variant_id: "pendulum_nr_control"` (no `@` separator). Task 4.3 says to populate `<select>` options from "unique tags found in entries." If the tag-extraction logic splits on `@` and takes the suffix, plain-name entries produce an empty string `""` as a tag. The select would render a blank option between "All versions" and "ns3-v24", confusing users.
- **Risk category**: ux
- **Mitigation**: (a) Filter endpoint should use equality on the extracted tag suffix, not substring on the full `variant_id`: split `variant_id` on `@`, return the entry only if `parts[-1] == requested_variant`. `?variant=all` bypasses the check. (b) `<select>` option population should skip entries where `"@"` is absent from `variant_id` — they appear only under "All" and do not generate a separate option.

---

### Challenge 5: `ns3_tag` as a redundant top-level leaderboard field creates two sources of truth
- **Source**: Task 3.2 ("expose `ns3_tag` as a top-level field in the leaderboard entry JSON alongside `variant_id`")
- **Assumption**: A separate `ns3_tag` field is useful because consumers should not parse `variant_id` strings.
- **Failure mode**: `variant_id` already encodes the tag as `"pendulum_nr_control@ns3-v24"`. Adding a separate `ns3_tag: "ns3-v24"` field means: (a) two sources of truth that can be written inconsistently if the injection site for the tag and the field are different; (b) the 12 existing synthetic leaderboard entries lack `ns3_tag`, so any reader that requires the field will break on old entries; (c) the `append_entry` writer in `cornet/leaderboard/writer.py` is intentionally schema-less (takes a raw `dict`) — there is no enforcement that `ns3_tag` and `variant_id` stay in sync. The leaderboard spec written during `cornet-docs-and-install` does not mention `ns3_tag`, so adding it creates an undocumented field.
- **Risk category**: correctness
- **Mitigation**: Drop Task 3.2 entirely. The tag is already in `variant_id`. Code that needs the tag parses it with `variant_id.split("@", 1)[-1] if "@" in variant_id else None`. This is a one-liner and needs no new field, no schema update, and no migration of existing entries.

---

## Counter-Designs

### Option 1: Tag Injection at Leaderboard Write Site (Writer-side kwarg)

Instead of mutating `config.experiment.name` in the orchestrator, pass the tag as an extra kwarg to `append_entry()`:

```python
ns3_tag = os.environ.get("CORNET_NS3_TAG")
# ... run experiment ...
append_entry(task_dir=..., entry={
    "variant_id": config.experiment.name + (f"@{ns3_tag}" if ns3_tag else ""),
    ...
})
```

This avoids touching `config.experiment.name` at all. The config object remains unchanged throughout the run.

**Pros**: Config is immutable during the run; no risk of ordering bugs (Challenge 1); no interaction with `ExperimentContext`; easy to test in isolation.

**Cons**: Requires finding every `append_entry` call site and passing the tag — there are two in `_run_variant()` (success path via `_eval_and_record` and error path). The success-path write is inside `_eval_and_record()` which would also need the tag propagated. Slightly more invasive call-chain change.

**Trade-offs**: Cleaner semantics at the cost of two extra call-site changes vs. one mutation.

---

### Option 2: `PATCH_SET` as a Positional Argument Instead of Env Var

Instead of `PATCH_SET=v2.4-ns3.38 bash install_ns3.sh`, use:
```bash
bash install_ns3.sh v2.4-ns3.38
```

**Pros**: Self-documenting in `--help`; discoverable without reading the script; cannot be inherited unexpectedly from a parent shell.

**Cons**: Changes the existing shell interface (breaking if any CI already sets `PATCH_SET`); Makefile composition with `export PATCH_SET=...` is idiomatic for multi-step recipes; env var approach is how existing `NS3_DIR` is already passed.

**Trade-offs**: Marginally more discoverable, but breaks existing interface convention with no practical benefit for this project.

---

**Recommendation**: Endorse the original proposal with one amendment: retain the `config.experiment.name` mutation approach from the proposal (Option 1's writer-site approach adds unnecessary call-chain complexity), but apply Challenge 1's fix — mutation must occur as the **first statement** in `_run_variant()`, before `ExperimentContext` is constructed. The env-var interface (Option 2's concern) should remain as-is.

---

## Decisions Made

- **D1**: Mutation of `config.experiment.name` via `CORNET_NS3_TAG` must happen as the first line in `_run_variant()`, before `ExperimentContext(variant_id=config.experiment.name)`. Task 3.1 is amended accordingly. — *Rationale: Without this ordering, success-path leaderboard entries and ExperimentContext both carry the un-tagged name, making the two NS-3 versions indistinguishable in the leaderboard.*

- **D2**: The `make validate` skip guard for v4.2 must test for the `.cornet-built` sentinel file at `$(NS3_DIR_V47)/.cornet-built` (not just directory existence). `NS3_DIR_V47` defaults to `~/ns-3-dev-v47` but is overridable. — *Rationale: A directory can exist without a successful install; sentinel-based checks are already the established pattern in `install_ns3.sh`.*

- **D3**: Task 3.2 is dropped. No separate `ns3_tag` top-level field is added to leaderboard entries. The tag is already encoded in `variant_id` and can be extracted with a one-liner at read time. — *Rationale: Two sources of truth for the same data create silent inconsistency; existing entries lack the field and would break any field-required reader.*

- **D4**: The `/api/leaderboard?variant=` filter uses **exact tag equality** on the suffix after `@`-split, not substring match on the full `variant_id`. Entries without `@` (legacy synthetic entries) are excluded from `<select>` option population and appear only under "All". — *Rationale: Substring match produces false positives as the task library grows; blank select options from tagless entries would confuse users.*

- **D5**: The bundled `v2.4-ns3.38/remote_robot_control-default.cc` file must include an origin comment block at the top of the file recording the CORNET3.0 source path and git commit hash at copy time. — *Rationale: Makes drift from upstream detectable; zero runtime cost.*

- **D6**: The `PATCH_SET` env-var interface is endorsed as-is. The positional argument alternative (Counter-Design 2) offers no practical advantage and would break the established `NS3_DIR=...` env-var convention already used throughout the Makefile. — *Rationale: Consistency with existing interface patterns outweighs marginal discoverability gain.*
