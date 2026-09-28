"""3GPP deployment presets and site positions.

Hexagonal site distances and angles are the tables in
``hexagonal-grid-scenario-helper.cc`` (5G-LENA). Indoor lattices follow
TR 38.901 Table 7.2 with a margin of ISD/2, the same spacing used for the
InF calibration halls.
"""

from __future__ import annotations

import math
from typing import Any

from cornet.config.schema import RadioSitesConfig

_DIST_2 = math.sqrt(3)
_SITE_DISTANCES = (
    [0.0]
    + [1.0] * 6
    + [_DIST_2] * 6
    + [2.0] * 6
)
_SITE_ANGLES_DEG = (
    [0.0]
    + [30.0, 90.0, 150.0, 210.0, 270.0, 330.0]
    + [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    + [30.0, 90.0, 150.0, 210.0, 270.0, 330.0]
)
_SITES_FOR_RINGS = {0: 1, 1: 7, 2: 19}

# TR 38.901 Table 7.4.2 / Table 7.2 height validity for ground UEs.
_AERIAL_SWITCH_M = {"UMa": 22.5, "UMi": 22.5, "RMa": 10.0}
_AERIAL_MAX_M = 300.0


def preset(radio: RadioSitesConfig) -> dict[str, Any]:
    """Derived, read-only deployment parameters."""
    name = radio.deployment
    if name == "single_cell":
        return {"kind": "file", "isd_m": None, "bs_height_m": 25.0, "channel": "UMa", "sites": 1}
    if name == "3gpp_inh_office":
        return {
            "kind": "grid",
            "hall_m": (120.0, 50.0),
            "isd_m": 20.0,
            "bs_height_m": 3.0,
            "cols": 6,
            "rows": 2,
            "channel": "InH",
            "sites": 12,
            "table": "TR 38.901 Table 7.2-1 / 7.2-4 InH-Office",
        }
    if name == "3gpp_inf":
        hall = (300.0, 150.0) if radio.inf_hall == "big" else (120.0, 60.0)
        isd = 50.0 if radio.inf_hall == "big" else 20.0
        sub = radio.inf_scenario or "SL"
        height = 8.0 if sub in {"SH", "DH"} else 1.5
        return {
            "kind": "grid",
            "hall_m": hall,
            "isd_m": isd,
            "bs_height_m": height,
            "cols": 6,
            "rows": 3,
            "channel": f"InF-{sub}",
            "sites": 18,
            "table": "TR 38.901 Table 7.2-1 / 7.8-7 InF",
        }
    if name == "3gpp_umi":
        return {"kind": "hex", "isd_m": 200.0, "bs_height_m": 10.0, "channel": "UMi", "sites": _SITES_FOR_RINGS[radio.rings]}
    if name == "3gpp_uma":
        return {"kind": "hex", "isd_m": 500.0, "bs_height_m": 25.0, "channel": "UMa", "sites": _SITES_FOR_RINGS[radio.rings]}
    if name == "3gpp_rma":
        isd = float(radio.rma_isd_m or 1732)
        return {"kind": "hex", "isd_m": isd, "bs_height_m": 35.0, "channel": "RMa", "sites": _SITES_FOR_RINGS[radio.rings]}
    return {"kind": "file", "isd_m": None, "bs_height_m": 25.0, "channel": "custom", "sites": len(radio.custom_sites)}


def hex_sites(rings: int, isd_m: float, height_m: float) -> list[dict[str, float]]:
    count = _SITES_FOR_RINGS[rings]
    sites = []
    for index in range(count):
        dist = _SITE_DISTANCES[index]
        angle = math.radians(_SITE_ANGLES_DEG[index])
        sites.append(
            {
                "name": f"gnb{index}",
                "x": isd_m * dist * math.cos(angle),
                "y": isd_m * dist * math.sin(angle),
                "z": height_m,
            }
        )
    return sites


def grid_sites(hall: tuple[float, float], isd_m: float, cols: int, rows: int, height_m: float) -> list[dict[str, float]]:
    margin = isd_m / 2.0
    sites = []
    index = 0
    for row in range(rows):
        for col in range(cols):
            sites.append(
                {
                    "name": f"gnb{index}",
                    "x": margin + col * isd_m,
                    "y": margin + row * isd_m,
                    "z": height_m,
                }
            )
            index += 1
    width, depth = hall
    if sites and (sites[-1]["x"] + margin > width + 1e-6 or sites[-1]["y"] + margin > depth + 1e-6):
        raise ValueError(f"grid does not fit hall {hall} at ISD {isd_m}")
    return sites


def site_positions(radio: RadioSitesConfig) -> list[dict[str, float]]:
    derived = preset(radio)
    if radio.deployment == "custom":
        sites = []
        for index, item in enumerate(radio.custom_sites):
            data = item if isinstance(item, dict) else item.model_dump()
            sites.append(
                {
                    "name": data.get("name") or f"gnb{index}",
                    "x": float(data["x"]),
                    "y": float(data["y"]),
                    "z": float(data["z"] if data.get("z") is not None else derived["bs_height_m"]),
                }
            )
        return sites
    if radio.deployment == "single_cell":
        return [{"name": "gnb0", "x": 0.0, "y": 0.0, "z": derived["bs_height_m"]}]
    if derived["kind"] == "hex":
        return hex_sites(radio.rings, derived["isd_m"], derived["bs_height_m"])
    return grid_sites(derived["hall_m"], derived["isd_m"], derived["cols"], derived["rows"], derived["bs_height_m"])


def select_channel(radio: RadioSitesConfig, ue_altitude_m: float) -> tuple[str, str | None, float]:
    """Return channel name, aerial caveat or None, and the altitude used.

    UMa/UMi switch above 22.5 m and RMa above 10 m. Altitude above 300 m is
    clamped. Indoor InH/InF stay terrestrial.
    """
    derived = preset(radio)
    channel = derived["channel"]
    family = {"UMa": "UMa", "UMi": "UMi", "RMa": "RMa"}.get(channel)
    altitude = ue_altitude_m
    caveat = None
    if altitude > _AERIAL_MAX_M:
        altitude = _AERIAL_MAX_M
    if family and ue_altitude_m > _AERIAL_SWITCH_M[family]:
        channel = f"{family}-AV"
        caveat = "aerial path loss only"
    return channel, caveat, altitude


def _centre_site(radio: RadioSitesConfig, sites: list[dict[str, float]]) -> dict[str, float]:
    """Central gNB. Hex and single-cell layouts put that site first."""
    derived = preset(radio)
    if derived["kind"] in {"hex", "file"} and radio.deployment != "custom":
        return sites[0]
    hall = derived.get("hall_m")
    if hall:
        cx, cy = hall[0] / 2.0, hall[1] / 2.0
    else:
        cx = sum(site["x"] for site in sites) / len(sites)
        cy = sum(site["y"] for site in sites) / len(sites)
    return min(sites, key=lambda site: (site["x"] - cx) ** 2 + (site["y"] - cy) ** 2)


def anchor_offset(radio: RadioSitesConfig, sites: list[dict[str, float]]) -> tuple[float, float]:
    """World-origin offset so the chosen anchor sits on the world origin."""
    anchor = radio.robot_anchor
    if anchor == "centre_site" or not sites:
        site = _centre_site(radio, sites)
        return site["x"], site["y"]
    if anchor == "cell_edge_0_1" and len(sites) >= 2:
        return (sites[0]["x"] + sites[1]["x"]) / 2.0, (sites[0]["y"] + sites[1]["y"]) / 2.0
    if anchor == "sector_boundary":
        return sites[0]["x"] + 10.0, sites[0]["y"]
    if anchor == "crossing" and len(sites) >= 2:
        return (sites[0]["x"] + sites[1]["x"]) / 2.0, (sites[0]["y"] + sites[1]["y"]) / 2.0
    return sites[0]["x"], sites[0]["y"]
