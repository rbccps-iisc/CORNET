## Context

OpenSpec's current three-phase workflow (`propose → apply → archive`) is linear and trusting: once a proposal is written, implementation begins immediately. There is no structured mechanism to challenge assumptions, explore alternatives, or document decisions before code is committed.

GSD Core (`open-gsd/gsd-core`) proves the value of a `discuss` phase: it surfaces gray areas — API shapes, data models, error-handling strategies — that a one-pass proposal leaves underspecified. Without this, the `apply` phase frequently hits mid-implementation pivots, ambiguous requirements, or design regressions that cost more to fix than prevent.

This design adds a `discuss` phase to OpenSpec with an adversarial AI sub-role that both critiques the proposal and generates counter-designs, then produces a `discussion.md` artifact that the `apply` phase consumes.

The workflow lives entirely in `.github/skills/` and `.github/prompts/` — no changes to the CORNET framework code are required.

## Goals / Non-Goals

**Goals:**
- Define the `discuss` phase command (`/opsx:discuss`) as a new skill + prompt
- Specify the `discussion.md` artifact schema (sections, content, format)
- Define the adversarial agent's two-output structure: critique + counter-design
- Specify how `apply` reads `discussion.md` when it exists
- Integrate optional caveman-mode compression into the discuss output
- Keep the phase optional: `propose → apply → archive` must work without it

**Non-Goals:**
- Adding real-time multi-agent debate or back-and-forth dialogue
- Persistent adversarial state across sessions
- Changing the OpenSpec CLI tool itself (only `.github/skills/` and `.github/prompts/`)
- Enforcing discuss as a required gate before apply

## Decisions

### D1: Discuss phase placement — between propose and apply

**Decision**: `/opsx:discuss` reads the change's `proposal.md` (and `design.md` + specs if they exist) and produces `discussion.md`. Apply reads `discussion.md` when present but doesn't require it.

**Rationale**: Aligns with GSD Core's model. The discuss phase is most valuable after the proposal is written but before any implementation decisions are locked. Making it optional (not a hard gate) preserves backward compatibility.

**Alternative considered**: Hard gate — `apply` refuses to run without `discussion.md`. Rejected: too disruptive, adds friction for small changes.

---

### D2: Two-output adversarial structure

**Decision**: The discuss skill produces exactly two sections in `discussion.md`:
1. **Challenge Report** — structured critique organized by assumption, risk category (correctness, performance, integration, security), failure mode, and mitigation
2. **Counter-Designs** — 1–3 alternative approaches with trade-offs, pro/con analysis, and a recommendation

**Rationale**: Separating critique from alternatives makes the output actionable. The challenge report answers "what could go wrong?"; the counter-designs answer "what else could we do?". Together they frame the decision space without prescribing an outcome.

**Alternative considered**: A single free-form critique. Rejected: too unstructured to be useful as apply-phase context.

---

### D3: Caveman-mode integration

**Decision**: The discuss skill accepts an optional `--compressed` / caveman-mode flag. When enabled, the `discussion.md` output uses caveman-compressed prose (short declarative statements, no filler). This is the same compression style as the existing `caveman` skill.

**Rationale**: Discuss artifacts can be verbose. Caveman mode keeps them scannable and token-efficient for downstream apply-phase context loading.

**Alternative considered**: Always compress. Rejected: full prose is easier for human review; compression should be opt-in.

---

### D4: Skill + prompt file structure

**Decision**: Implement as:
- `.github/skills/openspec-discuss/SKILL.md` — the invocable skill with detailed step-by-step instructions
- `.github/prompts/opsx-discuss.prompt.md` — the short trigger prompt (mirrors the pattern of `opsx-propose.prompt.md`)

Both files follow the existing OpenSpec skill/prompt conventions exactly.

---

### D5: Apply skill update

**Decision**: Add a single step at the top of `openspec-apply-change/SKILL.md`: "If `discussion.md` exists in the change directory, read it first and use the `Decisions Made` section as implementation constraints."

**Rationale**: Minimal invasive change. The discuss artifact provides a decision record; apply should honor it without being tightly coupled.

## Risks / Trade-offs

- **[Risk] Over-reliance on AI adversary** — AI-generated critiques may be shallow or hallucinated. → Mitigation: The skill instructs the AI to cite specific sections of the proposal when raising challenges; uncited challenges are flagged as speculative.
- **[Risk] Bloated discussion.md** — Verbose artifact inflates apply-phase context. → Mitigation: Caveman mode + explicit length caps per section (5 challenges max, 3 counter-designs max).
- **[Risk] Duplicate critique / propose overlap** — Some challenge material may repeat what's already in `design.md`. → Mitigation: Skill instruction tells the AI to skip anything already addressed in an existing design decision.
- **[Risk] Schema drift** — Adding `discussion.md` to `openspec/config.yaml` requires schema maintenance. → Mitigation: Mark the artifact as `optional: true` and do not add it to `applyRequires`.

## Open Questions

- Should the discuss skill be invokable multiple times on the same change (iterative discussion rounds)?
- Should caveman mode be a skill-level flag or a project-wide config setting in `openspec/config.yaml`?
- Is a `--focus <area>` flag (e.g., `--focus security`) useful for targeted adversarial runs?
