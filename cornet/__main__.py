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

    # ui subcommand
    ui_parser = subparsers.add_parser(
        "ui", help="Open the interactive web UI for a task"
    )
    ui_parser.add_argument("task", help="Path to task directory")
    ui_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: random free port)",
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

    elif args.command == "ui":
        _run_ui(args.task, port=args.port)

    elif args._task_positional:
        # bare positional: treat as run
        from cornet.orchestrator import Orchestrator
        orch = Orchestrator()
        orch.run(task_dir=args._task_positional)

    else:
        parser.print_help()
        sys.exit(1)


def _run_ui(task: str, port: int | None) -> None:
    """Start the CORNET web UI server for *task* and open a browser tab."""
    import asyncio
    import webbrowser
    from pathlib import Path

    task_dir = Path(task)
    if not task_dir.is_dir():
        print(f"error: '{task}' is not a directory", file=sys.stderr)
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        print(
            "error: the 'ui' subcommand requires the [ui] extras.\n"
            "Install with:  pip install cornet-framework[ui]",
            file=sys.stderr,
        )
        sys.exit(1)

    from cornet.ui.server import create_app, find_free_port

    app = create_app(task_dir)

    if port is not None:
        # User specified a port — bind directly; no TOCTOU concern.
        sock = None
        bind_port = port
    else:
        # Acquire a free port via pre-bound socket (D5: eliminates TOCTOU race).
        sock, bind_port = find_free_port()

    url = f"http://localhost:{bind_port}"
    print(url, file=sys.stderr)
    webbrowser.open(url)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=bind_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    if sock is not None:
        asyncio.run(server.serve(sockets=[sock]))
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
