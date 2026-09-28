#!/usr/bin/env python3
"""Report requires_nr_capability levels for a task config."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cornet.capabilities import report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Task config.yaml to read",
    )
    args = parser.parse_args(argv)
    if not args.config.is_file():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 1
    return report(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
