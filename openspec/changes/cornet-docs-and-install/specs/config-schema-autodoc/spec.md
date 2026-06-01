## ADDED Requirements

### Requirement: All Pydantic config models have Field descriptions
Every field in every `BaseModel` subclass in `cornet/config/schema.py` SHALL carry a `Field(description=...)` annotation. Descriptions SHALL include: purpose of the field, valid values or range where applicable, and units for numeric fields.

#### Scenario: No field is missing a description
- **WHEN** `UnifiedConfig.model_json_schema()` is called
- **THEN** every leaf property in the JSON schema SHALL contain a `"description"` key

### Requirement: Generator script produces Markdown reference
`scripts/gen_schema_docs.py` SHALL call `UnifiedConfig.model_json_schema()` and render `docs/reference/config-schema.md` as a set of per-model Markdown tables. Each table SHALL have columns: Field, Type, Default, Required, Description.

#### Scenario: Generator produces valid Markdown
- **WHEN** `python scripts/gen_schema_docs.py` is run
- **THEN** `docs/reference/config-schema.md` SHALL be created or overwritten with a valid Markdown file containing one `## <ModelName>` section per Pydantic model

#### Scenario: Generator is runnable without extra dependencies
- **WHEN** the generator is run in an environment with only `pip install -e .` completed
- **THEN** it SHALL succeed using only the stdlib and the `cornet` package

### Requirement: CI docs-check enforces freshness
`make docs-check` SHALL run the generator and then `git diff --exit-code docs/reference/config-schema.md`. If the file is stale (generator output differs from committed file), `make docs-check` SHALL exit 1.

#### Scenario: Stale docs detected in CI
- **WHEN** a new field is added to `schema.py` but `make docs` is not re-run before commit
- **THEN** `make docs-check` SHALL exit 1 with a diff showing the missing field
