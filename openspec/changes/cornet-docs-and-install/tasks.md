## 1. NS-3 Patch Bundle (Atomicity)

- [x] 1.1 Copy `ns3_lte_pdcp.patch` from CORNET3.0 into `scripts/patches/ns3/v2.4-ns3.38/`
- [x] 1.2 Copy `nr_edf_scheduler.patch` from CORNET3.0 into `scripts/patches/ns3/v2.4-ns3.38/`
- [x] 1.3 Perform dry-run on clean NR v2.4 checkout: apply all three patches in order; if CMakeLists conflict exists between `nr_edf_scheduler.patch` and `nr_aoi_mac_scheduler.patch`, merge into a single `nr_schedulers.patch`
- [x] 1.4 Copy (or place merged) `nr_aoi_mac_scheduler.patch` into `scripts/patches/ns3/v2.4-ns3.38/`
- [x] 1.5 Write `scripts/patches/ns3/README.md` (compatibility matrix, validated application order, per-patch description, files modified)
- [x] 1.6 Create `scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md` (lists all expected patch names with status: pending; used by compat check script to detect missing patches)

## 2. NS-3 Compatibility Check Script

- [x] 2.1 Scaffold `scripts/check_ns3_compat.py` with CLI argument parsing (`--ns3-dir`, `--patch-set`, `--json`)
- [x] 2.2 Implement check 1: version matrix validation (reads NS-3 `VERSION` and NR `RELEASE_NOTES.md`)
- [x] 2.3 Implement check 2: patch dry-run via `git apply --check` for all patches in the selected set; read `MIGRATION_STATUS.md` to enumerate expected patches — absent patches produce `FAIL("not-yet-migrated: <name>")` distinct from `FAIL("hunk-mismatch")`
- [x] 2.4 Implement check 3: anchor symbol existence (grep for `DoScheduleDlData`, `DoScheduleUlData`, `AssignStreams`, `InstallSingleUeDevice`, `LtePdcp` in target source files)
- [x] 2.5 Implement check 4: collision detection (verify CORNET-injected class names are absent from target NR headers)
- [x] 2.6 Implement check 5: CORNET scenario API drift detection (scan `cornet/scenarios/*/run.py` for known renamed symbols)
- [x] 2.7 Implement `CompatReport` with `to_text()`, `to_json()`, and `exit_code()` methods
- [x] 2.8 Wire all five checks into `CompatChecker.run_all()`; emit human-readable report by default, JSON with `--json`

## 3. Install Scripts

- [x] 3.1 Write `scripts/install/install_python.sh` (idempotency gate: `pip show cornet-framework`; installs `pip install -e .[dev]`)
- [x] 3.2 Write `scripts/install/install_ns3.sh` (gate: both sentinels `$NS3_DIR/.cornet-built` AND `$NS3_DIR/contrib/nr/.cornet-patched-v2.4` must exist; detect existing NR version and exit 1 with message if mismatch; clone NS-3 3.38 + NR v2.4; call `check_ns3_compat.py`; build; apply patches; write sentinels LAST in sequence)
- [x] 3.3 Write `scripts/install/install_mininet.sh` (gate: `python3 -c "import mininet"`; installs Mininet-WiFi + Docker)
- [x] 3.4 Write `scripts/install/install_gazebo_ros2.sh` (gate: `ros2 --version`; installs ros-humble-desktop + gazebo-ros-pkgs)
- [x] 3.5 Write `scripts/install/verify.sh` (checks all five components; exits 1 if any fail)
- [x] 3.6 Write top-level `Makefile` with targets: `install`, `install-python`, `install-ns3`, `install-mininet`, `install-gazebo`, `verify`, `docs`, `docs-check`, `compat-check`

## 4. Config Schema Annotations

- [x] 4.1 Annotate all fields in `ContainerConfig` with `Field(description=...)`
- [x] 4.2 Annotate all fields in `NodeConfig` with `Field(description=...)`
- [x] 4.3 Annotate all fields in `MininetConfig`, `MiddlewareConfig`, `MobilityConfig` with `Field(description=...)`
- [x] 4.4 Annotate all fields in `ScenarioConfig`, `NetworkConfig` with `Field(description=...)`
- [x] 4.5 Annotate all fields in `ModelConfig`, `PoseConfig`, `RobotEntry`, `RobotConfig` with `Field(description=...)`
- [x] 4.6 Annotate all fields in `SweepConfig`, `ExperimentConfig`, `UnifiedConfig` with `Field(description=...)`
- [x] 4.7 Verify `UnifiedConfig.model_json_schema()` contains `"description"` on every leaf property

## 5. Schema Auto-Gen Pipeline

- [x] 5.1 Write `scripts/gen_schema_docs.py` (calls `model_json_schema()`; renders per-model Markdown tables with Field/Type/Default/Required/Description columns; prepends "do not edit manually" header)
- [x] 5.2 Run generator and commit initial `docs/reference/config-schema.md`
- [x] 5.3 Add `docs` and `docs-check` targets to `Makefile` (docs-check runs generator then `git diff --exit-code`)

## 6. Reference Documentation

- [x] 6.1 Write `docs/reference/cli.md` (documents `run`, `view`, `ui` subcommands with flags and examples)
- [x] 6.2 Write `docs/reference/leaderboard-format.md` (JSON schema of entries, atomic write guarantee)

## 7. User Guides

- [x] 7.1 Write `docs/guides/writing-a-task.md` **[P0 — complete before other guides]** (directory layout, minimal config.yaml, run command, EvalTool hookup, leaderboard view; must cover all scenarios in user-guides spec)
- [x] 7.2 Write `docs/guides/custom-plugin.md` (Plugin ABC, five-method lifecycle, ExperimentContext fields, minimal skeleton)
- [x] 7.3 Write `docs/guides/custom-eval-tool.md` (EvalTool ABC, `format_result`, results_dir contract, example)
- [x] 7.4 Write `docs/guides/parameter-sweep.md` (axes declaration, variant ID construction, per-variant output_dir, repeats)
- [x] 7.5 Write `docs/guides/middleware.md` (AoI tracker, physics clock, packet dispatcher, TUN manager — what each does and when to enable)

## 8. Update Existing Docs

- [x] 8.1 Update `docs/INSTALL.md` — add "Quick Install" section pointing to `scripts/install/`; update NS-3 version to 3.38 + NR v2.4 with explicit note acknowledging change from prior v2.6 documentation; add Docker alternative callout; note v4.2 migration path
- [x] 8.2 Update `docs/GETTING_STARTED.md` — add "Guides" section with relative links to all five guides in `docs/guides/`

## 9. Migration Task (Tracked, Non-Blocking)

- [ ] 9.1 Rebase `ns3_lte_pdcp.patch` against NS-3 3.47; verify `lte-pdcp.cc` and `lte-helper.cc` hunks apply cleanly
- [ ] 9.2 Rebase `nr_edf_scheduler.patch` against NR v4.2; manually fix CMakeLists.txt hunk and `nr-mac-scheduler-ns3.cc` injection points
- [ ] 9.3 Rebase `nr_aoi_mac_scheduler.patch` against NR v4.2; manually fix CMakeLists.txt hunk
- [ ] 9.4 Update CORNET scenario scripts for NR v4.2 API renames (`NrEpsBearer` → `NrQosFlow`, `NrEpcTft` → `NrQosRule`, ARFCN migration)
- [ ] 9.5 Validate end-to-end: run AoI 5-phase eval and pendulum NR control with NS-3 3.47 + NR v4.2
- [ ] 9.6 Move rebased patches to `scripts/patches/ns3/v4.2-ns3.47/`; update `MIGRATION_STATUS.md` to done; flip `install_ns3.sh` default to latest
