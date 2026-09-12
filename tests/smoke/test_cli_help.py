"""Tests migrated to smoke/test_cli_help.py."""

from __future__ import annotations

from typer.testing import CliRunner

from music_rig.cli import app

runner = CliRunner()


def test_cli_reconcile_run_help():
    result = runner.invoke(app, ["reconcile", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
