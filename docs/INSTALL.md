# Installation Guide

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

```bash
# Install build dependencies
sudo apt-get install -y g++ python3 cmake ninja-build git \
    libgtk-3-dev libxml2 libxml2-dev libboost-all-dev

# Clone NS-3 + 5G NR module
git clone https://gitlab.com/cttc-lena/nr.git ns-3-dev
cd ns-3-dev
git checkout nr-v2.6
./ns3 configure --enable-examples --enable-tests
./ns3 build

# Apply CORNET patches (from rbccps-iisc/CORNET3.0)
# See network/NETWORK_SETUP.md in CORNET3.0
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

---

## Verify Installation

```bash
python -m cornet --help
python -m pytest tests/ -v
```
