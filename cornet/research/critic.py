"""Deterministic research rules and Challenge Report parsing."""

from __future__ import annotations

import re
from typing import Any

from cornet.capabilities import capability_level
from cornet.research.brief import Brief

_SEVERITY = re.compile(r"severity\**\s*:\s*(blocking|major|minor)", re.IGNORECASE)


def parse_challenge_report(text: str) -> list[dict[str, str]]:
    challenges: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if line.startswith("### Challenge"):
            if current:
                challenges.append(current)
            title = line.split(":", 1)[-1].strip()
            current = {"title": title, "severity": "minor", "detail": ""}
            continue
        if current is None:
            continue
        match = _SEVERITY.search(line)
        if match:
            current["severity"] = match.group(1).lower()
        else:
            current["detail"] += line.strip() + " "
    if current:
        challenges.append(current)
    return challenges


def has_blocking(challenges: list[dict[str, str]]) -> bool:
    return any(item.get("severity") == "blocking" for item in challenges)


def deterministic_checks(brief: Brief, overrides: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Violations are blocking regardless of the critic agent's text."""
    problems: list[dict[str, str]] = []
    scenario = brief.scenario or {}
    radio = scenario.get("radio_sites") or {}
    anchor = radio.get("robot_anchor") or radio.get("anchor")
    if anchor and anchor != "ring0" and not radio.get("wraparound"):
        problems.append(
            {
                "severity": "blocking",
                "title": "wrap-around",
                "detail": f"anchor {anchor} is outside ring 0 and wrap-around is off",
            }
        )
    needed = []
    if str(radio.get("deployment", "")).startswith("3gpp_inf") or radio.get("channel") == "InF":
        needed.append("channel_inf")
    if anchor == "crossing":
        needed.append("nr_handover")
    if radio.get("wraparound"):
        needed.append("hex_wraparound")
    for name in needed:
        if capability_level(name, brief.lane) is None:
            problems.append(
                {
                    "severity": "blocking",
                    "title": "lane capability",
                    "detail": f"{brief.lane} lacks {name}",
                }
            )
    for variable in brief.independent_variables:
        if variable.path.endswith("isd_m"):
            problems.append(
                {
                    "severity": "blocking",
                    "title": "ISD",
                    "detail": "ISD is derived from the deployment",
                }
            )
    changed = [item for item in (overrides or []) if len(item) > 1]
    if changed and not brief.factorial:
        keys = ", ".join(sorted(changed[0]))
        problems.append(
            {
                "severity": "blocking",
                "title": "confounding",
                "detail": f"batch changes {keys} together without a factorial design",
            }
        )
    if brief.repeats < 5:
        problems.append(
            {
                "severity": "blocking",
                "title": "repeats",
                "detail": f"repeats {brief.repeats} are below the minimum of 5",
            }
        )
    return problems


def caveats_for(entry: dict[str, Any], *, scenario: dict[str, Any] | None = None) -> list[str]:
    labels: list[str] = []
    scenario = scenario or {}
    radio = scenario.get("radio_sites") or {}
    world = scenario.get("world") or ""
    deployment = str(radio.get("deployment") or "")
    if entry.get("standard") is False:
        labels.append("non-standard deployment")
    if "warehouse" in world and deployment == "3gpp_inh_office":
        labels.append("InH approximation")
    if deployment.startswith("3gpp_inf") or radio.get("channel") == "InF":
        labels.append("InF (uncalibrated)")
    if radio.get("blockage") == "model_a":
        labels.append("statistical blockage only")
    if entry.get("caveat") == "aerial path loss only" or scenario.get("caveat") == "aerial path loss only":
        labels.append("aerial path loss only")
    rtf = entry.get("rtf_mean")
    if isinstance(rtf, (int, float)) and rtf < 1:
        labels.append("slowed co-simulation (rtf < 1)")
    if entry.get("timing_ok") is False:
        labels.append("timing assumption violated")
    return labels


def guard_metric_flags(brief: Brief, primary_delta: float, guards: dict[str, float]) -> list[dict[str, str]]:
    """Flag a comparison whose primary metric improved while a guard degraded."""
    flags = []
    for guard in brief.guard_metrics:
        delta = guards.get(guard.name)
        if delta is None:
            continue
        degraded = delta < -guard.tolerance if guard.higher_is_better else delta > guard.tolerance
        improved = primary_delta < 0  # lower primary (AoI) is an improvement
        if improved and degraded:
            flags.append(
                {
                    "severity": "major",
                    "title": "metric gaming",
                    "detail": f"{guard.name} degraded while the primary metric improved",
                }
            )
    return flags
