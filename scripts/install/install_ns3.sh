#!/usr/bin/env bash
# install_ns3.sh — Clone, build, and patch NS-3 + NR for CORNET.
#
# Idempotency (both sentinels must be present to skip):
#   $NS3_DIR/.cornet-built                               (written after NS-3 build)
#   $NS3_DIR/contrib/nr/.cornet-patched-<patch-set-ver>  (written after patching)
#
# D1: Sentinels are written LAST — a partial failure leaves one absent.
# D4: Detects existing NR version and exits 1 on mismatch with target version.
#
# Environment variables:
#   PATCH_SET — patch set to use (default: v2.4-ns3.38 — stable lane)
#               Supported: v2.4-ns3.38, v4.2-ns3.47, v5.1-ns3.48
#               Use PATCH_SET=v4.2-ns3.47 or 'make install-ns3-v47' for the v4.2 lane.
#               Use PATCH_SET=v5.1-ns3.48 or 'make install-ns3-v51' for the v5.1 lane.
#   PATCH_PROFILE — named profile under scripts/patches/ns3/$PATCH_SET/profiles/
#               (default: full). full applies every patch; unset matches that.
#   NS3_DIR   — where to clone/find NS-3 (default: ~/ns-3-dev)
set -euo pipefail

PATCH_SET="${PATCH_SET:-v2.4-ns3.38}"
PATCH_PROFILE="${PATCH_PROFILE:-full}"

# ── Version lookup table ────────────────────────────────────────────────────
case "$PATCH_SET" in
    v2.4-ns3.38)
        NS3_TAG="ns-3.38"
        NR_TAG="v2.4"
        TARGET_NR_VER="2.4"
        SENTINEL_SUFFIX="v2.4"
        ;;
    v4.2-ns3.47)
        NS3_TAG="ns-3.47"
        NR_TAG="v4.2"
        TARGET_NR_VER="4.2"
        SENTINEL_SUFFIX="v4.2"
        ;;
    v5.1-ns3.48)
        NS3_TAG="ns-3.48"
        NR_TAG="v5.1"
        TARGET_NR_VER="5.1"
        SENTINEL_SUFFIX="v5.1"
        # Peeled tag commits. Clone --branch checks these out; the installer rejects a mismatch.
        NS3_COMMIT="d2add90b452d600cfb4859baed8e9ea633519447"
        NR_COMMIT="cedceadda17392c90587fb9400eb9b1f8c236713"
        ;;
    *)
        echo "ERROR: Unknown PATCH_SET='$PATCH_SET'." >&2
        echo "       Supported values: v2.4-ns3.38, v4.2-ns3.47, v5.1-ns3.48" >&2
        exit 1
        ;;
esac

NS3_DIR="${NS3_DIR:-$HOME/ns-3-dev}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PATCHES_DIR="$REPO_ROOT/scripts/patches/ns3/$PATCH_SET"
SCRATCH_SRC="$REPO_ROOT/scripts/ns3/scratch/$PATCH_SET"

SENTINEL_BUILD="$NS3_DIR/.cornet-built"
SENTINEL_PATCHED="$NS3_DIR/contrib/nr/.cornet-patched-$SENTINEL_SUFFIX"

echo "==> CORNET NS-3 Installer"
echo "    PATCH_SET : $PATCH_SET"
echo "    PROFILE   : $PATCH_PROFILE"
echo "    NS3_DIR   : $NS3_DIR"
echo "    NS3_TAG   : $NS3_TAG"
echo "    NR_TAG    : $NR_TAG"
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
        echo "       Expected:      v$TARGET_NR_VER (for PATCH_SET=$PATCH_SET)" >&2
        echo "" >&2
        echo "  This installer targets NR v$TARGET_NR_VER. Your NS3_DIR has NR v$EXISTING_VER." >&2
        echo "  Remove the existing NR checkout and re-run:" >&2
        echo "" >&2
        echo "    rm -rf $NR_DIR" >&2
        echo "    # Then re-run this script" >&2
        echo "" >&2
        echo "  To install a different version, use a separate NS3_DIR:" >&2
        echo "    NS3_DIR=~/ns-3-dev-v47 PATCH_SET=v4.2-ns3.47 bash $0" >&2
        echo "  Or use: make install-ns3-v47" >&2
        exit 1
    fi
fi

# ── System dependencies ─────────────────────────────────────────────────────
echo "==> Installing build dependencies..."
sudo -n apt-get install -y \
    g++ python3 cmake ninja-build git \
    libgtk-3-dev libxml2 libxml2-dev libboost-all-dev \
    2>/dev/null || echo "    WARNING: apt-get failed — continuing (may already be installed)"

# ── Compat pre-flight (if NS-3 dir already exists) ─────────────────────────
if [[ -d "$NS3_DIR" ]] && [[ -f "$SENTINEL_BUILD" ]]; then
    echo "==> Running compatibility pre-flight check..."
    if ! python3 "$REPO_ROOT/scripts/check_ns3_compat.py" \
        --ns3-dir "$NS3_DIR" \
        --patch-set "$PATCH_SET"; then
        already=0
        if [[ -f "$PATCHES_DIR/ns3_lte_pdcp.patch" ]] \
            && git -C "$NS3_DIR" apply --reverse --check "$PATCHES_DIR/ns3_lte_pdcp.patch" 2>/dev/null \
            && git -C "$NR_DIR" apply --reverse --check "$PATCHES_DIR/nr_schedulers.patch" 2>/dev/null; then
            already=1
        fi
        if [[ "$already" -eq 1 ]]; then
            echo "    WARNING: patches are already applied; continuing so the rebuild can finish."
        else
            echo "ERROR: Pre-flight check failed. Review report above." >&2
            exit 1
        fi
    fi
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

if [[ -n "${NS3_COMMIT:-}" ]]; then
    actual="$(git -C "$NS3_DIR" rev-parse HEAD)"
    if [[ "$actual" != "$NS3_COMMIT" ]]; then
        echo "ERROR: NS-3 HEAD $actual != pinned $NS3_COMMIT" >&2
        exit 1
    fi
fi
if [[ -n "${NR_COMMIT:-}" ]]; then
    actual="$(git -C "$NR_DIR" rev-parse HEAD)"
    if [[ "$actual" != "$NR_COMMIT" ]]; then
        echo "ERROR: NR HEAD $actual != pinned $NR_COMMIT" >&2
        exit 1
    fi
fi

# A previous run may have left a scratch script that does not match this tree.
# The fresh copies are installed after the patches, before the second build.
if [[ -d "$SCRATCH_SRC" ]]; then
    for stale in "$SCRATCH_SRC"/*.cc "$REPO_ROOT/scripts/ns3/scratch/cornet_base.h"; do
        [[ -e "$stale" ]] || continue
        rm -f "$NS3_DIR/scratch/$(basename "$stale")"
    done
fi

# NS-3 3.48's CMakeLists requires CMake >= 3.25. Ubuntu 22.04 apt is 3.22.
# A `pip install --user cmake` binary lives in ~/.local/bin; prefer it when present.
if [[ -x "$HOME/.local/bin/cmake" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
fi
cmake_ver="$(cmake --version | awk 'NR==1 {print $3}')"
echo "==> Using cmake $cmake_ver ($(command -v cmake))"

# ── Build NS-3 ──────────────────────────────────────────────────────────────
echo "==> Configuring NS-3 (this may take a few minutes)..."
cd "$NS3_DIR"
# A failed configure with an older CMake leaves a cache that the next run reuses.
if [[ -f "$NS3_DIR/cmake-cache/CMakeCache.txt" ]]; then
    cached_cmake="$(grep -m1 '^CMAKE_COMMAND:' "$NS3_DIR/cmake-cache/CMakeCache.txt" | cut -d= -f2- || true)"
    if [[ -n "$cached_cmake" && "$cached_cmake" != "$(command -v cmake)" ]]; then
        echo "    Removing cmake-cache configured by $cached_cmake"
        rm -rf "$NS3_DIR/cmake-cache"
    fi
fi
./ns3 configure --enable-examples --enable-tests

echo "==> Building NS-3 + NR (this takes 20–30 minutes)..."
./ns3 build

# Write build sentinel (D1: written after successful build, before patches)
touch "$SENTINEL_BUILD"
echo "    Build sentinel written: $SENTINEL_BUILD"

# ── Apply CORNET patches ─────────────────────────────────────────────────────
PROFILE_FILE="$PATCHES_DIR/profiles/${PATCH_PROFILE}.txt"
if [[ ! -f "$PROFILE_FILE" ]]; then
    echo "ERROR: Unknown PATCH_PROFILE='$PATCH_PROFILE'." >&2
    echo "       Expected a file at $PROFILE_FILE" >&2
    exit 1
fi
echo "==> Applying CORNET patches (profile: $PATCH_PROFILE)..."
while IFS= read -r patch_line || [[ -n "$patch_line" ]]; do
    patch_name="${patch_line%%#*}"
    patch_name="${patch_name#"${patch_name%%[![:space:]]*}"}"
    patch_name="${patch_name%"${patch_name##*[![:space:]]}"}"
    if [[ -z "$patch_name" ]]; then
        continue
    fi
    patch_path="$PATCHES_DIR/$patch_name"
    if [[ ! -f "$patch_path" ]]; then
        echo "ERROR: Profile $PATCH_PROFILE lists missing patch $patch_name" >&2
        exit 1
    fi
    # ns3_*.patch edits the NS-3 tree (LTE, propagation, spectrum). Other patches edit NR.
    # A patch may also touch contrib/nr when the channel helper must learn a new scenario;
    # those paths are relative to NS3_DIR.
    if [[ "$patch_name" == ns3_* ]]; then
        apply_dir="$NS3_DIR"
    else
        apply_dir="$NR_DIR"
    fi
    if git -C "$apply_dir" apply --check "$patch_path" 2>/dev/null; then
        echo "    Applying $patch_name..."
        git -C "$apply_dir" apply "$patch_path"
    elif git -C "$apply_dir" apply --reverse --check "$patch_path" 2>/dev/null; then
        echo "    Already applied: $patch_name"
    else
        echo "ERROR: $patch_name does not apply in $apply_dir" >&2
        git -C "$apply_dir" apply --check "$patch_path" >&2 || true
        exit 1
    fi
done < "$PROFILE_FILE"

# ── Copy scratch scripts to NS-3 build tree ─────────────────────────────────
if [[ -d "$SCRATCH_SRC" ]]; then
    CC_COUNT=$(find "$SCRATCH_SRC" -maxdepth 1 -name '*.cc' | wc -l)
    if [[ "$CC_COUNT" -gt 0 ]]; then
        echo "==> Copying $CC_COUNT scratch script(s) from $SCRATCH_SRC to $NS3_DIR/scratch/..."
        cp "$SCRATCH_SRC"/*.cc "$NS3_DIR/scratch/"
        if compgen -G "$REPO_ROOT/scripts/ns3/scratch/*.h" > /dev/null; then
            cp "$REPO_ROOT/scripts/ns3/scratch/"*.h "$NS3_DIR/scratch/"
            echo "    Copied scratch headers"
        fi
        echo "    Copied: $(find "$SCRATCH_SRC" -maxdepth 1 -name '*.cc' -exec basename {} \; | tr '\n' ' ')"
    else
        echo "    WARNING: $SCRATCH_SRC exists but contains no .cc files (skipping scratch copy)"
    fi
else
    echo "    WARNING: No scratch scripts directory at $SCRATCH_SRC (skipping scratch copy)"
fi

# ── Rebuild with patches applied ────────────────────────────────────────────
echo "==> Rebuilding NS-3 with CORNET patches..."
cd "$NS3_DIR"
./ns3 build

# D1: both sentinels mean the patched build finished. A failed rebuild leaves this absent.
touch "$SENTINEL_PATCHED"
echo "    Patch sentinel written: $SENTINEL_PATCHED"

echo ""
echo "==> NS-3 ($NS3_TAG) + NR ($NR_TAG) installed and patched successfully."
echo "    PATCH_SET : $PATCH_SET"
echo "    NS3_DIR   : $NS3_DIR"
echo "    Set NS3_DIR=$NS3_DIR in your environment (or ~/.bashrc)."
echo "    Verify: python -m cornet --help"

# ── Set setuid on tap-creator (needed for non-root TAP bridge creation) ──────
TAP_CREATOR=$(find "$NS3_DIR/build/src/tap-bridge" -name "ns3.*-tap-creator-default" 2>/dev/null | head -1)
if [[ -n "$TAP_CREATOR" ]]; then
    echo ""
    echo "==> Setting setuid on tap-creator (required for non-root TAP bridge creation)..."
    if sudo -n chown root "$TAP_CREATOR" && sudo -n chmod u+s "$TAP_CREATOR"; then
        echo "    $TAP_CREATOR: $(ls -la "$TAP_CREATOR" | awk '{print $1,$3}')"
    else
        echo "    WARNING: sudo is unavailable, so tap-creator was left without setuid."
        echo "             TAP bridge creation will require running as root."
    fi
else
    echo ""
    echo "    WARNING: tap-creator binary not found under $NS3_DIR/build/src/tap-bridge"
    echo "             TAP bridge creation will require running as root."
fi
