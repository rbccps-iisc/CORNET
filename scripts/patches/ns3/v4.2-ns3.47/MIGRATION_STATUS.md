# Migration Status: NS-3 3.47 + NR v4.2

This directory tracks the migration of CORNET patches from the proven
`v2.4-ns3.38` set to NS-3 3.47 + NR v4.2.

The `check_ns3_compat.py` script reads this file to enumerate expected patches
for this version. Patches listed here but absent from this directory produce
`FAIL("not-yet-migrated: <name>")` in the compat report.

## Expected Patches

> **Note**: Capability status is now tracked in `scripts/patches/ns3/CAPABILITY_MATRIX.yaml`.
> This table tracks rebase progress only — not whether features are research-grade.
> `✅ done` here means the patch applies cleanly; it does NOT mean the feature
> is `cornet-validated`. See CAPABILITY_MATRIX.yaml for validation levels.

| Patch file | Rebase status | Notes |
|---|---|---|
| `ns3_lte_pdcp.patch` | ✅ applied | Rebased against NS-3 3.47; hunks apply with minor offsets |
| `nr_schedulers.patch` | ✅ applied | Rebased against NR v4.2; alphabetical CMake files, updated MacScheduler signature |

## API Surface — Rebase Verification Status

These entries track C++ API changes in the scratch script between v2.4 and v4.2.
All entries require `make validate-v47` to be promoted to `cornet-validated` in CAPABILITY_MATRIX.yaml.

| Symbol / API (v2.4) | Risk | Rebase status | Notes |
|---|---|---|---|
| `NrPointToPointEpcHelper` | High | ✅ applied | Verified existence in v4.2; same header |
| `CcBwpCreator::CreateOperationBandContiguousCc` | High | ✅ applied | Replaced `SimpleOperationBandConf` with `OperationBandConf` |
| `CcBwpCreator::GetAllBwps` | High | ✅ applied | Same BWP creator overhaul |
| `NrHelper::AttachToClosestEnb` | Medium | ✅ applied | Renamed to `AttachToClosestGnb` |
| `NrGnbNetDevice::UpdateConfig` | Medium | ⚠️ to-verify | Signature may have changed — requires runtime test |
| `NrUeNetDevice::UpdateConfig` | Medium | ⚠️ to-verify | Same — requires runtime test |
| `nrEpcHelper->GetPgwNode()` | Medium | ⚠️ to-verify | Requires runtime test (EPC mode) |
| `NrMacSchedulerOfdmaEdf` | Low | ✅ applied | Class names unchanged; built-in via rebased patch |
| `NrMacSchedulerOfdmaAoi` | Low | ✅ applied | Same |
| `nrHelper->SetSchedulerTypeId(...)` | Low | ⚠️ to-verify | Stable API but requires runtime test |

## Migration Checklist

- [x] Rebase `remote_robot_control-default.cc` for NR v4.2 API changes in
      `NrPointToPointEpcHelper`, `CcBwpCreator`, `AttachToClosestEnb`
      (see `scripts/ns3/scratch/v4.2-ns3.47/remote_robot_control-default.cc`)
- [x] Rebase `nr_schedulers.patch` — confirm `NrMacSchedulerOfdmaEdf` /
      `NrMacSchedulerOfdmaAoi` class names are unchanged in NR v4.2
      CMakeLists structure
- [x] Rebase `ns3_lte_pdcp.patch` against NS-3 3.47 `src/lte/` tree;
      verify `LteNetDevice` and `lte-pdcp.cc` hunks apply cleanly
- [ ] Clone NR v4.2 and scan CHANGES.md to confirm or deny each
      `⚠️ to-verify` entry above
- [ ] Run `make validate-v47` — on success, update `CAPABILITY_MATRIX.yaml`
      entries for v4.2 from `cornet-integrated` to `cornet-validated`
- [ ] Fix TUN naming: scratch scripts must consume `--tun{i}` args, not hard-code
      `tap-robot`/`tap-controller` (see tasks.md Phase 0, tasks 0.7–0.9)

