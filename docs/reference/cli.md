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
| `CORNET_LOG` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
