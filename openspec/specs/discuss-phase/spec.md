## ADDED Requirements

### Requirement: Discuss command is invocable on any active change
The system SHALL provide a `/opsx:discuss` command (and `openspec-discuss` skill) that can be invoked on any change that has at least a `proposal.md` artifact present.

#### Scenario: Discuss runs on a change with only proposal
- **WHEN** `/opsx:discuss` is invoked and the change has `proposal.md` but no `design.md`
- **THEN** the skill reads `proposal.md` and proceeds with discussion using only that context

#### Scenario: Discuss runs on a change with all artifacts
- **WHEN** `/opsx:discuss` is invoked and the change has `proposal.md`, `design.md`, and specs
- **THEN** the skill reads all available artifacts before generating the discussion

#### Scenario: Discuss is blocked when no proposal exists
- **WHEN** `/opsx:discuss` is invoked and no `proposal.md` exists in the change directory
- **THEN** the skill SHALL halt and instruct the user to run `/opsx:propose` first

### Requirement: Discuss phase produces a discussion.md artifact
The system SHALL write a `discussion.md` file to the change directory upon successful completion of the discuss phase.

#### Scenario: Output file is created
- **WHEN** the discuss phase completes successfully
- **THEN** `openspec/changes/<name>/discussion.md` SHALL exist and be non-empty

#### Scenario: Idempotent re-runs
- **WHEN** `/opsx:discuss` is invoked on a change that already has `discussion.md`
- **THEN** the skill SHALL warn the user that a prior discussion exists and ask whether to overwrite or append a new round

### Requirement: Discuss phase is optional in the apply workflow
The system SHALL allow the `apply` phase to proceed without a `discussion.md` being present.

#### Scenario: Apply proceeds without discussion
- **WHEN** `/opsx:apply` is invoked and no `discussion.md` exists
- **THEN** the apply phase SHALL proceed normally with no error or warning

#### Scenario: Apply loads discussion context when available
- **WHEN** `/opsx:apply` is invoked and `discussion.md` exists
- **THEN** the apply skill SHALL read the `Decisions Made` section of `discussion.md` and treat those decisions as implementation constraints throughout the apply phase

### Requirement: Discuss phase supports caveman-mode compression
The system SHALL accept an optional compressed-output flag that applies caveman-style prose compression to the `discussion.md` artifact.

#### Scenario: Compressed output on request
- **WHEN** `/opsx:discuss --compressed` is invoked (or the user explicitly requests caveman mode)
- **THEN** `discussion.md` SHALL be written in caveman-compressed prose: short declarative statements, no filler, bullet-heavy

#### Scenario: Default output is full prose
- **WHEN** `/opsx:discuss` is invoked without `--compressed`
- **THEN** `discussion.md` SHALL be written in standard readable prose
