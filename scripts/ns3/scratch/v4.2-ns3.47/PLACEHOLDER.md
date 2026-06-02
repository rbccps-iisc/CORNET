# Placeholder: NR v4.2 Scratch Scripts

This directory will contain the `v4.2-ns3.47` version of the NS-3 scratch
scripts once the migration from NR v2.4 → v4.2 is complete (Phase C).

## Expected contents

```
v4.2-ns3.47/
  remote_robot_control-default.cc   ← rebased from v2.4 version
```

## What must change (from v2.4 baseline)

See `scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md` for the full
migration surface. Key API changes expected in `remote_robot_control-default.cc`:

| API (v2.4) | Expected change (v4.2) | Risk |
|---|---|---|
| `NrPointToPointEpcHelper` | May be renamed | High |
| `CcBwpCreator::CreateOperationBandContiguousCc` | BWP API changed post-v2 | High |
| `CcBwpCreator::GetAllBwps` | Same | High |
| `NrHelper::AttachToClosestEnb` | "Enb" → "Gnb" rename likely | Medium |
| `NrGnbNetDevice::UpdateConfig` | Signature may change | Medium |
| `nrEpcHelper->GetPgwNode()` | PGW may move to 5GC model | Medium |

## How to populate this directory

1. Clone NR v4.2 and NS-3 3.47 (see `make install-ns3-v47`)
2. Copy `v2.4-ns3.38/remote_robot_control-default.cc` to this directory
3. Apply all API changes found in MIGRATION_STATUS.md
4. Update the origin comment to reflect v4.2 patch-set
5. Run `make validate-v47` to confirm the script builds and runs
