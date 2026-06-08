"""Tests for the unified `algo` CLI dispatcher."""

from __future__ import annotations

from algotrading import cli


def test_commands_listed() -> None:
    cmds = cli.commands()
    assert "backtest" in cmds and "dashboard" in cmds and "paper-trade" in cmds
    assert cmds == sorted(cmds)  # stable, sorted


def test_split_command() -> None:
    assert cli.split_command([]) == (None, [])
    assert cli.split_command(["-h"]) == (None, [])
    assert cli.split_command(["help"]) == (None, [])
    assert cli.split_command(["backtest", "--symbol", "INFY"]) == (
        "backtest",
        ["--symbol", "INFY"],
    )


def test_usage_mentions_commands() -> None:
    text = cli.usage()
    assert "algo <command>" in text
    assert "backtest" in text and "rotation" in text


def test_main_no_args_prints_usage(capsys) -> None:
    assert cli.main([]) == 0
    assert "commands:" in capsys.readouterr().out


def test_main_unknown_command_errors(capsys) -> None:
    assert cli.main(["frobnicate"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_every_command_maps_to_an_existing_script() -> None:
    scripts = cli._scripts_dir()
    for name in cli.commands():
        assert (scripts / cli._SCRIPTS[name]).exists(), name


def test_load_main_returns_callable() -> None:
    # backfill imports no heavy/optional deps -> safe to load here.
    fn = cli._load_main("backfill")
    assert callable(fn)
