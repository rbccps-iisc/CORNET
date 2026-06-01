# Discussion: cornet-docs-and-install

## Challenge Report

### Challenge 1: Sentinel file idempotency is brittle
- **Source**: Design §D6 — Idempotency strategy per component, NS-3 row
- **Assumption**: The sentinel file `$NS3_DIR/.cornet-patched` accurately reflects that NS-3 was fully built AND all three patches were applied successfully
- **Failure mode**: If the install script crashes mid-run (e.g., during the 20–30 minute build, power loss, disk full), the sentinel is either absent (safe) or already written (dangerous). If written before all steps finish — or if someone manually deletes `build/` while the sentinel survives — re-running the install script silently skips the rebuild and the researcher has a broken installation with no indication of the problem.
- **Risk category**: `correctness`
- **Mitigation**: Write the sentinel file as the **last step**, after `verify.sh` confirms the NS-3 build and all three patches are in effect. Split into two sentinels: `$NS3_DIR/.cornet-built` (written after build) and `$NS3_DIR/contrib/nr/.cornet-patched-v2.4` (written after patch application). The idempotency gate requires BOTH to be present. This way a partial failure leaves one missing, which correctly triggers re-run.

### Challenge 2: `nr_aoi_mac_scheduler.patch` was never wired into CORNET3.0's apply script
- **Source**: Proposal §What Changes, ns3-patch-bundle bullet — "three patches copied from CORNET3.0"
- **Assumption**: All three patches form a coherent, sequentially-applicable set that was validated together on a clean NR v2.4 checkout
- **Failure mode**: `nr_aoi_mac_scheduler.patch` exists in CORNET3.0's `network/` directory but is **not referenced** in `apply_urllc_enhanced_patches.sh`. It may be an experimental patch never integrated into the standard flow. Critically, both `nr_edf_scheduler.patch` and `nr_aoi_mac_scheduler.patch` touch `CMakeLists.txt` with separate hunks. Applying EDF first modifies line numbers in CMakeLists, making the AoI patch's context stanza stale — the second patch may fail cleanly on a tree where the first has already been applied.
- **Risk category**: `correctness`
- **Mitigation**: Before committing the patches to this repo (task 1.3), perform a dry-run on a clean NR v2.4 checkout: apply all three patches in order with `git apply --verbose` and confirm zero failures. If CMakeLists conflict exists, produce a single combined `nr_schedulers.patch` that applies EDF and AoI additions together. Document the validated application order in `scripts/patches/ns3/README.md`.

### Challenge 3: The v4.2 placeholder causes `compat-check` to vacuously pass or error uninformatively
- **Source**: Design §D3, ns3-compat-check spec §Requirement: Five-category compatibility check
- **Assumption**: Running `make compat-check` against `--patch-set v4.2-ns3.47` usefully tracks migration readiness
- **Failure mode**: The `v4.2-ns3.47/` directory contains only `MIGRATION_STATUS.md` — no patch files. The compat script's check 2 (patch dry-run) will either: (a) find no `*.patch` files and skip with a vacuous PASS, giving a false sense of readiness, or (b) error out on "no patches found" without a clear migration message. Neither outcome serves as the "migration readiness indicator" described in the design.
- **Risk category**: `integration`
- **Mitigation**: The compat script SHALL treat a missing patch file in a known version directory as `FAIL("not-yet-migrated: <patch-name>")`, explicitly distinct from `FAIL("hunk-mismatch")`. The script reads `MIGRATION_STATUS.md` to enumerate the expected patch names for that version and reports which are pending. This makes `make compat-check` a true migration progress tracker, not a binary pass/fail.

### Challenge 4: Downgrading INSTALL.md from NR v2.6 to NR v2.4 breaks users mid-setup
- **Source**: Proposal §Modified: docs/INSTALL.md — "updates NS-3 version target (NS-3 3.38 + NR v2.4, proven)"
- **Assumption**: Updating INSTALL.md to target NR v2.4 is an additive documentation change with no user-facing breakage
- **Failure mode**: Researchers who followed the old INSTALL.md already have NS-3 built with NR v2.6 on disk. The new `install_ns3.sh` targets NR v2.4. If they re-run the install script on their existing tree, the v2.4 patches will fail to apply to a v2.6 NR checkout, and the idempotency gate (checking for the sentinel) will be absent — the script will attempt a fresh install into the existing directory and conflict. The downgrade is a **breaking change** for anyone mid-setup on the old docs.
- **Risk category**: `ux`
- **Mitigation**: `install_ns3.sh` MUST detect the NR version in an existing `$NS3_DIR/contrib/nr` before proceeding. If a v2.6 (or any non-v2.4) installation is detected, the script SHALL emit a warning with the detected version, print the correct manual upgrade/downgrade path, and exit 1 without making changes. Add a note in INSTALL.md acknowledging the version change from the previous documentation.

### Challenge 5: Five guides in one change risks shallow, silently incomplete content
- **Source**: Proposal §New: docs/guides/ — five task-author and developer guides
- **Assumption**: Five complete, useful guides can be produced within the scope of a change that also includes install scripts, compat check script, schema annotations, generator pipeline, reference docs, and a CI target
- **Failure mode**: With 9 task groups (38+ subtasks) in `tasks.md`, guides are written last and under scope pressure. A `writing-a-task.md` that omits the EvalTool contract, or a `middleware.md` that describes fields without explaining their interaction, gives researchers false confidence. They begin building on incomplete documentation, hit undocumented edge cases, and lose trust in the docs entirely — which is worse than no guide.
- **Risk category**: `ux`
- **Mitigation**: Define a minimum-viable content checklist per guide in the spec. Each guide MUST cover the exact scenarios listed in its spec (which already exist). Guides MAY include "TODO: expand" callouts for secondary topics, but the primary workflow MUST be covered end-to-end. The `writing-a-task.md` guide is P0 (blocks all other users) and SHALL be completed before the others.

---

## Counter-Designs

### Counter-Design A: Minimal Scripts + Comprehensive Troubleshooting

**Key architectural difference**: Drop `check_ns3_compat.py` and the versioned patch directory structure. Ship only the v2.4 patches, a single `install.sh` (no modular breakdown), and put the saved engineering effort into a thorough `docs/troubleshooting.md` covering the 10 most common NS-3 install failures.

**Pros**:
- ~40% less code to write and maintain
- Troubleshooting docs have longer shelf life than install scripts (NS-3 install steps evolve less than they appear to)
- No sentinel file brittleness problem; no compat check ambiguity problem

**Cons**:
- Install is still manual for each backend — the core adoption blocker remains
- No automation means no CI validation of the install path
- Compat check value compounds over time as NS-3 versions advance; dropping it forfeits that

**Trade-off**: Prioritises documentation depth over install automation. Suitable if the audience is primarily experienced researchers who have already installed NS-3 before.

---

### Counter-Design B: Docker Image for NS-3 Backend

**Key architectural difference**: Instead of install scripts for NS-3 + NR, publish a `Dockerfile` in `scripts/docker/ns3/` that produces a pre-built NS-3 3.38 + NR v2.4 + CORNET patches image. Researchers run `docker run --rm --network host cornet-ns3 <scenario-args>` instead of a local build.

**Pros**:
- Eliminates the 20-minute NS-3 build entirely for end users
- Reproducible environment; no build-env variance
- Removes the sentinel file brittleness problem entirely
- Compat check becomes optional (image is pinned to a validated version)

**Cons**:
- `--network host` needed for TAP/TUN interfaces; restricts to Linux hosts
- Requires Docker daemon; adds a new infrastructure dependency
- Researchers who want to modify NS-3/NR source must re-build the image or abandon Docker
- Image size ~4–6 GB; not suitable for resource-constrained researcher machines

**Trade-off**: Best for reproducible benchmarking; worst for researchers who want to extend NS-3.

---

### Counter-Design C: Python Install Orchestrator (pip install cornet-install)

**Key architectural difference**: Replace the shell scripts with a Python CLI tool (`cornet-install`) published as a separate pip package. Researchers run `pip install cornet-install && cornet-install ns3 --version proven`.

**Pros**:
- Python is more portable than bash for complex conditional logic
- The install tool itself is testable with pytest
- `cornet-install check` maps directly to `check_ns3_compat.py` — unification

**Cons**:
- Two packages to maintain (`cornet-framework` + `cornet-install`)
- `pip install` cannot install system packages (apt/brew) — still need sudo helpers
- Overkill complexity for a research framework with a small contributor base

**Trade-off**: Over-engineers the install story. The main benefit (testability) can be achieved by making `check_ns3_compat.py` a standalone script with its own unit tests.

---

**Recommendation**: Endorse the original proposal with mitigations from all five challenges applied. The modular shell script + compat check approach is the right fit for a research framework. Counter-Design B (Docker) is worth noting in `docs/INSTALL.md` as an alternative for reproducibility use cases, but should not replace the local install path.

---

## Decisions Made

**D1** (from Challenge 1): Split the NS-3 idempotency sentinel into two files — `$NS3_DIR/.cornet-built` written after successful NS-3 build, and `$NS3_DIR/contrib/nr/.cornet-patched-v2.4` written after successful patch application. Both must be present for the idempotency gate to trigger. Sentinels are written LAST in each phase.
*Rationale*: A single sentinel written before all steps complete hides partial failures and makes re-runs unsafe.

**D2** (from Challenge 2): Task 1.3 (commit `nr_aoi_mac_scheduler.patch`) MUST be preceded by a dry-run on a clean NR v2.4 checkout applying all three patches in order. If the two NR patches have CMakeLists conflicts, they SHALL be merged into a single `nr_schedulers.patch` before committing. The validated application order SHALL be documented in `README.md`.
*Rationale*: `nr_aoi_mac_scheduler.patch` was never wired into CORNET3.0's apply script; its compatibility with `nr_edf_scheduler.patch` has not been verified.

**D3** (from Challenge 3): The compat check script SHALL read `MIGRATION_STATUS.md` to enumerate expected patch names per version directory. A patch that is expected but absent SHALL produce `FAIL("not-yet-migrated: <patch-name>")`. This makes `make compat-check` a migration progress tracker, not a trivially-passing no-op.
*Rationale*: A placeholder directory with no patch files must produce a meaningful signal, not a vacuous pass.

**D4** (from Challenge 4): `install_ns3.sh` SHALL detect the NR version of any existing `$NS3_DIR/contrib/nr` installation and exit 1 with an explanatory message if it does not match the target version. `docs/INSTALL.md` SHALL include a note acknowledging the version change from the prior documentation (NR v2.6 → NR v2.4) and explaining why.
*Rationale*: Researchers mid-setup on the old docs must not have their existing installation silently broken by the new install scripts.

**D5** (from Challenge 5): `docs/guides/writing-a-task.md` is P0 and SHALL be completed before the other four guides. Each guide SHALL cover at minimum the scenarios listed in its corresponding spec. Explicit `<!-- TODO: expand -->` callouts are permitted for secondary topics. Incomplete guides with no `TODO` markers are a review failure.
*Rationale*: A shallow guide without explicit scope markers gives researchers false confidence; incomplete coverage MUST be visible.

**D6** (from Counter-Design B endorsement): Add a brief "Docker alternative" callout to `docs/INSTALL.md` noting that a Dockerfile for NS-3 is a viable reproducibility approach for CI/benchmarking use cases, with a pointer to `scripts/docker/` as the future home if that path is ever pursued.
*Rationale*: The Docker approach was dismissed as out-of-scope for this change but is genuinely useful for some users; acknowledging it prevents confusion.
