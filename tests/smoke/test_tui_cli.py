"""Tests migrated to smoke/test_tui_cli.py."""

from __future__ import annotations


def test_cli_tui_debug_flag():
    import re

    from typer.testing import CliRunner

    from music_rig.cli import app

    result = CliRunner().invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--debug" in plain
