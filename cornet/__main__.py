"""Entry point: python -m cornet tasks/<name>  or  python -m cornet view tasks/<name>"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cornet",
        description="CORNET co-simulation framework",
    )
    subparsers = parser.add_subparsers(dest="command")

    # run subcommand (default when a path is given directly)
    run_parser = subparsers.add_parser("run", help="Run an experiment task")
    run_parser.add_argument("task", help="Path to task directory or config.yaml")

    # view subcommand
    view_parser = subparsers.add_parser("view", help="View experiment leaderboard")
    view_parser.add_argument("task", help="Path to task directory")
    view_parser.add_argument(
        "--higher-is-better",
        action="store_true",
        default=False,
        help="Sort leaderboard descending (higher metric = better)",
    )

    # Allow bare positional: `python -m cornet tasks/foo` treated as run
    parser.add_argument("_task_positional", nargs="?", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command == "view":
        from cornet.leaderboard.viewer import show
        show(args.task, higher_is_better=args.higher_is_better)

    elif args.command == "run":
        from cornet.orchestrator import Orchestrator
        orch = Orchestrator()
        orch.run(task_dir=args.task)

    elif args._task_positional:
        # bare positional: treat as run
        from cornet.orchestrator import Orchestrator
        orch = Orchestrator()
        orch.run(task_dir=args._task_positional)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
