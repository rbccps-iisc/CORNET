#!/usr/bin/env bash
# install_mininet.sh — Install Mininet-WiFi and Docker for CORNET Mininet plugin.
#
# Idempotency gate: skips if python3 can import mininet.
set -euo pipefail

echo "==> Checking Mininet prerequisites..."

# ── Idempotency gate ────────────────────────────────────────────────────────
if python3 -c "import mininet" &>/dev/null 2>&1; then
    echo "==> Mininet already installed — skipping Mininet-WiFi install."
else
    echo "==> Installing Mininet-WiFi..."
    WORKDIR=$(mktemp -d)
    trap 'rm -rf "$WORKDIR"' EXIT
    git clone --depth 1 https://github.com/intrig-unicamp/mininet-wifi "$WORKDIR/mininet-wifi"
    cd "$WORKDIR/mininet-wifi"
    sudo util/install.sh -Wlnfv
    echo "    Mininet-WiFi installed."
fi

# ── Docker ──────────────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
    echo "==> Docker already installed — skipping."
else
    echo "==> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "    Docker installed. Log out and back in for group membership to take effect."
fi

echo ""
echo "==> Mininet + Docker installation complete."
echo "    NOTE: Mininet requires root. Run CORNET with: sudo python -m cornet tasks/<name>"
