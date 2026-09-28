"""Catalogue packs, deployment presets, and the scenario compiler."""

from __future__ import annotations

import json
import math
import socket
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from cornet.catalog.compose import compose
from cornet.catalog.layout import anchor_offset, hex_sites, preset, select_channel, site_positions
from cornet.catalog.lfs import preflight
from cornet.catalog.licence import licence_issue, licence_problems
from cornet.catalog.loader import list_packs, load_pack
from cornet.catalog.relays import UdpRelay
from cornet.catalog.schema import ScenarioSpec
from cornet.config.loader import load_unified
from cornet.config.schema import RadioSitesConfig
from cornet.orchestrator import catalog_leaderboard_fields
from cornet.plugins.network.ns3_plugin import Ns3Plugin, nodes_payload

_HELPER = Path.home() / "ns-3-dev-v51/contrib/nr/helper/hexagonal-grid-scenario-helper.cc"


def _radio(**kwargs) -> RadioSitesConfig:
    return RadioSitesConfig.model_validate(kwargs)


def test_list_packs_has_the_shipped_names():
    names = {(pack.kind, pack.name) for pack in list_packs()}
    assert ("robots", "pendulum") in names
    assert ("worlds", "open_plain") in names
    assert ("networks", "nr") in names
    assert ("networks", "wifi_ns3") in names


def test_isd_and_height_are_not_user_fields():
    with pytest.raises(ValidationError):
        RadioSitesConfig.model_validate({"deployment": "3gpp_uma", "isd_m": 100})
    derived = preset(_radio(deployment="3gpp_uma", rings=1))
    assert derived["isd_m"] == 500
    assert derived["bs_height_m"] == 25
    assert derived["sites"] == 7
    inf = preset(_radio(deployment="3gpp_inf", inf_scenario="SH", inf_hall="small"))
    assert inf["isd_m"] == 20
    assert inf["bs_height_m"] == 8
    assert inf["sites"] == 18
    assert "Table 7.2" in inf["table"]


def test_inh_and_inf_grids_match_the_table_lattice():
    inh = site_positions(_radio(deployment="3gpp_inh_office"))
    assert len(inh) == 12
    assert inh[0] == {"name": "gnb0", "x": 10.0, "y": 10.0, "z": 3.0}
    assert inh[-1]["x"] == 110.0
    assert inh[-1]["y"] == 30.0
    inf = site_positions(_radio(deployment="3gpp_inf", inf_scenario="SL", inf_hall="big"))
    assert len(inf) == 18
    assert inf[0]["z"] == 1.5
    assert inf[0]["x"] == 25.0
    assert inf[-1]["x"] == 25.0 + 5 * 50.0


def test_hex_sites_match_the_lena_helper_tables():
    sites = hex_sites(2, isd_m=500.0, height_m=25.0)
    assert len(sites) == 19
    assert sites[0]["x"] == 0.0 and sites[0]["y"] == 0.0
    # Ring 1, first site: distance 1, angle 30 degrees.
    assert sites[1]["x"] == pytest.approx(500.0 * math.cos(math.radians(30)))
    assert sites[7]["x"] == pytest.approx(500.0 * math.sqrt(3))
    if not _HELPER.is_file():
        pytest.skip("5G-LENA hexagonal helper source is not on this machine")
    text = _HELPER.read_text()
    assert "30" in text and "distTo2ndRing = std::sqrt(3)" in text
    # The compiler uses the same polar form as CreateScenario().
    assert "m_isd * dist * cos(angleRad)" in text


def test_anchors_and_aerial_selection():
    uma = _radio(deployment="3gpp_uma", rings=1, robot_anchor="cell_edge_0_1")
    sites = site_positions(uma)
    ox, oy = anchor_offset(uma, sites)
    assert ox == pytest.approx((sites[0]["x"] + sites[1]["x"]) / 2)
    assert oy == pytest.approx((sites[0]["y"] + sites[1]["y"]) / 2)
    centre = _radio(deployment="3gpp_uma", rings=2, robot_anchor="centre_site")
    cx, cy = anchor_offset(centre, site_positions(centre))
    assert cx == 0.0 and cy == 0.0
    channel, caveat, altitude = select_channel(_radio(deployment="3gpp_uma"), 30.0)
    assert channel == "UMa-AV"
    assert caveat == "aerial path loss only"
    assert altitude == 30.0
    _channel, caveat, altitude = select_channel(_radio(deployment="3gpp_rma", rma_isd_m=1732), 350.0)
    assert caveat == "aerial path loss only"
    assert altitude == 300.0
    indoor, caveat, _altitude = select_channel(_radio(deployment="3gpp_inh_office"), 40.0)
    assert indoor == "InH"
    assert caveat is None


def test_compat_reasons():
    from cornet.catalog.compat import check_compat

    small_inf = check_compat(
        "turtlebot3",
        "warehouse_small",
        "wifi_ns3",
        _radio(deployment="3gpp_inf", inf_scenario="SL"),
    )
    assert any("does not support deployment" in reason for reason in small_inf)
    roof = check_compat("px4_x500", "warehouse_small", "nr", _radio(deployment="single_cell"))
    assert any("roof" in reason for reason in roof)
    clear = check_compat(
        "px4_x500",
        "warehouse_small",
        "nr",
        _radio(deployment="single_cell"),
        world_variant="no_roof",
    )
    assert clear == []
    wrap = check_compat(
        "turtlebot3",
        "open_plain",
        "nr",
        _radio(deployment="single_cell", wraparound=True),
    )
    assert any("wraparound" in reason for reason in wrap)
    count = check_compat("turtlebot3", "open_plain", "wifi_ns3", robot_count=9)
    assert any("outside" in reason for reason in count)


def test_licence_allowlist_and_shipped_packs():
    assert licence_problems() == []
    assert licence_issue("GPL-3.0", vendored=False, has_assets=False, has_license_file=False)
    assert licence_issue("proprietary", vendored=True, has_assets=False, has_license_file=False)
    assert licence_issue("MIT", vendored=False, has_assets=True, has_license_file=True)
    assert licence_issue("MIT-0", vendored=True, has_assets=False, has_license_file=False) is None


def test_hand_written_gnb_is_rejected_without_catalog(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  nodes:
    - {name: gnb, type: GNB}
  radio_sites:
    deployment: single_cell
robot:
  plugin: gazebo
experiment:
  name: handwritten
  duration: 1
"""
    )
    with pytest.raises(Exception, match="hand-written"):
        load_unified(cfg)


def test_compose_pendulum_is_deterministic(tmp_path: Path):
    spec = ScenarioSpec(
        id="pendulum_open_nr",
        robot="pendulum",
        world="open_plain",
        network="nr",
        radio_sites=_radio(deployment="single_cell"),
        seed=3,
        duration_s=5,
    )
    first = compose(spec, tmp_path / "a")
    second = compose(spec, tmp_path / "b")
    names = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
    assert names == sorted(path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file())
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    layout = json.loads((first / "layout.json").read_text())
    assert layout["standard"] is True
    assert layout["seed"] == 3
    assert [flow["port"] for flow in layout["flows"]] == [5001, 5002]
    assert (first / "models" / "pendulum.urdf").is_file()
    launch = (first / "launch.py").read_text()
    assert "headless" in launch and "use_sim_time" in launch
    config = load_unified(first / "config.yaml")
    assert config.network.mobility.enabled is False
    assert config.catalog.standard is True
    assert "lockstep" not in (first / "config.yaml").read_text()
    preflight()


def test_mobile_compose_enables_model_states_and_marks_custom(tmp_path: Path):
    spec = ScenarioSpec(
        id="bots",
        robot="turtlebot3",
        robot_count=2,
        world="open_plain",
        network="wifi_ns3",
        radio_sites=_radio(
            deployment="custom",
            custom_sites=[{"x": 1.0, "y": 2.0, "z": 3.0}],
            non_self_blockers="from_density",
        ),
        population=[{"archetype": "walker", "count": 1, "zone": "open_floor"}],
        seed=1,
    )
    task = compose(spec, tmp_path / "task")
    config = load_unified(task / "config.yaml")
    assert config.network.mobility.enabled is True
    assert config.network.mobility.source == "model_states"
    assert config.network.channel_update_ms == 100
    assert config.catalog.standard is False
    assert config.catalog.controller_placement == "edge_server"
    assert config.robot.robots[0].ros_namespace == "/turtlebot30"
    assert config.robot.robots[1].ros_namespace == "/turtlebot31"
    ports = [flow["port"] for flow in json.loads((task / "layout.json").read_text())["flows"]]
    assert ports[0] == 20000
    assert len(ports) == 6
    world = (task / "world.sdf").read_text()
    assert 'name="gnb0"' in world
    assert 'name="walker0"' in world
    assert "<max_step_size>0.004</max_step_size>" in world
    assert config.network.middleware.ip_list == ["10.0.0.2", "10.0.0.3", "10.0.1.1"]
    entry = {"metric": None}
    entry.update(catalog_leaderboard_fields(config))
    assert entry["standard"] is False


def test_position_payload_and_mobility_socket():
    payload = nodes_payload({}, {"bot": {"x": 1.0, "y": 2.0, "z": 3.0}}, 0.1)
    assert payload == {"nodes": {"bot": [1.0, 2.0, 3.0, 0.0, 0.0, 0.0]}}
    moved = nodes_payload({"bot": {"x": 1.0, "y": 2.0, "z": 3.0}}, {"bot": {"x": 2.0, "y": 2.0, "z": 3.0}}, 0.5)
    assert moved["nodes"]["bot"][3] == pytest.approx(2.0)

    class _Mob:
        enabled = True

    class _Net:
        mobility = _Mob()
        middleware = None

    plugin = Ns3Plugin()
    plugin._ensure_mobility_positions(_Net())
    assert plugin._positions_socket == "/tmp/cornet_positions.sock"
    assert plugin._pos_server is not None


def test_udp_relay_holds_on_the_wall_clock():
    relay = UdpRelay(("127.0.0.1", 0), ("127.0.0.1", 0), delay_s=0.05)
    try:
        port = relay.listen_address[1]
        relay._forward = ("127.0.0.1", port)
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        relay._forward = receiver.getsockname()
        relay.start()
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        started = time.monotonic()
        sender.sendto(b"ping", ("127.0.0.1", port))
        receiver.settimeout(1.0)
        data, _addr = receiver.recvfrom(32)
        elapsed = time.monotonic() - started
        assert data == b"ping"
        assert elapsed >= 0.04
    finally:
        relay.stop()


def test_wifi_presets_cite_the_tgax_document():
    pack = load_pack("networks", "wifi_ns3")
    names = {item["name"]: item for item in pack.provides["tgax"]}
    assert names["residential"]["apartment_m"] == [10, 10, 3]
    assert names["outdoor_large_bss"]["inter_ap_distance_m"] == [100, 200]
    assert names["enterprise"]["document"] == "IEEE 802.11-14/0980r16"


def test_large_warehouse_records_tables_and_upstream_notes():
    pack = load_pack("worlds", "warehouse_large")
    tables = " ".join(str(point.get("table", "")) for point in pack.mounting_points)
    assert "7.2-1" in tables and "7.2-4" in tables
    assert "accesspoint_namespace" in pack.notes
    assert "LICENSE" in pack.notes
