"""Seeded comparison. The agent does not compute these numbers."""

from __future__ import annotations

import math
from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    return sum((v - mu) ** 2 for v in values) / (len(values) - 1)


def _normality_ok(values: list[float]) -> bool:
    if len(values) < 3:
        return True
    try:
        from scipy import stats
    except ImportError:
        return True
    _stat, p_value = stats.shapiro(values)
    return float(p_value) >= 0.05


def _welch(a: list[float], b: list[float]) -> tuple[float, float]:
    from scipy import stats

    result = stats.ttest_ind(a, b, equal_var=False)
    return float(result.statistic), float(result.pvalue)


def _mann_whitney(a: list[float], b: list[float]) -> tuple[float, float]:
    from scipy import stats

    result = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(result.statistic), float(result.pvalue)


def _cohens_d(a: list[float], b: list[float]) -> float:
    va, vb = _variance(a), _variance(b)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / max(len(a) + len(b) - 2, 1))
    if pooled == 0:
        return 0.0
    return (_mean(a) - _mean(b)) / pooled


def _ci(a: list[float], b: list[float]) -> tuple[float, float]:
    diff = _mean(a) - _mean(b)
    se = math.sqrt(_variance(a) / len(a) + _variance(b) / len(b))
    return diff - 1.96 * se, diff + 1.96 * se


def compare_samples(
    a: list[float],
    b: list[float],
    *,
    alpha: float = 0.05,
    expect: str = "different",
) -> dict[str, Any]:
    if len(a) < 2 or len(b) < 2:
        raise ValueError("compare needs at least two samples on each side")
    normal = _normality_ok(a) and _normality_ok(b)
    test = "welch" if normal else "mannwhitney"
    _stat, p_value = _welch(a, b) if normal else _mann_whitney(a, b)
    mean_a, mean_b = _mean(a), _mean(b)
    low, high = _ci(a, b)
    if p_value > alpha:
        verdict = "inconclusive"
    elif expect == "a_lower" and mean_a < mean_b:
        verdict = "supported"
    elif expect == "a_higher" and mean_a > mean_b:
        verdict = "supported"
    elif expect == "different" and mean_a != mean_b:
        verdict = "supported"
    else:
        verdict = "refuted"
    return {
        "test": test,
        "p_value": p_value,
        "alpha": alpha,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "effect_size": _cohens_d(a, b),
        "ci95": [low, high],
        "verdict": verdict,
    }
