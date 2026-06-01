## MODIFIED Requirements

### Requirement: Unified YAML config schema for network and robot deployment
The framework SHALL define a single Pydantic v2 model (`UnifiedConfig`) in `cornet/config/schema.py` that validates a task config YAML covering both `network` and `robot` top-level sections. The schema SHALL be the authoritative definition for all new task configs. The `config_manager.load_unified()` function SHALL raise a descriptive `ConfigValidationError` listing every field violation when validation fails. When a YAML is missing or has the wrong `_schema` tag AND contains any of the unified-schema sentinel keys (`robot`, `experiment`, `sweep`), the error message SHALL include the suggestion `"Did you forget to add '_schema: unified-v1' at the top?"`. Every field in every model SHALL carry a `Field(description=...)` annotation that appears in the JSON schema output of `UnifiedConfig.model_json_schema()`.

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

#### Scenario: Unified-looking YAML without _schema tag gives helpful error
- **WHEN** a YAML contains `robot:` or `experiment:` or `sweep:` at the top level but no `_schema: unified-v1` tag
- **THEN** `load_unified()` SHALL raise `ConfigValidationError` whose message includes `"Did you forget to add '_schema: unified-v1' at the top?"`

#### Scenario: All fields have descriptions in JSON schema
- **WHEN** `UnifiedConfig.model_json_schema()` is called after this change is applied
- **THEN** every property in the schema's `properties` and `$defs` SHALL contain a `"description"` key with a non-empty string
