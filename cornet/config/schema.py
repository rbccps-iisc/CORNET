"""Pydantic v2 unified config schema for CORNET experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ConfigValidationError(ValueError):
    """Raised when a unified config fails schema validation."""


# ── Node models ──────────────────────────────────────────────────────────────

class ContainerConfig(BaseModel):
    image: str
    environment: dict[str, str] = {}
    volumes: list[str] = []


class NodeConfig(BaseModel):
    name: str
    type: Literal["MOBILE", "STATIC", "UE", "GNB", "EPC"] = "MOBILE"
    container: ContainerConfig | None = None
    # Arbitrary extra keys (e.g. position, speed) are allowed
    model_config = ConfigDict(extra="allow")


# ── Network section ───────────────────────────────────────────────────────────

class MininetConfig(BaseModel):
    wmediumd: bool = False
    ssid: str = "cornet-net"
    mode: str = "g"
    channel: int = 1


class NetworkConfig(BaseModel):
    plugin: str
    type: Literal["ns3", "mininet", "ns3+mininet"]
    nodes: list[NodeConfig] = []
    mininet: MininetConfig | None = None
    # NS-3 specific keys forwarded as-is
    model_config = ConfigDict(extra="allow")


# ── Robot section ─────────────────────────────────────────────────────────────

class ModelConfig(BaseModel):
    type: Literal["urdf", "sdf"]
    path: str  # relative to task dir or absolute


class PoseConfig(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


class RobotEntry(BaseModel):
    name: str
    model: ModelConfig
    pose: PoseConfig = PoseConfig()
    ros_namespace: str | None = None


class RobotConfig(BaseModel):
    plugin: str
    launch_file: str | None = None
    world: str | None = None
    robots: list[RobotEntry] = []


# ── Experiment section ────────────────────────────────────────────────────────

class SweepConfig(BaseModel):
    axes: dict[str, list[Any]]       # e.g. {"network.numerology": [2,4], "network.bandwidth": [20,40]}
    parallel: bool = False
    repeats: int = 1

    @field_validator("repeats")
    @classmethod
    def _positive_repeats(cls, v: int) -> int:
        if v < 1:
            raise ConfigValidationError("sweep.repeats must be >= 1")
        return v


class ExperimentConfig(BaseModel):
    name: str
    duration: float                  # seconds
    output_dir: str = "results"
    primary_metric: str | None = None
    higher_is_better: bool = False
    sweep: SweepConfig | None = None


# ── Top-level ─────────────────────────────────────────────────────────────────

class UnifiedConfig(BaseModel):
    """Root config model for CORNET unified schema (``_schema: unified-v1``)."""

    _schema: str = "unified-v1"      # literal marker; not validated by pydantic
    network: NetworkConfig
    robot: RobotConfig
    experiment: ExperimentConfig

    @model_validator(mode="after")
    def _cross_validate(self) -> "UnifiedConfig":
        # Mininet wmediumd requires Docker support — warn but don't error
        return self
