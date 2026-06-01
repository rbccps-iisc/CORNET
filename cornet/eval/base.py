"""EvalTool base class for CORNET tasks."""

from __future__ import annotations

import abc
import math


class EvalTool(abc.ABC):
    """Task-local metric extractor.

    Contract:
    - Return first line in the form `SUCCESS, <metric>` or `FAILURE,`
    - Additional lines may follow with debugging details
    """

    @classmethod
    def format_result(cls, value: float, status: str = "SUCCESS") -> str:
        """Construct a correctly formatted result string for run_evaluation().

        :param value: The primary metric value; must be a finite float.
        :param status: Result status string (default ``"SUCCESS"``).
        :raises TypeError: if *value* cannot be interpreted as a float.
        :raises ValueError: if *value* is not finite (inf or nan).
        """
        v = float(value)
        if not math.isfinite(v):
            raise ValueError(
                f"EvalTool.format_result() value must be a finite float; got {value!r}"
            )
        return f"{status}, {v}"

    @abc.abstractmethod
    def run_evaluation(self, results_dir: str) -> str:
        """Evaluate one completed run directory and return the status string."""
