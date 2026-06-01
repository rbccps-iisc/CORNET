#!/usr/bin/env bash
# verify.sh — Verify all CORNET components are correctly installed.
#
# Checks five components and exits 1 if any fail.
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

echo ""
echo "================================="
echo "Results: $PASS passed, $FAIL failed"

if [[ "$FAIL" -gt 0 ]]; then
    echo ""
    echo "Some components are missing. Install only what you need:"
    echo "  make install-python   — CORNET Python package (required)"
    echo "  make install-ns3      — NS-3 + 5G NR (for network.plugin: ns3)"
    echo "  make install-mininet  — Mininet-WiFi + Docker (for network.plugin: mininet)"
    echo "  make install-gazebo   — ROS 2 + Gazebo (for robot.plugin: gazebo)"
    exit 1
fi

echo "All components verified successfully."
