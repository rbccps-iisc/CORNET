## Context

CORNET_Research is the authoritative source for running CORNET experiments,
but it currently depends on a separate CORNET3.0 checkout for the NS-3 scratch
script (`remote_robot_control.cc`). The install scripts never copy the script
into `$NS3_DIR/scratch/`, so `python -m cornet tasks/pendulum_nr_control`
fails immediately when NS-3 cannot find `remote_robot_control-default`.

The existing infrastructure (install scripts, compat-check, leaderboard writer,
web UI) is all in place. The missing pieces are: (1) the scratch script in the
repo, (2) a way to install two NS-3 versions side-by-side, (3) a way to tag
and compare leaderboard entries across those versions, and (4) an accurate
migration status document for NR v4.2.

**Current leaderboard entries are synthetic** — all 12.0 values from pytest
runs using mock output directories. A real end-to-end run has never been
performed from this repo.

## Goals / Non-Goals

**Goals:**
- Make this repo self-contained: cloning it + `make install-ns3` + `make validate` should produce a real leaderboard entry
- Support two NS-3 installations at `~/ns-3-dev-v24` and `~/ns-3-dev-v47` without conflicts
- Tag leaderboard entries with NS-3 version (`ns3-v24`, `ns3-v47`) and expose a filter in the web UI
- Correct the inaccurate NR v4.2 API migration surface in `MIGRATION_STATUS.md`
- Allow doc consistency issues to surface naturally through the real pipeline run

**Non-Goals:**
- Numerical parity between v2.4 and v4.2 AoI results (scheduler internals differ)
- Real-time Gazebo simulation for CI (Gazebo plugin will be mocked / skipped in automated tests)
- Supporting more than two NS-3 versions simultaneously
- Changing the `UnifiedConfig` schema

## Decisions

**D1 — Scratch script layout and naming**

Scripts live under `scripts/ns3/scratch/<patch-set>/`. The filename matches
the `simulation_script` value in `config.yaml` exactly (including any suffix):

```
scripts/ns3/scratch/
  v2.4-ns3.38/
    remote_robot_control-default.cc   ← simulation_script value: "remote_robot_control-default"
  v4.2-ns3.47/
    remote_robot_control-default.cc   ← rebased for v4.2
```

Naming convention: `<task-script-base>-<profile-suffix>.cc`. The `-default`
suffix means "default network profile" (accepts `--networkPreset` CLI arg).
Profile-specific variants (e.g. `-urllc`, `-embb`) would be separate files.
The install script copies all files in the matching `scratch/<patch-set>/`
directory into `$NS3_DIR/scratch/`.

**D2 — Dual-version install via `PATCH_SET` env var**

`install_ns3.sh` reads `PATCH_SET` (default: `v2.4-ns3.38`). The env var
controls which patch directory and which NS-3/NR git tags to use:

```
PATCH_SET        NS3_TAG     NR_TAG   SENTINEL
v2.4-ns3.38      ns-3.38     v2.4     .cornet-patched-v2.4
v4.2-ns3.47      ns-3.47     v4.2     .cornet-patched-v4.2
```

Convention: `NS3_DIR` is set by the caller. Makefile targets use:
- `make install-ns3-v24`  → `NS3_DIR=~/ns-3-dev-v24 PATCH_SET=v2.4-ns3.38`
- `make install-ns3-v47`  → `NS3_DIR=~/ns-3-dev-v47 PATCH_SET=v4.2-ns3.47`
- `make install-ns3`      → keeps current default (v2.4, `~/ns-3-dev`)

**D3 — Leaderboard version tagging via `CORNET_NS3_TAG` env var**

The orchestrator reads `CORNET_NS3_TAG` (if set) and appends it to the
`variant_id` of each leaderboard entry: `{original_variant_id}@{ns3_tag}`.
Example: `pendulum_nr_control@ns3-v24`.

Rationale: avoids changing `config.yaml` per run; keeps the task definition
version-agnostic; the tag is injected at runtime by `make validate`.

`make validate` runs both versions sequentially:
```makefile
validate:
    NS3_DIR=~/ns-3-dev-v24 CORNET_NS3_TAG=ns3-v24 python -m cornet tasks/pendulum_nr_control
    NS3_DIR=~/ns-3-dev-v47 CORNET_NS3_TAG=ns3-v47 python -m cornet tasks/pendulum_nr_control
```

**D4 — UI variant filter via query param on `/api/leaderboard`**

`GET /api/leaderboard?variant=ns3-v24` returns only entries whose
`variant_id` contains `ns3-v24`. `?variant=all` (default) returns all.

The frontend adds a `<select id="variant-filter">` above the leaderboard
table. The JS poll loop appends `?variant=<selected>` to the fetch URL.
Existing `select` CSS styling applies without changes.

**D5 — MIGRATION_STATUS.md correction strategy**

Replace the current incorrect symbols (`NrEpsBearer`, `NrEpcTft`,
`SetDlEarfcn`) with the actual API surface found in
`remote_robot_control.cc`. Mark each as `⚠️ to-verify` (not yet confirmed
against v4.2 source). Once the v4.2 run passes, update to `✅ done` and
remove `to-verify` markers.

Actual migration surface (from code exploration):

| Symbol / API | Risk | Notes |
|---|---|---|
| `NrPointToPointEpcHelper` | High | Renamed at least once historically; check v4.2 header |
| `CcBwpCreator::CreateOperationBandContiguousCc` | High | BWP API heavily changed post-v2 |
| `CcBwpCreator::GetAllBwps` | High | Same |
| `NrHelper::AttachToClosestEnb` | Medium | "Enb" → "Gnb" rename likely in v4 |
| `NrGnbNetDevice::UpdateConfig` | Medium | Signature may change |
| `nrEpcHelper->GetPgwNode()` | Medium | PGW may move to 5GC model |
| `NrMacSchedulerOfdmaEdf` / `OfdmaAoi` | Low | CORNET-custom class names; survive via patch |
| `nrHelper->SetSchedulerTypeId(...)` | Low | Stable NrHelper public API |

## Risks / Trade-offs

**NR v4.2 source required for Phase C**: The v4.2 scratch script rebase and
patch rebase cannot be done without `git clone` of the NR v4.2 tree (network
access). Phase A (bundling v2.4 script) and Phase B (baseline run) are fully
unblocked today.

**`~/ns-3-dev-v24` and `~/ns-3-dev-v47` are outside the workspace**: They are
never added to `.gitignore` (nothing to ignore — they aren't under the repo
root). Users with a custom `NS3_DIR` already set must export the new named
paths explicitly.

**Bandwidth unit inconsistency (pre-existing bug)**: `pendulum_nr_control/config.yaml`
uses flat `bandwidth: 100e6` (Hz) while the nested `ScenarioConfig.bandwidth_mhz`
path in the plugin uses MHz units. These two code paths produce different
`--bandwidth` CLI arg values to NS-3. This bug will surface during Phase B
and should be fixed as part of the doc consistency pass — not pre-emptively.

**Leaderboard `variant_id` format change**: Existing synthetic entries use
`variant_id: "pendulum_nr_control"` (plain task name). After this change,
real entries will use `"pendulum_nr_control@ns3-v24"`. The UI filter handles
this via substring match, so old and new entries coexist without issue.
