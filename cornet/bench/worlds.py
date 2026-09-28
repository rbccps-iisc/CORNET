"""Generate headless Gazebo benchmark worlds and resolve warehouse paths."""

from __future__ import annotations

import os
import re
from pathlib import Path

_EMPTY = """<?xml version="1.0" ?>
<sdf version="1.6">
  <world name="cornet_bench">
    <physics name="default_physics" type="ode">
      <max_step_size>{step}</max_step_size>
      <real_time_update_rate>{rate}</real_time_update_rate>
    </physics>
    <include>
      <uri>model://ground_plane</uri>
    </include>
    <include>
      <uri>model://sun</uri>
    </include>
    {inserts}
  </world>
</sdf>
"""


def _known_worlds() -> dict[str, list[Path]]:
    home = Path.home()
    return {
        "small": [
            home / "catkin_ws/src/aws-robomaker-small-warehouse-world/worlds/small_warehouse.world",
        ],
        "large": [
            home / "warehouse_ws/src/networked_warehouse_automation/warehouse_gazebo/worlds/large_warehouse.world",
        ],
    }


def _catalog_worlds() -> dict[str, list[Path]]:
    root = Path(__file__).resolve().parents[2] / "cornet" / "catalog" / "worlds"
    return {
        "small": list((root / "warehouse_small").glob("**/*.*")) if (root / "warehouse_small").is_dir() else [],
        "large": list((root / "warehouse_large").glob("**/*.*")) if (root / "warehouse_large").is_dir() else [],
    }


def _pick_world_file(path: Path, kind: str) -> Path | None:
    if path.is_file() and path.suffix in {".world", ".sdf"}:
        return path
    if not path.is_dir():
        return None
    names = {
        "small": ("small_warehouse.world", "small_warehouse.sdf"),
        "large": ("large_warehouse.world", "large_warehouse.sdf"),
    }[kind]
    for name in names:
        matches = list(path.rglob(name))
        if matches:
            return matches[0]
    worlds = list(path.rglob("*.world")) + list(path.rglob("*.sdf"))
    return worlds[0] if worlds else None


def resolve_world(kind: str) -> Path | None:
    """Resolve ``empty``, ``small`` or ``large``. Missing warehouses return None."""
    if kind == "empty":
        return None
    env_name = {"small": "CORNET_SMALL_WAREHOUSE", "large": "CORNET_LARGE_WAREHOUSE"}[kind]
    candidates: list[Path] = []
    env = os.environ.get(env_name)
    if env:
        candidates.append(Path(env))
    candidates.extend(_known_worlds()[kind])
    for path in _catalog_worlds()[kind]:
        if path.suffix in {".world", ".sdf"}:
            candidates.append(path)
    for candidate in candidates:
        found = _pick_world_file(candidate, kind)
        if found is not None and found.is_file():
            return found
    return None


def _robot_model(camera: bool) -> str:
    return "turtlebot3_waffle" if camera else "turtlebot3_burger"


def _robot_include(index: int, camera: bool) -> str:
    x = (index % 4) * 2.0
    y = (index // 4) * 2.0
    model = _robot_model(camera)
    return (
        f'<include><uri>model://{model}</uri><name>robot{index}</name>'
        f"<pose>{x} {y} 0 0 0 0</pose></include>"
    )


def _actor(index: int) -> str:
    x0 = -2.0 - index
    x1 = x0 + 4.0
    return f"""
    <actor name="walker{index}">
      <skin><filename>walk.dae</filename><scale>1.0</scale></skin>
      <script>
        <loop>true</loop>
        <auto_start>true</auto_start>
        <trajectory id="0" type="walking">
          <waypoint><time>0</time><pose>{x0} -2 1 0 0 0</pose></waypoint>
          <waypoint><time>8</time><pose>{x1} -2 1 0 0 0</pose></waypoint>
        </trajectory>
      </script>
    </actor>
    """


def _patch_physics(text: str, step_s: float, update_rate: int) -> str:
    step = f"{step_s:.6g}"
    if "<max_step_size>" in text:
        text = re.sub(
            r"<max_step_size>.*?</max_step_size>",
            f"<max_step_size>{step}</max_step_size>",
            text,
            count=1,
        )
    if "<real_time_update_rate>" in text:
        text = re.sub(
            r"<real_time_update_rate>.*?</real_time_update_rate>",
            f"<real_time_update_rate>{update_rate}</real_time_update_rate>",
            text,
            count=1,
        )
    return text


def model_path_for(world_file: Path | None) -> str:
    parts: list[str] = []
    if world_file is not None:
        sibling = world_file.parent.parent / "models"
        if sibling.is_dir():
            parts.append(str(sibling))
    for candidate in (
        "/opt/ros/humble/share/turtlebot3_gazebo/models",
        "/usr/share/gazebo-11/models",
    ):
        if Path(candidate).is_dir():
            parts.append(candidate)
    existing = os.environ.get("GAZEBO_MODEL_PATH", "")
    if existing:
        parts.append(existing)
    return ":".join(parts)


def generate_world(
    dest: Path,
    *,
    world: str,
    robots: int,
    actors: int,
    camera: bool,
    step_ms: float,
    update_rate: int,
) -> Path | None:
    """Write a world copy. Returns None when a warehouse world is missing."""
    inserts = "\n".join(_robot_include(i, camera) for i in range(robots))
    inserts += "\n".join(_actor(i) for i in range(actors))
    step_s = float(step_ms) / 1000.0
    if world == "empty":
        text = _EMPTY.format(step=f"{step_s:.6g}", rate=int(update_rate), inserts=inserts)
    else:
        source = resolve_world(world)
        if source is None:
            return None
        text = source.read_text()
        text = _patch_physics(text, step_s, int(update_rate))
        text = text.replace("</world>", inserts + "\n  </world>", 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    return dest
