"""Tests migrated to smoke/test_production_readonly.py."""

from __future__ import annotations

from music_rig import question_service
from music_rig.agent import (
    build_agent_packet,
)
from music_rig.models import AnswerState, QuestionStatus, TodoStatus
from music_rig.store import load_questions, load_todo


def test_production_q001_baseline_preserved():
    """Do not undo Stage 18 Q-001 reconciliation during Stage 19."""
    doc = load_questions()
    q1 = doc.question_map()["Q-001"]
    assert q1.status == QuestionStatus.RESOLVED
    assert q1.answer.strip()
    assert q1.resolved_at is not None
    assert q1.reconciled_at is not None
    assert "Alesis 2" in q1.answer and "Alesis 1" in q1.answer
    assert question_service.derive_answer_state(q1) == AnswerState.FINAL
    assert question_service.lifecycle_label(q1) == "RESOLVED/RECONCILED"

    for qid in ("Q-002", "Q-003", "Q-004", "Q-006"):
        q = doc.question_map()[qid]
        assert q.status == QuestionStatus.RESOLVED
        assert q.reconciled_at is not None

    todo = load_todo()
    r3 = todo.task_map()["RIG-003"]
    assert r3.status == TodoStatus.DONE
    assert "RIG-003" not in todo.next_session


def test_production_readonly_packet_q007():
    """Read-only production packet — no mutation."""
    before = question_service.get_question("Q-007")
    packet = build_agent_packet("Q-007")
    assert "ART P48" in packet["final_human_answer"]
    assert "Behringer PX3000" in packet["final_human_answer"]
    assert packet["relevant_current_context"].get("unit_identity_note")
    after = question_service.get_question("Q-007")
    assert after.answer == before.answer
    assert after.reconciled_at == before.reconciled_at
