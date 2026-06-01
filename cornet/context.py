"""ExperimentContext — shared state passed between plugins during a run."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NetworkContext:
    """State populated by the network plugin after start()."""

    # Maps node/UE name → assigned IP address (set by network plugin after start)
    node_ips: dict[str, str] = field(default_factory=dict)


@dataclass
class RobotContext:
    """State populated by the robot plugin after start()."""

    # Maps robot name → spawned namespace (set by robot plugin after start)
    robot_namespaces: dict[str, str] = field(default_factory=dict)


@dataclass
class ExperimentContext:
    """Top-level context object shared across all plugins in a single run."""

    network: NetworkContext = field(default_factory=NetworkContext)
    robot: RobotContext = field(default_factory=RobotContext)

    # Variant ID for sweep runs (e.g. "numerology=2_bandwidth=40"); "default" otherwise
    variant_id: str = "default"
