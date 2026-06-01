# Getting Started

## 1. Install the package

```bash
git clone https://github.com/rbccps-iisc/CORNET
cd CORNET
pip install -e .[dev]
```

Install simulator prerequisites only for the plugins you plan to use. See [INSTALL.md](INSTALL.md).

## 2. Understand the task layout

Each experiment lives in `tasks/<name>/`:

```text
tasks/
  pendulum_nr_control/
    config.yaml
    eval/
      eval_tool.py
  uav_wifi_control/
    config.yaml
    eval/
      eval_tool.py
```

`config.yaml` declares:
- `network`: `ns3`, `mininet`, or `ns3+mininet`
- `robot`: Gazebo/ROS 2 deployment
- `experiment`: duration, output directory, primary metric, optional sweep

## 3. Run a task

```bash
python -m cornet tasks/pendulum_nr_control
```

If the task folder includes `launch.py` or `world.sdf`, CORNET auto-discovers them. Otherwise the Gazebo plugin auto-generates a launch file.

## 4. Run a sweep

```yaml
experiment:
  sweep:
    axes:
      network.numerology: [1, 2, 3]
      network.bandwidth: [20, 40]
    repeats: 2
```

Then run the task normally:

```bash
python -m cornet tasks/aoi_5phase_eval
```

CORNET expands the cartesian product and writes results per variant under `experiment.output_dir/<variant_id>/`.

## 5. View the leaderboard

```bash
python -m cornet view tasks/pendulum_nr_control
```

This prints a `rich` table sorted by the configured primary metric.
