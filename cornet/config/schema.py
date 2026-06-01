"""Pydantic v2 unified config schema for CORNET experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_VALID_SCENARIO_PROFILES = ("5g_nr_urllc", "5g_nr_embb", "5g_nr_mmtc", "6g_thz")


class ConfigValidationError(ValueError):
    """Raised when a unified config fails schema validation."""


# ── Node models ──────────────────────────────────────────────────────────────

class ContainerConfig(BaseModel):
    image: str
    environment: dict[str, str] = {}
    volumes: list[str] = []
    cpu_quota: float | None = None    # fraction of one CPU core, e.g. 0.5
    mem_limit_mb: int | None = None   # memory limit in MiB


class NodeConfig(BaseModel):
    name: str
    type: Literal["MOBILE", "STATIC", "UE", "GNB", "EPC"] = "MOBILE"
    container: ContainerConfig | None = None
    # First-class position and network identity fields
    ip: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    model_name: str | None = None  # when set, node is tracked by PositionBroadcaster
    # Arbitrary extra keys are allowed for forward-compatibility
    model_config = ConfigDict(extra="allow")


# ── Network section ───────────────────────────────────────────────────────────

class MininetConfig(BaseModel):
    wmediumd: bool = False
    ssid: str = "cornet-net"
    mode: str = "g"
    channel: int = 1


class MiddlewareConfig(BaseModel):
    """Co-simulation middleware settings (TUN, PacketDispatcher, AoI)."""
    enabled: bool = False
    ip_list: list[str] = []
    rtf: float = 1.0                          # real-time factor (0 = max speed)
    deadline_s: float = 0.5                   # drop packets older than this
    ber: float = 0.0                          # bit-error rate (0 = disabled)
    clock_timeout_s: float = 5.0             # fallback to wall clock after this
    clock_socket: str = "/tmp/cornet_clock.sock"
    positions_socket: str = "/tmp/cornet_positions.sock"


class MobilityConfig(BaseModel):
    """Live position update settings for PositionBroadcaster."""
    enabled: bool = False
    source: str = "socket"                    # socket | ros2_topic | none
    update_hz: float = 10.0
    update_mode: Literal["periodic", "threshold", "step_aligned"] = "periodic"
    position_threshold_m: float = 0.5        # used when update_mode=threshold


class ScenarioConfig(BaseModel):
    """5G/6G NS-3 scenario profile selection."""
    profile: str
    numerology: int | None = None
    bandwidth_mhz: float | None = None
    scheduler: str | None = None
    experimental: bool = False

    @field_validator("profile")
    @classmethod
    def _valid_profile(cls, value: str) -> str:
        if value not in _VALID_SCENARIO_PROFILES:
            valid = ", ".join(_VALID_SCENARIO_PROFILES)
            raise ConfigValidationError(
                f"scenario.profile must be one of: {valid}"
            )
        return value

    @model_validator(mode="after")
    def _mark_experimental(self) -> "ScenarioConfig":
        if self.profile == "6g_thz":
            self.experimental = True
        return self


class NetworkConfig(BaseModel):
    plugin: str
    type: Literal["ns3", "mininet", "ns3+mininet"]
    nodes: list[NodeConfig] = []
    mininet: MininetConfig | None = None
    middleware: MiddlewareConfig | None = None
    mobility: MobilityConfig | None = None
    scenario: ScenarioConfig | None = None
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
