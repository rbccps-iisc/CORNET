from __future__ import annotations

from pathlib import Path

from cornet.config.loader import load_unified


TASK_ROOT = Path(__file__).parent.parent / "tasks"


def test_pendulum_task_config_loads() -> None:
    cfg = load_unified(TASK_ROOT / "pendulum_nr_control" / "config.yaml")
    assert cfg.network.plugin == "ns3"
    assert cfg.robot.plugin == "gazebo"
    assert cfg.experiment.primary_metric == "mean_aoi_ms"


def test_uav_task_config_loads() -> None:
    cfg = load_unified(TASK_ROOT / "uav_wifi_control" / "config.yaml")
    assert cfg.network.plugin == "mininet"
    assert cfg.network.mininet is not None
    assert cfg.network.mininet.wmediumd is True
    assert cfg.experiment.primary_metric == "position_rms"
