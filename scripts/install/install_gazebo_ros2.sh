#!/usr/bin/env bash
# install_gazebo_ros2.sh — Install Gazebo Classic 11 + ROS 2 Humble for CORNET robot plugin.
#
# Idempotency gate: skips if ros2 command is available.
# Requires Ubuntu 22.04 (Jammy).
set -euo pipefail

echo "==> Checking Gazebo/ROS 2 prerequisites..."

# ── Idempotency gate ────────────────────────────────────────────────────────
if command -v ros2 &>/dev/null; then
    ROS_VER="$(ros2 --version 2>/dev/null | head -1 || echo 'unknown')"
    echo "==> ROS 2 already installed ($ROS_VER) — skipping."
    exit 0
fi

# ── OS check ────────────────────────────────────────────────────────────────
if ! grep -q "22.04" /etc/os-release 2>/dev/null; then
    echo "WARNING: This script targets Ubuntu 22.04 (Jammy)."
    echo "         Your OS may not be fully supported."
    echo "         See: https://docs.ros.org/en/humble/Installation.html"
fi

echo "==> Installing ROS 2 Humble + Gazebo ROS packages..."
sudo apt-get update
sudo apt-get install -y \
    ros-humble-desktop \
    ros-humble-gazebo-ros-pkgs \
    python3-colcon-common-extensions

# Add ROS 2 sourcing to bashrc if not already present
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# ROS 2 Humble (added by CORNET install_gazebo_ros2.sh)" >> ~/.bashrc
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
    echo "    Added 'source /opt/ros/humble/setup.bash' to ~/.bashrc"
fi

echo ""
echo "==> Gazebo + ROS 2 Humble installed successfully."
echo "    Run in current shell: source /opt/ros/humble/setup.bash"
echo "    Or start a new terminal (setup.bash added to ~/.bashrc)."
