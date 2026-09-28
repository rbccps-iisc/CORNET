"""Compile a scenario spec into a task directory. Realtime mode only."""

from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path
from typing import Any

import yaml

from cornet.catalog.compat import check_compat
from cornet.catalog.layout import anchor_offset, preset, select_channel, site_positions
from cornet.catalog.lfs import preflight
from cornet.catalog.loader import load_pack, pack_dir
from cornet.catalog.schema import ScenarioSpec
from cornet.config.loader import load_unified

_PORT_START = 20000
_PORT_END = 29999
_ACTOR_PLUGIN = (
    Path(__file__).resolve().parents[2] / "scripts" / "gazebo" / "actor_collisions" / "build" / "libActorCollisionsPlugin.so"
)


def _flow_ports(robot, robot_count: int) -> list[int]:
    """One UDP port per declared flow. Explicit pack ports are kept; the rest come from 20000–29999."""
    flows = list(robot.network_flows)
    if flows and all(flow.port is not None for flow in flows):
        ports = []
        span = len(flows)
        for index in range(robot_count):
            for flow in flows:
                ports.append(int(flow.port) + index * span)
        return ports
    needed = robot_count * max(1, len(flows))
    if _PORT_START + needed > _PORT_END:
        raise ValueError("catalog port range 20000-29999 is exhausted")
    return list(range(_PORT_START, _PORT_START + needed))


def compose(spec: ScenarioSpec, task_dir: Path, *, lane: str | None = None) -> Path:
    preflight()
    chosen_lane = lane or spec.lane or "v2.4-ns3.38"
    reasons = check_compat(
        spec.robot,
        spec.world,
        spec.network,
        spec.radio_sites,
        spec.population,
        chosen_lane,
        robot_count=spec.robot_count,
        world_variant=spec.world_variant,
        ue_altitude_m=spec.ue_altitude_m,
    )
    if reasons:
        raise ValueError("incompatible scenario: " + "; ".join(reasons))
    _require_actor_plugin(spec)

    robot = load_pack("robots", spec.robot)
    world = load_pack("worlds", spec.world)
    network = load_pack("networks", spec.network)
    sites = site_positions(spec.radio_sites)
    derived = preset(spec.radio_sites)
    channel, caveat, altitude = select_channel(spec.radio_sites, spec.ue_altitude_m)
    origin_x, origin_y = anchor_offset(spec.radio_sites, sites)
    moving = spec.robot in {"turtlebot3", "px4_x500"} or any(
        item.get("archetype") in {"walker", "walker_with_phone"} for item in spec.population
    )
    standard = spec.radio_sites.deployment != "custom" and spec.radio_sites.non_self_blockers != "from_density"

    task_dir.mkdir(parents=True, exist_ok=True)
    ports = _flow_ports(robot, spec.robot_count)
    _copy_model(task_dir, robot)
    nodes = _nodes(spec, sites, origin_x, origin_y)
    flows = []
    port_index = 0
    for robot_index in range(spec.robot_count):
        for flow in robot.network_flows:
            flows.append(
                {
                    "robot": f"{spec.robot}{robot_index}",
                    "name": flow.name,
                    "direction": flow.direction,
                    "port": ports[port_index],
                    "processing_delay_ms": flow.processing_delay_ms,
                }
            )
            port_index += 1

    actor_xml, devices = _population(spec, world)
    layout = {
        "deployment": spec.radio_sites.deployment,
        "standard": standard,
        "channel": channel,
        "caveat": caveat,
        "ue_altitude_m": altitude,
        "isd_m": derived.get("isd_m"),
        "bs_height_m": derived.get("bs_height_m"),
        "wraparound": spec.radio_sites.wraparound,
        "sectors": spec.radio_sites.sectors,
        "blockage": spec.radio_sites.blockage == "model_a",
        "indoor": spec.radio_sites.indoor_building,
        "channel_update_ms": 100 if moving else 0,
        "background_ues_per_cell": spec.radio_sites.background_ues_per_cell,
        "num_non_self_blocking": _non_self_blocking(spec, world),
        "wifi_channel": 36,
        "origin": {"x": origin_x, "y": origin_y},
        "sites": sites,
        "robots": [
            {
                "name": f"{spec.robot}{index}",
                "x": origin_x,
                "y": origin_y + index * 1.0,
                "z": altitude if spec.robot == "px4_x500" else 0.0,
            }
            for index in range(spec.robot_count)
        ],
        "flows": flows,
        "seed": spec.seed,
        "devices": devices,
    }
    (task_dir / "layout.json").write_text(json.dumps(layout, indent=2, sort_keys=True) + "\n")

    config = _config(
        spec,
        nodes,
        network,
        world,
        robot,
        moving,
        standard,
        channel,
        caveat,
        "layout.json",
    )
    (task_dir / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    _write_world(task_dir, world, sites, actor_xml, robot.physics_step_s or 0.001, spec.world_variant)
    _write_launch(task_dir, spec, robot)
    _write_eval(task_dir, robot)
    (task_dir / "relays.yaml").write_text(yaml.safe_dump({"flows": flows, "controller_placement": spec.controller_placement}, sort_keys=False))
    (task_dir / "README.md").write_text(
        f"# {spec.id}\n\nCompiled from catalogue packs {spec.robot}, {spec.world}, {spec.network}. "
        f"Realtime mode. standard={standard}. channel={channel}.\n"
    )
    load_unified(task_dir / "config.yaml")
    return task_dir


def _nodes(spec: ScenarioSpec, sites: list[dict[str, float]], origin_x: float, origin_y: float) -> list[dict[str, Any]]:
    """UE nodes only. Site positions live in layout.json, not as hand-written GNB nodes."""
    nodes = []
    for index in range(spec.robot_count):
        nodes.append(
            {
                "name": f"{spec.robot}{index}",
                "type": "UE",
                "ip": f"10.0.0.{index + 2}",
                "x": origin_x,
                "y": origin_y + index,
                "z": spec.ue_altitude_m if spec.robot == "px4_x500" else 0.0,
            }
        )
    if spec.controller_placement == "ue":
        nodes.append({"name": "controller", "type": "UE", "ip": "10.0.0.1", "x": sites[0]["x"], "y": sites[0]["y"], "z": 1.5})
    else:
        nodes.append({"name": "controller", "type": "STATIC", "ip": "10.0.1.1"})
    return nodes


def _config(
    spec: ScenarioSpec,
    nodes: list[dict[str, Any]],
    network,
    world,
    robot,
    moving: bool,
    standard: bool,
    channel: str,
    caveat: str | None,
    layout_file: str,
) -> dict[str, Any]:
    script = {"nr": "nr_multicell-default", "lte": "lte_multicell-default", "wifi_ns3": "wifi_basic-default"}[spec.network]
    radio = spec.radio_sites
    model_type, model_path, extra_model_paths = _robot_model(robot)
    return {
        "_schema": "unified-v1",
        "catalog": {
            "robot": spec.robot,
            "world": spec.world,
            "network": spec.network,
            "versions": {spec.robot: load_pack("robots", spec.robot).version, spec.world: world.version, spec.network: network.version},
            "standard": standard,
            "controller_placement": spec.controller_placement,
        },
        "network": {
            "plugin": "ns3",
            "type": "ns3",
            "simulation_script": script,
            "layoutFile": layout_file,
            "nodes": nodes,
            "middleware": {
                "enabled": False,
                "ip_list": [node["ip"] for node in nodes if node.get("ip")],
            },
            "mobility": {
                "enabled": moving,
                "source": "model_states" if moving else "socket",
                "update_hz": 10.0,
            },
            "blockage": radio.blockage,
            "non_self_blockers": radio.non_self_blockers,
            "channel_update_ms": 100 if moving else None,
            "population": spec.population,
            "radio_sites": radio.model_dump(mode="json"),
            "scenario": {"profile": "5g_nr_urllc"} if spec.network == "nr" else None,
            "requires_nr_capability": _required(channel, radio, caveat),
        },
        "robot": {
            "plugin": "gazebo",
            "world": "world.sdf",
            "model_paths": list(world.model_paths) + extra_model_paths,
            "robots": [
                {
                    "name": f"{spec.robot}{index}",
                    "model": {"type": model_type, "path": model_path},
                    "pose": {"x": 0.0, "y": float(index), "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
                    "ros_namespace": f"/{spec.robot}{index}",
                }
                for index in range(spec.robot_count)
            ],
        },
        "experiment": {
            "name": spec.id,
            "duration": spec.duration_s,
            "output_dir": "results",
            "seed": spec.seed,
        },
    }


def _required(channel: str, radio, caveat: str | None) -> list[str]:
    names = []
    if channel.startswith("InF"):
        names.append("channel_inf")
    if radio.wraparound:
        names.append("hex_wraparound")
    if caveat:
        names.append("channel_aerial_36777")
    return names


def _robot_model(robot) -> tuple[str, str, list[str]]:
    """Return Gazebo model type, path, and extra model search directories."""
    installed = Path("/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf")
    if not robot.model_path and robot.name == "turtlebot3" and installed.is_file():
        return "sdf", str(installed), [str(installed.parent.parent)]
    model_file = Path(robot.model_path).name if robot.model_path else "robot.urdf"
    kind = "sdf" if model_file.endswith(".sdf") else "urdf"
    return kind, f"models/{model_file}", []


def _copy_model(task_dir: Path, robot) -> None:
    if not robot.model_path:
        return
    src = Path(robot.model_path)
    if not src.is_absolute():
        src = Path(__file__).resolve().parents[2] / robot.model_path
    if not src.is_file():
        return
    dest = task_dir / "models" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def _require_actor_plugin(spec: ScenarioSpec) -> None:
    if not any(item.get("archetype") in {"walker", "walker_with_phone"} for item in spec.population):
        return
    path = Path(os.environ.get("CORNET_ACTOR_PLUGIN", str(_ACTOR_PLUGIN)))
    if not path.is_file():
        raise FileNotFoundError(
            f"actor-collisions plugin not found at {path}; build target: make actor-collisions"
        )


def _non_self_blocking(spec: ScenarioSpec, world) -> int | None:
    """Non-standard density map. Model A itself does not depend on population."""
    if spec.radio_sites.non_self_blockers != "from_density":
        return None
    bodies = sum(
        int(item.get("count") or 1)
        for item in spec.population
        if item.get("archetype") in {"walker", "walker_with_phone"}
    )
    bounds = world.bounds or {"x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0}
    area = max(
        (float(bounds["x_max"]) - float(bounds["x_min"])) * (float(bounds["y_max"]) - float(bounds["y_min"])),
        1.0,
    )
    scaled = int(round((bodies / area) / 0.01 * 4))
    return min(10, max(1, scaled))


def _zone_box(world, name: str | None) -> dict[str, float]:
    bounds = world.bounds or {"x_min": -5.0, "x_max": 5.0, "y_min": -5.0, "y_max": 5.0}
    zones = {zone.get("name"): zone for zone in world.zones}
    zone = zones.get(name) if name else None
    return zone or bounds


def _population(spec: ScenarioSpec, world) -> tuple[list[str], list[dict[str, Any]]]:
    """Seeded actors and the NS-3 devices bound to them. Same seed, same trajectories."""
    rng = random.Random(spec.seed)
    actors: list[str] = []
    devices: list[dict[str, Any]] = []
    index = 0
    for item in spec.population:
        archetype = item.get("archetype")
        zone = _zone_box(world, item.get("zone"))
        traffic = (item.get("traffic") or {}).get("profile") or ""
        channel = item.get("channel")
        speeds = (item.get("motion") or {}).get("speed_mps") or [1.0, 1.0]
        count = int(item.get("count") or 1)
        for _copy in range(count):
            speed = max(0.1, rng.uniform(float(speeds[0]), float(speeds[-1])))
            samples = [
                (
                    rng.uniform(float(zone["x_min"]), float(zone["x_max"])),
                    rng.uniform(float(zone["y_min"]), float(zone["y_max"])),
                )
                for _step in range(3)
            ]
            if archetype in {"walker", "walker_with_phone"}:
                elapsed = 0.0
                waypoints = []
                previous = samples[0]
                for step, (x, y) in enumerate(samples):
                    if step:
                        elapsed += math.hypot(x - previous[0], y - previous[1]) / speed
                    previous = (x, y)
                    waypoints.append(
                        f"<waypoint><time>{elapsed:.3f}</time><pose>{x:.3f} {y:.3f} 0 0 0 0</pose></waypoint>"
                    )
                actors.append(
                    f'<actor name="walker{index}">'
                    f'<plugin name="actor_collisions_walker{index}" filename="libActorCollisionsPlugin.so"/>'
                    f"<skin><filename>walk.dae</filename></skin>"
                    f'<animation name="walking"><filename>walk.dae</filename><interpolate_x>true</interpolate_x></animation>'
                    f"<script><loop>true</loop><trajectory id=\"0\" type=\"walking\">{''.join(waypoints)}</trajectory></script>"
                    f"</actor>"
                )
            x0, y0 = samples[0]
            if archetype == "walker_with_phone":
                devices.append(
                    {"name": f"walker{index}", "kind": archetype, "x": round(x0, 3), "y": round(y0, 3), "z": 1.5, "traffic": traffic, "channel": channel, "mobile": True}
                )
            elif archetype in {"static_user", "iot_sensor", "wifi_neighbour"}:
                devices.append(
                    {
                        "name": f"{'neighbour' if archetype == 'wifi_neighbour' else archetype}{index}",
                        "kind": archetype,
                        "x": round(x0, 3),
                        "y": round(y0, 3),
                        "z": 1.5,
                        "traffic": traffic or ("periodic_iot" if archetype == "iot_sensor" else ""),
                        "channel": 36 if channel is None and archetype == "wifi_neighbour" else channel,
                        "mobile": False,
                    }
                )
            index += 1
    return actors, devices


def _write_world(
    task_dir: Path,
    world,
    sites: list[dict[str, float]],
    actors: list[str],
    step_s: float,
    variant: str | None,
) -> None:
    root = pack_dir("worlds", world.name)
    source = root / ("no_roof.sdf" if variant == "no_roof" and (root / "no_roof.sdf").is_file() else "world.sdf")
    if source.is_file():
        text = source.read_text()
    else:
        text = """<?xml version="1.0"?>
<sdf version="1.6"><world name="catalog">
  <include><uri>model://ground_plane</uri></include>
  <include><uri>model://sun</uri></include>
</world></sdf>
"""
    bounds = world.bounds or {"x_min": -1e9, "x_max": 1e9, "y_min": -1e9, "y_max": 1e9}
    includes = []
    for site in sites:
        if bounds["x_min"] <= site["x"] <= bounds["x_max"] and bounds["y_min"] <= site["y"] <= bounds["y_max"]:
            includes.append(
                f'  <model name="{site["name"]}"><static>true</static><pose>{site["x"]} {site["y"]} {site["z"]} 0 0 0</pose>'
                f'<link name="link"><collision name="c"><geometry><box><size>0.3 0.3 0.8</size></box></geometry></collision>'
                f'<visual name="v"><geometry><box><size>0.3 0.3 0.8</size></box></geometry></visual></link></model>'
            )
    if "<physics" not in text:
        includes.append(
            f"  <physics type=\"ode\"><max_step_size>{step_s}</max_step_size><real_time_update_rate>0</real_time_update_rate></physics>"
        )
    includes.extend(actors)
    if "</world>" in text:
        text = text.replace("</world>", "\n".join(includes) + "\n</world>", 1)
    (task_dir / "world.sdf").write_text(text)


def _write_launch(task_dir: Path, spec: ScenarioSpec, robot) -> None:
    step = robot.physics_step_s or 0.001
    rate = max(1.0 / step, 10.0)
    (task_dir / "launch.py").write_text(
        "\n".join(
            [
                "def generate():",
                "    # Headless gzserver. publish_rate is at least 1/max_step_size.",
                f"    return {{'publish_rate': {rate}, 'max_step_size': {step}, 'headless': True, 'use_sim_time': True}}",
                "",
            ]
        )
    )


def _write_eval(task_dir: Path, robot) -> None:
    metric = robot.provides.get("metric", "mean_aoi_ms")
    path = task_dir / "eval"
    path.mkdir(exist_ok=True)
    (path / "eval_tool.py").write_text(
        "\n".join(
            [
                "from cornet.eval.base import EvalTool as BaseEvalTool",
                "",
                "class EvalTool(BaseEvalTool):",
                "    def run_evaluation(self, output_dir: str) -> str:",
                "        # The metric named by the robot pack is filled by a real run.",
                f"        return 'FAILURE,'  # {metric}",
                "",
            ]
        )
    )
