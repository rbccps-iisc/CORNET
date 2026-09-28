# Installation Guide

## Quick Install

The fastest way to install all required components is via the provided scripts:

```bash
# Install everything (Python package + NS-3 + Mininet + Gazebo/ROS 2)
make install

# Or install only what you need:
make install-python   # Python package only
make install-ns3      # NS-3 3.38 + NR v2.4 + CORNET patches (stable default)
make install-ns3-v47  # NS-3 3.47 + NR v4.2 (explicit stepping stone)
make install-ns3-v51  # NS-3 3.48 + NR v5.1 (explicit; pins in scripts/patches/ns3/v5.1-ns3.48/README.md)
make install-mininet  # Mininet-WiFi + Docker
make install-gazebo   # ROS 2 Humble + Gazebo Classic 11 + TurtleBot3
make install-px4      # PX4 Classic iris SITL (aerial pack; not part of `make install`)

# Verify all components are functional:
make verify
```

All scripts are in `scripts/install/` and are idempotent — safe to re-run.

> **Docker alternative**: If you prefer a containerised setup, Docker images
> are available under `scripts/docker/`. Run `docker compose up` from that
> directory to start a pre-configured CORNET environment without manual
> dependency installation.

---

## Python Package

```bash
pip install cornet-framework
# or from source
git clone https://github.com/rbccps-iisc/CORNET
cd CORNET
pip install -e .[dev]
```

Requires Python 3.10+.

## System Prerequisites

CORNET plugins require system-level simulators. Install only what you need for your chosen backend.

---

### NS-3 with 5G NR (for `network.plugin: ns3`)

> **Version note**: CORNET's default install targets **NS-3 3.38 + NR v2.4**.
> Two explicit lanes sit beside it: NS-3 3.47 + NR v4.2 (`make install-ns3-v47`)
> and NS-3 3.48 + NR v5.1 (`make install-ns3-v51`). Neither replaces the default.
> See `scripts/patches/ns3/CAPABILITY_MATRIX.yaml` for what each lane has validated.

On Ubuntu 22.04 the v5.1 lane builds with g++ 11 (C++20), Python 3.10, and Ninja 1.10.
NS-3 3.48 requires **CMake 3.25 or newer**. Ubuntu 22.04's apt package is 3.22,
which stops `./ns3 configure`. This machine has `g++` 11.4.0, `python3` 3.10.12,
and `ninja` 1.10.1; its system CMake is 3.22.1, so the v5.1 install needs a
newer CMake on `PATH`. Without sudo, install one for this user and leave `~/.local/bin` ahead of `/usr/bin`:

```bash
python3 -m pip install --user 'cmake>=3.25'
export PATH="$HOME/.local/bin:$PATH"
```

`make install-ns3-v51` prefers `$HOME/.local/bin/cmake` when that file exists. NS-3 3.48
is pinned to `d2add90b452d600cfb4859baed8e9ea633519447` and 5G-LENA v5.1 to
`cedceadda17392c90587fb9400eb9b1f8c236713`.

```bash
# Stable default: NS-3 3.38 + NR v2.4 into ~/ns-3-dev
make install-ns3

# Stepping stone: NS-3 3.47 + NR v4.2 into ~/ns-3-dev-v47
make install-ns3-v47

# Latest explicit lane: NS-3 3.48 + NR v5.1 into ~/ns-3-dev-v51
# Needs CMake >= 3.25 on PATH (see above). Does not replace the default.
make install-ns3-v51
```

The installer clones the pinned tag, checks the commit, configures, builds, then applies the lane's `profiles/full.txt`. A manual checkout should use those same pins from `scripts/patches/ns3/v5.1-ns3.48/README.md` (or the v2.4 / v4.2 READMEs) rather than a floating branch.

Run the compat check script before applying patches to a pre-existing installation:

```bash
# Default check (v4.2-ns3.47)
python3 scripts/check_ns3_compat.py --ns3-dir /path/to/ns-3-dev

# Legacy check (v2.4-ns3.38)
python3 scripts/check_ns3_compat.py --ns3-dir /path/to/ns-3-dev --patch-set v2.4-ns3.38
```

The `ns3` plugin searches for the NS-3 build at `NS3_DIR` environment variable, then `~/ns-3-dev/`.

---

### Mininet-WiFi + Docker (for `network.plugin: mininet`)

```bash
# Install Mininet-WiFi
git clone https://github.com/intrig-unicamp/mininet-wifi
cd mininet-wifi
sudo util/install.sh -Wlnfv

# Install Docker (for container nodes)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Mininet requires root — always run with sudo:
sudo python -m cornet tasks/<name>
```

---

### Gazebo Classic 11 + ROS 2 Humble (for `robot.plugin: gazebo`)

```bash
# ROS 2 Humble (Ubuntu 22.04)
sudo apt-get install -y ros-humble-desktop ros-humble-gazebo-ros-pkgs

# Source ROS 2 in every terminal (or add to ~/.bashrc)
source /opt/ros/humble/setup.bash
```

The `gazebo` plugin calls `ros2 launch` internally; ROS 2 must be sourced before running.

`make install-gazebo` also installs the TurtleBot3 burger model that catalogue compose uses:

`/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf`

Gazebo load benchmarks (`python -m cornet bench gazebo`) spawn that model. Source ROS 2 before those runs.

### PX4 Classic iris (for the `px4_x500` catalogue pack)

`make install` does not build PX4. After Gazebo is installed:

```bash
make install-px4
```

The script clones `~/simulation/PX4-Autopilot` at `36006b6d703a421175587d386a535bbdf8eb0a9c` with the Gazebo Classic submodule `5b6966ed572a02e8273f446acb504a45a841ca53`, then runs `DONT_RUN=1 make px4_sitl gazebo-classic`. The airframe is iris. It also installs `libgz-transport13`, `libgz-msgs10`, and `libgz-utils2` from the OSRF Gazebo apt repository, because that binary links them. An existing checkout at a different commit is left in place.

Warehouse worlds are optional. Set `CORNET_SMALL_WAREHOUSE` and `CORNET_LARGE_WAREHOUSE` to a world file or package directory. When unset, the suite looks at the known local AWS and ARTPARK checkouts, then at vendored `cornet/catalog/worlds/` paths. Missing worlds are skipped.

---

## Git LFS

Catalogue meshes and textures (`cornet/catalog/**/*.dae`, `*.stl`, `*.png`, `*.jpg`) are stored with Git LFS. After cloning, install the client once and pull the objects:

```bash
git lfs install
git lfs pull
```

The scenario compiler refuses to run when a vendored asset is still a Git LFS pointer. On this machine the client is `~/.local/bin/git-lfs` 3.8.0, because installing the apt package needs sudo.

---

## Verify Installation

```bash
python -m cornet --help
python -m pytest tests/ -v
```
