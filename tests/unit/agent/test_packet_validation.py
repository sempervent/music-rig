"""Tests migrated to unit/agent/test_packet_validation.py."""

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

def test_agent_packet_q007_shaped(fx20):
    packet = build_agent_packet("Q-200", ctx=fx20["ctx"])
    assert packet["final_human_answer"].startswith("PB-A")
    assert "ART P48" in packet["final_human_answer"]
    assert "unit_identity_note" in packet["relevant_current_context"]
    assert "wishlist" not in json.dumps(packet).casefold()
    assert "midi" not in packet["relevant_current_context"]
    # Determinism
    p2 = build_agent_packet("Q-200", ctx=fx20["ctx"])
    assert packet["packet_hash"] == p2["packet_hash"]

def test_agent_packet_rejects_unit_id_invention(fx20):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-200",
        status=ProposalStatus.READY,
        rationale="guess unit ids",
        operations=[
            RigOperation(
                namespace="patchbay",
                action="set_model",
                args={"bay_id": "PB-A", "model": "art-p48-1", "question_id": "Q-200"},
            )
        ],
    )
    result = validate_proposal(proposal, ctx=fx20["ctx"])
    assert result["ok"] is False
    assert any("unit-id" in e for e in result["errors"])

def test_ambiguous_proposal_no_writes(fx20):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-202",
        status=ProposalStatus.NEEDS_HUMAN_CLARIFICATION,
        clarification_questions=[
            "Which Alesis return is Acoustic — 2 or 3?"
        ],
        operations=[],
    )
    result = apply_proposal(proposal, ctx=fx20["ctx"], dry_run=False, yes=True)
    assert result["ok"] is True
    assert result["applied"] == []
    q = load_questions(fx20["questions"]).question_map()["Q-202"]
    assert q.reconciled_at is None

