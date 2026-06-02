## ADDED Requirements

### Requirement: patch-set-env-var
`install_ns3.sh` reads `PATCH_SET` (default: `v2.4-ns3.38`). The value
determines the NS-3 tag, NR tag, patch directory, and sentinel filename.

#### Scenario: default install targets v2.4
- **WHEN** `bash scripts/install/install_ns3.sh` is run without any env vars
- **THEN** NS-3 3.38 is cloned, NR v2.4 is cloned, `v2.4-ns3.38` patches are applied
- **THEN** sentinel `.cornet-patched-v2.4` is written to `$NS3_DIR/contrib/nr/`

#### Scenario: v4.2 install targets correct versions
- **WHEN** `PATCH_SET=v4.2-ns3.47 NS3_DIR=~/ns-3-dev-v47 bash scripts/install/install_ns3.sh`
- **THEN** NS-3 3.47 is cloned, NR v4.2 is cloned, `v4.2-ns3.47` patches are applied
- **THEN** sentinel `.cornet-patched-v4.2` is written to `$NS3_DIR/contrib/nr/`

#### Scenario: idempotency gate is patch-set-specific
- **WHEN** both `.cornet-built` and `.cornet-patched-v4.2` exist in `$NS3_DIR`
- **THEN** `install_ns3.sh` with `PATCH_SET=v4.2-ns3.47` exits early without re-patching
- **WHEN** `.cornet-patched-v4.2` is absent but `.cornet-patched-v2.4` exists
- **THEN** the script does NOT treat the tree as already patched for v4.2

### Requirement: makefile-version-targets
The Makefile exposes named targets for each NS-3 version.

#### Scenario: install v2.4 via make
- **WHEN** `make install-ns3-v24` is run
- **THEN** `NS3_DIR=~/ns-3-dev-v24 PATCH_SET=v2.4-ns3.38` is passed to `install_ns3.sh`

#### Scenario: install v4.2 via make
- **WHEN** `make install-ns3-v47` is run
- **THEN** `NS3_DIR=~/ns-3-dev-v47 PATCH_SET=v4.2-ns3.47` is passed to `install_ns3.sh`

#### Scenario: legacy make install-ns3 unchanged
- **WHEN** `make install-ns3` is run
- **THEN** behaviour is identical to before this change (v2.4, default NS3_DIR)

### Requirement: version-mismatch-guard-extended
The D4 version mismatch guard in `install_ns3.sh` must also cover v4.2.

#### Scenario: existing NR v4.1 when targeting v4.2
- **WHEN** `$NS3_DIR/contrib/nr` contains NR v4.1 and `PATCH_SET=v4.2-ns3.47`
- **THEN** the script exits 1 with a clear message identifying the version conflict
