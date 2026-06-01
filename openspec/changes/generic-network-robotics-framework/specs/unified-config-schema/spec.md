## ADDED Requirements

### Requirement: Unified YAML config schema for network and robot deployment
The framework SHALL define a single Pydantic v2 model (`UnifiedConfig`) in `framework/config/schema.py` that validates a task config YAML covering both `network` and `robot` top-level sections. The schema SHALL be the authoritative definition for all new task configs. The `config_manager.load_unified()` function SHALL raise a descriptive `ConfigValidationError` listing every field violation when validation fails.

#### Scenario: Valid unified config loads without error
- **WHEN** a YAML file contains valid `network`, `robot`, and `experiment` sections matching the schema
- **THEN** `config_manager.load_unified(path)` SHALL return a populated `UnifiedConfig` instance with no exceptions

#### Scenario: Missing required field raises descriptive error
- **WHEN** the YAML is missing `network.type`
- **THEN** `load_unified()` SHALL raise `ConfigValidationError` with a message identifying the missing field by dotted path (e.g. `network.type`)

#### Scenario: Network type validation
- **WHEN** `network.type` is set to a value other than `ns3`, `mininet`, or `ns3+mininet`
- **THEN** `load_unified()` SHALL raise `ConfigValidationError` with the allowed values listed

#### Scenario: Robot section is optional
- **WHEN** the YAML omits the `robot` section entirely
- **THEN** `load_unified()` SHALL succeed and set `config.robot` to `None`
- **THEN** the orchestrator SHALL skip all robot plugins

### Requirement: Backward-compatible loading of legacy scenario YAMLs
The `config_manager` SHALL continue to load all existing `scenarios/*.yaml` files using the legacy loader path without any changes to those files.

#### Scenario: Legacy scenario YAML loads via fallback
- **WHEN** a YAML file lacks a `network.type` field but has the legacy `network.nr` or `network.lte` structure
- **THEN** `config_manager.load(path)` SHALL use the legacy loader and return the existing config dict
- **THEN** no `ConfigValidationError` SHALL be raised

#### Scenario: Explicit new-format detection
- **WHEN** a YAML contains `_schema: unified-v1` at the top level
- **THEN** `config_manager.load(path)` SHALL use `load_unified()` exclusively and not fall back to the legacy loader
