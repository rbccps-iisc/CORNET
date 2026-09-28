#!/usr/bin/env bash
# install_px4.sh — Gazebo Classic iris SITL for the px4_x500 catalogue pack.
#
# Pins the checkout that the indoor smoke flew:
#   PX4-Autopilot 36006b6d703a421175587d386a535bbdf8eb0a9c
#   sitl_gazebo-classic 5b6966ed572a02e8273f446acb504a45a841ca53
# Airframe is iris. The binary links Gazebo Transport 13 even for Classic SITL.
#
# Idempotent. Refuses to move an existing checkout that is not the pin.
# Requires Gazebo Classic headers (`make install-gazebo`) before a compile.
# Override the tree with PX4_DIR. Does not run `make install`.
set -euo pipefail

PX4_DIR="${PX4_DIR:-$HOME/simulation/PX4-Autopilot}"
PIN="36006b6d703a421175587d386a535bbdf8eb0a9c"
SUB_PIN="5b6966ed572a02e8273f446acb504a45a841ca53"
SUB_PATH="Tools/simulation/gazebo-classic/sitl_gazebo-classic"
BIN="$PX4_DIR/build/px4_sitl_default/bin/px4"
IRIS="$PX4_DIR/$SUB_PATH/models/iris/iris.sdf.jinja"

echo "==> Checking PX4 Classic SITL prerequisites..."

if ! grep -q "22.04" /etc/os-release 2>/dev/null; then
    echo "WARNING: This script targets Ubuntu 22.04 (Jammy)."
fi

gz_lib_missing() {
    local name="$1"
    ! ldconfig -p 2>/dev/null | grep -q "$name"
}

if gz_lib_missing "libgz-transport13.so.13" \
    || gz_lib_missing "libgz-msgs10.so.10" \
    || gz_lib_missing "libgz-utils2.so.2"; then
    echo "==> Installing Gazebo Transport libraries used by the PX4 binary..."
    if [[ ! -f /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg ]]; then
        sudo wget https://packages.osrfoundation.org/gazebo.gpg \
            -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
    fi
    if [[ ! -f /etc/apt/sources.list.d/gazebo-stable.list ]]; then
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
            | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
    fi
    sudo apt-get update
    sudo apt-get install -y \
        libgz-transport13 \
        libgz-msgs10 \
        libgz-utils2 \
        libgz-transport13-dev \
        libgz-msgs10-dev
else
    echo "==> Gazebo Transport libraries already installed — skipping."
fi

if [[ ! -d "$PX4_DIR/.git" ]]; then
    echo "==> Cloning PX4-Autopilot into $PX4_DIR"
    mkdir -p "$(dirname "$PX4_DIR")"
    git clone --filter=blob:none https://github.com/PX4/PX4-Autopilot.git "$PX4_DIR"
    git -C "$PX4_DIR" checkout "$PIN"
else
    head="$(git -C "$PX4_DIR" rev-parse HEAD)"
    if [[ "$head" != "$PIN" ]]; then
        echo "PX4 checkout is $head." >&2
        echo "Expected $PIN. Refusing to move $PX4_DIR." >&2
        exit 1
    fi
    echo "==> PX4 checkout already at $PIN"
fi

if [[ ! -e "$PX4_DIR/$SUB_PATH/.git" ]]; then
    echo "==> Initialising gazebo-classic submodule..."
    git -C "$PX4_DIR" submodule update --init "$SUB_PATH"
fi
sub_head="$(git -C "$PX4_DIR/$SUB_PATH" rev-parse HEAD)"
if [[ "$sub_head" != "$SUB_PIN" ]]; then
    echo "gazebo-classic submodule is $sub_head." >&2
    echo "Expected $SUB_PIN. Refusing to move it." >&2
    exit 1
fi

if [[ -x "$BIN" && -f "$IRIS" ]]; then
    echo "==> PX4 iris SITL already built — skipping compile."
    echo "    $BIN"
    exit 0
fi

if ! pkg-config --exists gazebo; then
    echo "Gazebo Classic headers are missing. Run: make install-gazebo" >&2
    exit 1
fi

echo "==> Installing PX4 SITL build packages..."
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    ninja-build \
    python3-jinja2 \
    python3-numpy \
    python3-empy \
    python3-toml \
    libeigen3-dev \
    libopencv-dev \
    protobuf-compiler \
    libgstreamer-plugins-base1.0-dev

if [[ -f "$PX4_DIR/Tools/setup/requirements.txt" ]]; then
    python3 -m pip install --user -r "$PX4_DIR/Tools/setup/requirements.txt"
fi

echo "==> Building px4_sitl gazebo-classic (iris)..."
(
    cd "$PX4_DIR"
    DONT_RUN=1 make px4_sitl gazebo-classic
)

if [[ ! -x "$BIN" || ! -f "$IRIS" ]]; then
    echo "Build finished without $BIN or iris.sdf.jinja." >&2
    exit 1
fi

echo ""
echo "==> PX4 Classic iris SITL installed."
echo "    $BIN"
echo "    Model: gazebo-classic_iris"
