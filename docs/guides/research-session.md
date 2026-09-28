# Research session

A research session turns a question into a brief, a critic's review, one or more experiment runs, and a report. The command is:

```bash
python -m cornet research "<question>" --task tasks/<name>
```

The first task the harness is built to score is `tasks/pendulum_nr_control`. That task runs Gazebo Classic with a pendulum and NS-3 5G NR, and the eval tool scores mean Age of Information in milliseconds (`mean_aoi_ms`). Lower is better.

This page records the session that was run on 28 September 2026, then the phases and commands that session walked.

## What that check did

The live Cursor agent was not available: `cursor-sdk` was not installed, and `CURSOR_API_KEY` was unset. Install the SDK with the research extra (`pip install -e ".[research]"`, which pins `cursor-sdk==0.1.6`). A live session still needs `CURSOR_API_KEY` in the environment. The state machine in this check ran with a scripted researcher and a scripted critic. The experiment itself was a real `python3 -m cornet run` of a copy of the pendulum task.

The copy lived outside the git checkout, at `/tmp/cornet_research_e2e`, so the run could not commit and could not append to the shipped `tasks/pendulum_nr_control/leaderboard.json`.

Gazebo never started. `ros2` failed while importing `rclpy` because the shell had not sourced ROS 2 Humble (`librcl_action.so` was not on the library path). The harness still finished: it wrote a leaderboard row, left the hypothesis open, and wrote a report. Wall time was 619 ms.

## Steps, in order

### 1. Prepare an isolated task

```bash
mkdir -p /tmp/cornet_research_e2e/tasks
cp -a tasks/pendulum_nr_control /tmp/cornet_research_e2e/tasks/
```

The shipped config uses `experiment.duration: 60.0`. The copy was shortened to `5.0` so a single trial would be a workflow check. Middleware stays off in this config, so the run does not create TUN devices and does not need `CAP_NET_ADMIN`.

### 2. Point the simulators at this machine

```bash
export PATH="$HOME/.local/bin:$PATH"
export NS3_DIR="$HOME/ns-3-dev-v51"
export CORNET_NS3_TAG=ns3-v51
export GAZEBO_MASTER_URI=http://127.0.0.1:11460
export ROS_DOMAIN_ID=42
unset DISPLAY
```

`NS3_DIR` matters here. The plugin looks at `$NS3_DIR`, then `~/ns-3-dev`. This machine's v5.1 tree is `~/ns-3-dev-v51`, and that tree already contains `scratch/remote_robot_control-default.cc`, which is the pendulum script. `PATH` includes the user-local CMake, which `./ns3` needs.

This shell left ROS 2 unloaded. That is why step 7 failed on 28 September. The Gazebo plugin now sources `/opt/ros/humble/setup.bash` itself when `ROS_DISTRO` is unset. Set `CORNET_ROS_SETUP` to use a different setup file. Sourcing Humble in the shell still works and is skipped when `ROS_DISTRO` is already set.

### 3. Open the session

The driver called `run_session` on the copied task with the question "Does one short pendulum run record mean AoI?". The session id printed first:

```text
0d2a94f2
```

`tasks/pendulum_nr_control/research/session.json` was created with phase `intake`, then moved to `brief`. The default budget is 40 trials, 3600 simulated seconds, 8 wall-clock hours, and 40 agent runs.

### 4. Brief

The researcher reply was a YAML brief. The harness validated it, wrote `research/brief.yaml`, and appended the hypothesis to `research/hypotheses.jsonl` with status `open`.

The brief named one independent variable, `network.schedulerType: [edf]`, and one dependent variable, `mean_aoi_ms`. `repeats` was 5, which is the minimum the critic's deterministic checks allow. `lane` was `v5.1-ns3.48`. There was no catalogue `scenario`, so the compile phase did not compose a new task.

A brief is rejected when a hypothesis has no falsification, or when an independent variable sets inter-site distance (`isd_m`). ISD comes from the deployment.

### 5. Critique

The critic reply was a Challenge Report with one item, severity `minor` (a single trial is a small sample). Deterministic checks then ran on the brief:

- no anchor outside ring 0
- no InF, handover, or wrap-around capability demand
- no ISD variable
- a single override key, so the batch is not a confounded factorial
- `repeats` is at least 5

No challenge was `blocking`, so the session moved to `compile`. A blocking item would have gone back to the researcher and stopped before any simulator started.

### 6. Compile

The eval tool was hashed and frozen. For this copy the hash is `33767f3d3ef9a71255e0ee4af133dd654c62b2efe39375ceb365a9b763d1b2b5`. `primary_metric` was read from the config: `mean_aoi_ms`. A later submit that sees a different eval file, or a primary metric that is not one of the brief's dependent variables, returns `evaluation is frozen` and does not start a run.

### 7. One experiment

The researcher reply was one batch:

```json
{
  "hypothesis_id": "h1",
  "repeats": 1,
  "groups": [
    {"name": "edf", "overrides": {"network.schedulerType": "edf"}, "seed": 1}
  ]
}
```

`submit_experiment` checked that `network.schedulerType=edf` is inside the brief, then queued one job. Concurrency is 1. The job runner started:

```bash
python3 -m cornet run /tmp/cornet_research_e2e/tasks/pendulum_nr_control
```

with `CORNET_HYPOTHESIS_ID=h1`, `CORNET_EXPERIMENT_SEED=1`, and `CORNET_OVERRIDES` set to the group's overrides. The orchestrator applies that seed and those overrides before NS-3 starts, and the variant id gains the override, for example `pendulum_nr_control+schedulerType=edf`. On 28 September the runner exported the seed and then launched the task file unchanged.

The orchestrator starts the robot plugin before the network plugin. Gazebo is launched with `ros2 launch`. That process exited immediately:

```text
ImportError: librcl_action.so: cannot open shared object file: No such file or directory
```

`ros2` was on `PATH` (`/opt/ros/humble/bin/ros2`) but the Humble libraries were not loaded, because `setup.bash` had not been sourced. NS-3 was not started. The orchestrator still stopped the plugins and appended a leaderboard row.

The new row, abbreviated, is:

| Field | Value |
|---|---|
| `timestamp` | `2026-09-28T17:15:19.580553` |
| `variant_id` | `pendulum_nr_control@ns3-v51` |
| `status` | `FAILURE` |
| `metric` | `null` |
| `primary_metric` | `mean_aoi_ms` |
| `hypothesis_id` | `h1` |
| `seed` | `1` |
| `lane` | `ns3-v51` |
| `standard` | `true` |
| `git_sha` | `null` |
| `config_hash` | `5e59d57bfd4170d7983f6a4fa7d7c674b571a19554d22f0636701f3627949131` |
| `timing_ok` | `false` |
| `rtf_mean` | `1.0` |

`git_sha` is null because the copy is not a git checkout. The job runner's working directory was `/tmp/cornet_research_e2e`.

`timing_ok` and `rtf_mean` on that row came from an older file. The copy included the task's existing `results/timing.json` from 27 September 2026 (`wall_s` about 60, Gazebo RTF mean 1.0, NS-3 lag over the 1 ms budget). This launch left that file in place, and provenance read it anyway. That session counted 1 trial and 5.0 simulated seconds, the configured duration, even though the simulator exited before those 5 seconds began.

A launch that exits before telemetry starts now records `timing_ok: unavailable` and omits `rtf_mean`, so an older `timing.json` is not treated as this run. A failed trial adds only the repeats that actually finished.

### 8. Compare was skipped

Comparison runs when a batch has two groups, the submit did not return an error, and the job finished. This batch had one group, and the launch failed, so `compare` did not run. Hypothesis `h1` stayed `open`. A verdict of supported, refuted, or inconclusive is written only by `compare`, from a Welch t-test or a Mann-Whitney U test at α = 0.05, using at least two samples on each side.

### 9. Report

Phase moved to `report`. The harness wrote the question, brief, verdict, and caveats. The agent supplied only the discussion. `research/report.md`:

```markdown
# Research report

## Question

Does one short pendulum run record mean AoI?

## Brief

Does the shipped pendulum task complete and record mean AoI?

## Hypothesis h1

Verdict: open

## Caveats

- pendulum_nr_control@ns3-v51: timing assumption violated

## Discussion

One trial was executed. The metric comes from the leaderboard row.
```

`session.json` then recorded phase `done`.

## Files the session left behind

```text
/tmp/cornet_research_e2e/tasks/pendulum_nr_control/research/
  session.json
  brief.yaml
  hypotheses.jsonl
  report.md
```

A session that asks the user a question also stores it in `session.json`. Answering is `POST /api/questions/{id}` on `python -m cornet ui`, or the prompt printed on resume. `ask_user` does not block the agent; it returns `question queued; end your turn`.

A two-group batch that finishes also writes `research/comparisons.json` and `research/journal.md`.

## Phases

```text
intake → brief → critique → compile → loop → report → done
```

| Phase | What is written | What stops the session |
|---|---|---|
| brief | `brief.yaml`, `hypotheses.jsonl` | Invalid brief, or a catalogue scenario that fails `check_compat` |
| critique | nothing until the report | Any challenge with severity `blocking` |
| compile | frozen eval hash, `primary_metric` | — |
| loop | leaderboard rows, optional comparison | Budget exhausted, or a submit error |
| report | `report.md` | — |

If the brief includes a catalogue scenario (`robot`, `world`, `network`, `radio_sites`), compile calls `compose` and the session continues in `tasks/<scenario id>/`.

## Agents and tools

Install the research extra before a live session. It pins `cursor-sdk==0.1.6` and `scipy==1.8.0`.

```bash
pip install -e ".[research]"
export PATH="$HOME/.local/bin:$PATH"
export NS3_DIR="$HOME/ns-3-dev"          # or ~/ns-3-dev-v51 on a v5.1 tree
export CORNET_NS3_TAG=ns3-v51            # optional lane label
export CURSOR_API_KEY="..."
export CORNET_RESEARCH_MODEL=composer-2.5
python -m cornet research "Which scheduler lowers mean AoI?" \
  --task tasks/pendulum_nr_control
```

`pip install -e ".[research]"` installs `cursor-sdk==0.1.6`. Without that package, `python -m cornet research` exits and names the extra. Without `CURSOR_API_KEY` it exits before creating an agent. The Gazebo plugin sources ROS 2 Humble when the shell has not.

Both agents run on this machine. `setting_sources` is empty, so the agent uses only the tools passed in. The allow-list is `mcp`, plus `webSearch` only when the session allows it. These custom tools are the whole surface:

| Tool | Role |
|---|---|
| `ask_user` | Queue a question and end the turn |
| `list_packs`, `describe_pack`, `check_compat`, `compose` | Catalogue |
| `smoke_test` | Short check of a composed task |
| `submit_experiment`, `experiment_status` | Queue and poll one run at a time |
| `leaderboard_summary` | Counts, means, and the five lowest metrics |
| `compare` | Statistical verdict |
| `read_run_artifacts` | Selected files from one run |
| `record_hypothesis`, `append_journal` | Journal. Verdicts come from `compare` only |

`shell`, `edit`, and `task` are not offered. Mininet without root, and middleware without `CAP_NET_ADMIN`, return an error and queue a question. The harness does not call `sudo`.

Resume an unfinished session with:

```bash
python -m cornet research --resume 0d2a94f2 --task tasks/pendulum_nr_control
```

## What a finished scientific run still needs

This check showed that the state machine writes a brief, survives a failed launch, keeps the hypothesis open, and writes a report. It did not show a Gazebo and NS-3 co-simulation, a mean AoI number, or a supported or refuted hypothesis.

Before treating a pendulum session as evidence:

1. Set `NS3_DIR` to the tree that contains `remote_robot_control-default.cc`.
2. Use at least two groups and at least five repeats when the question is a comparison. The brief's `repeats` field must be at least 5 or the critic blocks the batch.
3. Install `cornet[research]` and set `CURSOR_API_KEY` when the researcher and critic should be live agents. The SDK package alone does not authenticate the agent.

`python -m cornet ui tasks/<name>` shows the leaderboard, including Seed and Lane. Entries written before provenance existed still render.
