# Migration Status: NS-3 3.47 + NR v4.2

This directory tracks the migration of CORNET patches from the proven
`v2.4-ns3.38` set to NS-3 3.47 + NR v4.2.

The `check_ns3_compat.py` script reads this file to enumerate expected patches
for this version. Patches listed here but absent from this directory produce
`FAIL("not-yet-migrated: <name>")` in the compat report.

## Expected Patches

| Patch file | Status | Notes |
|---|---|---|
| `ns3_lte_pdcp.patch` | ⏳ pending | Targets `src/lte/` — verify NS-3 3.47 LTE module API stability |
| `nr_schedulers.patch` | ⏳ pending | Targets `contrib/nr` — NR v4.2 renames `NrEpsBearer→NrQosFlow`, `NrEpcTft→NrQosRule`; CMakeLists structure changed |

## Known API Changes in NR v4.2 (vs v2.4)

These symbols appear in CORNET scenario scripts and may need updating:

| Old symbol (v2.4) | New symbol (v4.2) | Affected files |
|---|---|---|
| `NrEpsBearer` | `NrQosFlow` | `cornet/scenarios/*/run.py` |
| `NrEpcTft` | `NrQosRule` | `cornet/scenarios/*/run.py` |
| `SetDlEarfcn` / `SetUlEarfcn` | ARFCN-based API | scenario scripts |
| `NrHelper::InstallSingleUeDevice` | signature changed | scenario scripts |

## Migration Checklist

- [ ] Rebase `ns3_lte_pdcp.patch` against NS-3 3.47 `src/lte/` tree
- [ ] Rebase `nr_schedulers.patch` against NR v4.2 (fix CMakeLists hunks, rename symbols)
- [ ] Update `cornet/scenarios/*/run.py` for v4.2 API renames
- [ ] Validate end-to-end with `aoi_5phase_eval` and `pendulum_nr_control`
- [ ] Move completed patches here, update status above to ✅ done
- [ ] Update `scripts/install/install_ns3.sh` default to NS-3 3.47 + NR v4.2
