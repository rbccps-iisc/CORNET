# Installation Guide

## Quick Install

The fastest way to install all required components is via the provided scripts:

```bash
# Install everything (Python package + NS-3 + Mininet + Gazebo/ROS 2)
make install

# Or install only what you need:
make install-python   # Python package only
make install-ns3      # NS-3 3.38 + NR v2.4 + CORNET patches
make install-mininet  # Mininet-WiFi + Docker
make install-gazebo   # ROS 2 Humble + Gazebo Classic 11

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

> **Version note**: CORNET targets **NS-3 3.38 + NR v2.4**. Earlier documentation
> referenced NR v2.6, which is incompatible with the CORNET patch set. If you
> have an existing NR v2.6 installation, `scripts/install/install_ns3.sh`
> will detect it and exit with instructions before making any changes.

```bash
# Automated (recommended — handles clone, checkout, patch, and build):
make install-ns3

# Manual
sudo apt-get install -y g++ python3 cmake ninja-build git \
    libgtk-3-dev libxml2 libxml2-dev libboost-all-dev

git clone https://gitlab.com/nsnam/ns-3-dev.git
cd ns-3-dev
git checkout ns-3.38
git clone https://gitlab.com/cttc-lena/nr.git contrib/nr
cd contrib/nr && git checkout v2.4 && cd ../..

# Apply CORNET patches:
git apply ../../scripts/patches/ns3/v2.4-ns3.38/ns3_lte_pdcp.patch
git -C contrib/nr apply ../../../../scripts/patches/ns3/v2.4-ns3.38/nr_schedulers.patch

./ns3 configure --enable-examples --enable-tests
./ns3 build
```

Run the compat check script before applying patches to a pre-existing installation:

```bash
python3 scripts/check_ns3_compat.py --ns3-dir /path/to/ns-3-dev --patch-set v2.4-ns3.38
```

The `ns3` plugin searches for the NS-3 build at `NS3_DIR` environment variable, then `~/ns-3-dev/`.

> **NS-3 3.47 + NR v4.2 migration**: Support for NS-3 3.47 is tracked in
> `scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md`. It is not yet
> available; see that file for the current status and API rename table.

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

---

## Verify Installation

```bash
python -m cornet --help
python -m pytest tests/ -v
```
