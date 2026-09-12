"""Tests migrated to integration/reconciliation/test_sweep_and_queue.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import inspect_service, patchbay_state, question_service, store
from music_rig.cli import app
from music_rig.models import QuestionStatus, ReconciliationState, TodoStatus
from music_rig.presentation import format_domains_table, format_reconcile_queue_table
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.types import Capability, VerificationStatus
from music_rig.store import StoreError, load_changes, load_questions, load_todo

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

