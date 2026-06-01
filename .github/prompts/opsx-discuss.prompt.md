---
description: Run adversarial discuss phase on an OpenSpec change — stress-test a proposal before implementation starts
---

Run adversarial discuss phase on an OpenSpec change.

The discuss phase sits **between `propose` and `apply`**. It reads the current change's artifacts (proposal, design, specs) and produces a `discussion.md` file containing a structured Challenge Report, alternative Counter-Designs, and a final Decisions Made section. The apply phase reads `discussion.md` as binding implementation constraints when present.

Use this before `/opsx:apply` whenever you want to catch design flaws, stress-test assumptions, or explore alternative approaches before writing code.

---

**Invocation**

- `/opsx:discuss` — auto-detect the active change and run the discuss phase
- `/opsx:discuss <change-name>` — run the discuss phase on a specific change
- `/opsx:discuss --compressed` — produce a caveman-compressed `discussion.md` (token-efficient)
- `/opsx:discuss <change-name> --compressed` — both

**What it produces**

`openspec/changes/<name>/discussion.md` with three sections:

1. **Challenge Report** — up to 5 cited challenges, each with: assumption, failure mode, risk category, and mitigation
2. **Counter-Designs** — 1–3 alternative architectural approaches with pros/cons and a recommendation
3. **Decisions Made** — binding implementation constraints that `/opsx:apply` will honor

**Workflow**

```
/opsx:propose <name>    →  proposal.md, design.md, specs/, tasks.md
/opsx:discuss [<name>]  →  discussion.md          ← you are here
/opsx:apply [<name>]    →  implements tasks (reads discussion.md if present)
/opsx:archive [<name>]  →  archives the completed change
```

The discuss phase is **optional** — `/opsx:apply` works without it. Run it when the proposal has real design uncertainty or when you want structured critique before committing to implementation.
