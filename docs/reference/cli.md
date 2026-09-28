# CORNET CLI Reference

<!-- auto-generated marker: DO NOT remove — checked by docs-check CI -->

## Overview

```
python -m cornet <subcommand> [options]
# or, if installed as entry point:
cornet <subcommand> [options]
```

## Subcommands

---

### `run` — Run an experiment task

```bash
python -m cornet run tasks/<name>
# or shorthand (positional):
python -m cornet tasks/<name>
```

Loads `tasks/<name>/config.yaml`, starts all plugins, runs for `experiment.duration` seconds, invokes the eval tool (if present), and appends a leaderboard entry.

**Arguments**

| Argument | Description |
|---|---|
| `task` | Path to the task directory (containing `config.yaml`) or to the `config.yaml` file itself. |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | Experiment completed; leaderboard entry written. |
| `1` | Configuration error, plugin startup failure, or eval tool error. |

**Example**

```bash
python -m cornet tasks/pendulum_nr_control
```

---

### `view` — View experiment leaderboard

```bash
python -m cornet view tasks/<name> [--higher-is-better]
```

Reads `tasks/<name>/leaderboard.json` and prints a `rich` table sorted by `experiment.primary_metric`.

**Arguments**

| Argument | Flag | Default | Description |
|---|---|---|---|
| `task` | — | — | Path to the task directory. |
| `--higher-is-better` | flag | `false` | Sort leaderboard descending (higher metric = better rank). Overrides `experiment.higher_is_better` in config. |

**Example**

```bash
python -m cornet view tasks/pendulum_nr_control
python -m cornet view tasks/uav_wifi_control --higher-is-better
```

---

### `ui` — Open the interactive web UI

```bash
python -m cornet ui tasks/<name> [--port PORT]
```

Starts a local FastAPI server and opens the leaderboard in the browser with live-reloading charts.

**Arguments**

| Argument | Flag | Default | Description |
|---|---|---|---|
| `task` | — | — | Path to the task directory. |
| `--port` | `--port N` | random free port | TCP port to bind the web server. |

**Example**

```bash
python -m cornet ui tasks/pendulum_nr_control
python -m cornet ui tasks/uav_wifi_control --port 8080
```

---

### `research` — Run an auto-research session

```bash
python -m cornet research "<question>" [--task tasks/<name>]
python -m cornet research --resume <session-id> [--task tasks/<name>]
```

Runs the phases intake, brief, critique, compile, experiment loop, and report. Session state is `tasks/<name>/research/session.json`. The default task is `tasks/pendulum_nr_control`.

The live session needs `pip install -e ".[research]"` and `CURSOR_API_KEY`. Agents are local. Their tool list is the research custom tools. `shell`, `edit`, and `task` are not offered.

**Arguments**

| Argument | Flag | Default | Description |
|---|---|---|---|
| `question` | — | — | Research question. Required unless `--resume` is set. |
| `--task` | `--task PATH` | `tasks/pendulum_nr_control` | Task directory the session scores. |
| `--resume` | `--resume ID` | — | Resume a session by its id. |

**Example**

```bash
export NS3_DIR="$HOME/ns-3-dev"
export CURSOR_API_KEY="..."
python -m cornet research "Which scheduler lowers mean AoI?" --task tasks/pendulum_nr_control
```

---

## Global flags

```
python -m cornet --help        # show help
python -m cornet --version     # show version (if installed via pip)
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NS3_DIR` | `~/ns-3-dev` | Path to the NS-3 build root used by the `ns3` network plugin. |
| `CORNET_NS3_TAG` | unset | Lane label stored on the leaderboard entry, for example `ns3-v51`. |
| `CORNET_LOG` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `CURSOR_API_KEY` | unset | Required by `research` when the agents are the Cursor SDK. |
| `CORNET_RESEARCH_MODEL` | `composer-2.5` | Model id for the researcher agent. |
| `CORNET_CRITIC_MODEL` | same as the researcher | Model id for the critic agent. |
| `CORNET_HYPOTHESIS_ID` | unset | Set by the job runner on each trial. Written to the leaderboard entry. |
| `CORNET_EXPERIMENT_SEED` | unset | Set by the job runner. Overrides `experiment.seed` for that process. |
| `CORNET_OVERRIDES` | unset | JSON object of config key paths applied to that trial. The variant id gains `+key=value`. |
| `CORNET_ROS_SETUP` | `/opt/ros/humble/setup.bash` | Setup file the Gazebo plugin sources when `ROS_DISTRO` is unset. |
