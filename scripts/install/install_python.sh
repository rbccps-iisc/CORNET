#!/usr/bin/env bash
# install_python.sh — Install the CORNET Python package in editable mode.
#
# Idempotency gate: skips if cornet-framework is already installed.
# Run from the CORNET_Research repository root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Checking Python prerequisites..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first." >&2
    exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
REQUIRED_MINOR=10
ACTUAL_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
ACTUAL_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
if [[ "$ACTUAL_MAJOR" -lt 3 ]] || { [[ "$ACTUAL_MAJOR" -eq 3 ]] && [[ "$ACTUAL_MINOR" -lt "$REQUIRED_MINOR" ]]; }; then
    echo "ERROR: Python 3.10+ required, found $PY_VERSION" >&2
    exit 1
fi

echo "    Python $PY_VERSION — OK"

# Idempotency gate
if python3 -c "import cornet" &>/dev/null 2>&1; then
    INSTALLED_VER="$(python3 -c 'import importlib.metadata; print(importlib.metadata.version("cornet-framework"))' 2>/dev/null || echo 'unknown')"
    echo "==> cornet-framework $INSTALLED_VER already installed — skipping."
    echo "    To reinstall: pip install -e .[dev] --force-reinstall"
    exit 0
fi

echo "==> Installing cornet-framework in editable mode..."
cd "$REPO_ROOT"
pip install -e ".[dev]"

echo ""
echo "==> cornet-framework installed successfully."
echo "    Verify: python -m cornet --help"
