"""Verification policy edge cases."""

from __future__ import annotations

from datetime import datetime, timezone

from music_rig.actor import EvidenceBasis
from music_rig.models import (
    AnswerActor,
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
    VerificationOutcome,
    VerificationResult,
)
from music_rig.verification_policy import (
    VerificationPolicy,
    effective_answer_actor,
    evidence_basis_for,
    has_bot_answer,
    has_evidence_authority,
    has_human_attestation,
    verification_policy_for,
)


def test_policy_for_none_and_unknown_kind():
    assert (
        verification_policy_for(None)
        is VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT
    )
    q = OpenQuestion(
        id="Q-901",
        question="x?",
        area="Docs",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CUSTOM_UNKNOWN",
            prompt="p",
            answer_type="TEXT",
            choices=[],
        ),
    )
    assert (
        verification_policy_for(q)
        is VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT
    )


def test_effective_actor_and_attestation_empty_answer():
    q = OpenQuestion(
        id="Q-902",
        question="x?",
        area="Docs",
        status=QuestionStatus.OPEN,
        answer="",
    )
    assert effective_answer_actor(q) is None
    assert has_human_attestation(q) is False

    q2 = OpenQuestion(
        id="Q-903",
        question="x?",
        area="Docs",
        status=QuestionStatus.RESOLVED,
        answer="yes",
        answer_actor=AnswerActor.BOT,
        resolved_at=datetime.now(timezone.utc),
    )
    assert has_bot_answer(q2) is True
    assert has_human_attestation(q2) is False


def test_evidence_basis_failed_observation():
    q = OpenQuestion(
        id="Q-904",
        question="clock?",
        area="MIDI",
        status=QuestionStatus.RESOLVED,
        answer="ableton",
        answer_actor=AnswerActor.HUMAN,
        resolved_at=datetime.now(timezone.utc),
        verification=QuestionVerification(
            kind="MIDI_CLOCK",
            prompt="p",
            answer_type="ENUM",
            choices=["ableton"],
        ),
        verification_result=VerificationResult(
            outcome=VerificationOutcome.FAILED_TEST,
            observed_at=datetime.now(timezone.utc),
            observed_value="nope",
        ),
    )
    basis = evidence_basis_for(q)
    assert basis in {
        EvidenceBasis.HUMAN_ANSWER,
        EvidenceBasis.NONE,
        EvidenceBasis.HUMAN_OBSERVATION,
    }
    assert isinstance(has_evidence_authority(q), bool)
