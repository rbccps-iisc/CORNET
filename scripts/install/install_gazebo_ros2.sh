#!/usr/bin/env bash
# install_gazebo_ros2.sh — Install Gazebo Classic 11 + ROS 2 Humble for CORNET robot plugin.
#
# Idempotency: skips ROS 2 when `ros2` is on PATH, and skips TurtleBot3 when the
# burger SDF is already installed. Requires Ubuntu 22.04 (Jammy).
set -euo pipefail

BURGER_SDF="/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf"

echo "==> Checking Gazebo/ROS 2 prerequisites..."

if ! grep -q "22.04" /etc/os-release 2>/dev/null; then
    echo "WARNING: This script targets Ubuntu 22.04 (Jammy)."
    echo "         Your OS may not be fully supported."
    echo "         See: https://docs.ros.org/en/humble/Installation.html"
fi

if command -v ros2 &>/dev/null; then
    ROS_VER="$(ros2 --version 2>/dev/null | head -1 || echo 'unknown')"
    echo "==> ROS 2 already installed ($ROS_VER) — skipping ROS packages."
else
    echo "==> Installing ROS 2 Humble + Gazebo ROS packages..."
    sudo apt-get update
    sudo apt-get install -y \
        ros-humble-desktop \
        ros-humble-gazebo-ros-pkgs \
        python3-colcon-common-extensions

    if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
        echo "" >> ~/.bashrc
        echo "# ROS 2 Humble (added by CORNET install_gazebo_ros2.sh)" >> ~/.bashrc
        echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
        echo "    Added 'source /opt/ros/humble/setup.bash' to ~/.bashrc"
    fi
fi

if [[ -f "$BURGER_SDF" ]]; then
    echo "==> TurtleBot3 burger model already installed — skipping."
else
    echo "==> Installing TurtleBot3 Gazebo model..."
    sudo apt-get update
    sudo apt-get install -y \
        ros-humble-turtlebot3-gazebo \
        ros-humble-turtlebot3-description
fi

echo ""
echo "==> Gazebo + ROS 2 Humble installed successfully."
echo "    TurtleBot3 burger: $BURGER_SDF"
echo "    Run in current shell: source /opt/ros/humble/setup.bash"
echo "    Or start a new terminal (setup.bash added to ~/.bashrc)."
