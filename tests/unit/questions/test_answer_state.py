"""Tests migrated to unit/questions/test_answer_state.py."""

from __future__ import annotations

from fixtures.repo_fixtures import _clock
from music_rig import question_service
from music_rig.models import AnswerState, QuestionStatus, ReconciliationState
from music_rig.reconciliation import service as reconcile_service


def test_answer_state_derivation_rules(fx19):
    q = question_service.get_question("Q-191")
    assert question_service.derive_answer_state(q) == AnswerState.UNANSWERED
    assert question_service.lifecycle_label(q) == "OPEN/UNANSWERED"

    draft = question_service.draft_question("Q-191", "provisional", render=False, clock=_clock)
    assert draft["answer_state"] == "DRAFT"
    assert draft["question_status"] == "OPEN"
    assert draft["resolved_at"] is None
    assert draft["reconciled_at"] is None
    q = question_service.get_question("Q-191")
    assert question_service.derive_answer_state(q) == AnswerState.DRAFT
    assert question_service.lifecycle_label(q) == "OPEN/DRAFT"

    fin = question_service.answer_question("Q-191", "final text", render=False, clock=_clock)
    assert fin["answer_state"] == "FINAL"
    assert fin["question_status"] == "RESOLVED"
    assert fin["resolved_at"] is not None
    assert fin["reconciled_at"] is None
    q = question_service.get_question("Q-191")
    assert question_service.derive_answer_state(q) == AnswerState.FINAL
    assert question_service.lifecycle_label(q) == "RESOLVED/UNRECONCILED"
    assert q.verification_result is None


def test_verification_result_null_on_answer_alone(fx19):
    question_service.answer_question("Q-190", "A→Alesis2 B→Alesis1", render=False)
    q = question_service.get_question("Q-190")
    assert q.verification_result is None
    assert q.status == QuestionStatus.RESOLVED


def test_draft_not_unqualified_needs_answer(fx19):
    question_service.draft_question("Q-190", "draft destinations", render=False)
    st = reconcile_service.question_state(question_service.get_question("Q-190"))
    assert st == ReconciliationState.DRAFT_ANSWER
    plan = reconcile_service.plan_question("Q-190")
    assert plan.state == ReconciliationState.DRAFT_ANSWER
    assert any("resolve" in c for c in plan.suggested_commands)
    sweep = reconcile_service.sweep(dry_run=True, yes=True)
    assert sweep["counts"]["draft_answer"] >= 1
    assert "Q-190" not in (sweep.get("would_finalize") or [])
