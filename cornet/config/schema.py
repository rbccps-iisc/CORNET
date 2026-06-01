"""Pydantic v2 unified config schema for CORNET experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_VALID_SCENARIO_PROFILES = ("5g_nr_urllc", "5g_nr_embb", "5g_nr_mmtc", "6g_thz")


class ConfigValidationError(ValueError):
    """Raised when a unified config fails schema validation."""


# ── Node models ──────────────────────────────────────────────────────────────

class ContainerConfig(BaseModel):
    image: str = Field(description="Docker image name (e.g. 'ros:humble' or a custom image built from the task's Dockerfile).")
    environment: dict[str, str] = Field(default={}, description="Environment variables injected into the container at start-up.")
    volumes: list[str] = Field(default=[], description="Host-to-container volume mounts in 'host:container[:mode]' format.")
    cpu_quota: float | None = Field(default=None, description="CPU quota as a fraction of one core (e.g. 0.5 = 50% of one CPU). None = unlimited.")
    mem_limit_mb: int | None = Field(default=None, description="Container memory limit in MiB. None = unlimited.")


class NodeConfig(BaseModel):
    name: str = Field(description="Unique node identifier within the network topology.")
    type: Literal["MOBILE", "STATIC", "UE", "GNB", "EPC"] = Field(
        default="MOBILE",
        description="Node role. MOBILE/STATIC for Mininet nodes; UE/GNB/EPC for NS-3 5G nodes.",
    )
    container: ContainerConfig | None = Field(default=None, description="Docker container config for this node. None = bare Mininet host.")
    # First-class position and network identity fields
    ip: str | None = Field(default=None, description="Static IP address (CIDR or bare, e.g. '10.0.0.1/24'). None = assigned by network plugin.")
    x: float | None = Field(default=None, description="Initial X position in metres (simulation world frame).")
    y: float | None = Field(default=None, description="Initial Y position in metres (simulation world frame).")
    z: float | None = Field(default=None, description="Initial Z position in metres (simulation world frame, 0 = ground level).")
    model_name: str | None = Field(default=None, description="Gazebo model name to track for live position updates via PositionBroadcaster.")
    # Arbitrary extra keys are allowed for forward-compatibility
    model_config = ConfigDict(extra="allow")


# ── Network section ───────────────────────────────────────────────────────────

class MininetConfig(BaseModel):
    wmediumd: bool = Field(default=False, description="Enable wmediumd wireless medium daemon for realistic Wi-Fi interference emulation (requires Docker).")
    ssid: str = Field(default="cornet-net", description="SSID for the Mininet-WiFi access point.")
    mode: str = Field(default="g", description="IEEE 802.11 mode ('a', 'b', 'g', 'n', 'ac').")
    channel: int = Field(default=1, description="Wi-Fi channel number (1–14 for 2.4 GHz, 36–165 for 5 GHz).")


class MiddlewareConfig(BaseModel):
    """Co-simulation middleware settings (TUN, PacketDispatcher, AoI)."""
    enabled: bool = Field(default=False, description="Enable the CORNET co-simulation middleware layer (TUN manager, packet dispatcher, AoI tracker, physics clock).")
    ip_list: list[str] = Field(default=[], description="IP addresses of simulation nodes that the TUN manager should bridge to the robot network.")
    rtf: float = Field(default=1.0, description="Real-time factor. 1.0 = wall-clock speed. Values < 1 slow simulation; 0 = maximum simulation speed (decoupled from wall clock).")
    deadline_s: float = Field(default=0.5, description="Packet age deadline in seconds. Packets older than this are dropped by the dispatcher before delivery.")
    ber: float = Field(default=0.0, description="Bit-error rate in [0, 1]. 0 = no artificial errors. Applied by the dispatcher before AoI accounting.")
    clock_timeout_s: float = Field(default=5.0, description="Seconds after which the physics clock falls back to wall clock if no NS-3 clock tick is received.")
    clock_socket: str = Field(default="/tmp/cornet_clock.sock", description="UNIX socket path for the physics clock synchronisation channel.")
    positions_socket: str = Field(default="/tmp/cornet_positions.sock", description="UNIX socket path for the PositionBroadcaster live position feed.")


class MobilityConfig(BaseModel):
    """Live position update settings for PositionBroadcaster."""
    enabled: bool = Field(default=False, description="Enable the PositionBroadcaster, which pushes Gazebo model poses to NS-3 node positions in real time.")
    source: str = Field(default="socket", description="Position data source: 'socket' (CORNET middleware), 'ros2_topic' (ROS 2 /tf), or 'none' (static positions only).")
    update_hz: float = Field(default=10.0, description="Position update rate in Hz when update_mode='periodic'.")
    update_mode: Literal["periodic", "threshold", "step_aligned"] = Field(
        default="periodic",
        description="When to push position updates: 'periodic' (every 1/update_hz s), 'threshold' (when movement exceeds position_threshold_m), 'step_aligned' (on NS-3 simulation step boundaries).",
    )
    position_threshold_m: float = Field(default=0.5, description="Minimum Euclidean movement in metres that triggers a position update when update_mode='threshold'.")


class ScenarioConfig(BaseModel):
    """5G/6G NS-3 scenario profile selection."""
    profile: str = Field(description="NS-3 scenario profile to run. One of: 5g_nr_urllc, 5g_nr_embb, 5g_nr_mmtc, 6g_thz.")
    numerology: int | None = Field(default=None, description="5G NR numerology index (0–4). Controls subcarrier spacing: 0=15kHz, 1=30kHz, 2=60kHz, 3=120kHz, 4=240kHz. None = scenario default.")
    bandwidth_mhz: float | None = Field(default=None, description="Channel bandwidth in MHz (e.g. 20, 40, 100). None = scenario default.")
    scheduler: str | None = Field(default=None, description="NR MAC scheduler override: 'ofdma-rr', 'ofdma-pf', 'ofdma-edf', 'ofdma-aoi'. None = scenario default.")
    experimental: bool = Field(default=False, description="Automatically set to True for profiles that are not production-ready (e.g. 6g_thz). Do not set manually.")

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
    plugin: str = Field(description="Network backend plugin identifier: 'ns3', 'mininet', or 'ns3+mininet'.")
    type: Literal["ns3", "mininet", "ns3+mininet"] = Field(description="Network simulation type. Must match plugin.")
    nodes: list[NodeConfig] = Field(default=[], description="List of network nodes in the topology.")
    mininet: MininetConfig | None = Field(default=None, description="Mininet-WiFi configuration. Required when type includes 'mininet'.")
    middleware: MiddlewareConfig | None = Field(default=None, description="Co-simulation middleware settings (TUN bridge, packet dispatcher, AoI tracker).")
    mobility: MobilityConfig | None = Field(default=None, description="Live position update settings (PositionBroadcaster from Gazebo to NS-3).")
    scenario: ScenarioConfig | None = Field(default=None, description="5G/6G NS-3 scenario profile. Required when type includes 'ns3'.")
    # NS-3 specific keys forwarded as-is
    model_config = ConfigDict(extra="allow")


# ── Robot section ─────────────────────────────────────────────────────────────

class ModelConfig(BaseModel):
    type: Literal["urdf", "sdf"] = Field(description="Robot model format: 'urdf' (ROS 2) or 'sdf' (Gazebo/SDF).")
    path: str = Field(description="Path to the model file, relative to the task directory or absolute.")


class PoseConfig(BaseModel):
    x: float = Field(default=0.0, description="X position in metres (world frame).")
    y: float = Field(default=0.0, description="Y position in metres (world frame).")
    z: float = Field(default=0.0, description="Z position in metres (world frame, 0 = ground level).")
    roll: float = Field(default=0.0, description="Roll angle in radians.")
    pitch: float = Field(default=0.0, description="Pitch angle in radians.")
    yaw: float = Field(default=0.0, description="Yaw angle in radians (0 = facing +X axis).")


class RobotEntry(BaseModel):
    name: str = Field(description="Unique robot identifier within the simulation (used as ROS namespace and Gazebo model name).")
    model: ModelConfig = Field(description="Robot model file reference (URDF or SDF).")
    pose: PoseConfig = Field(default_factory=PoseConfig, description="Initial spawn pose in the Gazebo world.")
    ros_namespace: str | None = Field(default=None, description="ROS 2 namespace for this robot's topics and services. None = uses robot name.")


class RobotConfig(BaseModel):
    plugin: str = Field(description="Robot simulation backend plugin identifier (e.g. 'gazebo').")
    launch_file: str | None = Field(default=None, description="Path to a ROS 2 launch file to use instead of auto-generated launch. None = Gazebo plugin auto-generates.")
    world: str | None = Field(default=None, description="Path to the Gazebo world file (.sdf or .world). None = Gazebo plugin auto-generates an empty world.")
    robots: list[RobotEntry] = Field(default=[], description="List of robots to spawn in the simulation world.")


# ── Experiment section ────────────────────────────────────────────────────────

class SweepConfig(BaseModel):
    axes: dict[str, list[Any]] = Field(
        description="Parameter sweep axes as a mapping of dot-path config keys to lists of values (e.g. {'network.numerology': [1, 2, 3], 'network.bandwidth_mhz': [20, 40]}). The cartesian product of all axes is expanded into one variant per combination."
    )
    parallel: bool = Field(default=False, description="Run sweep variants in parallel subprocesses. False = sequential (safer for resource-limited machines).")
    repeats: int = Field(default=1, description="Number of independent repetitions per variant (for statistical averaging). Must be >= 1.")

    @field_validator("repeats")
    @classmethod
    def _positive_repeats(cls, v: int) -> int:
        if v < 1:
            raise ConfigValidationError("sweep.repeats must be >= 1")
        return v


class ExperimentConfig(BaseModel):
    name: str = Field(description="Human-readable experiment name, used as the leaderboard title.")
    duration: float = Field(description="Experiment wall-clock duration in seconds. The orchestrator terminates all plugins after this time.")
    output_dir: str = Field(default="results", description="Directory where results, logs, and leaderboard entries are written (relative to task directory or absolute).")
    primary_metric: str | None = Field(default=None, description="Key from EvalTool output to rank leaderboard entries by. None = leaderboard is unranked.")
    higher_is_better: bool = Field(default=False, description="Leaderboard sort direction for primary_metric. True = higher score ranks first; False = lower score ranks first.")
    sweep: SweepConfig | None = Field(default=None, description="Parameter sweep configuration. When set, the orchestrator expands variants and runs each independently.")


# ── Top-level ─────────────────────────────────────────────────────────────────

class UnifiedConfig(BaseModel):
    """Root config model for CORNET unified schema (``_schema: unified-v1``)."""

    _schema: str = "unified-v1"      # literal marker; not validated by pydantic
    network: NetworkConfig = Field(description="Network simulation backend configuration (NS-3, Mininet, or both).")
    robot: RobotConfig = Field(description="Robot simulation backend configuration (Gazebo + ROS 2).")
    experiment: ExperimentConfig = Field(description="Experiment runtime settings: duration, output, metrics, and optional parameter sweep.")

    @model_validator(mode="after")
    def _cross_validate(self) -> "UnifiedConfig":
        # Mininet wmediumd requires Docker support — warn but don't error
        return self
