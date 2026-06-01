"""5G NR eMBB scenario template."""

from __future__ import annotations

import argparse


DEFAULTS = {
    "profile": "5g_nr_embb",
    "numerology": 1,
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