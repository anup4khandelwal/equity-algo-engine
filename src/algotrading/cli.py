"""Unified command-line entry point.

``algo <command> [args...]`` dispatches to the existing scripts, each of which
exposes a ``main(argv)`` function. Run it via ``uv run python scripts/algo.py``
(or ``algo`` if the project is installed as a package).
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path

# command name -> script filename under scripts/
_SCRIPTS: dict[str, str] = {
    "backfill": "backfill.py",
    "backtest": "backtest.py",
    "rotation": "rotation_backtest.py",
    "optimize": "optimize.py",
    "paper-trade": "paper_trade.py",
    "dashboard": "dashboard.py",
    "refresh-token": "refresh_token.py",
}


def commands() -> list[str]:
    """All available subcommands, sorted."""
    return sorted(_SCRIPTS)


def usage() -> str:
    return "usage: algo <command> [args...]\n\ncommands:\n  " + "\n  ".join(commands())


def split_command(argv: list[str]) -> tuple[str | None, list[str]]:
    """Split argv into (command, remaining-args). ``None`` means show help."""
    if not argv or argv[0] in ("-h", "--help", "help"):
        return None, []
    return argv[0], list(argv[1:])


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "scripts"


def _load_main(command: str) -> Callable[[list[str]], int]:
    path = _scripts_dir() / _SCRIPTS[command]
    spec = importlib.util.spec_from_file_location(f"_algo_{command.replace('-', '_')}", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load script for command {command!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command, rest = split_command(argv)
    if command is None:
        print(usage())
        return 0
    if command not in _SCRIPTS:
        print(f"unknown command: {command}\n\n{usage()}", file=sys.stderr)
        return 2
    return _load_main(command)(rest)
