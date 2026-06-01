"""Built-in NS-3 scenario template paths for CORNET."""

from __future__ import annotations

from pathlib import Path


def scenario_root() -> Path:
    return Path(__file__).parent