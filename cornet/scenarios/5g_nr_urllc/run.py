"""5G NR URLLC scenario template.

Template metadata consumed by CORNET. The actual NS-3 integration layer may
wrap this file in a larger launcher, but the CLI surface is stable here.
"""

from __future__ import annotations

import argparse


DEFAULTS = {
    "profile": "5g_nr_urllc",
    "numerology": 3,
    "bandwidth_mhz": 100.0,
    "scheduler": "NrMacSchedulerTdmaRR",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bandwidth-mhz", type=float, default=DEFAULTS["bandwidth_mhz"])
    parser.add_argument("--num-ue", type=int, default=1)
    parser.add_argument("--num-gnb", type=int, default=1)
    parser.add_argument("--numerology", type=int, default=DEFAULTS["numerology"])
    parser.add_argument("--scheduler", default=DEFAULTS["scheduler"])
    parser.add_argument("--tun0")
    parser.add_argument("--tun1")
    return parser


if __name__ == "__main__":
    build_parser().parse_args()