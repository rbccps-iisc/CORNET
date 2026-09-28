"""CSV results, classification and the summary report."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from cornet.telemetry import percentile

_NS3_KEYS = (
    "sites",
    "sectors",
    "ues_per_cell",
    "traffic",
    "channel_update_ms",
    "numerology",
    "wraparound",
    "scheduler",
)
_GAZEBO_KEYS = ("world", "robots", "actors", "camera", "step_ms")

COLUMNS = [
    "suite",
    "config_id",
    "repeat",
    "seed",
    "mode",
    "pin_cpu",
    "tap",
    "tap_status",
    "sim_s",
    "wall_s",
    "speed_factor",
    "rtf_mean",
    "rtf_p5",
    "rtf_min_sample",
    "lag_p99",
    "lag_mean",
    "cpu_ns3",
    "cpu_gzserver",
    "error",
    "ns3_lane",
    "gazebo_version",
    "ros_version",
    "cpu_model",
    "cores",
    "ram_gb",
    "kernel",
    "gpu",
    *_NS3_KEYS,
    *_GAZEBO_KEYS,
]


def _median(values: list[float]) -> float:
    return percentile(values, 50)


def append_row(csv_path: Path, row: dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in COLUMNS})


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        return []
    with csv_path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _f(row: dict[str, str], key: str) -> float | None:
    raw = row.get(key, "")
    if raw in ("", None):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _ns3_identity(row: dict[str, str]) -> tuple:
    return tuple(row.get(key, "") for key in _NS3_KEYS)


def _prefer_tap(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], str]:
    tap_rows = [row for row in rows if row.get("tap") in {"True", "true", "1"} and row.get("tap_status") not in {"", "skipped"}]
    if tap_rows:
        return tap_rows, "tap"
    return rows, "no-TAP"


def classify_rows(
    rows: list[dict[str, str]],
    *,
    rtf_min: float = 0.95,
    lag_budget_ms: float = 1.0,
    speed_margin: float = 1.5,
) -> list[dict[str, Any]]:
    """Classify configs that appear in the combined suite. Others stay incomplete."""
    combined = [row for row in rows if row.get("suite") == "combined" and not row.get("error")]
    ns3_speed = [
        row
        for row in rows
        if row.get("suite") == "ns3" and row.get("mode") == "speed" and not row.get("error")
    ]
    by_name: dict[str, list[dict[str, str]]] = {}
    for row in combined:
        by_name.setdefault(row.get("config_id", ""), []).append(row)
    reports: list[dict[str, Any]] = []
    for name, group in by_name.items():
        chosen, tap_label = _prefer_tap(group)
        identity = _ns3_identity(chosen[0]) if chosen else tuple()
        speeds = [
            value
            for row in ns3_speed
            if _ns3_identity(row) == identity
            for value in [_f(row, "speed_factor")]
            if value is not None
        ]
        lags = [value for row in chosen if (value := _f(row, "lag_p99")) is not None]
        rtfs = [value for row in chosen if (value := _f(row, "rtf_p5")) is not None]
        if not speeds or not lags or not rtfs:
            label = "incomplete"
            recommendation = "run `python -m cornet bench all` so standalone speed and combined timing both exist"
        else:
            speed = _median(speeds)
            lag = _median(lags)
            rtf = _median(rtfs)
            ns3_ok = speed >= speed_margin and lag <= lag_budget_ms
            gazebo_ok = rtf >= rtf_min
            if ns3_ok and gazebo_ok:
                label = "realtime-ok"
                recommendation = "stay on realtime mode"
            elif ns3_ok and not gazebo_ok:
                label = "gazebo-limited"
                recommendation = "reduce Gazebo load or adopt NS-3-follows-Gazebo mode"
            else:
                label = "ns3-limited"
                recommendation = "reduce NS-3 load or revive lockstep"
        reports.append(
            {
                "config_id": name,
                "classification": label,
                "recommendation": recommendation,
                "tap_label": tap_label,
                "rtf_min": rtf_min,
                "lag_budget_ms": lag_budget_ms,
                "speed_margin": speed_margin,
            }
        )
    return reports


def _bar_svg(title: str, pairs: list[tuple[str, float]]) -> str:
    width = 640
    height = 40 + 28 * max(1, len(pairs))
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<text x="8" y="18" font-size="14">{title}</text>',
    ]
    max_value = max((value for _, value in pairs), default=1.0) or 1.0
    for index, (label, value) in enumerate(pairs):
        y = 32 + index * 28
        bar = int(420 * (value / max_value))
        lines.append(f'<text x="8" y="{y + 14}" font-size="12">{label}</text>')
        lines.append(f'<rect x="180" y="{y}" width="{bar}" height="16" fill="#3b6ea5"/>')
        lines.append(f'<text x="{190 + bar}" y="{y + 13}" font-size="12">{value:.3g}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def write_summary(
    dest_dir: Path,
    rows: list[dict[str, str]],
    classifications: list[dict[str, Any]],
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    speed_pairs: list[tuple[str, float]] = []
    for row in rows:
        if row.get("mode") == "speed":
            value = _f(row, "speed_factor")
            if value is not None:
                speed_pairs.append((f"{row.get('config_id')} r{row.get('repeat')}", value))
    rtf_pairs: list[tuple[str, float]] = []
    for row in rows:
        if row.get("suite") in {"gazebo", "combined"}:
            value = _f(row, "rtf_mean")
            if value is not None:
                rtf_pairs.append((f"{row.get('config_id')} r{row.get('repeat')}", value))
    (dest_dir / "speed.svg").write_text(_bar_svg("NS-3 speed factor", speed_pairs[:40]))
    (dest_dir / "rtf.svg").write_text(_bar_svg("Gazebo RTF mean", rtf_pairs[:40]))
    thresholds = ""
    if classifications:
        sample = classifications[0]
        thresholds = (
            f"Thresholds: speed_margin={sample['speed_margin']}, "
            f"lag_budget_ms={sample['lag_budget_ms']}, rtf_min={sample['rtf_min']}."
        )
    lines = [
        "# Co-simulation benchmark summary",
        "",
        thresholds,
        "",
        f"Rows: {len(rows)}.",
        "",
        "## Classification",
        "",
    ]
    if not classifications:
        lines.append("No combined configurations to classify.")
    for item in classifications:
        lines.append(
            f"- `{item['config_id']}`: **{item['classification']}** "
            f"({item['tap_label']}) — {item['recommendation']}"
        )
    lines.extend(
        [
            "",
            "## Plots",
            "",
            "![NS-3 speed](speed.svg)",
            "",
            "![Gazebo RTF](rtf.svg)",
            "",
        ]
    )
    path = dest_dir / "summary.md"
    path.write_text("\n".join(lines) + "\n")
    return path
