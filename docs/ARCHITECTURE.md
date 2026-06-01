# Architecture

## High-level flow

```text
                 python -m cornet tasks/<name>
                               |
                               v
                        +---------------+
                        | Orchestrator   |
                        +---------------+
                               |
                    +----------+-----------+
                    |                      |
                    v                      v
             +-------------+        +-------------+
             | SweepExpander|       | Task Loader |
             +-------------+        +-------------+
                    |                      |
                    +----------+-----------+
                               |
                               v
                   [PluginLifecycle x N variants]
                               |
      +------------------------+------------------------+
      |                         |                        |
      v                         v                        v
+--------------+        +---------------+        +---------------+
| NetworkPlugin|        | RobotPlugin   |        | EvalTool      |
| ns3/mininet  |        | gazebo        |        | per-task      |
+--------------+        +---------------+        +---------------+
      |                         |                        |
      +-----------+-------------+                        |
                  |                                      |
                  v                                      v
            +------------------+                 +---------------+
            | ExperimentContext|                 | leaderboard   |
            | node IPs, etc.   |                 | append-only   |
            +------------------+                 +---------------+
```

## Key pieces

- `cornet/orchestrator.py`: task resolution, lifecycle, sweep dispatch, EvalTool hook
- `cornet/plugins/`: network and robot backends
- `cornet/config/`: Pydantic schema + loader for `unified-v1`
- `cornet/sweep/`: cartesian product expansion of parameter sweeps
- `cornet/leaderboard/`: atomic writer + `rich` terminal viewer
- `tasks/<name>/`: portable experiment definitions

## Plugin lifecycle

1. `configure(config, context)`
2. `start()`
3. `run()`
4. `stop()`
5. `collect(output_dir)`

The orchestrator always calls `stop()` in reverse order for already-started plugins if any later phase raises.

## OpenSpec workflow

CORNET uses OpenSpec (spec-driven development CLI) to manage framework changes. The workflow has four phases:

```
propose  →  [discuss]  →  apply  →  archive
```

| Command | Skill | What it does |
|---|---|---|
| `/opsx:propose` | `openspec-propose` | Creates a change directory with `proposal.md`, `design.md`, `specs/`, and `tasks.md` |
| `/opsx:discuss` | `openspec-discuss` | **Adversarial discuss phase** — reads artifacts, generates `discussion.md` (Challenge Report + Counter-Designs + Decisions Made) |
| `/opsx:apply` | `openspec-apply-change` | Implements the task list; reads `discussion.md` constraints if present |
| `/opsx:archive` | `openspec-archive-change` | Archives the completed change to `openspec/changes/archive/` and syncs specs |

The discuss phase is optional. When present, `discussion.md` constraints are treated as binding during apply. Use `--compressed` for caveman-mode output.

Skills live in `.github/skills/openspec-*/SKILL.md`. Prompts in `.github/prompts/opsx-*.prompt.md`.

