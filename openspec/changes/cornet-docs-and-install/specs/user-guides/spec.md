## ADDED Requirements

### Requirement: Five user guides covering task-author and plugin-developer workflows
`docs/guides/` SHALL contain five Markdown guides: `writing-a-task.md`, `custom-plugin.md`, `custom-eval-tool.md`, `parameter-sweep.md`, and `middleware.md`. Each guide SHALL be self-contained and link to relevant reference docs.

#### Scenario: Writing-a-task guide covers the full workflow
- **WHEN** a new researcher reads `docs/guides/writing-a-task.md`
- **THEN** they SHALL find: directory layout, a minimal `config.yaml` example, how to run the task, how to add an EvalTool, and how to view the leaderboard — sufficient to create and run a new task without reading source code

#### Scenario: Custom-plugin guide covers the Plugin ABC
- **WHEN** a simulator developer reads `docs/guides/custom-plugin.md`
- **THEN** they SHALL find: the five-method lifecycle contract (`configure`, `start`, `run`, `stop`, `collect`), the `ExperimentContext` fields available, and a minimal skeleton plugin implementation

#### Scenario: Parameter-sweep guide explains variant IDs
- **WHEN** a researcher reads `docs/guides/parameter-sweep.md`
- **THEN** they SHALL find: how to declare axes and repeats in config.yaml, how variant IDs are constructed, and where per-variant results are written

### Requirement: GETTING_STARTED.md links to guides
`docs/GETTING_STARTED.md` SHALL contain a "Guides" section with links to all five guide files. The existing quick-start content SHALL remain unchanged.

#### Scenario: Links are present and relative
- **WHEN** `docs/GETTING_STARTED.md` is read
- **THEN** it SHALL contain relative Markdown links to each of the five guides under `docs/guides/`
