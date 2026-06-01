## ADDED Requirements

### Requirement: Parameter sweep declared in task config
A task config SHALL support an optional `experiment.sweep` section containing a dict of config keypaths to lists of values. The framework SHALL enumerate all combinations using cartesian product and run each as an independent variant.

#### Scenario: Sweep config expands into N variants
- **WHEN** the config contains:
  ```yaml
  experiment:
    sweep:
      network.ns3.numerology: [1, 2, 3]
      network.ns3.bandwidth: [20, 40]
  ```
- **THEN** the orchestrator SHALL produce 6 variant configs (3 × 2)
- **THEN** each variant SHALL be assigned a `variant_id` of the form `numerology=1_bandwidth=20`
- **THEN** each variant's results SHALL be written to `experiment.output_dir/<variant_id>/`

#### Scenario: Sweep with no cross-product axes
- **WHEN** `experiment.sweep` has only one keypath with N values
- **THEN** exactly N variants SHALL be produced

#### Scenario: Sweep with repeats
- **WHEN** `experiment.sweep.repeats: 3` is set
- **THEN** each combination SHALL run 3 times with variant_ids `<combo>_run1`, `<combo>_run2`, `<combo>_run3`

#### Scenario: No sweep runs single experiment
- **WHEN** `experiment.sweep` is absent
- **THEN** the orchestrator SHALL run exactly one experiment with `variant_id: "default"`

### Requirement: Sequential execution is the default; parallel is opt-in
Sweep variants SHALL run sequentially by default. Parallel execution SHALL only be enabled when `experiment.sweep.parallel: true` is set.

#### Scenario: Sequential sweep runs one variant at a time
- **WHEN** `experiment.sweep.parallel` is absent or false
- **THEN** each variant SHALL complete (stop + collect) before the next starts
- **THEN** only one Gazebo instance and one network topology SHALL be active at any time

#### Scenario: Parallel sweep assigns isolated ROS_DOMAIN_IDs
- **WHEN** `experiment.sweep.parallel: true`
- **THEN** each variant subprocess SHALL receive a unique `ROS_DOMAIN_ID` environment variable (base + variant index)
- **THEN** the orchestrator SHALL verify no `ROS_DOMAIN_ID` value exceeds 101 (ROS 2 limit)

#### Scenario: Sweep replaces batch runner scripts
- **WHEN** the 5-phase AoI evaluation is expressed as a sweep over `network.scheduler: [pf, edf_urllc, aoi_pf, aoi_send, mac_aoi]`
- **THEN** running `python -m framework tasks/aoi_5phase_eval` SHALL reproduce the same 5 experiment runs as `run_aoi_multiue_evaluation.py` without any custom batch script
