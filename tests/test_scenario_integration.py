"""Integration tests for 5G/6G NS-3 scenario templates.

These tests exercise scenario scripts against a real NS-3 installation and
are automatically skipped when NS-3 is not available on the host.

Run only integration tests:
    pytest -m integration tests/test_scenario_integration.py

The following environment variables are respected:
    NS3_DIR  — path to the NS-3 build directory (overrides default search)
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cornet.plugins.network.ns3_plugin import _find_ns3_dir, _SCENARIO_TEMPLATES
from cornet.scenarios import scenario_root

_SCENARIOS_ROOT = scenario_root()


# ---------------------------------------------------------------------------
# Session-scoped fixture: locate NS-3 or skip the entire module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ns3_bin(tmp_path_factory) -> Path:
    """Return path to the ``ns3`` binary, or skip the whole module."""
    ns3_dir = _find_ns3_dir()
    if ns3_dir is None:
        pytest.skip(
            "NS-3 installation not found. "
            "Set $NS3_DIR or install to ~/ns-3-dev/. "
            "See docs/INSTALL.md."
        )
    binary = ns3_dir / "ns3"
    if not binary.exists():
        # Fall back to PATH
        found = shutil.which("ns3")
        if found is None:
            pytest.skip("ns3 binary not found in NS3_DIR or PATH.")
        binary = Path(found)
    return binary


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _invoke(ns3_bin: Path, profile: str, extra_args: list[str]) -> subprocess.CompletedProcess:
    script = _SCENARIOS_ROOT / _SCENARIO_TEMPLATES[profile]
    return subprocess.run(
        [str(ns3_bin), "run", str(script), "--"] + extra_args,
        capture_output=True,
        text=True,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Scenario template path resolution
# ---------------------------------------------------------------------------

class TestScenarioTemplatePaths:
    """Verify every registered profile resolves to an existing file."""

    @pytest.mark.parametrize("profile,rel_path", list(_SCENARIO_TEMPLATES.items()))
    def test_template_exists(self, profile, rel_path):
        full = _SCENARIOS_ROOT / rel_path
        assert full.exists(), (
            f"Scenario template for '{profile}' not found at {full}. "
            "Re-run the implementation step to regenerate the file."
        )

    def test_all_profiles_registered(self):
        expected = {"5g_nr_urllc", "5g_nr_embb", "5g_nr_mmtc", "6g_thz"}
        assert set(_SCENARIO_TEMPLATES.keys()) == expected


# ---------------------------------------------------------------------------
# NS-3 binary smoke test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNs3Available:
    def test_ns3_version(self, ns3_bin):
        result = subprocess.run(
            [str(ns3_bin), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"ns3 --version failed (exit {result.returncode}): {result.stderr}"
        )

    def test_cttc_nr_module_present(self, ns3_bin):
        """CTTC NR module is required for all 5G profiles."""
        result = subprocess.run(
            [str(ns3_bin), "show", "modules"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "nr" in result.stdout.lower(), (
            "CTTC NR module not found in ns3 show modules. "
            "Install from https://gitlab.com/cttc-lena/nr and rebuild NS-3. "
            "See docs/INSTALL.md#cttc-nr."
        )

    def test_thz_module_present_or_skip(self, ns3_bin):
        """ns3-thz module is required for the 6G THz profile."""
        result = subprocess.run(
            [str(ns3_bin), "show", "modules"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if "thz" not in result.stdout.lower():
            pytest.skip(
                "ns3-thz module not installed — 6G THz profile will raise "
                "PluginConfigError at runtime. "
                "Install from https://github.com/thz-ns3/ns3-thz. "
                "See docs/INSTALL.md#ns3-thz."
            )


# ---------------------------------------------------------------------------
# Per-profile --help invocation via ns3 run
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNs3ScenarioHelp:
    """ns3 run <template> -- --help must exit 0 and list expected flags."""

    def test_urllc_help(self, ns3_bin):
        result = _invoke(ns3_bin, "5g_nr_urllc", ["--help"])
        assert result.returncode == 0, result.stderr
        assert "--bandwidth-mhz" in result.stdout
        assert "--numerology" in result.stdout
        assert "--scheduler" in result.stdout

    def test_embb_help(self, ns3_bin):
        result = _invoke(ns3_bin, "5g_nr_embb", ["--help"])
        assert result.returncode == 0, result.stderr
        assert "--bandwidth-mhz" in result.stdout
        assert "--numerology" in result.stdout

    def test_mmtc_help(self, ns3_bin):
        result = _invoke(ns3_bin, "5g_nr_mmtc", ["--help"])
        assert result.returncode == 0, result.stderr
        assert "--bandwidth-mhz" in result.stdout
        assert "--num-ue" in result.stdout
        assert "--tun0" in result.stdout
        assert "--tun31" in result.stdout

    def test_thz_help(self, ns3_bin):
        result = _invoke(ns3_bin, "6g_thz", ["--help"])
        assert result.returncode == 0, result.stderr
        assert "--center-frequency-ghz" in result.stdout
        assert "--bandwidth-mhz" in result.stdout


# ---------------------------------------------------------------------------
# Per-profile default invocation (no --help, no simulation args)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNs3ScenarioDefaultRun:
    """Run each script with no arguments via ns3 run; must exit cleanly."""

    def test_urllc_no_args(self, ns3_bin):
        result = _invoke(ns3_bin, "5g_nr_urllc", [])
        assert result.returncode == 0, (
            f"5g_nr_urllc exited {result.returncode}:\n{result.stderr}"
        )

    def test_embb_no_args(self, ns3_bin):
        result = _invoke(ns3_bin, "5g_nr_embb", [])
        assert result.returncode == 0, (
            f"5g_nr_embb exited {result.returncode}:\n{result.stderr}"
        )

    def test_mmtc_no_args(self, ns3_bin):
        result = _invoke(ns3_bin, "5g_nr_mmtc", [])
        assert result.returncode == 0, (
            f"5g_nr_mmtc exited {result.returncode}:\n{result.stderr}"
        )

    def test_thz_no_args(self, ns3_bin):
        """Requires ns3-thz module; automatically skipped if missing."""
        result = _invoke(ns3_bin, "6g_thz", [])
        assert result.returncode == 0, (
            f"6g_thz exited {result.returncode}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# TUN argument forwarding
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNs3TunArgForwarding:
    """Verify that --tunX args are accepted without error."""

    def test_urllc_tun_args_accepted(self, ns3_bin):
        result = _invoke(
            ns3_bin, "5g_nr_urllc",
            ["--tun0=cornet0,10.0.0.1", "--tun1=cornet1,10.0.0.2"],
        )
        assert result.returncode == 0, (
            f"URLLC rejected tun args (exit {result.returncode}):\n{result.stderr}"
        )

    def test_mmtc_multi_tun_accepted(self, ns3_bin):
        tun_args = [f"--tun{i}=cornet{i},10.0.{i}.1" for i in range(4)]
        result = _invoke(ns3_bin, "5g_nr_mmtc", tun_args)
        assert result.returncode == 0, (
            f"mMTC rejected multi-tun args (exit {result.returncode}):\n{result.stderr}"
        )
