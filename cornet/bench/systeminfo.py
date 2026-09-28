"""Machine and software facts recorded on every benchmark row."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def has_cap_net_admin() -> bool:
    if os.geteuid() == 0:
        return True
    try:
        status = Path("/proc/self/status").read_text()
    except OSError:
        return False
    for line in status.splitlines():
        if line.startswith("CapEff:"):
            cap_eff = int(line.split(":", 1)[1].strip(), 16)
            return bool(cap_eff & (1 << 12))
    return False


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _ram_gb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                kb = float(line.split()[1])
                return round(kb / 1024 / 1024, 2)
    except OSError:
        pass
    return 0.0


def _gpu() -> str:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                text=True,
                timeout=5,
            )
            name = out.strip().splitlines()
            if name:
                return name[0]
        except (subprocess.SubprocessError, OSError):
            pass
    try:
        out = subprocess.check_output(["lspci"], text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return "unknown"
    for line in out.splitlines():
        lower = line.lower()
        if "vga" in lower or "3d controller" in lower:
            return line.split(":", 2)[-1].strip()
    return "unknown"


def _first_line(cmd: list[str]) -> str:
    if not shutil.which(cmd[0]):
        return "unavailable"
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return "unavailable"
    line = out.strip().splitlines()
    return line[0] if line else "unavailable"


def machine_info() -> dict[str, str | int | float]:
    return {
        "cpu_model": _cpu_model(),
        "cores": os.cpu_count() or 0,
        "ram_gb": _ram_gb(),
        "kernel": platform.release(),
        "gpu": _gpu(),
    }


def software_info(ns3_dir: Path | None) -> dict[str, str]:
    lane = "unknown"
    if ns3_dir is not None:
        for sentinel in ns3_dir.glob(".cornet-patched-*"):
            lane = sentinel.name.removeprefix(".cornet-patched-")
            break
        if lane == "unknown" and "v24" in str(ns3_dir):
            lane = "v2.4-ns3.38"
        elif lane == "unknown":
            lane = ns3_dir.name
    return {
        "ns3_lane": lane,
        "gazebo_version": _first_line(["gzserver", "--version"]),
        "ros_version": _first_line(["ros2", "--version"]) if shutil.which("ros2") else "unavailable",
    }


def find_ns3_dir() -> Path | None:
    env = os.environ.get("NS3_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    home = Path.home()
    candidates.extend(
        [
            home / "ns-3-dev",
            home / "ns-3-dev-v24",
            home / "ns-3-dev-v47",
            home / "ns-3-dev-v51",
        ]
    )
    for path in candidates:
        if (path / "ns3").is_file():
            return path
    return None
