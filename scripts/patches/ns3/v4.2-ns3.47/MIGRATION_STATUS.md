# Migration Status: NS-3 3.47 + NR v4.2

This directory tracks the migration of CORNET patches from the proven
`v2.4-ns3.38` set to NS-3 3.47 + NR v4.2.

The `check_ns3_compat.py` script reads this file to enumerate expected patches
for this version. Patches listed here but absent from this directory produce
`FAIL("not-yet-migrated: <name>")` in the compat report.

## Expected Patches

| Patch file | Status | Notes |
|---|---|---|
| `ns3_lte_pdcp.patch` | ⚠️ to-verify | Targets `src/lte/lte-pdcp.cc` — verify NS-3 3.47 LTE module is structurally identical |
| `nr_schedulers.patch` | ⚠️ to-verify | Targets `contrib/nr` — adds `NrMacSchedulerOfdmaEdf` / `NrMacSchedulerOfdmaAoi`; check CMakeLists structure in NR v4.2 |

## Actual API Surface at Risk (from `remote_robot_control-default.cc`)

These are the NR/LTE symbols from the scratch script that may have changed
between NR v2.4 and v4.2. All entries are `⚠️ to-verify` until a successful
`make validate-v47` run confirms them.

> **Note**: The previously listed symbols `NrEpsBearer`, `NrEpcTft`, and
> `SetDlEarfcn` do **not** appear in `remote_robot_control-default.cc` and
> have been removed. The affected files are in the scratch script, not in
> `cornet/scenarios/*/run.py`.

| Symbol / API (v2.4) | Risk | Status | Notes |
|---|---|---|---|
| `NrPointToPointEpcHelper` | High | ⚠️ to-verify | Used for EPC setup; may be renamed in 5GC migration |
| `CcBwpCreator::CreateOperationBandContiguousCc` | High | ⚠️ to-verify | BWP API heavily revised post-v2; signature may differ |
| `CcBwpCreator::GetAllBwps` | High | ⚠️ to-verify | Same BWP creator overhaul |
| `NrHelper::AttachToClosestEnb` | Medium | ⚠️ to-verify | "Enb" → "Gnb" rename likely in NR v4 |
| `NrGnbNetDevice::UpdateConfig` | Medium | ⚠️ to-verify | Signature may have changed |
| `NrUeNetDevice::UpdateConfig` | Medium | ⚠️ to-verify | Same |
| `nrEpcHelper->GetPgwNode()` | Medium | ⚠️ to-verify | PGW node may move to 5GC architecture |
| `NrMacSchedulerOfdmaEdf` | Low | ⚠️ to-verify | CORNET-custom class added via `nr_schedulers.patch`; survives if patch applies |
| `NrMacSchedulerOfdmaAoi` | Low | ⚠️ to-verify | Same |
| `nrHelper->SetSchedulerTypeId(...)` | Low | ⚠️ to-verify | Stable NrHelper public API; expected unchanged |

## Migration Checklist

- [ ] Rebase `remote_robot_control-default.cc` for NR v4.2 API changes in
      `NrPointToPointEpcHelper`, `CcBwpCreator`, `AttachToClosestEnb`
      (see `scripts/ns3/scratch/v4.2-ns3.47/PLACEHOLDER.md`)
- [ ] Rebase `nr_schedulers.patch` — confirm `NrMacSchedulerOfdmaEdf` /
      `NrMacSchedulerOfdmaAoi` class names are unchanged in NR v4.2
      CMakeLists structure
- [ ] Rebase `ns3_lte_pdcp.patch` against NS-3 3.47 `src/lte/` tree;
      verify `LteNetDevice` and `lte-pdcp.cc` hunks apply cleanly
- [ ] Clone NR v4.2 and scan CHANGES.md to confirm or deny each
      `⚠️ to-verify` entry above
- [ ] Run `make validate-v47` — on success, update all entries above to
      `✅ done` and remove this checklist
- [ ] Update `scripts/install/install_ns3.sh` default PATCH_SET comment
      to note v4.2 is now validated

