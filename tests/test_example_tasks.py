from __future__ import annotations

from pathlib import Path

from cornet.config.loader import load_unified


TASK_ROOT = Path(__file__).parent.parent / "tasks"


def test_pendulum_task_config_loads() -> None:
    cfg = load_unified(TASK_ROOT / "pendulum_nr_control" / "config.yaml")
    assert cfg.network.plugin == "ns3"
    assert cfg.robot.plugin == "gazebo"
    assert cfg.experiment.primary_metric == "mean_aoi_ms"


def test_pendulum_launch_assets_exist_and_publish_clock() -> None:
    from cornet.gazebo.generic_launch import generate
    from cornet.orchestrator import Orchestrator

    task = TASK_ROOT / "pendulum_nr_control"
    cfg = load_unified(task / "config.yaml")
    Orchestrator()._resolve_robot_assets(cfg, task)

    world = Path(cfg.robot.world)
    model = Path(cfg.robot.robots[0].model.path)
    assert world.is_file()
    assert model.is_file()
    assert "libgazebo_ros_init.so" not in world.read_text()

    launch = generate(cfg.robot, task)
    try:
        source = launch.read_text()
        compile(source, str(launch), "exec")
        assert '-s", "libgazebo_ros_init.so"' in source
        assert str(world) in source
        assert str(model) in source
    finally:
        launch.unlink(missing_ok=True)


def test_uav_task_config_loads() -> None:
    cfg = load_unified(TASK_ROOT / "uav_wifi_control" / "config.yaml")
    assert cfg.network.plugin == "mininet"
    assert cfg.network.mininet is not None
    assert cfg.network.mininet.wmediumd is True
    assert cfg.experiment.primary_metric == "position_rms"
