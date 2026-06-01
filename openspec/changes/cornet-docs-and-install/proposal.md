## Why

CORNET has no automated installation path and no comprehensive user-facing documentation. Researchers wanting to use the framework must execute 10–15 manual steps per simulator backend, and new task authors have no guide covering the config schema, middleware, or how to write a custom EvalTool. The framework has reached a level of maturity where this gap actively blocks adoption.

## What Changes

- **New**: Idempotent install scripts (`scripts/install/`) for Python package, NS-3 + 5G-LENA NR, Mininet-WiFi, and Gazebo + ROS 2, driven by a `Makefile`
- **New**: `scripts/check_ns3_compat.py` — read-only compatibility checker that validates whether CORNET patches will apply cleanly to any given NS-3 + NR version before installation
- **New**: NS-3 CORNET patches committed to `scripts/patches/ns3/v2.4-ns3.38/` for atomicity (three patches copied from CORNET3.0); `scripts/patches/ns3/v4.2-ns3.47/` placeholder with migration status
- **New**: Auto-generated config schema reference — Pydantic `Field(description=...)` annotations added to all models in `cornet/config/schema.py`; `scripts/gen_schema_docs.py` renders `docs/reference/config-schema.md`
- **New**: `docs/guides/` — five task-author and developer guides: `writing-a-task.md`, `custom-plugin.md`, `custom-eval-tool.md`, `parameter-sweep.md`, `middleware.md`
- **New**: `docs/reference/` — CLI reference, leaderboard format reference, and auto-generated config schema reference
- **Modified**: `docs/INSTALL.md` — adds "quick install" section pointing to scripts; updates NS-3 version target (NS-3 3.38 + NR v2.4, proven) and notes migration path to latest
- **Modified**: `docs/GETTING_STARTED.md` — stays as quick-start; adds links to new guides
- **New CI target**: `make docs-check` fails if auto-generated docs are stale

## Capabilities

### New Capabilities

- `install-automation`: Idempotent, modular install scripts and Makefile targets for all CORNET simulator backends; covers NS-3 + NR patch application with pre-flight compatibility check
- `ns3-patch-bundle`: CORNET-specific NS-3 + NR patches (EDF scheduler, AoI MAC scheduler, LTE PDCP) committed to this repo; versioned patch sets with compatibility matrix
- `ns3-compat-check`: Read-only compatibility check script that validates patch applicability, anchor symbol existence, collision detection, and CORNET scenario API drift across NS-3 + NR version upgrades
- `config-schema-autodoc`: Pydantic `Field(description=...)` annotations on all config models; generator script renders Markdown reference; CI diff-check enforces freshness
- `user-guides`: Five Markdown guides covering the full task-author and plugin-developer workflow
- `reference-docs`: CLI reference, leaderboard JSON format, and auto-generated config schema reference

### Modified Capabilities

- `unified-config-schema`: Field-level descriptions added to all Pydantic models (no behavior changes; annotation-only)

## Impact

- `cornet/config/schema.py`: All `BaseModel` fields annotated with `Field(description=...)` — no runtime behavior change
- `scripts/`: New top-level directory; `install/`, `patches/ns3/`, `gen_schema_docs.py`, `check_ns3_compat.py`
- `docs/guides/`: Five new Markdown files
- `docs/reference/`: Three new Markdown files (one auto-generated)
- `docs/INSTALL.md`, `docs/GETTING_STARTED.md`: Edited (additive only)
- `Makefile`: New top-level Makefile
- No changes to plugin lifecycle, orchestrator, middleware, or test suite
