## ADDED Requirements

### Requirement: CORNET NS-3 patches committed to repo
The framework SHALL commit the three CORNET-specific NS-3 patches to `scripts/patches/ns3/v2.4-ns3.38/`: `ns3_lte_pdcp.patch`, `nr_edf_scheduler.patch`, and `nr_aoi_mac_scheduler.patch`. These SHALL be the exact patch files sourced from `rbccps-iisc/CORNET3.0` at the commit they were developed against (NR v2.4 + NS-3 3.38).

#### Scenario: Patches directory is self-contained
- **WHEN** the repo is cloned fresh on a new machine
- **THEN** `scripts/patches/ns3/v2.4-ns3.38/` SHALL contain all three patch files without requiring access to CORNET3.0

### Requirement: Versioned patch directories with README
`scripts/patches/ns3/` SHALL contain a `README.md` documenting: the compatibility matrix (which NR version pairs with which NS-3 version), which patch set is currently proven, what each patch does, and which files each patch modifies.

#### Scenario: README documents all three patches
- **WHEN** a developer reads `scripts/patches/ns3/README.md`
- **THEN** they SHALL find the target NR + NS-3 version, the three patch names, a one-line description of each patch, and the files each patch modifies

### Requirement: Migration placeholder for latest versions
`scripts/patches/ns3/v4.2-ns3.47/` SHALL exist and contain a `MIGRATION_STATUS.md` tracking the rebase status of each patch against NR v4.2 + NS-3 3.47. Each entry SHALL state: patch name, rebase status (pending / in-progress / done), blocking issues, and files requiring manual rebase.

#### Scenario: Migration status is visible in CI
- **WHEN** `make compat-check` is run against the v4.2-ns3.47 patch set before migration is complete
- **THEN** the exit code SHALL be 1 and the output SHALL reference `MIGRATION_STATUS.md`
