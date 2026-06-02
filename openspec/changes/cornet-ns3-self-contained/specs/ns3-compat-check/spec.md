## MODIFIED Requirements

### Requirement: accurate-migration-surface
`scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md` must document the
**actual** C++ API surface of `remote_robot_control-default.cc` that is at
risk when migrating from NR v2.4 to v4.2. Previously listed symbols
(`NrEpsBearer`, `NrEpcTft`, `SetDlEarfcn`) do NOT appear in the script and
must be removed.

#### Scenario: migration status lists only real call sites
- **WHEN** a developer reads MIGRATION_STATUS.md before starting the v4.2 rebase
- **THEN** every listed symbol/API appears in `remote_robot_control-default.cc`
- **THEN** the affected file column names `remote_robot_control-default.cc` (not `cornet/scenarios/*/run.py`)

### Requirement: migration-status-lifecycle
Each entry in MIGRATION_STATUS.md must carry one of three lifecycle markers:
`⚠️ to-verify` (not yet confirmed against v4.2 source), `✅ done` (rebased
and tested), or `❌ blocked` (cannot proceed without external resource).

#### Scenario: pre-run state uses to-verify
- **WHEN** the v4.2 source has not yet been checked out
- **THEN** all entries carry `⚠️ to-verify` (not `⏳ pending`)

#### Scenario: post-run state updates to done
- **WHEN** `make validate` produces a `@ns3-v47` leaderboard entry with status SUCCESS
- **THEN** all entries in MIGRATION_STATUS.md are updated to `✅ done`

### Requirement: migration-checklist-completeness
The migration checklist in MIGRATION_STATUS.md must list all work items
required for a successful `make validate` v4.2 run, including the scratch
script rebase and any C++ changes needed in `remote_robot_control-default.cc`.

#### Scenario: checklist covers scratch script
- **WHEN** a developer reads the checklist
- **THEN** there is an explicit item: "Rebase `remote_robot_control-default.cc` for NR v4.2 API changes in `NrPointToPointEpcHelper`, `CcBwpCreator`, `AttachToClosestEnb`"
