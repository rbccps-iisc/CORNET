## ADDED Requirements

### Requirement: Five-category compatibility check
`scripts/check_ns3_compat.py` SHALL perform five check categories against a given NS-3 + NR installation: (1) version matrix validation, (2) patch dry-run via `git apply --check`, (3) anchor symbol existence in target source files, (4) collision detection for CORNET-injected symbols, (5) CORNET scenario Python API drift detection. The script SHALL be read-only — it SHALL NOT modify any file in `$NS3_DIR`.

#### Scenario: Script is read-only
- **WHEN** `check_ns3_compat.py` is run against any NS-3 + NR directory
- **THEN** no file in `$NS3_DIR` SHALL be created, modified, or deleted

#### Scenario: Version mismatch blocks all other checks
- **WHEN** the detected NR version is not in the known compatibility matrix for the given NS-3 version
- **THEN** the script SHALL emit a FAIL for check 1 and skip checks 2–5

#### Scenario: Patch dry-run failure reports hunk location
- **WHEN** a patch hunk cannot be applied due to context mismatch
- **THEN** the script SHALL include the failing hunk's file name and approximate line number in the output

#### Scenario: Collision check detects upstream adoption
- **WHEN** a symbol injected by a CORNET patch (e.g. `NrMacSchedulerOfdmaEdf`) already exists in the target NR version's headers
- **THEN** the script SHALL emit a WARN with the file and line where the symbol was found

#### Scenario: Scenario API drift check finds stale Python references
- **WHEN** a CORNET scenario script references `NrEpsBearer` and the target NR version has renamed it to `NrQosFlow`
- **THEN** the script SHALL emit a WARN citing the file and line number

### Requirement: Structured output for human and CI consumption
The script SHALL support `--json` flag to emit machine-readable output. Without `--json`, it SHALL emit a human-readable report. The exit code SHALL be 0 only when all checks pass; 1 otherwise.

#### Scenario: JSON output is parseable
- **WHEN** `check_ns3_compat.py --json` is run
- **THEN** stdout SHALL be valid JSON with a top-level `overall` field set to `"COMPATIBLE"`, `"NEEDS_MIGRATION"`, or `"INCOMPATIBLE"`, and a `results` array with one entry per check

#### Scenario: Exit code is 0 on full pass
- **WHEN** all five checks pass with no WARN or FAIL
- **THEN** the script SHALL exit 0

#### Scenario: Exit code is 1 on any WARN or FAIL
- **WHEN** any check produces WARN or FAIL status
- **THEN** the script SHALL exit 1

### Requirement: --patch-set flag selects versioned patch directory
The script SHALL accept a `--patch-set` argument (e.g. `v2.4-ns3.38`, `v4.2-ns3.47`) that selects which `scripts/patches/ns3/<version>/` directory to use for the dry-run check.

#### Scenario: Unknown patch set emits clear error
- **WHEN** `--patch-set v99.0-ns3.99` is passed but that directory does not exist
- **THEN** the script SHALL exit 1 with a message listing available patch sets
