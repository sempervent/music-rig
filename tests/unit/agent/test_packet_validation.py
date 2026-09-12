"""Tests migrated to unit/agent/test_packet_validation.py."""

from __future__ import annotations

import json

from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    build_agent_packet,
    validate_proposal,
)
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import load_questions


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
        clarification_questions=["Which Alesis return is Acoustic — 2 or 3?"],
        operations=[],
    )
    result = apply_proposal(proposal, ctx=fx20["ctx"], dry_run=False, yes=True)
    assert result["ok"] is True
    assert result["applied"] == []
    q = load_questions(fx20["questions"]).question_map()["Q-202"]
    assert q.reconciled_at is None


def test_validate_proposal_rejects_unregistered_and_empty_ready(fx20):
    bad = AgentReconciliationProposal(
        artifact_id="Q-200",
        status=ProposalStatus.READY,
        rationale="shell",
        operations=[RigOperation(namespace="shell", action="rm", args={"path": "/"})],
    )
    result = validate_proposal(bad, ctx=fx20["ctx"])
    assert result["ok"] is False

    empty = AgentReconciliationProposal(
        artifact_id="Q-200",
        status=ProposalStatus.READY,
        rationale="nothing",
        operations=[],
    )
    result2 = validate_proposal(empty, ctx=fx20["ctx"])
    # READY with zero ops should be rejected or flagged
    assert result2["ok"] is False or result2.get("warnings") or result2.get("errors")


def test_build_packet_unknown_question(fx20):
    import pytest

    with pytest.raises(Exception):
        build_agent_packet("Q-999", ctx=fx20["ctx"])
