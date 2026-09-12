"""Tests migrated to integration/reconciliation/test_sweep_and_queue.py."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from music_rig.cli import app

runner = CliRunner()


def test_sweep_dry_run_json_counts(fx15):
    runner = CliRunner()
    result = runner.invoke(app, ["reconcile", "sweep", "--dry-run", "--json"])
    assert result.exit_code == 0, result.stdout
    assert "\x1b[" not in result.stdout
    payload = json.loads(result.stdout)
    counts = payload["result"]["counts"]
    for key in (
        "ready_to_finalize",
        "needs_answer",
        "needs_target_metadata",
        "needs_agent_action",
        "blocked_by_dod",
        "already_reconciled",
    ):
        assert key in counts
    assert "suggested_next_commands" in payload["result"]
    assert counts["needs_answer"] >= 1
