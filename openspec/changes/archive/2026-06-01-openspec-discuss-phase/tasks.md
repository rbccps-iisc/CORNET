## 1. Skill File — openspec-discuss

- [x] 1.1 Create `.github/skills/openspec-discuss/SKILL.md` with invocation trigger (`/opsx:discuss` and `openspec discuss`)
- [x] 1.2 Write the skill description: "Run adversarial discuss phase on an OpenSpec change — critiques the proposal, generates counter-designs, and records decisions before apply"
- [x] 1.3 Write the step-by-step skill instructions:
  - Step 1: Identify active change (from argument or `openspec status`)
  - Step 2: Assert `proposal.md` exists; halt with guidance if not
  - Step 3: Read `proposal.md`; read `design.md` if present; read all specs under `specs/` if present
  - Step 4: If `discussion.md` exists, ask user: overwrite or append new round
  - Step 5: Invoke adversarial agent (self-dialogue): generate Challenge Report (≤5 challenges, cited)
  - Step 6: Generate Counter-Designs section (1–3 alternatives with trade-offs + recommendation)
  - Step 7: Generate Decisions Made section (synthesized from challenge responses + endorsed/modified design)
  - Step 8: If `--compressed` flag or caveman mode requested, apply caveman compression to all sections
  - Step 9: Write `discussion.md` to the change directory
  - Step 10: Print summary — N challenges raised, M counter-designs, K decisions made
- [x] 1.4 Ensure skill file follows the existing `openspec-propose/SKILL.md` heading and structure conventions

## 2. Prompt File — opsx-discuss

- [x] 2.1 Create `.github/prompts/opsx-discuss.prompt.md` with short trigger text
- [x] 2.2 Write the prompt body: one-paragraph summary of what the discuss phase does and when to use it
- [x] 2.3 Add invocation examples: `/opsx:discuss`, `/opsx:discuss --compressed`, `/opsx:discuss --change <name>`
- [x] 2.4 Cross-reference the `openspec-discuss` skill in the prompt frontmatter

## 3. Apply Skill Update

- [x] 3.1 Read existing `.github/skills/openspec-apply-change/SKILL.md`
- [x] 3.2 Add a pre-flight step at the start of the apply instructions: "If `discussion.md` exists in the change directory, read its `## Decisions Made` section; treat each listed decision as a binding implementation constraint for this apply run"
- [x] 3.3 Verify the added step does not break the existing apply flow for changes without `discussion.md`

## 4. discussion.md Artifact Schema (openspec/config.yaml)

- [x] 4.1 Read `openspec/config.yaml` to understand the existing `spec-driven` schema structure
- [x] 4.2 Add `discussion` as an optional artifact entry (does NOT appear in `applyRequires`)
- [x] 4.3 Set `outputPath: discussion.md`, `optional: true`, `description: "Adversarial discussion artifact — challenges, counter-designs, and decisions"`
- [x] 4.4 Run `openspec status` on a test change to verify the schema loads without errors

## 5. opsx-discuss Prompt Registration

- [x] 5.1 Verify `.github/prompts/opsx-discuss.prompt.md` is discoverable via the VS Code prompts panel
- [x] 5.2 Check that the prompt appears in `openspec list` or equivalent status output alongside `opsx-propose`, `opsx-apply`, `opsx-archive`

## 6. Documentation

- [x] 6.1 Update `docs/ARCHITECTURE.md` to include the discuss phase in the OpenSpec workflow diagram/description
- [x] 6.2 Add a `## Discuss Phase` section to `docs/GETTING_STARTED.md` explaining when to use it and what it produces
- [x] 6.3 Add a one-line mention in `README.md` OpenSpec section (if applicable)

## 7. Validation

- [x] 7.1 Run `/opsx:discuss` on the `openspec-discuss-phase` change itself as a self-referential smoke test
- [x] 7.2 Verify `discussion.md` is created with all three required sections
- [x] 7.3 Run `/opsx:apply` on a test change that has `discussion.md` and confirm the Decisions Made constraints are honored
- [x] 7.4 Run `/opsx:apply` on a test change without `discussion.md` and confirm no regression
- [x] 7.5 Test `--compressed` flag: verify caveman prose output, verify all three sections still present
