"""5G NR mMTC scenario template."""

from __future__ import annotations

import argparse


DEFAULTS = {
    "profile": "5g_nr_mmtc",
    "numerology": 0,
    "bandwidth_mhz": 20.0,
    "scheduler": "NrMacSchedulerTdmaRR",
    "num_ue": 32,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bandwidth-mhz", type=float, default=DEFAULTS["bandwidth_mhz"])
    parser.add_argument("--num-ue", type=int, default=DEFAULTS["num_ue"])
    parser.add_argument("--num-gnb", type=int, default=1)
    parser.add_argument("--numerology", type=int, default=DEFAULTS["numerology"])
    parser.add_argument("--scheduler", default=DEFAULTS["scheduler"])
    for index in range(32):
        parser.add_argument(f"--tun{index}")
    return parser


if __name__ == "__main__":
    build_parser().parse_args()