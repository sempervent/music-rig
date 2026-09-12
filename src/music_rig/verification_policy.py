"""Verification policy — when HUMAN_ANSWER attestation suffices vs explicit observation."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from music_rig.actor import EvidenceBasis
from music_rig.models import AnswerActor

if TYPE_CHECKING:
    from music_rig.models import OpenQuestion


class VerificationPolicy(str, Enum):
    """Per verification-kind policy (not inferred from free prose each time)."""

    ANSWER_ATTESTATION_SUFFICIENT = "ANSWER_ATTESTATION_SUFFICIENT"
    EXPLICIT_OBSERVATION_REQUIRED = "EXPLICIT_OBSERVATION_REQUIRED"
    NO_VERIFICATION_REQUIRED = "NO_VERIFICATION_REQUIRED"


# Production Stage-16 kinds → policy. Inspected against Q-001..Q-020 semantics.
# CONTROLLER_MAPPING asks whether a documented mapping actually works → observation.
_KIND_POLICY: dict[str, VerificationPolicy] = {
    "PATCHBAY_UNIT": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "PATCHBAY_MODE": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "ROUTING_VISUAL": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "ROUTING_COMPARE": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "MANUAL_FACT": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "BOARD_COMPARE": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "INVENTORY_LOCATION": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "POWER_AUDIT": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "MIDI_CLOCK": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "MIDI_PHYSICAL": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "ABLETON_SETTING": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "CAMERA_AUDIT": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "WORKFLOW": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT,
    "CONTROLLER_MAPPING": VerificationPolicy.EXPLICIT_OBSERVATION_REQUIRED,
}


def verification_policy_for(question: OpenQuestion | None) -> VerificationPolicy:
    if question is None:
        return VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT
    kind = ""
    if question.verification and question.verification.kind:
        kind = question.verification.kind.strip().upper()
    if kind in _KIND_POLICY:
        return _KIND_POLICY[kind]
    # Unknown / missing kind: prefer attestation for factual answers (narrow observation).
    return VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT


def effective_answer_actor(question: OpenQuestion) -> AnswerActor | None:
    if not (question.answer or "").strip():
        return None
    if question.answer_actor is not None:
        return question.answer_actor
    return AnswerActor.LEGACY_UNKNOWN


def has_human_attestation(question: OpenQuestion) -> bool:
    """FINAL answer supplied by a HUMAN — factual attestation authority."""
    from music_rig.models import QuestionStatus

    if question.status != QuestionStatus.RESOLVED:
        return False
    if not (question.answer or "").strip():
        return False
    return effective_answer_actor(question) is AnswerActor.HUMAN


def has_bot_answer(question: OpenQuestion) -> bool:
    return effective_answer_actor(question) is AnswerActor.BOT


def evidence_basis_for(question: OpenQuestion) -> EvidenceBasis:
    """Derive evidence basis without fabricating verification_result."""
    from music_rig.models import VerificationOutcome
    from music_rig.reconciliation.action_packet import has_positive_observation

    if has_positive_observation(question):
        return EvidenceBasis.HUMAN_OBSERVATION
    policy = verification_policy_for(question)
    if (
        policy is VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT
        and has_human_attestation(question)
    ):
        return EvidenceBasis.HUMAN_ANSWER
    # FAILED_TEST / UNKNOWN observations do not grant positive basis
    vr = question.verification_result
    if vr and vr.outcome in {
        VerificationOutcome.UNKNOWN,
        VerificationOutcome.FAILED_TEST,
    }:
        return EvidenceBasis.NONE
    return EvidenceBasis.NONE


def has_evidence_authority(question: OpenQuestion) -> bool:
    """True when CURRENT evidence escalation / verify-apply may proceed."""
    return evidence_basis_for(question) is not EvidenceBasis.NONE


def policy_matrix() -> dict[str, str]:
    return {k: v.value for k, v in sorted(_KIND_POLICY.items())}
