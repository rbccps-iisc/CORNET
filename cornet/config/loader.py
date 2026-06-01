"""Config loader for CORNET unified schema.

Usage:
    from cornet.config.loader import load_unified
    cfg = load_unified("tasks/my_task/config.yaml")
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cornet.config.schema import ConfigValidationError, UnifiedConfig


def load_unified(path: str | Path) -> UnifiedConfig:
    """Load and validate a unified-v1 YAML config file.

    Raises:
        ConfigValidationError: if the file is not unified-v1 or fails validation.
        FileNotFoundError: if *path* does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")

    with p.open() as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ConfigValidationError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    schema_tag = raw.get("_schema", "")
    if schema_tag != "unified-v1":
        raise ConfigValidationError(
            f"Expected '_schema: unified-v1', got '{schema_tag}'. "
            "This loader only handles unified configs."
        )

    try:
        return UnifiedConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigValidationError(str(exc)) from exc


def is_unified(path: str | Path) -> bool:
    """Return True if the YAML file at *path* declares ``_schema: unified-v1``."""
    p = Path(path)
    if not p.exists():
        return False
    try:
        with p.open() as fh:
            raw = yaml.safe_load(fh)
        return isinstance(raw, dict) and raw.get("_schema") == "unified-v1"
    except Exception:
        return False
