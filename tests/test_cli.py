"""Tests for omnote.__main__ command-line handling."""
from __future__ import annotations

import os
import sys
import types

import pytest

ENV_VARS = ("OMNOTE_THEME_MODE", "MICROPAD_THEME_MODE", "OMNOTE_NO_WATCH", "MICROPAD_NO_WATCH")


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    """Run the CLI against a stub app; returns (main, list of argvs the app received)."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    received: list[list[str]] = []
    stub = types.ModuleType("omnote.app")
    stub.main = lambda argv: received.append(argv) or 0  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "omnote.app", stub)
    monkeypatch.setattr(sys, "argv", ["omnote"])

    from omnote.__main__ import main
    return main, received


def test_no_args(cli) -> None:
    main, received = cli
    assert main([]) == 0
    assert received == [["omnote"]]


def test_files_reach_gapplication(cli) -> None:
    """Issue #1: `omnote file.txt` was rejected by argparse."""
    main, received = cli
    main(["notes.txt", "todo.md"])
    assert received == [["omnote", "notes.txt", "todo.md"]]


def test_custom_flags_set_env_and_are_not_forwarded(cli) -> None:
    """Issue #2: GApplication rejected --system-theme / --no-watch with 'Unknown option'."""
    main, received = cli
    main(["--system-theme", "--no-watch", "notes.txt"])
    assert received == [["omnote", "notes.txt"]]
    assert os.environ["OMNOTE_THEME_MODE"] == "system"
    assert os.environ["OMNOTE_NO_WATCH"] == "1"


def test_dash_filename_is_not_mistaken_for_an_option(cli) -> None:
    main, received = cli
    main(["--", "-notes.txt"])
    assert received == [["omnote", "./-notes.txt"]]


def test_unknown_option_is_rejected(cli) -> None:
    main, received = cli
    with pytest.raises(SystemExit) as exc:
        main(["--bogus"])
    assert exc.value.code == 2
    assert received == []
