"""CLI surface smoke tests for 5G/6G NS-3 scenario templates.

Exercises the Python argument-parsing layer only — no real NS-3 installation
required.  Each scenario exposes a ``build_parser()`` function and a
``__main__`` entry point; both are validated here.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCENARIOS_ROOT = Path(__file__).parent.parent / "cornet" / "scenarios"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scenario(profile: str) -> ModuleType:
    """Dynamically load a scenario run.py without importing the package."""
    spec_path = _SCENARIOS_ROOT / profile / "run.py"
    spec = importlib.util.spec_from_file_location(f"scenario_{profile}", spec_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Default value tests
# ---------------------------------------------------------------------------

class TestScenarioDefaults:
    def test_urllc_defaults(self):
        mod = _load_scenario("5g_nr_urllc")
        args = mod.build_parser().parse_args([])
        assert args.numerology == 3
        assert args.bandwidth_mhz == 100.0
        assert args.scheduler == "NrMacSchedulerTdmaRR"
        assert args.num_ue == 1
        assert args.num_gnb == 1
        assert args.tun0 is None
        assert args.tun1 is None

    def test_embb_defaults(self):
        mod = _load_scenario("5g_nr_embb")
        args = mod.build_parser().parse_args([])
        assert args.numerology == 1
        assert args.bandwidth_mhz == 100.0
        assert args.scheduler == "NrMacSchedulerTdmaRR"

    def test_mmtc_defaults(self):
        mod = _load_scenario("5g_nr_mmtc")
        args = mod.build_parser().parse_args([])
        assert args.numerology == 0
        assert args.bandwidth_mhz == 20.0
        assert args.num_ue == 32
        # mMTC exposes tun0 … tun31
        for i in range(32):
            assert hasattr(args, f"tun{i}"), f"tun{i} missing from mMTC parser"

    def test_6g_thz_defaults(self):
        mod = _load_scenario("6g_thz")
        args = mod.build_parser().parse_args([])
        assert args.center_frequency_ghz == 300.0
        assert args.bandwidth_mhz == 2000.0
        assert mod.DEFAULTS["experimental"] is True

    def test_urllc_defaults_dict(self):
        mod = _load_scenario("5g_nr_urllc")
        assert mod.DEFAULTS["profile"] == "5g_nr_urllc"
        assert mod.DEFAULTS["numerology"] == 3

    def test_embb_defaults_dict(self):
        mod = _load_scenario("5g_nr_embb")
        assert mod.DEFAULTS["profile"] == "5g_nr_embb"
        assert mod.DEFAULTS["numerology"] == 1

    def test_mmtc_defaults_dict(self):
        mod = _load_scenario("5g_nr_mmtc")
        assert mod.DEFAULTS["profile"] == "5g_nr_mmtc"
        assert mod.DEFAULTS["numerology"] == 0

    def test_thz_defaults_dict(self):
        mod = _load_scenario("6g_thz")
        assert mod.DEFAULTS["profile"] == "6g_thz"


# ---------------------------------------------------------------------------
# Override / pass-through tests
# ---------------------------------------------------------------------------

class TestScenarioOverrides:
    def test_tun_args_accepted(self):
        mod = _load_scenario("5g_nr_urllc")
        args = mod.build_parser().parse_args(
            ["--tun0=cornet0,10.0.0.1", "--tun1=cornet1,10.0.0.2"]
        )
        assert args.tun0 == "cornet0,10.0.0.1"
        assert args.tun1 == "cornet1,10.0.0.2"

    def test_bandwidth_override(self):
        mod = _load_scenario("5g_nr_urllc")
        args = mod.build_parser().parse_args(["--bandwidth-mhz=200.0"])
        assert args.bandwidth_mhz == 200.0

    def test_numerology_override(self):
        mod = _load_scenario("5g_nr_urllc")
        args = mod.build_parser().parse_args(["--numerology=2"])
        assert args.numerology == 2

    def test_thz_frequency_override(self):
        mod = _load_scenario("6g_thz")
        args = mod.build_parser().parse_args(["--center-frequency-ghz=350.0"])
        assert args.center_frequency_ghz == 350.0

    def test_mmtc_tun_mid_range(self):
        mod = _load_scenario("5g_nr_mmtc")
        args = mod.build_parser().parse_args(["--tun15=cornet15,10.0.0.16"])
        assert args.tun15 == "cornet15,10.0.0.16"

    def test_ue_count_override(self):
        mod = _load_scenario("5g_nr_mmtc")
        args = mod.build_parser().parse_args(["--num-ue=8"])
        assert args.num_ue == 8


# ---------------------------------------------------------------------------
# Subprocess entry-point tests (validates __main__ block)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile", [
    "5g_nr_urllc", "5g_nr_embb", "5g_nr_mmtc", "6g_thz",
])
class TestScenarioEntryPoint:
    def test_help_exits_zero(self, profile):
        script = _SCENARIOS_ROOT / profile / "run.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--bandwidth-mhz" in result.stdout

    def test_no_args_exits_zero(self, profile):
        """Scenario scripts must accept zero arguments (all have defaults)."""
        script = _SCENARIOS_ROOT / profile / "run.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_unknown_flag_exits_nonzero(self, profile):
        script = _SCENARIOS_ROOT / profile / "run.py"
        result = subprocess.run(
            [sys.executable, str(script), "--not-a-real-flag"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
