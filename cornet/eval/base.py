"""EvalTool base class for CORNET tasks."""

from __future__ import annotations

import abc


class EvalTool(abc.ABC):
    """Task-local metric extractor.

    Contract:
    - Return first line in the form `SUCCESS, <metric>` or `FAILURE,`
    - Additional lines may follow with debugging details
    """

    @abc.abstractmethod
    def run_evaluation(self, results_dir: str) -> str:
        """Evaluate one completed run directory and return the status string."""
