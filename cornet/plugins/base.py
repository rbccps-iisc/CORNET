"""Abstract Plugin base class defining the CORNET lifecycle interface."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cornet.config.schema import UnifiedConfig
    from cornet.context import ExperimentContext


class Plugin(abc.ABC):
    """Base class for all CORNET network and robot plugins.

    Lifecycle (called in this order by the Orchestrator):
        configure(config, context)
        start()
        run()
        stop()          # always called, even on error
        collect(output_dir)
    """

    @abc.abstractmethod
    def configure(self, config: "UnifiedConfig", context: "ExperimentContext") -> None:
        """Read config and context; prepare internal state. Must not start processes."""

    @abc.abstractmethod
    def start(self) -> None:
        """Launch subprocesses, create network topology, etc."""

    def run(self) -> None:  # noqa: B027 — intentionally non-abstract default
        """Block for experiment duration. Default: no-op (duration handled by Orchestrator)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Tear down subprocesses and topology. Must be idempotent."""

    def collect(self, output_dir: Path) -> None:  # noqa: B027
        """Copy results / metrics to output_dir. Default: no-op."""
