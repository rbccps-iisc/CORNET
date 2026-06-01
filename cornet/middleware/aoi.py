"""AoITracker — per-flow Age-of-Information tracker.

Tracks the age of each flow's most recent status update relative to the
physics clock.  Writes a CSV trace on close and computes percentile
statistics using only the Python standard library (no numpy).

Age-of-Information (AoI) for flow f at time t:
    AoI_f(t) = t - u_f
where u_f is the physics timestamp of f's last received update.
"""

from __future__ import annotations

import csv
import logging
import math
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def _flow_filename(flow_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", flow_id).strip("_") or "unknown"
    return f"aoi_{safe}.csv"


class AoITracker:
    """Track Age-of-Information per flow.

    Parameters
    ----------
    trace_path:
        File path for the CSV trace.  Parent directories are created if they
        do not already exist.  Pass ``None`` to disable CSV output.
    sample_hz:
        How often (simulated-second-equivalent) the tracker samples AoI for
        each flow when the ``sample()`` method is called.
    """

    def __init__(
        self,
        trace_path: Path | str | None = None,
        sample_hz: float = 1.0,
    ) -> None:
        self._trace_path = Path(trace_path) if trace_path is not None else None
        self._sample_hz = sample_hz

        self._lock = threading.Lock()
        # flow_id -> physics_time of last update
        self._last_update: dict[str, float] = {}
        # flow_id -> list of (physics_time, aoi) samples
        self._samples: dict[str, list[tuple[float, float]]] = {}

        self._physics_time: float = 0.0

        self._closed = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_physics_time(self, t: float) -> None:
        """Advance the physics clock.  Thread-safe."""
        with self._lock:
            self._physics_time = t

    def record_update(self, flow_id: str, physics_time: float) -> None:
        """Record that flow ``flow_id`` delivered a fresh update at ``physics_time``."""
        with self._lock:
            self._last_update[flow_id] = physics_time

    def sample(self) -> dict[str, float]:
        """Sample the current AoI for every known flow.

        Returns a dict mapping flow_id -> current AoI in simulated seconds.
        Also appends a row to the CSV trace if enabled.
        """
        with self._lock:
            t = self._physics_time
            result: dict[str, float] = {}
            for flow_id, last_t in self._last_update.items():
                aoi = max(0.0, t - last_t)
                result[flow_id] = aoi
                self._samples.setdefault(flow_id, []).append((t, aoi))
        return result

    def summary(self) -> dict[str, dict[str, float]]:
        """Return per-flow summary statistics.

        Uses stdlib ``statistics`` for mean and linear interpolation for
        percentiles — no numpy required.
        """
        import statistics as _stats

        with self._lock:
            samples = {
                fid: [aoi for (_, aoi) in pts]
                for fid, pts in self._samples.items()
            }

        result: dict[str, dict[str, float]] = {}
        for flow_id, values in samples.items():
            if not values:
                result[flow_id] = {}
                continue
            sorted_v = sorted(values)
            result[flow_id] = {
                "mean_s": _stats.mean(sorted_v),
                "p50_s": _percentile(sorted_v, 50),
                "p90_s": _percentile(sorted_v, 90),
                "p95_s": _percentile(sorted_v, 95),
                "p99_s": _percentile(sorted_v, 99),
                "max_s": sorted_v[-1],
                "count": float(len(sorted_v)),
            }
        return result

    def export_json(self, path: Path | str) -> None:
        """Write summary statistics to a JSON file and emit per-flow CSV traces."""
        import json

        data = self.summary()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            snapshot = {
                flow_id: list(samples)
                for flow_id, samples in self._samples.items()
            }

        for flow_id, samples in snapshot.items():
            csv_path = out.parent / _flow_filename(flow_id)
            with csv_path.open("w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["physics_time", "aoi_s"])
                for physics_time, aoi in samples:
                    writer.writerow([f"{physics_time:.6f}", f"{aoi:.6f}"])

        with open(out, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("AoI summary written to %s", out)

    def close(self) -> None:
        """Mark the tracker closed. Export remains available after close()."""
        self._closed = True


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _percentile(sorted_data: list[float], pct: float) -> float:
    """Compute the *pct*-th percentile of already-sorted data.

    Uses linear interpolation (same as numpy's default).

    Parameters
    ----------
    sorted_data:
        Ascending-sorted list of floats.
    pct:
        Percentile value in [0, 100].
    """
    n = len(sorted_data)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_data[0]
    k = (pct / 100.0) * (n - 1)
    lo = int(math.floor(k))
    hi = lo + 1
    frac = k - lo
    if hi >= n:
        return sorted_data[-1]
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])
