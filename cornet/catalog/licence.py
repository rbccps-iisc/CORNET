"""Machine-checked licence provenance for catalogue packs."""

from __future__ import annotations

from pathlib import Path

from cornet.catalog.loader import CATALOG_ROOT, list_packs

_ALLOW = {"MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "project-owned"}
_ASSET_SUFFIXES = {".dae", ".stl", ".png", ".jpg", ".jpeg"}


def _assets(pack_path: Path) -> list[Path]:
    return [
        path
        for path in pack_path.rglob("*")
        if path.is_file() and path.suffix.lower() in _ASSET_SUFFIXES
    ]


def licence_issue(spdx: str, *, vendored: bool, has_assets: bool, has_license_file: bool) -> str | None:
    """Return one reason a pack licence is unacceptable, or None."""
    if "GPL" in spdx.upper():
        return f"GPL licence ({spdx}) cannot be vendored"
    if spdx not in _ALLOW:
        return f"licence {spdx} is not on the allowlist"
    if vendored and spdx != "project-owned" and has_assets and not has_license_file:
        return "vendored pack has assets and no LICENSE file"
    if not vendored and has_assets:
        return "vendored: false but the pack contains asset files"
    return None


def licence_problems() -> list[str]:
    problems: list[str] = []
    for pack in list_packs():
        label = f"{pack.kind}/{pack.name}"
        root = CATALOG_ROOT / pack.kind / pack.name
        issue = licence_issue(
            pack.license.spdx,
            vendored=pack.license.vendored,
            has_assets=bool(_assets(root)),
            has_license_file=(root / "LICENSE").is_file(),
        )
        if issue:
            problems.append(f"{label}: {issue}")
    return problems
