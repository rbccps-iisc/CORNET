## 1. NS-3 Scratch Script Bundle (Phase A — unblocked)

- [x] 1.1 Copy `remote_robot_control.cc` from CORNET3.0 to `scripts/ns3/scratch/v2.4-ns3.38/remote_robot_control-default.cc` (rename to match `simulation_script` value in config)
- [x] 1.2 Update `scripts/install/install_ns3.sh` — after patch application, copy all files from `scripts/ns3/scratch/$PATCH_SET/` to `$NS3_DIR/scratch/`
- [x] 1.3 Add `scripts/ns3/scratch/v4.2-ns3.47/` directory with a `PLACEHOLDER.md` explaining the rebase requirement (populated in Group 4)
- [ ] 1.4 Verify locally: confirm `$NS3_DIR/scratch/remote_robot_control-default.cc` exists after running the updated install step

## 2. Dual-Version Install Support (Phase A — unblocked)

- [x] 2.1 Extend `install_ns3.sh` to read `PATCH_SET` env var (default: `v2.4-ns3.38`); derive `NS3_TAG`, `NR_TAG`, and sentinel filename from a lookup table in the script
- [x] 2.2 Make sentinel filename patch-set-specific: `.cornet-patched-v2.4` for v2.4 and `.cornet-patched-v4.2` for v4.2; update idempotency gate to use the derived sentinel name
- [x] 2.3 Extend D4 version mismatch guard to cover NR v4.2 target (detect `v4.x` vs expected `v4.2`)
- [x] 2.4 Add `install-ns3-v24` Makefile target: `NS3_DIR=~/ns-3-dev-v24 PATCH_SET=v2.4-ns3.38 bash scripts/install/install_ns3.sh`
- [x] 2.5 Add `install-ns3-v47` Makefile target: `NS3_DIR=~/ns-3-dev-v47 PATCH_SET=v4.2-ns3.47 bash scripts/install/install_ns3.sh`
- [x] 2.6 Keep existing `install-ns3` Makefile target unchanged (v2.4, default `NS3_DIR`)

## 3. NS-3 Version Tagging in Orchestrator and Leaderboard (Phase A — unblocked)

- [x] 3.1 In `cornet/orchestrator.py`, read `CORNET_NS3_TAG` env var in `_run_variant()`; if set, append `@{tag}` to `config.experiment.name` before writing the leaderboard entry
- [~] 3.2 ~~Update `cornet/leaderboard/writer.py` to expose `ns3_tag` as a top-level field~~ — DROPPED per Discussion D3 (tag already encoded in `variant_id`; redundant field creates two sources of truth)
- [x] 3.3 Add `validate` Makefile target that: (a) runs v2.4 with `NS3_DIR=~/ns-3-dev-v24 CORNET_NS3_TAG=ns3-v24`, (b) checks `~/ns-3-dev-v47/.cornet-built` before running v4.2 (skip with warning if absent), (c) exits non-zero if v2.4 run fails
- [x] 3.4 Add `validate-v24` and `validate-v47` single-version targets for independent use

## 4. UI Variant Filter (Phase A — unblocked)

- [x] 4.1 Update `cornet/ui/server.py` `/api/leaderboard` endpoint to accept `variant` query param; filter entries by exact tag equality after `@`-split (Discussion D4) when `variant != "all"` (default: `"all"`)
- [x] 4.2 Update the UI HTML (or `cornet/ui/static/`) — add `<select id="variant-filter">` above the leaderboard table with "All versions" option plus one option per unique variant tag found in entries
- [x] 4.3 Update the frontend JS poll loop to append `?variant=<selected>` to the `/api/leaderboard` fetch URL; re-populate the `<select>` options on each poll with current unique tags
- [x] 4.4 Write a unit test for the `/api/leaderboard?variant=ns3-v24` filtering in `tests/`

## 5. MIGRATION_STATUS.md Correction (Phase A — unblocked, no v4.2 source needed)

- [x] 5.1 Rewrite `scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md` — replace incorrect symbols (`NrEpsBearer`, `NrEpcTft`, `SetDlEarfcn`) with the actual API surface found in `remote_robot_control-default.cc`: `NrPointToPointEpcHelper`, `CcBwpCreator::CreateOperationBandContiguousCc / GetAllBwps`, `NrHelper::AttachToClosestEnb`, `NrGnbNetDevice/NrUeNetDevice::UpdateConfig`, `nrEpcHelper->GetPgwNode()`
- [x] 5.2 Update all entries to use `⚠️ to-verify` lifecycle marker (replacing `⏳ pending`)
- [x] 5.3 Add explicit migration checklist item: "Rebase `remote_robot_control-default.cc` for NR v4.2 API changes in `NrPointToPointEpcHelper`, `CcBwpCreator`, `AttachToClosestEnb`"
- [x] 5.4 Add checklist item: "Rebase `nr_schedulers.patch` — confirm `NrMacSchedulerOfdmaEdf` / `NrMacSchedulerOfdmaAoi` class names are unchanged in NR v4.2 CMakeLists structure"

## 6. v2.4 Baseline Run + Doc Consistency Pass (Phase B — requires installed v2.4)

- [ ] 6.1 Run `make install-ns3-v24` on the target machine; confirm both sentinels written
- [ ] 6.2 Run `make validate-v24`; record exact error output if it fails; fix any errors found (bandwidth unit bug expected: `bandwidth: 100e6` flat key vs `bandwidth_mhz` path in plugin)
- [ ] 6.3 Confirm a real leaderboard entry with `variant_id: pendulum_nr_control@ns3-v24` appears in `tasks/pendulum_nr_control/leaderboard.json`
- [ ] 6.4 Run `python -m cornet view tasks/pendulum_nr_control` and `python -m cornet ui tasks/pendulum_nr_control`; confirm variant filter shows `ns3-v24`
- [ ] 6.5 Fix any doc inconsistencies revealed by the run (expected: `writing-a-task.md` flat vs nested config keys, leaderboard entry format in `leaderboard-format.md`, bandwidth unit explanation)

## 7. NR v4.2 Migration — Patches and Scratch Script (Phase C — requires network / NR v4.2 source)

- [ ] 7.1 Clone NR v4.2 into a temporary tree; scan CHANGES.md entries from v2.4 to v4.2 to confirm or deny each `⚠️ to-verify` entry in MIGRATION_STATUS.md
- [ ] 7.2 Rebase `scripts/patches/ns3/v4.2-ns3.47/nr_schedulers.patch` against NR v4.2 `CMakeLists.txt` and scheduler source; confirm `NrMacSchedulerOfdmaEdf` / `OfdmaAoi` class names survive
- [ ] 7.3 Rebase `scripts/patches/ns3/v4.2-ns3.47/ns3_lte_pdcp.patch` against NS-3 3.47 `src/lte/`; verify `LteNetDevice`, `lte-pdcp.cc` hunks apply cleanly
- [ ] 7.4 Write `scripts/ns3/scratch/v4.2-ns3.47/remote_robot_control-default.cc` — copy v2.4 version and apply all API changes confirmed in 7.1 (rename `AttachToClosestEnb`, update `CcBwpCreator` calls, etc.)
- [ ] 7.5 Update MIGRATION_STATUS.md: change each confirmed item from `⚠️ to-verify` to `✅ done`; move patch files from `PLACEHOLDER.md` to real patch files

## 8. v4.2 Validation Run (Phase C — requires Phase 7 complete)

- [ ] 8.1 Run `make install-ns3-v47`; confirm both sentinels (`.cornet-built`, `.cornet-patched-v4.2`) written
- [ ] 8.2 Run `python3 scripts/check_ns3_compat.py --ns3-dir ~/ns-3-dev-v47 --patch-set v4.2-ns3.47`; all 5 checks must pass (Check 2 will be WARN-not-FAIL on clean tree)
- [ ] 8.3 Run `make validate-v47`; confirm leaderboard entry `pendulum_nr_control@ns3-v47` written with status SUCCESS
- [ ] 8.4 Run `make validate` (both versions); confirm two entries in leaderboard; verify UI variant filter shows both `ns3-v24` and `ns3-v47` options
- [ ] 8.5 Final MIGRATION_STATUS.md update: all items `✅ done`; update `install_ns3.sh` default PATCH_SET comment to note v4.2 is now validated
