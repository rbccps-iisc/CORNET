from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cornet.capabilities import (
    assess,
    capability_level,
    enforce_declared_capabilities,
    load_matrix,
    required_lane,
)


class _Net:
    def __init__(self, declared):
        self.plugin = "ns3"
        self.requires_nr_capability = declared


class _Cfg:
    def __init__(self, declared):
        self.network = _Net(declared)


def test_shipped_matrix_loads() -> None:
    names = {entry["name"] for entry in load_matrix()}
    assert "subband_csi" in names
    assert "nr_channel_helper" in names
    assert "hex_wraparound" in names


def test_stable_lane_refuses_latest_only_capability() -> None:
    matrix = load_matrix()
    errors, warnings = assess("subband_csi", "v2.4-ns3.38", matrix)
    assert not warnings
    assert errors
    assert "only available in v4.2-ns3.47" in errors[0]
    assert "upstream-available in v4.2 but not cornet-integrated" in errors[0]
    assert "make install-ns3-v47" in errors[0]


def test_integrated_capability_warns_and_continues() -> None:
    matrix = load_matrix()
    errors, warnings = assess("cornet_tap_bridge_contract", "v4.2-ns3.47", matrix)
    assert not errors
    assert warnings
    assert "integrated but not validated" in warnings[0]
    assert "cornet-integrated in v4.2" in warnings[0]


def test_unknown_capability_is_an_error() -> None:
    errors, _warnings = assess("not_a_feature", "v2.4-ns3.38", load_matrix())
    assert "unknown capability" in errors[0]


def test_absent_declaration_is_a_noop() -> None:
    enforce_declared_capabilities(_Cfg(None))


def test_profile_files_name_real_patches() -> None:
    root = Path(__file__).resolve().parents[1] / "scripts" / "patches" / "ns3"
    for lane in ("v2.4-ns3.38", "v4.2-ns3.47"):
        profiles = root / lane / "profiles"
        names = {path.name for path in profiles.glob("*.txt")}
        assert {"full.txt", "infrastructure.txt", "aoi-measurement.txt", "upstream-only.txt"} <= names
        for path in profiles.glob("*.txt"):
            for line in path.read_text().splitlines():
                name = line.split("#", 1)[0].strip()
                if name:
                    assert (root / lane / name).is_file()


def test_matrix_yaml_round_trip_has_ordered_levels() -> None:
    data = yaml.safe_load(
        (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "patches"
            / "ns3"
            / "CAPABILITY_MATRIX.yaml"
        ).read_text()
    )
    levels = {
        row["level"]
        for entry in data["capabilities"]
        for row in entry["supported_in"]
    }
    assert levels <= {"upstream-available", "cornet-integrated", "cornet-validated"}


def test_capability_level_and_required_lane() -> None:
    assert capability_level("custom_edf_scheduler", "v4.2-ns3.47") == "cornet-validated"
    assert capability_level("pdcp_aoi_timestamps", "v4.2-ns3.47") == "cornet-integrated"
    assert capability_level("custom_edf_scheduler", "v5.1-ns3.48") == "cornet-integrated"
    errors, _warnings = assess("nr_handover", "v2.4-ns3.38", load_matrix())
    assert "v5.1-ns3.48" in errors[0]
    deferred, _warnings = assess("blockage_model_b", "v5.1-ns3.48", load_matrix())
    assert "not supported on any lane" in deferred[0]
    assert "deferred" in deferred[0]
    assert required_lane("pdcp_aoi_timestamps") == "v2.4-ns3.38"


def test_missing_lane_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS3_DIR", str(tmp_path))
    with pytest.raises(SystemExit):
        enforce_declared_capabilities(_Cfg("subband_csi"))
