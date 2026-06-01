#!/usr/bin/env python3
"""
check_ns3_compat.py — CORNET NS-3 compatibility pre-flight checker.

Performs five read-only checks against a given NS-3 + NR installation:
  1. Version matrix validation
  2. Patch dry-run (git apply --check)
  3. Anchor symbol existence in target source files
  4. Collision detection for CORNET-injected symbols
  5. CORNET scenario Python API drift detection

Usage:
  python3 scripts/check_ns3_compat.py --ns3-dir ~/ns-3-dev
  python3 scripts/check_ns3_compat.py --ns3-dir ~/ns-3-dev --patch-set v4.2-ns3.47
  python3 scripts/check_ns3_compat.py --ns3-dir ~/ns-3-dev --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Version matrix: known-compatible (ns3_version, nr_version) pairs
# ---------------------------------------------------------------------------
VERSION_MATRIX: dict[str, str] = {
    "3.38": "2.4",   # proven — CORNET patches validated here
    "3.47": "4.2",   # latest — migration pending
}

# Anchored symbols that MUST exist before CORNET patches can apply cleanly
ANCHOR_SYMBOLS: dict[str, list[tuple[str, str]]] = {
    # (relative-path-from-ns3-root, symbol-to-grep)
    "ns3": [
        ("src/lte/model/lte-pdcp.cc", "LtePdcp"),
        ("src/lte/helper/lte-helper.cc", "InstallSingleUeDevice"),
        ("src/lte/model/lte-net-device.cc", "LteNetDevice"),
    ],
    "nr": [
        ("model/nr-mac-scheduler-ns3.cc", "DoScheduleDlData"),
        ("model/nr-mac-scheduler-ns3.cc", "DoScheduleUlData"),
        ("model/nr-mac-scheduler-ns3.cc", "AssignStreams"),
        ("model/nr-mac-scheduler-lcg.h", "NrMacSchedulerLCG"),
    ],
}

# CORNET-injected class names that must NOT exist pre-patch (collision check)
INJECTED_SYMBOLS: list[str] = [
    "NrMacSchedulerOfdmaEdf",
    "NrMacSchedulerOfdmaAoi",
    "NrMacSchedulerUeInfoEdf",
    "NrMacSchedulerUeInfoAoi",
]

# API symbols that were renamed between NR v2.4 and v4.2
# Each entry: (old_symbol, new_symbol, nr_version_where_renamed)
API_DRIFT_SYMBOLS: list[tuple[str, str, str]] = [
    ("NrEpsBearer", "NrQosFlow", "4.0"),
    ("NrEpcTft", "NrQosRule", "4.0"),
    ("SetDlEarfcn", "SetDlArfcn", "3.2"),
    ("SetUlEarfcn", "SetUlArfcn", "3.2"),
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

CheckStatus = Literal["PASS", "WARN", "FAIL", "SKIP"]


@dataclass
class CheckResult:
    check_id: int
    name: str
    status: CheckStatus
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "check": self.check_id,
            "name": self.name,
            "status": self.status,
            "details": self.details,
        }


class CompatReport:
    def __init__(self, results: list[CheckResult]) -> None:
        self.results = results

    def overall(self) -> Literal["COMPATIBLE", "NEEDS_MIGRATION", "INCOMPATIBLE"]:
        statuses = {r.status for r in self.results}
        if "FAIL" in statuses:
            return "INCOMPATIBLE"
        if "WARN" in statuses:
            return "NEEDS_MIGRATION"
        return "COMPATIBLE"

    def exit_code(self) -> int:
        return 0 if self.overall() == "COMPATIBLE" else 1

    def to_text(self) -> str:
        lines: list[str] = ["CORNET NS-3 Compatibility Report", "=" * 40]
        for r in self.results:
            icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "SKIP": "–"}.get(r.status, "?")
            lines.append(f"\n[{r.check_id}] {r.name}: {icon} {r.status}")
            for detail in r.details:
                lines.append(f"    {detail}")
        lines.append("\n" + "=" * 40)
        lines.append(f"Overall: {self.overall()}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "overall": self.overall(),
                "results": [r.to_dict() for r in self.results],
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grep(path: Path, pattern: str) -> list[tuple[int, str]]:
    """Return list of (line_number, line) matching pattern in path."""
    if not path.is_file():
        return []
    hits = []
    try:
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if re.search(pattern, line):
                hits.append((i, line.rstrip()))
    except OSError:
        pass
    return hits


def _detect_ns3_version(ns3_dir: Path) -> str | None:
    version_file = ns3_dir / "VERSION"
    if version_file.is_file():
        text = version_file.read_text().strip()
        # Format: "3.38" or "ns-3.38" or "3.38.0"
        m = re.search(r"(\d+\.\d+)", text)
        if m:
            return m.group(1)
    # Fallback: check CMakeLists.txt
    cmake = ns3_dir / "CMakeLists.txt"
    if cmake.is_file():
        text = cmake.read_text()
        m = re.search(r"set\s*\(\s*NS3_VERSION\s+(\d+\.\d+)", text)
        if m:
            return m.group(1)
    return None


def _detect_nr_version(nr_dir: Path) -> str | None:
    for candidate in ["RELEASE_NOTES.md", "CHANGES.md", "version.txt"]:
        path = nr_dir / candidate
        if path.is_file():
            text = path.read_text(errors="replace")
            # Look for "NR v2.4" or "## [2.4]" or "nr-2.4" patterns
            m = re.search(r"[Nn][Rr][\s\-]?v?(\d+\.\d+)", text)
            if m:
                return m.group(1)
    # Fallback: git describe
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=nr_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()  # e.g. "v2.4"
            m = re.search(r"v?(\d+\.\d+)", tag)
            if m:
                return m.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _patches_dir(script_dir: Path, patch_set: str) -> Path:
    return script_dir / "patches" / "ns3" / patch_set


def _available_patch_sets(script_dir: Path) -> list[str]:
    patches_root = script_dir / "patches" / "ns3"
    if not patches_root.is_dir():
        return []
    return [d.name for d in sorted(patches_root.iterdir()) if d.is_dir()]


def _expected_patches_from_migration_status(patch_set_dir: Path) -> list[str]:
    """Read MIGRATION_STATUS.md and return list of expected patch file names."""
    status_file = patch_set_dir / "MIGRATION_STATUS.md"
    if not status_file.is_file():
        return []
    expected = []
    text = status_file.read_text()
    # Match table rows: | `ns3_lte_pdcp.patch` | ⏳ pending | ...
    for m in re.finditer(r"`([^`]+\.patch)`", text):
        expected.append(m.group(1))
    return expected


# ---------------------------------------------------------------------------
# The five checks
# ---------------------------------------------------------------------------

def check_version_matrix(ns3_dir: Path) -> CheckResult:
    """Check 1: Detected NS-3 and NR versions are in the known compat matrix."""
    nr_dir = ns3_dir / "contrib" / "nr"
    ns3_ver = _detect_ns3_version(ns3_dir)
    nr_ver = _detect_nr_version(nr_dir) if nr_dir.is_dir() else None

    details: list[str] = []
    details.append(f"Detected NS-3 version: {ns3_ver or 'UNKNOWN'}")
    details.append(f"Detected NR version:   {nr_ver or 'UNKNOWN'}")

    if ns3_ver is None or nr_ver is None:
        return CheckResult(1, "Version matrix", "FAIL", details + [
            "Could not detect NS-3 or NR version — is NS3_DIR correct?",
        ])

    expected_nr = VERSION_MATRIX.get(ns3_ver)
    if expected_nr is None:
        return CheckResult(1, "Version matrix", "FAIL", details + [
            f"NS-3 {ns3_ver} is not in CORNET's compatibility matrix.",
            f"Known NS-3 versions: {', '.join(VERSION_MATRIX)}",
        ])

    if nr_ver != expected_nr:
        return CheckResult(1, "Version matrix", "FAIL", details + [
            f"NS-3 {ns3_ver} expects NR v{expected_nr}, but found NR v{nr_ver}.",
            "Install the correct NR version or update the matrix in check_ns3_compat.py.",
        ])

    return CheckResult(1, "Version matrix", "PASS", details)


def check_patch_dry_run(
    ns3_dir: Path,
    script_dir: Path,
    patch_set: str,
) -> CheckResult:
    """Check 2: All patches in the selected set apply cleanly (git apply --check)."""
    patch_set_dir = _patches_dir(script_dir, patch_set)
    nr_dir = ns3_dir / "contrib" / "nr"

    if not patch_set_dir.is_dir():
        available = _available_patch_sets(script_dir)
        return CheckResult(2, "Patch dry-run", "FAIL", [
            f"Patch set directory not found: {patch_set_dir}",
            f"Available patch sets: {', '.join(available) or 'none'}",
        ])

    # Determine expected patches from MIGRATION_STATUS.md (D3 constraint)
    expected = _expected_patches_from_migration_status(patch_set_dir)

    # Collect actual patch files (exclude individual EDF/AoI originals if
    # the combined nr_schedulers.patch is present)
    patch_files = sorted(patch_set_dir.glob("*.patch"))
    actual_names = {p.name for p in patch_files}

    details: list[str] = []

    # Check for missing patches (MIGRATION_STATUS entries without a file)
    for expected_name in expected:
        if expected_name not in actual_names:
            details.append(f'FAIL(not-yet-migrated: {expected_name})')

    if any("not-yet-migrated" in d for d in details):
        return CheckResult(2, "Patch dry-run", "FAIL", details)

    if not patch_files:
        return CheckResult(2, "Patch dry-run", "SKIP", [
            f"No *.patch files found in {patch_set_dir}",
        ])

    # Map patch to its application directory
    # Patches are applied in canonical order: ns3_lte_pdcp (NS-3 root), then nr_*
    all_passed = True
    for patch_path in patch_files:
        name = patch_path.name
        # LTE PDCP patch applies to NS-3 root; NR patches apply to contrib/nr
        if "lte" in name:
            apply_dir = ns3_dir
        else:
            apply_dir = nr_dir

        if not apply_dir.is_dir():
            details.append(f"SKIP {name} — target dir not found: {apply_dir}")
            continue

        result = subprocess.run(
            ["git", "apply", "--check", str(patch_path)],
            cwd=apply_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            details.append(f"PASS {name}")
        else:
            all_passed = False
            stderr = result.stderr.strip()
            # Extract failing file and hunk info for diagnostic
            for line in stderr.splitlines():
                if "patch failed" in line.lower() or "error:" in line.lower():
                    details.append(f'FAIL(hunk-mismatch: {name}) — {line.strip()}')

    status: CheckStatus = "PASS" if all_passed else "FAIL"
    return CheckResult(2, "Patch dry-run", status, details)


def check_anchor_symbols(ns3_dir: Path) -> CheckResult:
    """Check 3: Key symbols that patches depend on exist in the target source."""
    nr_dir = ns3_dir / "contrib" / "nr"
    details: list[str] = []
    all_found = True

    for scope, entries in ANCHOR_SYMBOLS.items():
        base = ns3_dir if scope == "ns3" else nr_dir
        for rel_path, symbol in entries:
            full = base / rel_path
            hits = _grep(full, re.escape(symbol))
            if hits:
                details.append(f"PASS {rel_path}: found '{symbol}' (line {hits[0][0]})")
            else:
                all_found = False
                if not full.is_file():
                    details.append(f"FAIL {rel_path}: file not found")
                else:
                    details.append(f"FAIL {rel_path}: symbol '{symbol}' not found")

    return CheckResult(3, "Anchor symbols", "PASS" if all_found else "FAIL", details)


def check_collision(ns3_dir: Path) -> CheckResult:
    """Check 4: CORNET-injected class names must NOT already exist in NR headers."""
    nr_dir = ns3_dir / "contrib" / "nr"
    details: list[str] = []
    any_collision = False

    if not nr_dir.is_dir():
        return CheckResult(4, "Collision detection", "SKIP", [
            "contrib/nr directory not found — skipping"
        ])

    for symbol in INJECTED_SYMBOLS:
        header_dir = nr_dir / "model"
        collisions = []
        if header_dir.is_dir():
            for header in header_dir.glob("*.h"):
                hits = _grep(header, re.escape(symbol))
                for lineno, _ in hits:
                    collisions.append(f"{header.name}:{lineno}")
        if collisions:
            any_collision = True
            details.append(f"WARN '{symbol}' already present in: {', '.join(collisions)}")
        else:
            details.append(f"PASS '{symbol}' not found in NR headers (safe to inject)")

    status: CheckStatus = "WARN" if any_collision else "PASS"
    return CheckResult(4, "Collision detection", status, details)


def check_scenario_api_drift(ns3_dir: Path, repo_root: Path) -> CheckResult:
    """Check 5: CORNET scenario scripts must not reference renamed NR API symbols."""
    nr_dir = ns3_dir / "contrib" / "nr"
    nr_ver = _detect_nr_version(nr_dir)
    details: list[str] = []
    any_drift = False

    scenarios_dir = repo_root / "cornet" / "scenarios"
    if not scenarios_dir.is_dir():
        return CheckResult(5, "Scenario API drift", "SKIP", [
            f"No scenarios directory found at {scenarios_dir}"
        ])

    for old_sym, new_sym, renamed_in_ver in API_DRIFT_SYMBOLS:
        # Only warn if the target NR version >= the version where it was renamed
        if nr_ver is not None:
            try:
                target = tuple(int(x) for x in nr_ver.split(".")[:2])
                threshold = tuple(int(x) for x in renamed_in_ver.split(".")[:2])
                if target < threshold:
                    continue  # old symbol still valid in target version
            except ValueError:
                pass  # version parse failure — check anyway

        for run_py in scenarios_dir.rglob("run.py"):
            hits = _grep(run_py, re.escape(old_sym))
            for lineno, _ in hits:
                any_drift = True
                rel = run_py.relative_to(repo_root)
                details.append(
                    f"WARN {rel}:{lineno}: '{old_sym}' renamed to '{new_sym}' in NR v{renamed_in_ver}"
                )

    if not any_drift:
        details.append("No stale API references found in cornet/scenarios/*/run.py")

    status: CheckStatus = "WARN" if any_drift else "PASS"
    return CheckResult(5, "Scenario API drift", status, details)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

class CompatChecker:
    def __init__(
        self,
        ns3_dir: Path,
        patch_set: str,
        script_dir: Path,
        repo_root: Path,
    ) -> None:
        self.ns3_dir = ns3_dir
        self.patch_set = patch_set
        self.script_dir = script_dir
        self.repo_root = repo_root

    def run_all(self) -> CompatReport:
        results: list[CheckResult] = []

        # Check 1: version matrix (gate — if FAIL, skip checks 2–5)
        r1 = check_version_matrix(self.ns3_dir)
        results.append(r1)
        if r1.status == "FAIL":
            for i, name in enumerate(
                [
                    "Patch dry-run",
                    "Anchor symbols",
                    "Collision detection",
                    "Scenario API drift",
                ],
                2,
            ):
                results.append(CheckResult(i, name, "SKIP", ["Skipped: version check failed"]))
            return CompatReport(results)

        results.append(check_patch_dry_run(self.ns3_dir, self.script_dir, self.patch_set))
        results.append(check_anchor_symbols(self.ns3_dir))
        results.append(check_collision(self.ns3_dir))
        results.append(check_scenario_api_drift(self.ns3_dir, self.repo_root))

        return CompatReport(results)


def _default_patch_set() -> str:
    return "v2.4-ns3.38"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CORNET NS-3 compatibility pre-flight checker (read-only).",
    )
    parser.add_argument(
        "--ns3-dir",
        required=True,
        type=Path,
        metavar="DIR",
        help="Path to the NS-3 installation root (contains src/, contrib/, VERSION).",
    )
    parser.add_argument(
        "--patch-set",
        default=_default_patch_set(),
        metavar="NAME",
        help=f"Versioned patch set to check against (default: {_default_patch_set()}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON to stdout.",
    )
    args = parser.parse_args()

    ns3_dir = args.ns3_dir.expanduser().resolve()
    if not ns3_dir.is_dir():
        print(f"error: --ns3-dir '{ns3_dir}' does not exist or is not a directory", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    checker = CompatChecker(
        ns3_dir=ns3_dir,
        patch_set=args.patch_set,
        script_dir=script_dir,
        repo_root=repo_root,
    )
    report = checker.run_all()

    if args.json_output:
        print(report.to_json())
    else:
        print(report.to_text())

    sys.exit(report.exit_code())


if __name__ == "__main__":
    main()
