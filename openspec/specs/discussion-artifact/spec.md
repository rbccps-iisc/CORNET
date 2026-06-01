## ADDED Requirements

### Requirement: discussion.md has a defined section structure
The `discussion.md` artifact SHALL follow a fixed section structure that is machine-readable by the apply phase skill.

#### Scenario: All required sections present
- **WHEN** `discussion.md` is written
- **THEN** it SHALL contain exactly these top-level sections in order:
  1. `## Challenge Report`
  2. `## Counter-Designs`
  3. `## Decisions Made`

#### Scenario: Decisions Made section is required
- **WHEN** the discuss phase completes
- **THEN** the `## Decisions Made` section SHALL be present and contain at least one decision entry, even if the original proposal is fully endorsed

### Requirement: Decisions Made section captures actionable implementation constraints
The `## Decisions Made` section of `discussion.md` SHALL summarize the outcome of the discussion in a format consumable by the apply phase.

#### Scenario: Decision entries are structured
- **WHEN** a decision is recorded
- **THEN** each entry SHALL include: the decision ID (D1, D2, ...), a one-sentence decision statement, and the rationale (one sentence)

#### Scenario: Apply phase uses decisions as constraints
- **WHEN** the apply skill reads `discussion.md`
- **THEN** it SHALL treat each entry in `## Decisions Made` as a binding implementation constraint for that change

### Requirement: discussion.md supports optional round numbering
The artifact SHALL support multiple discussion rounds on the same change by marking each round with a header.

#### Scenario: First round has no round header
- **WHEN** `discussion.md` is created for the first time
- **THEN** no round prefix is required; the standard sections are written at the top level

#### Scenario: Subsequent rounds are appended with a round header
- **WHEN** the user chooses to append a new discussion round to an existing `discussion.md`
- **THEN** a `## Round N` header SHALL precede the new `## Challenge Report`, `## Counter-Designs`, and `## Decisions Made` sections, where N is the next integer

### Requirement: Caveman-mode compression preserves structure
When compressed mode is active, `discussion.md` SHALL retain the required section structure but use caveman-compressed prose.

#### Scenario: Compressed output retains sections
- **WHEN** `discussion.md` is written in compressed mode
- **THEN** all three required sections (`## Challenge Report`, `## Counter-Designs`, `## Decisions Made`) SHALL still be present

#### Scenario: Compressed entries are shorter
- **WHEN** a challenge or counter-design entry is written in compressed mode
- **THEN** each entry SHALL be ≤3 lines of bullet prose with no filler words
