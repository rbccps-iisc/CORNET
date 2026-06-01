## Why

The current OpenSpec workflow (`propose → apply → archive`) moves directly from a written proposal into implementation. This skips a critical decision-making gap: unchallenged assumptions, unexplored alternatives, and gray-area design questions that emerge when a proposal is stress-tested. GSD Core's `discuss` phase demonstrates the value of capturing these decisions *before* planning begins — the output feeds directly into implementation and prevents costly course-corrections mid-apply.

## What Changes

- Adds a new `discuss` phase that sits between `propose` and `apply`
- Introduces a new `openspec-discuss` skill (`/opsx:discuss`) and companion prompt file
- Adds a `discussion.md` artifact to the spec-driven schema that captures decisions, challenges, and alternatives
- The adversarial role generates two outputs: (1) structured critique / failure-mode analysis and (2) counter-proposals or alternative designs
- Integrates optional caveman-mode compression for token-efficient discussion artifacts
- Updates `openspec-apply-change` skill to reference `discussion.md` context when present

## Capabilities

### New Capabilities

- `discuss-phase`: A structured adversarial discussion command (`/opsx:discuss`) that reads the current change's `proposal.md`, `design.md`, and any existing specs, then produces a `discussion.md` artifact containing: challenge questions, failure-mode analysis, alternative designs, and final decisions made
- `adversarial-critique`: The AI's devil's advocate sub-role that systematically challenges every major assumption in the proposal — surfaces edge cases, integration conflicts, and hidden dependencies before code is written
- `discussion-artifact`: A new `discussion.md` schema artifact type with sections for: challenges raised, alternatives considered (and why rejected), risks and mitigations, and compressed implementation decisions

### Modified Capabilities

- `plugin-orchestrator`: No spec-level requirement changes; discuss phase will enrich the apply context but does not alter the plugin contract

## Impact

- **New files**: `.github/skills/openspec-discuss/SKILL.md`, `.github/prompts/opsx-discuss.prompt.md`
- **Schema addition**: `discussion.md` artifact added to `openspec/config.yaml` spec-driven schema (optional artifact, does not block apply)
- **Apply skill update**: `openspec-apply-change/SKILL.md` gains a step to read `discussion.md` if present
- **No breaking changes**: The discuss phase is optional; all existing `propose → apply → archive` flows remain valid
