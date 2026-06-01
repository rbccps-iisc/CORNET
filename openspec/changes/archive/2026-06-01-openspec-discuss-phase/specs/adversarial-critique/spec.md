## ADDED Requirements

### Requirement: Adversarial critique generates a structured Challenge Report
The system SHALL generate a Challenge Report as the first section of `discussion.md`. The Challenge Report SHALL contain up to five challenges, each tied to a specific section or assumption in the input artifacts.

#### Scenario: Challenge cites source
- **WHEN** a challenge is generated
- **THEN** each challenge SHALL reference the specific proposal section, design decision, or spec requirement it is challenging (e.g., "Proposal §What Changes, bullet 3")

#### Scenario: Uncited challenges are flagged
- **WHEN** the adversarial agent cannot cite a specific source for a challenge
- **THEN** the challenge SHALL be marked `[speculative]` and de-prioritized

#### Scenario: Challenge limit enforced
- **WHEN** the adversarial agent identifies more than five candidate challenges
- **THEN** it SHALL select the five with the highest estimated impact (correctness > security > performance > integration)

### Requirement: Adversarial critique generates risk-categorized failure modes
Each challenge in the Challenge Report SHALL include a failure-mode analysis categorized by type.

#### Scenario: Challenge includes failure mode and category
- **WHEN** a challenge is written
- **THEN** it SHALL include: the assumption being challenged, the failure mode if the assumption is wrong, the risk category (correctness | security | performance | integration | ux), and a proposed mitigation

#### Scenario: No duplicate categories without justification
- **WHEN** two challenges share the same risk category
- **THEN** the second SHALL explicitly explain why the risk warrants a separate entry

### Requirement: Adversarial critique generates Counter-Designs
The system SHALL generate a Counter-Designs section as the second section of `discussion.md`. The Counter-Designs section SHALL contain 1–3 alternative designs, each with trade-offs, pros/cons, and a recommendation.

#### Scenario: Counter-design is meaningfully different
- **WHEN** a counter-design is generated
- **THEN** it SHALL differ from the proposed design in at least one architectural decision (not just in implementation detail)

#### Scenario: Counter-design limit enforced
- **WHEN** the adversarial agent generates counter-designs
- **THEN** no more than three SHALL be included in `discussion.md`

#### Scenario: Recommendation is present
- **WHEN** multiple counter-designs are generated
- **THEN** the section SHALL conclude with a single sentence recommendation: either endorse the original proposal or select one counter-design, with a one-line rationale

### Requirement: Adversarial agent skips already-addressed concerns
The system SHALL not repeat challenges for decisions already explicitly addressed in an existing `design.md`.

#### Scenario: Challenge skipped when addressed
- **WHEN** a candidate challenge maps to an assumption that is already resolved in `design.md` under a `Decisions` sub-section
- **THEN** that challenge SHALL be omitted from the Challenge Report

#### Scenario: Partial address triggers a focused challenge
- **WHEN** a design decision in `design.md` addresses a concern but its mitigation is incomplete
- **THEN** the adversarial agent MAY generate a focused challenge on the mitigation gap, citing the specific design decision
