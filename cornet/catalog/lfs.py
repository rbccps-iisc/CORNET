"""Git LFS preflight for vendored catalogue meshes and textures."""

from __future__ import annotations

from pathlib import Path

_POINTER_MARK = "version https://git-lfs.github.com/spec/v1"
_SUFFIXES = {".dae", ".stl", ".png", ".jpg", ".jpeg"}


def missing_lfs_objects(root: Path | None = None) -> list[Path]:
    """Return asset paths that are still Git LFS pointers rather than file contents."""
    base = root or Path(__file__).resolve().parent
    missing: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SUFFIXES:
            continue
        try:
            head = path.read_text(errors="ignore")[:80]
        except OSError:
            continue
        if head.startswith(_POINTER_MARK):
            missing.append(path)
    return missing


def preflight(root: Path | None = None) -> None:
    missing = missing_lfs_objects(root)
    if missing:
        listed = ", ".join(str(path) for path in missing[:8])
        raise RuntimeError(
            "Git LFS objects are missing ("
            + listed
            + "). Run `git lfs install` and `git lfs pull` before compiling a scenario."
        )
