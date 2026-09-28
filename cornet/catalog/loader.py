"""Load ``pack.yaml`` files from ``cornet/catalog``."""

from __future__ import annotations

from pathlib import Path

import yaml

from cornet.catalog.schema import Pack

CATALOG_ROOT = Path(__file__).resolve().parent
_KINDS = ("robots", "worlds", "networks")


def pack_dir(kind: str, name: str) -> Path:
    return CATALOG_ROOT / kind / name


def load_pack(kind: str, name: str) -> Pack:
    path = pack_dir(kind, name) / "pack.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"catalogue pack not found: {kind}/{name}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a mapping")
    pack = Pack.model_validate(data)
    if pack.kind != kind or pack.name != name:
        raise ValueError(f"{path} declares {pack.kind}/{pack.name}, expected {kind}/{name}")
    return pack


def list_packs(kind: str | None = None) -> list[Pack]:
    kinds = (kind,) if kind else _KINDS
    found: list[Pack] = []
    for item in kinds:
        root = CATALOG_ROOT / item
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/pack.yaml")):
            found.append(load_pack(item, path.parent.name))
    return found
