"""Gazebo Classic + ROS 2 robot plugin for CORNET."""

from __future__ import annotations

import logging
import signal
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cornet.plugins.base import Plugin

if TYPE_CHECKING:
    from cornet.config.schema import UnifiedConfig
    from cornet.context import ExperimentContext

logger = logging.getLogger(__name__)

_CLOCK_TOPIC_TIMEOUT = 60  # seconds to wait for /clock to appear


class GazeboPlugin(Plugin):
    """Launches Gazebo Classic via ros2 launch; spawns robots per config.

    If ``robot.launch_file`` is set, that file is used directly.
    Otherwise, a launch file is auto-generated from ``robot.robots``.
    """

    def __init__(self) -> None:
        self._config = None
        self._context = None
        self._launch_path: Path | None = None
        self._launch_proc: subprocess.Popen | None = None
        self._auto_generated = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def configure(self, config: "UnifiedConfig", context: "ExperimentContext") -> None:
        self._config = config
        self._context = context

        if config.robot.launch_file:
            self._launch_path = Path(config.robot.launch_file)
            self._auto_generated = False
        else:
            # Will be set in start() once we know task_dir — we need task_dir
            # The Orchestrator sets launch_file via auto-discovery before configure(),
            # so if we get here launch_file is truly absent.
            self._auto_generated = True

    def start(self) -> None:
        cfg = self._config

        if self._auto_generated:
            # Generate from robot config — use a temp dir
            import tempfile
            task_dir = Path(tempfile.mkdtemp(prefix="cornet_launch_"))
            from cornet.gazebo.generic_launch import generate
            self._launch_path = generate(cfg.robot, task_dir)
            logger.info("Auto-generated launch file: %s", self._launch_path)

        if self._launch_path is None or not self._launch_path.exists():
            raise FileNotFoundError(f"Launch file not found: {self._launch_path}")

        logger.info("Launching Gazebo via: ros2 launch %s", self._launch_path)
        self._launch_proc = subprocess.Popen(
            ["ros2", "launch", str(self._launch_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self._wait_for_clock()

    def run(self) -> None:
        pass

    def stop(self) -> None:
        if self._launch_proc is not None and self._launch_proc.poll() is None:
            self._launch_proc.send_signal(signal.SIGTERM)
            try:
                self._launch_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._launch_proc.kill()
                self._launch_proc.wait()
            logger.info("Gazebo launch process stopped")
        self._launch_proc = None

        # Clean up auto-generated file
        if self._auto_generated and self._launch_path and self._launch_path.exists():
            self._launch_path.unlink(missing_ok=True)

    def collect(self, output_dir: Path) -> None:
        pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _wait_for_clock(self) -> None:
        """Poll until Gazebo /clock topic appears or timeout."""
        deadline = time.monotonic() + _CLOCK_TOPIC_TIMEOUT
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["ros2", "topic", "list"],
                capture_output=True,
                text=True,
            )
            if "/clock" in result.stdout:
                logger.info("Gazebo /clock topic available — simulation running")
                return
            if self._launch_proc and self._launch_proc.poll() is not None:
                raise RuntimeError(
                    f"ros2 launch exited early (code {self._launch_proc.returncode})"
                )
            time.sleep(2)
        raise TimeoutError(
            f"Gazebo /clock not available after {_CLOCK_TOPIC_TIMEOUT} s. "
            "Check Gazebo installation and ROS 2 environment."
        )


# Register
from cornet.plugins import register as _register
_register("gazebo", GazeboPlugin)
