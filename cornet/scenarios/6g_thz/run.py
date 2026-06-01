"""Experimental 6G THz scenario template."""

from __future__ import annotations

import argparse


DEFAULTS = {
    "profile": "6g_thz",
    "center_frequency_ghz": 300.0,
    "bandwidth_mhz": 2000.0,
    "experimental": True,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--center-frequency-ghz", type=float, default=DEFAULTS["center_frequency_ghz"])
    parser.add_argument("--bandwidth-mhz", type=float, default=DEFAULTS["bandwidth_mhz"])
    parser.add_argument("--tun0")
    parser.add_argument("--tun1")
    return parser


if __name__ == "__main__":
    build_parser().parse_args()