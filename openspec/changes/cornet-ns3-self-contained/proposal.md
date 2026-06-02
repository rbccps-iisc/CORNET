## Why

CORNET currently cannot run an end-to-end experiment without a separate
CORNET3.0 checkout. The NS-3 scratch script (`remote_robot_control.cc`)
that drives the `pendulum_nr_control` task lives outside this repository and
is never copied into the NS-3 build tree by the install scripts. This means:

1. `python -m cornet tasks/pendulum_nr_control` fails silently — NS-3 cannot
   find `remote_robot_control-default` in its scratch directory.
2. There is no way to reproduce a known result from this repo alone.
3. There is no validated path from `make install-ns3` to
   `python -m cornet view` producing a leaderboard entry.

Additionally, the NS-3 3.47 + NR v4.2 migration (tracked in
`scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md`) has never been
exercised. The current MIGRATION_STATUS.md lists incorrect API symbols as
migration targets. Running `pendulum_nr_control` against both NS-3 versions
would: (a) produce a confirmed v2.4 baseline, (b) drive the actual v4.2
migration to completion, and (c) let the UI compare results across versions.

The timing is right: the install scripts, compat-check, and leaderboard
infra are all complete. The only missing piece is the scratch script bundle.

## What Changes

1. **Scratch script bundle** (`scripts/ns3/scratch/`): `remote_robot_control.cc`
   from CORNET3.0 is copied into this repo under a versioned layout. The
   install scripts copy the correct version into `$NS3_DIR/scratch/` during
   installation, making the repo self-contained.

2. **Dual-version install support**: `install_ns3.sh` gains a `--patch-set`
   flag. `NS3_DIR=~/ns-3-dev-v24` installs 3.38 + NR v2.4; `NS3_DIR=~/ns-3-dev-v47`
   installs 3.47 + NR v4.2. The `Makefile` gains `install-ns3-v24` and
   `install-ns3-v47` targets.

3. **Dual-run validation** (`make validate`): Runs `pendulum_nr_control`
   against both NS-3 versions, tagging each leaderboard entry with a
   `variant_id` of `ns3-v24` or `ns3-v47`. The web UI gains variant-filter
   controls so both can be viewed and compared side-by-side.

4. **MIGRATION_STATUS.md correction**: All known API migration issues for
   v4.2 are documented accurately (correcting the wrong `NrEpsBearer`/
   `NrEpcTft` entries), then updated to `✅ done` once the v4.2 run passes.

5. **Doc consistency pass**: The `writing-a-task.md` and
   `leaderboard-format.md` docs that were written before a real end-to-end
   run are corrected after running through the actual pipeline.

## Capabilities

### New Capabilities

- `ns3-scratch-bundle`: Version-controlled NS-3 scratch scripts bundled in
  `scripts/ns3/scratch/<version>/`, copied into `$NS3_DIR/scratch/` by the
  install script. Naming convention: `<task>-<profile>.cc` (e.g.
  `remote_robot_control-default.cc`).

- `dual-ns3-install`: `install_ns3.sh` supports `PATCH_SET` env var
  (`v2.4-ns3.38` or `v4.2-ns3.47`). Separate `$NS3_DIR` per version.
  Sentinels are version-specific (`.cornet-patched-v2.4`, `.cornet-patched-v4.2`).

- `dual-run-validation`: `make validate` orchestrates both installs and runs,
  writing leaderboard entries tagged by NS-3 version. The `cornet ui` frontend
  exposes a variant-filter dropdown to select `ns3-v24` vs `ns3-v47`.

### Modified Capabilities

- `ns3-compat-check`: `MIGRATION_STATUS.md` for v4.2-ns3.47 is corrected to
  reflect the actual C++ API surface of `remote_robot_control.cc` (not the
  incorrectly-listed `NrEpsBearer`/`NrEpcTft` symbols).

## Impact

- **New files**: `scripts/ns3/scratch/v2.4-ns3.38/remote_robot_control-default.cc`,
  `scripts/ns3/scratch/v4.2-ns3.47/remote_robot_control-default.cc` (rebased),
  `scripts/install/install_ns3_v47.sh` (or flag on existing script)
- **Modified files**: `scripts/install/install_ns3.sh` (scratch copy step),
  `Makefile` (new targets), `cornet/ui/server.py` (variant filter),
  `cornet/ui/static/` (filter UI), `scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md`
- **Dependencies**: NS-3 3.47 + NR v4.2 source (network access required for v4.2 phase)
- **No schema changes**: `UnifiedConfig` is unchanged
