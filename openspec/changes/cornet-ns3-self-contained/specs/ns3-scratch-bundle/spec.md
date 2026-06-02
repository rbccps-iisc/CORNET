## ADDED Requirements

### Requirement: versioned-scratch-layout
NS-3 scratch scripts are stored in `scripts/ns3/scratch/<patch-set>/` and
named to exactly match the `simulation_script` value in `config.yaml`.

#### Scenario: install copies scratch scripts to NS-3 build tree
- **WHEN** `install_ns3.sh` completes for patch-set `v2.4-ns3.38`
- **THEN** all files from `scripts/ns3/scratch/v2.4-ns3.38/` are copied to `$NS3_DIR/scratch/`

#### Scenario: NS-3 can find the script by name
- **WHEN** `python -m cornet tasks/pendulum_nr_control` is run with a valid NS-3 install
- **THEN** `$NS3_DIR/ns3 run remote_robot_control-default` resolves without "script not found" error

#### Scenario: v4.2 patch-set has its own scratch directory
- **WHEN** `PATCH_SET=v4.2-ns3.47` is set during install
- **THEN** files from `scripts/ns3/scratch/v4.2-ns3.47/` are copied (not the v2.4 versions)

### Requirement: script-naming-convention
Scratch script filenames follow the pattern `<task-script-base>-<profile-suffix>.cc`.
The `-default` suffix means "accepts `--networkPreset` CLI argument at runtime".

#### Scenario: new task requires a custom script
- **WHEN** a task sets `simulation_script: my_task-urllc` in `config.yaml`
- **THEN** the script file is expected at `scripts/ns3/scratch/<patch-set>/my_task-urllc.cc`
