#!/usr/bin/env bash
# verify.sh — Verify all CORNET components are correctly installed.
#
# Checks the stable components plus TurtleBot3 and PX4 Classic iris.
# When ~/ns-3-dev-v51 exists, also checks the v5.1 sentinel.
# Exits 1 if any check fails.
set -euo pipefail

NS3_DIR="${NS3_DIR:-$HOME/ns-3-dev}"

PASS=0
FAIL=0

check() {
    local label="$1"
    local ok="$2"   # "1" = pass, "0" = fail
    local detail="$3"
    if [[ "$ok" == "1" ]]; then
        echo "  ✓ $label"
        [[ -n "$detail" ]] && echo "      $detail"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $label"
        [[ -n "$detail" ]] && echo "      $detail"
        FAIL=$((FAIL + 1))
    fi
}

echo "CORNET Installation Verification"
echo "================================="
echo ""

# 1. Python package
if python3 -c "import cornet" &>/dev/null 2>&1; then
    VER="$(python3 -c 'import importlib.metadata; print(importlib.metadata.version("cornet-framework"))' 2>/dev/null || echo '?')"
    check "cornet-framework" "1" "version $VER"
else
    check "cornet-framework" "0" "not importable — run: make install-python"
fi

# 2. NS-3
if [[ -f "$NS3_DIR/.cornet-built" ]] && [[ -f "$NS3_DIR/contrib/nr/.cornet-patched-v2.4" ]]; then
    check "NS-3 + NR v2.4 (patched)" "1" "NS3_DIR=$NS3_DIR"
elif [[ -d "$NS3_DIR" ]]; then
    MISSING=""
    [[ ! -f "$NS3_DIR/.cornet-built" ]] && MISSING+=" .cornet-built"
    [[ ! -f "$NS3_DIR/contrib/nr/.cornet-patched-v2.4" ]] && MISSING+=" .cornet-patched-v2.4"
    check "NS-3 + NR v2.4 (patched)" "0" "missing sentinels:$MISSING — run: make install-ns3"
else
    check "NS-3 + NR v2.4 (patched)" "0" "NS3_DIR=$NS3_DIR not found — run: make install-ns3"
fi

# 3. Mininet
if python3 -c "import mininet" &>/dev/null 2>&1; then
    check "Mininet-WiFi" "1" ""
else
    check "Mininet-WiFi" "0" "not importable — run: make install-mininet"
fi

# 4. Docker
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    VER="$(docker --version | awk '{print $3}' | tr -d ',')"
    check "Docker" "1" "version $VER"
elif command -v docker &>/dev/null; then
    check "Docker" "0" "installed but daemon not running — try: sudo systemctl start docker"
else
    check "Docker" "0" "not found — run: make install-mininet (installs Docker)"
fi

# 5. ROS 2 / Gazebo
if command -v ros2 &>/dev/null; then
    VER="$(ros2 --version 2>/dev/null | head -1 || echo '?')"
    check "ROS 2 / Gazebo" "1" "$VER"
else
    check "ROS 2 / Gazebo" "0" "ros2 not found — run: make install-gazebo"
fi

# 6. TurtleBot3 burger model used by catalogue compose
BURGER_SDF="/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf"
if [[ -f "$BURGER_SDF" ]]; then
    check "TurtleBot3 burger" "1" "$BURGER_SDF"
else
    check "TurtleBot3 burger" "0" "model missing — run: make install-gazebo"
fi

# 7. PX4 Classic iris SITL (optional tree; required once PX4_DIR is set or the default exists)
PX4_DIR="${PX4_DIR:-$HOME/simulation/PX4-Autopilot}"
PX4_PIN="36006b6d703a421175587d386a535bbdf8eb0a9c"
PX4_SUB_PIN="5b6966ed572a02e8273f446acb504a45a841ca53"
PX4_BIN="$PX4_DIR/build/px4_sitl_default/bin/px4"
PX4_IRIS="$PX4_DIR/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris/iris.sdf.jinja"
if [[ -d "$PX4_DIR/.git" || -x "$PX4_BIN" ]]; then
    px4_head="$(git -C "$PX4_DIR" rev-parse HEAD 2>/dev/null || echo missing)"
    px4_sub="$(git -C "$PX4_DIR/Tools/simulation/gazebo-classic/sitl_gazebo-classic" rev-parse HEAD 2>/dev/null || echo missing)"
    if [[ -x "$PX4_BIN" && -f "$PX4_IRIS" && "$px4_head" == "$PX4_PIN" && "$px4_sub" == "$PX4_SUB_PIN" ]]; then
        check "PX4 Classic iris" "1" "$px4_head"
    else
        check "PX4 Classic iris" "0" "checkout or binary does not match the pin — run: make install-px4"
    fi
    gz_ok=1
    for soname in libgz-transport13.so.13 libgz-msgs10.so.10 libgz-utils2.so.2; do
        if ! ldconfig -p 2>/dev/null | grep -q "$soname"; then
            gz_ok=0
        fi
    done
    if [[ "$gz_ok" == "1" ]]; then
        check "PX4 Gazebo Transport libs" "1" "libgz-transport13, libgz-msgs10, libgz-utils2"
    else
        check "PX4 Gazebo Transport libs" "0" "not on the library path — run: make install-px4"
    fi
else
    check "PX4 Classic iris" "0" "not installed — run: make install-px4"
fi

# 8. v5.1 lane, only when that tree is present
NS3_V51="${NS3_DIR_V51:-$HOME/ns-3-dev-v51}"
if [[ -d "$NS3_V51" ]]; then
    if [[ -f "$NS3_V51/contrib/nr/.cornet-patched-v5.1" ]]; then
        check "NS-3 + NR v5.1 (patched)" "1" "NS3_DIR=$NS3_V51"
    else
        check "NS-3 + NR v5.1 (patched)" "0" "sentinel missing — run: make install-ns3-v51"
    fi
fi

echo ""
echo "================================="
echo "Results: $PASS passed, $FAIL failed"

if [[ "$FAIL" -gt 0 ]]; then
    echo ""
    echo "Some components are missing. Install only what you need:"
    echo "  make install-python   — CORNET Python package (required)"
    echo "  make install-ns3      — NS-3 + 5G NR (for network.plugin: ns3)"
    echo "  make install-mininet  — Mininet-WiFi + Docker (for network.plugin: mininet)"
    echo "  make install-gazebo   — ROS 2 + Gazebo + TurtleBot3 (for robot.plugin: gazebo)"
    echo "  make install-px4      — PX4 Classic iris SITL (aerial catalogue pack)"
    echo "  make install-ns3-v51  — NS-3 3.48 + NR v5.1 (catalogue lane, when that tree is present)"
    exit 1
fi

echo "All components verified successfully."
