"""One compatibility check for a robot, world, network, and deployment."""

from __future__ import annotations

from typing import Any

from cornet.capabilities import capability_level
from cornet.catalog.layout import preset, select_channel
from cornet.catalog.loader import load_pack
from cornet.catalog.schema import Pack
from cornet.config.schema import RadioSitesConfig


def _allows(pack: Pack, key: str, name: str) -> bool:
    allowed = pack.compatible.get(key)
    if not allowed:
        return True
    return name in allowed


def check_compat(
    robot: str,
    world: str,
    network: str,
    radio_sites: RadioSitesConfig | dict[str, Any] | None = None,
    population: list[dict[str, Any]] | None = None,
    lane: str = "v2.4-ns3.38",
    *,
    robot_count: int = 1,
    world_variant: str | None = None,
    ue_altitude_m: float = 1.5,
) -> list[str]:
    """Return a list of reasons. An empty list means the combination is allowed."""
    reasons: list[str] = []
    robot_pack = load_pack("robots", robot)
    world_pack = load_pack("worlds", world)
    network_pack = load_pack("networks", network)
    radio = radio_sites if isinstance(radio_sites, RadioSitesConfig) else RadioSitesConfig.model_validate(radio_sites or {"deployment": "single_cell"})

    if not robot_pack.count_min <= robot_count <= robot_pack.count_max:
        reasons.append(
            f"{robot} count {robot_count} is outside {robot_pack.count_min}..{robot_pack.count_max}"
        )
    if not _allows(robot_pack, "worlds", world) or not _allows(world_pack, "robots", robot):
        reasons.append(f"{robot} is not compatible with world {world}")
    if not _allows(robot_pack, "networks", network) or not _allows(network_pack, "robots", robot):
        reasons.append(f"{robot} is not compatible with network {network}")
    if not _allows(world_pack, "networks", network):
        reasons.append(f"world {world} is not compatible with network {network}")

    deployment = radio.deployment
    if radio.indoor_building:
        if deployment not in world_pack.indoor_of:
            reasons.append(f"{world} cannot be an indoor building of {deployment}")
    elif deployment not in world_pack.supported_deployments:
        reasons.append(f"{world} does not support deployment {deployment}")

    if radio.robot_anchor not in world_pack.supported_anchors:
        reasons.append(f"{world} does not support anchor {radio.robot_anchor}")

    if robot == "px4_x500":
        variant = world_variant or (world_pack.roof_variants[0] if world_pack.roof_variants else None)
        roof = world_pack.roof
        if world_pack.roof_variants and variant == "no_roof":
            roof = False
        if roof:
            reasons.append(f"px4_x500 rejects a roofed world ({world}); use the no-roof variant")

    derived = preset(radio)
    channel, caveat, _altitude = select_channel(radio, ue_altitude_m)
    needed: list[str] = []
    if str(derived.get("channel", "")).startswith("InF"):
        needed.append("channel_inf")
    if radio.wraparound:
        needed.append("hex_wraparound")
    if radio.robot_anchor == "crossing" and network in {"nr", "lte"}:
        needed.append("nr_handover")
    if caveat:
        needed.append("channel_aerial_36777")
    if population and any(item.get("archetype") == "walker_with_phone" for item in population):
        if capability_level("cornet_tap_bridge_contract", lane) is None and lane == "unknown":
            reasons.append("walker_with_phone needs a detected NS-3 lane for the position feed")

    for name in needed:
        if capability_level(name, lane) is None:
            reasons.append(f"{name} is not available on {lane}")

    if radio.wraparound and derived["kind"] != "hex":
        reasons.append("wraparound applies only to hexagonal UMi, UMa, and RMa deployments")

    return reasons
