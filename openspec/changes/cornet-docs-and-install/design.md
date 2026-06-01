## Context

CORNET's install process requires 10–15 manual steps per backend, referencing an external repo (CORNET3.0) for NS-3 patches that must be copied by hand. The config schema has zero `Field(description=...)` annotations, making any auto-generated reference unusable without annotation work. Documentation currently consists of three terse files (ARCHITECTURE, INSTALL, GETTING_STARTED) with no task-author guides, no config field reference, and no troubleshooting material.

Three external repositories are relevant:
- `rbccps-iisc/CORNET3.0`: source of the three NS-3 patches (NR v2.4 + NS-3 3.38)
- `nsnam/ns-3-dev`: NS-3 core (tags ns-3.38 through ns-3.47)
- `cttc-lena/nr`: 5G-LENA NR module (tags v2.4 through v4.2, compatibility matrix verified)

## Goals / Non-Goals

**Goals:**
- Single-command install for each backend (idempotent, safe to re-run)
- Read-only compat check script that validates CORNET patches against any NS-3 + NR version
- NS-3 patches committed to this repo (atomicity; no external dependency at install time)
- Config schema fully annotated; generator script produces always-accurate Markdown reference
- Five user guides covering the full task-author and plugin-developer workflow
- CI diff-check to enforce docs freshness (`make docs-check`)

**Non-Goals:**
- Migrating patches to NR v4.2 / NS-3 3.47 (tracked as a separate task; install defaults to v2.4 proven set)
- Sphinx/MkDocs/API-reference site (Markdown-in-repo is sufficient)
- Docker/devcontainer support
- macOS support for Mininet (Linux-only)
- Changes to orchestrator, plugin lifecycle, middleware, or tests

## Decisions

### D1 — Proven NS-3 + NR versions as default install target

**Decision**: Install scripts target NS-3 3.38 + NR v2.4 (the proven combination from CORNET3.0). Scripts for latest (NS-3 3.47 + NR v4.2) require migrated patches before they can succeed.

**Rationale**: The three CORNET patches were developed and validated against NR v2.4. The diff between v2.4 and v4.2 includes 1016+ lines of churn in `nr-mac-scheduler-ns3.cc` and a 713-line CMakeLists.txt restructure — context mismatches are certain. Shipping broken install scripts is worse than shipping proven ones with a clear migration path.

**Alternative considered**: Target NR v2.6 as stated in the old INSTALL.md. Rejected: v2.6 is not the version patches were developed against, and v2.6 is not the latest either; skipping directly to v4.2 (latest) is cleaner.

### D2 — Version-stratified patch directories

**Decision**: `scripts/patches/ns3/v2.4-ns3.38/` holds the three working patches; `scripts/patches/ns3/v4.2-ns3.47/` is a placeholder directory with `MIGRATION_STATUS.md` tracking rebase progress.

**Rationale**: A single directory of "current patches" offers no indication of what version they target. Versioned directories make the compatibility model explicit and allow the compat check script to select the right set automatically.

### D3 — `check_ns3_compat.py` as a read-only pre-flight gate

**Decision**: The script has five check categories (version matrix, patch dry-run, anchor symbols, collision detection, scenario API drift) and outputs a structured report with exit code 0/1. `install_ns3.sh` calls it before any `git apply`.

**Rationale**: NS-3 build takes 20–30 minutes. A failed patch that is discovered only at compile time (after a full build) wastes significant researcher time. The compat check catches mismatches in seconds.

**Alternative considered**: Skip the compat script; just run `git apply --check` inside the install script. Rejected: `git apply --check` only detects hunk failures; it cannot detect anchor symbol drift, symbol collisions, or Python API renames in CORNET scenarios.

The compat script also reads `MIGRATION_STATUS.md` to enumerate expected patch names per version directory. A patch that is expected but absent produces `FAIL("not-yet-migrated: <patch-name>")`, making `make compat-check` a migration progress tracker rather than a vacuously-passing no-op against an empty placeholder directory.

### D4 — Auto-gen via `Field(description=...)` annotations, not docstrings or external files

**Decision**: Descriptions are added as `Field(description=...)` inline in `schema.py`. The generator calls `UnifiedConfig.model_json_schema()` and renders per-model tables to `docs/reference/config-schema.md`.

**Rationale**: Pydantic v2 `model_json_schema()` natively surfaces `description` from `Field()`; the output is always in sync with the model. Docstrings require separate parsing; external YAML/TOML description files create a maintenance split between schema definition and its documentation.

**Alternative considered**: Hand-written config reference (no generator). Rejected: will drift from schema as fields are added/changed; defeats the purpose.

### D5 — CI docs freshness via diff-check, not pre-commit hook

**Decision**: `make docs-check` runs `gen_schema_docs.py` then `git diff --exit-code docs/reference/config-schema.md`. CI fails if the generated file is stale.

**Rationale**: Pre-commit hooks are skipped with `--no-verify` and require every contributor to install them. A CI diff-check is unconditional and catches the same staleness.

### D6 — Idempotency strategy per component

Each install script has a fast "already done" gate at the top:

| Component | Idempotency gate |
|-----------|-----------------|
| Python package | `pip show cornet-framework` succeeds |
| NS-3 build | sentinel `$NS3_DIR/.cornet-built` exists (written **last**, after build succeeds) |
| NR patches | sentinel `$NS3_DIR/contrib/nr/.cornet-patched-v2.4` exists (written **last**, after all 3 patches applied) |
| Both required | **Both** sentinels must be present; a partial failure leaves one missing and correctly triggers re-run |
| Mininet | `python3 -c "import mininet"` succeeds |
| Docker | `docker info` succeeds |
| ROS 2 + Gazebo | `ros2 --version` succeeds |

The sentinel file approach for NS-3 avoids the 20-minute rebuild on re-run. `git apply --check` is the fallback verification when the sentinel is absent.

## Risks / Trade-offs

- **[Patch anchor drift]** → The `check_ns3_compat.py` anchor check mitigates this; CI can be configured to run the check against a nightly NS-3 build to detect drift early.

- **[NS-3 build environment variance]** → `verify.sh` catches the most common issues (missing `libboost`, `libxml2`, `cmake`) before the long build starts; the install script checks deps first.

- **[Schema annotation quality]** → Descriptions are only as good as what's written. Mitigation: treat schema annotation as a first-class review item; poor descriptions fail review the same way poor code does.

- **[v4.2 migration never happens]** → The compat check script returns a non-zero exit code for the v4.2 patch set until migration is complete, making the gap visible in CI. The migration task is in `tasks.md` and will block a future "latest NS-3 support" milestone.

- **[docs/INSTALL.md now says NR v2.6 (stale)]** → `docs/INSTALL.md` is being updated in this change to reflect NS-3 3.38 + NR v2.4 as the default, with NR v4.2 as the tracked future target. `install_ns3.sh` detects any existing NR version at `$NS3_DIR/contrib/nr` and exits 1 with an explanatory message if it does not match v2.4, preventing silent breakage for users mid-setup on the old docs.

## Open Questions

- **Q1**: Should `install_ns3.sh` clone NS-3 + NR into `$HOME/ns-3-dev/contrib/nr` (user-global) or into `network/ns-3/` inside the repo (project-local, like CORNET3.0)? Project-local avoids clobbering a researcher's existing NS-3 install but adds 8+ GB to the repo working tree.
  - *Default choice*: user-global (`$HOME/ns-3-dev/`) with `NS3_DIR` override; consistent with what INSTALL.md currently documents.

- **Q2**: Should `gen_schema_docs.py` be a standalone script or a `Makefile` phony implemented inline? Standalone script is more testable and importable from CI.
  - *Default choice*: standalone Python script.
