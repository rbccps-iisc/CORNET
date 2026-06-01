# Discussion: openspec-discuss-phase

## Challenge Report

### Challenge 1: Optional artifact with no schema enforcement creates silent integration drift
- **Source**: Design §D1 (optional placement between propose and apply); Proposal §What Changes bullet 6 ("Apply skill update")
- **Assumption**: The apply skill will always check for `discussion.md` before starting implementation, making the Decisions Made constraints reliably honored.
- **Failure mode**: If the apply skill is updated independently (e.g., by a future `openspec-apply-change` version bump that regenerates the SKILL.md), the Step 0 pre-flight check may be silently dropped. Since `discussion.md` is not schema-tracked, no warning surface exists.
- **Risk category**: integration
- **Mitigation**: Pin the Step 0 addition with a distinctive comment (`# discuss-phase integration`) so future reviewers know it was intentionally added and must be preserved. Additionally, the `opsx-discuss.prompt.md` documents the apply integration explicitly, providing a secondary reference.

### Challenge 2: Adversarial agent challenges may be vacuous without domain grounding
- **Source**: Specs `adversarial-critique/spec.md` §"Adversarial critique generates a structured Challenge Report"
- **Assumption**: The AI adversarial role can generate meaningful, cited challenges from the proposal text alone.
- **Failure mode**: For domain-specific proposals (e.g., NS-3 NR numerology trade-offs), the adversarial agent may produce generic software-engineering challenges that are too shallow to be useful — "have you considered error handling?" style.
- **Risk category**: correctness
- **Mitigation**: The skill instruction explicitly requires challenges to cite specific sections. The `[speculative]` tag for uncited challenges and the 5-challenge cap together force the agent to focus on substantive concerns rather than padding with generic observations.

### Challenge 3: Caveman compression may break the three-section parse contract for the apply skill
- **Source**: Design §D3 (caveman mode); Specs `discussion-artifact/spec.md` §"Caveman-mode compression preserves structure"
- **Assumption**: Caveman-compressed output always retains `## Challenge Report`, `## Counter-Designs`, and `## Decisions Made` as exact header strings.
- **Failure mode**: If the caveman skill rewrites prose aggressively enough to alter headers (e.g., collapsing `## Decisions Made` to `## Decisions`), the apply skill's naive string search for `## Decisions Made` will fail silently — the section is present but not recognized.
- **Risk category**: correctness
- **Mitigation**: The skill instruction explicitly states that compressed mode "affects prose style only — never omit required sections." The three section headers are treated as invariant structure, not prose, and therefore must not be compressed. Add a guardrail note to this effect (already present in SKILL.md Step 9 and the Guardrails section).

### Challenge 4: Round-numbering for append mode requires manual counting, creating inconsistency risk
- **Source**: Specs `discussion-artifact/spec.md` §"discussion.md supports optional round numbering"
- **Assumption**: The skill correctly increments the round number by reading the existing file and counting prior `## Round N` headers.
- **Failure mode**: If the file has one prior round without a `## Round N` header (first-run case), the append logic may label the new content "Round 1" instead of "Round 2," producing `## Round 1` nested below unlabeled Round 1 content.
- **Risk category**: correctness
- **Mitigation**: The spec clarifies that the first round has no header (top-level sections). The append logic should treat "no round header present" as Round 1 already complete and label the new content starting at `## Round 2`.

### Challenge 5: No test coverage for the discuss skill behavior
- **Source**: Tasks §7 (Validation tasks are all manual)
- **Assumption**: Manual smoke tests are sufficient to validate the skill's output structure.
- **Failure mode**: Future edits to SKILL.md (e.g., adding new flags) may inadvertently break the `## Decisions Made` section requirement without detection, since there are no automated assertions.
- **Risk category**: integration
- **Mitigation**: The `discussion.md` artifact contract is documented both in the spec and in the config.yaml comment block. For now, manual smoke tests are acceptable given the skill is a prompt/instruction file rather than executable code. A future `tests/test_discuss_phase.py` could validate the artifact structure if needed.

## Counter-Designs

### Option 1: discussion.md as a schema-tracked artifact (strict gate)
Make `discussion.md` a first-class artifact in the `spec-driven` schema, added to `applyRequires`. The CLI would block `openspec instructions apply` until `discussion.md` exists.

**Pros**: Enforced — no silent skip; schema-aware tooling can surface it in `openspec status`
**Cons**: Breaking change to the workflow for all existing changes; adds mandatory friction to simple changes
**Trade-offs**: High enforcement value at the cost of ergonomics for one-liner changes

### Option 2: Discuss as an explicit apply flag (--skip-discuss / --with-discuss)
Rather than a separate pre-apply step, the discuss phase is embedded into the apply skill as an optional preamble triggered by `--with-discuss`.

**Pros**: Single command workflow; no separate artifact file needed
**Cons**: Mixes critique generation with implementation in one context window; can't save/revisit the critique separately; loses the "pause and review" moment
**Trade-offs**: Simpler UX but loses the deliberate decision checkpoint value

### Option 3: Current design — optional artifact, optional phase (proposed approach)
`discussion.md` is a convention artifact, not schema-tracked. The discuss phase is a separate voluntary step between propose and apply.

**Pros**: Non-breaking; preserves `propose → apply` fast path; discuss artifact is a persistent decision record; apply honors it when present
**Cons**: Not enforced; easy to skip; no CLI visibility in `openspec status`
**Trade-offs**: Best ergonomics, weakest enforcement

**Recommendation**: Endorse **Option 3** (current design). The discuss phase is most valuable when developers choose to use it — mandatory gates reduce adoption for routine changes. The persistent `discussion.md` artifact provides the decision record without blocking the fast path.

## Decisions Made

- **D1**: The discuss phase is implemented as an optional skill (`/opsx:discuss`) that produces `discussion.md` as a convention artifact, not schema-tracked. — *Balances adoption (no friction for simple changes) with value (persistent decision record for complex ones).*
- **D2**: The apply skill's Step 0 pre-flight check reads `discussion.md → Decisions Made` only when the file is present; absence is silent and non-blocking. — *Preserves the existing apply workflow for all active changes that predate this feature.*
- **D3**: Caveman compressed mode applies only to prose within sections; the three required section headers (`## Challenge Report`, `## Counter-Designs`, `## Decisions Made`) are invariant and must never be compressed or renamed. — *Ensures the apply skill's section-lookup logic remains reliable regardless of compression setting.*
- **D4**: Round-append logic must treat the absence of any `## Round N` header as "Round 1 already complete" and begin appending at `## Round 2`. — *Prevents duplicate unlabeled-round confusion on the first re-run.*
- **D5**: The 5-challenge cap and the `[speculative]` tag together enforce signal quality in the Challenge Report; the adversarial agent must cite a specific source for every non-speculative challenge. — *Prevents the discuss phase from degenerating into generic boilerplate critique.*
