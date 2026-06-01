## ADDED Requirements

### Requirement: Idempotent per-backend install scripts
The framework SHALL provide shell scripts under `scripts/install/` for each simulator backend: `install_python.sh`, `install_ns3.sh`, `install_mininet.sh`, `install_gazebo_ros2.sh`, and `verify.sh`. Each script SHALL be idempotent — running it a second time on an already-configured system SHALL produce no changes and exit 0.

#### Scenario: Python package install is idempotent
- **WHEN** `install_python.sh` is run and `pip show cornet-framework` already succeeds
- **THEN** the script SHALL print a skip message and exit 0 without calling `pip install`

#### Scenario: NS-3 install skips full build on re-run
- **WHEN** `install_ns3.sh` is run and `$NS3_DIR/build/ns3 --version` succeeds and the sentinel file `$NS3_DIR/.cornet-patched` exists
- **THEN** the script SHALL skip cloning, building, and patching and exit 0

#### Scenario: verify.sh reports all installed components
- **WHEN** `verify.sh` is run after a complete installation
- **THEN** it SHALL print a pass/fail line for each component (Python package, NS-3, Mininet, Docker, ROS 2, Gazebo) and exit 0 if all pass

#### Scenario: verify.sh exits non-zero on missing component
- **WHEN** `verify.sh` is run and any component check fails
- **THEN** it SHALL exit 1 and clearly identify which component is missing

### Requirement: Makefile top-level entry points
The framework SHALL provide a `Makefile` at the repo root with targets: `install`, `install-python`, `install-ns3`, `install-mininet`, `install-gazebo`, `verify`, `docs`, and `docs-check`. The default `install` target SHALL install only the Python package and print guidance for backend-specific targets.

#### Scenario: make install completes the Python-only install
- **WHEN** `make install` is run in a clean environment
- **THEN** `cornet-framework` SHALL be importable and `cornet --help` SHALL succeed

#### Scenario: make docs-check fails on stale generated docs
- **WHEN** `cornet/config/schema.py` has been edited with new fields but `make docs` has not been re-run
- **THEN** `make docs-check` SHALL exit 1 with a message indicating the generated file is stale

### Requirement: Install script calls compat check before patching NS-3
`install_ns3.sh` SHALL invoke `scripts/check_ns3_compat.py` before applying any patch. If the compat check exits non-zero, the install script SHALL print the compat report and exit 1 without modifying any NS-3 files.

#### Scenario: Install fails cleanly when patches are incompatible
- **WHEN** `install_ns3.sh` is run targeting a version for which no migrated patches exist
- **THEN** the script SHALL print the compat check output, including the names of failed checks, and exit 1
- **THEN** no NS-3 files SHALL be modified
