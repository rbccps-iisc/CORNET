"""Resolve ``requires_nr_capability`` against ``CAPABILITY_MATRIX.yaml``."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

_MATRIX = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "patches"
    / "ns3"
    / "CAPABILITY_MATRIX.yaml"
)

_PATCH_SET_BY_SENTINEL = {
    "v2.4": "v2.4-ns3.38",
    "v4.2": "v4.2-ns3.47",
    "v5.1": "v5.1-ns3.48",
}

_LANE_TAG = {
    "v2.4-ns3.38": "ns3-v24",
    "v4.2-ns3.47": "ns3-v47",
    "v5.1-ns3.48": "ns3-v51",
}

_LEVEL_RANK = {
    "upstream-available": 1,
    "cornet-integrated": 2,
    "cornet-validated": 3,
}


def load_matrix(path: Path | None = None) -> list[dict[str, Any]]:
    data = yaml.safe_load((path or _MATRIX).read_text())
    caps = data.get("capabilities") if isinstance(data, dict) else None
    if not isinstance(caps, list):
        raise ValueError(f"{path or _MATRIX} has no capabilities list")
    return caps


def find_ns3_dir() -> Path | None:
    env_dir = os.environ.get("NS3_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    for candidate in (
        Path.home() / "ns-3-dev",
        Path.home() / "ns-3-dev-v24",
        Path.home() / "ns-3-dev-v47",
        Path.home() / "ns-3-dev-v51",
    ):
        if candidate.exists():
            return candidate
    return None


def installed_patch_set(ns3_dir: Path) -> str | None:
    nr = ns3_dir / "contrib" / "nr"
    if not nr.is_dir():
        return None
    for path in sorted(nr.glob(".cornet-patched-*")):
        suffix = path.name.removeprefix(".cornet-patched-")
        if suffix in _PATCH_SET_BY_SENTINEL:
            return _PATCH_SET_BY_SENTINEL[suffix]
    return None


def capability_level(
    name: str,
    lane: str,
    matrix: list[dict[str, Any]] | None = None,
) -> str | None:
    """Return the level of *name* on *lane*, or None if the lane has no row."""
    entry = _lookup(matrix if matrix is not None else load_matrix(), name)
    if entry is None:
        return None
    for row in entry.get("supported_in") or []:
        if row.get("patch_set") == lane:
            level = row.get("level")
            return level if isinstance(level, str) else None
    return None


def required_lane(
    name: str,
    matrix: list[dict[str, Any]] | None = None,
) -> str | None:
    """Return the patch set with the strongest level for *name*.

    Ties keep the earlier ``supported_in`` row, which lists the stable lane first.
    """
    entry = _lookup(matrix if matrix is not None else load_matrix(), name)
    if entry is None:
        return None
    best_set: str | None = None
    best_rank = 0
    for row in entry.get("supported_in") or []:
        patch_set = row.get("patch_set")
        rank = _LEVEL_RANK.get(row.get("level"), 0)
        if isinstance(patch_set, str) and rank > best_rank:
            best_set = patch_set
            best_rank = rank
    return best_set


def detected_lane_tag(ns3_dir: Path | None = None) -> str | None:
    """Tag for the NS-3 tree the plugin will launch, from its patch sentinel."""
    tree = ns3_dir if ns3_dir is not None else find_ns3_dir()
    if tree is None:
        return None
    patch_set = installed_patch_set(tree)
    if patch_set is None:
        return None
    return _LANE_TAG.get(patch_set)


def _names(declared: str | list[str] | None) -> list[str]:
    if declared is None:
        return []
    if isinstance(declared, str):
        return [declared]
    return list(declared)


def _lookup(matrix: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for entry in matrix:
        if entry.get("name") == name:
            return entry
    return None


def assess(
    declared: str | list[str] | None,
    patch_set: str,
    matrix: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for the installed patch set."""
    errors: list[str] = []
    warnings: list[str] = []
    for name in _names(declared):
        entry = _lookup(matrix, name)
        if entry is None:
            errors.append(
                f"unknown capability '{name}' is not in CAPABILITY_MATRIX.yaml"
            )
            continue
        supported = entry.get("supported_in") or []
        mine = next((row for row in supported if row.get("patch_set") == patch_set), None)
        if not supported:
            errors.append(
                f"this task requires `{name}`, which is not supported on any lane and is deferred."
            )
            continue
        if mine is None:
            other = supported[0] if supported else None
            other_set = other.get("patch_set") if other else "another lane"
            short = other_set.split("-", 1)[0] if other_set else "another lane"
            install = {
                "v2.4-ns3.38": "make install-ns3",
                "v4.2-ns3.47": "make install-ns3-v47",
                "v5.1-ns3.48": "make install-ns3-v51",
            }.get(other_set, "make install-ns3-v47")
            needed = required_lane(name, matrix)
            if other and other.get("level") == "upstream-available":
                errors.append(
                    f"this task requires `{name}`, only available in {other_set}. "
                    f"Install with `{install}`. required lane: {needed}. "
                    f"{name} is upstream-available in {short} but not cornet-integrated. "
                    f"Install `{install}` and write a scratch script to use it."
                )
            else:
                errors.append(
                    f"this task requires `{name}`, only available in {other_set}. "
                    f"Install with `{install}`. required lane: {needed}."
                )
            continue
        level = mine.get("level")
        if level == "cornet-integrated":
            short = patch_set.split("-", 1)[0]
            warnings.append(
                f"{name} is integrated but not validated. "
                f"{name} is cornet-integrated in {short} but not yet cornet-validated. "
                "Results may differ from v2.4 baseline."
            )
        elif level == "upstream-available":
            warnings.append(
                f"{name} is upstream-available in {patch_set} but not cornet-integrated. "
                "A scratch script is required to use it through CORNET."
            )
    return errors, warnings


def enforce_declared_capabilities(config: Any, *, matrix_path: Path | None = None) -> None:
    """Exit if a declared capability is missing from the installed lane."""
    network = getattr(config, "network", None)
    declared = getattr(network, "requires_nr_capability", None)
    if not _names(declared):
        return
    if getattr(network, "plugin", "") not in {"ns3", "ns3+mininet"}:
        return
    ns3_dir = find_ns3_dir()
    if ns3_dir is None:
        print(
            "ERROR: requires_nr_capability is set but no NS-3 tree was found. "
            "Set NS3_DIR or install with make install-ns3.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    patch_set = installed_patch_set(ns3_dir)
    if patch_set is None:
        print(
            f"ERROR: {ns3_dir} has no .cornet-patched-* sentinel, so the lane is unknown.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    errors, warnings = assess(declared, patch_set, load_matrix(matrix_path))
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)


def report(config_path: Path) -> int:
    """Print the level of each capability declared in a task config."""
    data = yaml.safe_load(config_path.read_text())
    network = data.get("network") if isinstance(data, dict) else None
    declared = None if not isinstance(network, dict) else network.get("requires_nr_capability")
    names = _names(declared)
    ns3_dir = find_ns3_dir()
    patch_set = installed_patch_set(ns3_dir) if ns3_dir else None
    print(f"config: {config_path}")
    print(f"ns3_dir: {ns3_dir or 'not found'}")
    print(f"patch_set: {patch_set or 'unknown'}")
    if not names:
        print("declared: none")
        return 0
    matrix = load_matrix()
    if patch_set is None:
        print("declared capabilities cannot be checked without an installed lane")
        return 1
    errors, warnings = assess(declared, patch_set, matrix)
    for name in names:
        entry = _lookup(matrix, name)
        row = None
        if entry:
            row = next(
                (item for item in entry.get("supported_in") or [] if item.get("patch_set") == patch_set),
                None,
            )
        level = row.get("level") if row else "absent"
        print(f"  {name}: {level}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0
