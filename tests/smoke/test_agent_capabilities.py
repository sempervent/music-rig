"""Tests migrated to smoke/test_agent_capabilities.py."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import agent as agent_mod
from music_rig import patchbay_state, question_service
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    build_agent_packet,
    validate_proposal,
)
from music_rig.cli import app
from music_rig.models import QuestionStatus
from music_rig.reconciliation.checks import (
    FindingStatus,
    QuestionConvergenceCheck,
    run_checks,
)
from music_rig.reconciliation.context import ReconciliationContext, ReconciliationPaths
from music_rig.reconciliation.operation_registry import (
    allowlisted_kinds,
    get_spec,
    validate_operation_shape,
)
from music_rig.reconciliation.operation_renderer import render_cli
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, load_questions
from music_rig import store as store_mod

runner = CliRunner()

def test_production_q007_packet_readonly():
    """Read-only production packet — no mutation."""
    before = question_service.get_question("Q-007")
    packet = build_agent_packet("Q-007")
    assert "ART P48" in packet["final_human_answer"]
    assert "Behringer PX3000" in packet["final_human_answer"]
    assert packet["relevant_current_context"].get("unit_identity_note")
    after = question_service.get_question("Q-007")
    assert after.answer == before.answer
    assert after.reconciled_at == before.reconciled_at

def test_agent_capabilities_cli(tmp_path, monkeypatch):
    monkeypatch.setattr("music_rig.store.ROOT", tmp_path)
    monkeypatch.setattr("music_rig.local_config.ROOT", tmp_path)
    r = runner.invoke(app, ["agent", "capabilities", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["result"]["provider_configured"] is False

