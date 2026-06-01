#!/usr/bin/env bash
# install_ns3.sh — Clone, build, and patch NS-3 3.38 + NR v2.4 for CORNET.
#
# Idempotency:
#   Both sentinel files must be present to skip:
#     $NS3_DIR/.cornet-built          (written after successful NS-3 build)
#     $NS3_DIR/contrib/nr/.cornet-patched-v2.4  (written after patch application)
#
# D1: Sentinels are written LAST — a partial failure leaves one absent.
# D4: Detects existing NR version and exits 1 on mismatch with target v2.4.
#
# Environment variables:
#   NS3_DIR   — where to clone/find NS-3 (default: ~/ns-3-dev)
#   NR_TAG    — NR git tag to checkout (default: v2.4)
#   NS3_TAG   — NS-3 git tag to checkout (default: ns-3.38)
set -euo pipefail

NS3_DIR="${NS3_DIR:-$HOME/ns-3-dev}"
NR_TAG="${NR_TAG:-v2.4}"
NS3_TAG="${NS3_TAG:-ns-3.38}"
TARGET_NR_VER="2.4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PATCHES_DIR="$REPO_ROOT/scripts/patches/ns3/v2.4-ns3.38"

SENTINEL_BUILD="$NS3_DIR/.cornet-built"
SENTINEL_PATCHED="$NS3_DIR/contrib/nr/.cornet-patched-v2.4"

echo "==> CORNET NS-3 Installer"
echo "    NS3_DIR : $NS3_DIR"
echo "    NS3_TAG : $NS3_TAG"
echo "    NR_TAG  : $NR_TAG"
echo ""

# ── Idempotency gate ────────────────────────────────────────────────────────
if [[ -f "$SENTINEL_BUILD" ]] && [[ -f "$SENTINEL_PATCHED" ]]; then
    echo "==> NS-3 already built and patched — skipping."
    echo "    Build sentinel    : $SENTINEL_BUILD"
    echo "    Patch sentinel    : $SENTINEL_PATCHED"
    echo "    To reinstall: remove both sentinel files and re-run."
    exit 0
fi

# ── D4: Detect existing NR version mismatch ────────────────────────────────
NR_DIR="$NS3_DIR/contrib/nr"
if [[ -d "$NR_DIR" ]]; then
    EXISTING_VER=""
    if command -v git &>/dev/null; then
        EXISTING_VER="$(cd "$NR_DIR" && git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || true)"
    fi
    if [[ -z "$EXISTING_VER" ]] && [[ -f "$NR_DIR/CHANGES.md" ]]; then
        EXISTING_VER="$(grep -oP 'NR v\K[0-9]+\.[0-9]+' "$NR_DIR/CHANGES.md" | head -1 || true)"
    fi
    if [[ -n "$EXISTING_VER" ]] && [[ "$EXISTING_VER" != "$TARGET_NR_VER" ]]; then
        echo "ERROR: Existing NR installation detected at $NR_DIR" >&2
        echo "       Found version: v$EXISTING_VER" >&2
        echo "       Expected:      v$TARGET_NR_VER" >&2
        echo "" >&2
        echo "  This installer targets NR v$TARGET_NR_VER (the version CORNET patches" >&2
        echo "  were validated against). Your installation has NR v$EXISTING_VER." >&2
        echo "" >&2
        echo "  If you previously installed NR v2.6 following an older version of" >&2
        echo "  docs/INSTALL.md, you need to remove the existing NR checkout first:" >&2
        echo "" >&2
        echo "    rm -rf $NR_DIR" >&2
        echo "    # Then re-run this script" >&2
        echo "" >&2
        echo "  For migration to NR v4.2 (NS-3 3.47), see:" >&2
        echo "    scripts/patches/ns3/v4.2-ns3.47/MIGRATION_STATUS.md" >&2
        exit 1
    fi
fi

# ── System dependencies ─────────────────────────────────────────────────────
echo "==> Installing build dependencies..."
sudo apt-get install -y \
    g++ python3 cmake ninja-build git \
    libgtk-3-dev libxml2 libxml2-dev libboost-all-dev \
    2>/dev/null || echo "    WARNING: apt-get failed — continuing (may already be installed)"

# ── Compat pre-flight (if NS-3 dir already exists) ─────────────────────────
if [[ -d "$NS3_DIR" ]] && [[ -f "$SENTINEL_BUILD" ]]; then
    echo "==> Running compatibility pre-flight check..."
    python3 "$REPO_ROOT/scripts/check_ns3_compat.py" \
        --ns3-dir "$NS3_DIR" \
        --patch-set "v2.4-ns3.38" || {
        echo "ERROR: Pre-flight check failed. Review report above." >&2
        exit 1
    }
fi

# ── Clone NS-3 (if needed) ──────────────────────────────────────────────────
if [[ ! -d "$NS3_DIR/.git" ]]; then
    echo "==> Cloning NS-3 ($NS3_TAG) into $NS3_DIR..."
    git clone --branch "$NS3_TAG" --depth 1 \
        https://gitlab.com/nsnam/ns-3-dev.git "$NS3_DIR"
else
    echo "==> NS-3 directory exists — skipping clone."
fi

# ── Clone NR module (if needed) ────────────────────────────────────────────
if [[ ! -d "$NR_DIR/.git" ]]; then
    echo "==> Cloning 5G-LENA NR ($NR_TAG) into $NR_DIR..."
    git clone --branch "$NR_TAG" --depth 1 \
        https://gitlab.com/cttc-lena/nr.git "$NR_DIR"
else
    echo "==> NR directory exists — skipping clone."
fi

# ── Build NS-3 ──────────────────────────────────────────────────────────────
echo "==> Configuring NS-3 (this may take a few minutes)..."
cd "$NS3_DIR"
./ns3 configure --enable-examples --enable-tests

echo "==> Building NS-3 + NR (this takes 20–30 minutes)..."
./ns3 build

# Write build sentinel (D1: written after successful build, before patches)
touch "$SENTINEL_BUILD"
echo "    Build sentinel written: $SENTINEL_BUILD"

# ── Apply CORNET patches ─────────────────────────────────────────────────────
echo "==> Applying CORNET patches..."

echo "    Applying ns3_lte_pdcp.patch (NS-3 src)..."
git apply "$PATCHES_DIR/ns3_lte_pdcp.patch"

echo "    Applying nr_schedulers.patch (contrib/nr)..."
cd "$NR_DIR"
git apply "$PATCHES_DIR/nr_schedulers.patch"

# D1: Write patch sentinel LAST — both sentinels now present means success
touch "$SENTINEL_PATCHED"
echo "    Patch sentinel written: $SENTINEL_PATCHED"

# ── Rebuild with patches applied ────────────────────────────────────────────
echo "==> Rebuilding NS-3 with CORNET patches..."
cd "$NS3_DIR"
./ns3 build

echo ""
echo "==> NS-3 3.38 + NR v2.4 installed and patched successfully."
echo "    Set NS3_DIR=$NS3_DIR in your environment (or ~/.bashrc)."
echo "    Verify: python -m cornet --help"
