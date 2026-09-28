"""Pack and scenario-spec models for the CORNET catalogue."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cornet.config.schema import RadioSitesConfig


class LicenseInfo(BaseModel):
    spdx: str
    vendored: bool = True
    provenance: str = ""
    authors: list[str] = Field(default_factory=list)
    source_url: str = ""
    model_config = ConfigDict(extra="forbid")


class NetworkFlow(BaseModel):
    name: str
    direction: Literal["robot_to_controller", "controller_to_robot"]
    topic: str = ""
    rate_hz: float = 10.0
    size_bytes: int = 64
    processing_delay_ms: float = 0.0
    port: int | None = None
    model_config = ConfigDict(extra="forbid")


class Pack(BaseModel):
    """One catalogue directory: ``cornet/catalog/<kind>/<name>/pack.yaml``."""

    name: str
    kind: Literal["robots", "worlds", "networks"]
    version: str
    description: str = ""
    provides: dict[str, Any] = Field(default_factory=dict)
    requires: dict[str, Any] = Field(default_factory=dict)
    compatible: dict[str, Any] = Field(default_factory=dict)
    license: LicenseInfo
    bounds: dict[str, float] | None = None
    origin: dict[str, float] | None = None
    mounting_points: list[dict[str, Any]] = Field(default_factory=list)
    spawn_slots: list[dict[str, Any]] = Field(default_factory=list)
    zones: list[dict[str, Any]] = Field(default_factory=list)
    supported_deployments: list[str] = Field(default_factory=list)
    supported_anchors: list[str] = Field(default_factory=list)
    indoor_of: list[str] = Field(default_factory=list)
    model_paths: list[str] = Field(default_factory=list)
    roof: bool | None = None
    roof_variants: list[str] = Field(default_factory=list)
    network_flows: list[NetworkFlow] = Field(default_factory=list)
    physics_step_s: float | None = None
    intake_questions: list[str] = Field(default_factory=list)
    count_min: int = 1
    count_max: int = 1
    model_path: str | None = None
    notes: str = ""
    model_config = ConfigDict(extra="allow")


class ScenarioSpec(BaseModel):
    """Input to ``compose``. Mobile scenarios stay in realtime mode."""

    id: str
    robot: str
    robot_count: int = 1
    world: str
    world_variant: str | None = None
    network: str
    radio_sites: RadioSitesConfig
    population: list[dict[str, Any]] = Field(default_factory=list)
    controller_placement: Literal["edge_server", "ue"] = "edge_server"
    ue_altitude_m: float = 1.5
    seed: int = 1
    duration_s: float = 5.0
    lane: str | None = None
    model_config = ConfigDict(extra="forbid")
