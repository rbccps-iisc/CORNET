---
name: openspec-discuss
description: Run adversarial discuss phase on an OpenSpec change — critiques the proposal, generates counter-designs, and records decisions before apply. Use when the user wants to stress-test a proposal before implementation starts.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

Run adversarial discuss phase on an OpenSpec change — critiques the proposal, generates counter-designs, and records decisions before apply.

The discuss phase sits **between `propose` and `apply`**. It is optional but recommended for any non-trivial change. It produces a `discussion.md` artifact that the apply phase reads as binding implementation constraints.

When done, run `/opsx:apply` to start implementation.

---

**Input**: Optionally specify a change name (e.g., `/opsx:discuss add-auth`). Optionally append `--compressed` to request caveman-mode output. If no name is provided, infer from context or prompt.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user recently mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` and use the **AskUserQuestion tool** to let the user select

   Always announce: "Using change: <name>"

2. **Assert proposal exists**

   Check whether `openspec/changes/<name>/proposal.md` exists.
   - If it does **not** exist: halt and tell the user to run `/opsx:propose` first
   - If it exists: proceed

3. **Read all available artifacts**

   Read the following files if they exist in `openspec/changes/<name>/`:
   - `proposal.md` (required)
   - `design.md` (optional — read if present)
   - All spec files under `specs/**/*.md` (optional — read if present)

   Use `openspec status --change "<name>" --json` to enumerate completed artifacts and their paths.

4. **Check for existing discussion.md**

   If `openspec/changes/<name>/discussion.md` already exists:
   - Use the **AskUserQuestion tool** to ask:
     > "A prior `discussion.md` exists for this change. What would you like to do?"
     - Option A: Overwrite — start a fresh discussion (replaces the file)
     - Option B: Append — add a new round below the existing content
   - Remember the choice for step 9.

5. **Detect compressed mode**

   Check whether `--compressed` was passed or whether the user explicitly requested caveman mode in the conversation. Set an internal flag for step 9.

6. **Generate Challenge Report (adversarial role)**

   Act as a structured adversarial reviewer of the proposal. Generate **up to 5 challenges** against the proposal (and design/specs if available).

   For each challenge:
   - **Cite the source**: reference the specific section/decision being challenged (e.g., "Proposal §What Changes, bullet 2" or "Design §D3")
   - **State the assumption** being made
   - **Describe the failure mode** if the assumption is wrong
   - **Assign a risk category**: `correctness` | `security` | `performance` | `integration` | `ux`
   - **Propose a mitigation**

   Rules:
   - Only include challenges that cite a specific source; mark unsourced challenges `[speculative]`
   - Skip challenges already fully addressed by an explicit decision in `design.md`
   - If more than 5 candidates exist, prioritize: correctness > security > performance > integration > ux
   - If a design decision partially addresses a concern, you MAY raise a focused challenge on the mitigation gap

7. **Generate Counter-Designs section (adversarial role)**

   Generate **1 to 3 alternative designs** that meaningfully differ from the proposed approach in at least one architectural decision.

   For each counter-design:
   - Give it a short name
   - Describe the key architectural difference from the proposal
   - List pros and cons
   - Note trade-offs

   End the section with a single **Recommendation**: either endorse the original proposal or select one counter-design, with a one-sentence rationale.

8. **Generate Decisions Made section**

   Synthesize the outcomes of steps 6–7 into concrete implementation constraints.

   For each decision (D1, D2, ...):
   - **Decision**: one sentence stating what was decided
   - **Rationale**: one sentence explaining why

   At minimum, include one entry endorsing or modifying the original proposal's approach, even if no major challenges were found.

9. **Write discussion.md**

   Based on the choice from step 4 (or "overwrite" if file did not exist):

   **Overwrite or first run** — write the file with this structure:
   ```
   # Discussion: <change-name>

   ## Challenge Report

   ### Challenge 1: <title>
   - **Source**: <citation>
   - **Assumption**: <what the proposal assumes>
   - **Failure mode**: <what happens if wrong>
   - **Risk category**: <category>
   - **Mitigation**: <proposed fix>

   [... up to 5 challenges ...]

   ## Counter-Designs

   ### Option 1: <name>
   <description of architectural difference>

   **Pros**: ...
   **Cons**: ...
   **Trade-offs**: ...

   [... up to 3 options ...]

   **Recommendation**: <one sentence>

   ## Decisions Made

   - **D1**: <decision statement> — *<rationale>*
   [... more decisions ...]
   ```

   **Append (new round)** — append below existing content:
   ```
   ---

   ## Round N

   ## Challenge Report
   [...]

   ## Counter-Designs
   [...]

   ## Decisions Made
   [...]
   ```

   **If compressed mode is active**: apply caveman-style compression to all prose — short declarative statements, bullet-heavy, no filler. All three required sections must still be present.

10. **Print summary**

    Show:
    - Change name and artifact path
    - N challenges raised
    - M counter-designs generated (and which was recommended)
    - K decisions recorded
    - Next step: "Run `/opsx:apply` to implement with these constraints, or `/opsx:propose` to revise the proposal first."

**Output**

```
## Discuss: <change-name>

Reading artifacts... ✓

Running adversarial review...
  Challenge Report: 4 challenges (1 correctness, 2 integration, 1 performance)
  Counter-Designs: 2 alternatives generated
  Recommendation: original proposal endorsed with D2 amendment

Writing discussion.md... ✓

## Decisions Made
- D1: ...
- D2: ...

discussion.md written to openspec/changes/<change-name>/discussion.md

Run /opsx:apply to implement with these constraints.
```

**Guardrails**
- Always read proposal.md before generating challenges — never generate from memory alone
- Challenges must cite specific sections; mark uncited challenges `[speculative]`
- Do not repeat challenges already addressed in design.md
- Counter-designs must differ architecturally, not just in implementation detail
- Decisions Made must contain at least one entry
- The `--compressed` flag affects prose style only — never omit required sections
- If no proposal.md exists, halt immediately and guide the user to `/opsx:propose`
