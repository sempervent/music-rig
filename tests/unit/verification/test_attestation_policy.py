"""Tests migrated to unit/verification/test_attestation_policy.py."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner
from music_rig.actor import ActorKind, get_actor, reset_actor, set_actor
from music_rig.cli import app
from music_rig.models import AnswerActor, ReconciliationState
from music_rig.reconciliation.dispatch import DispatchMode, classify_reconciliation_dispatch
from music_rig.reconciliation.types import Capability, Plan
from music_rig.verification_policy import (
    VerificationPolicy,
    evidence_basis_for,
    has_evidence_authority,
    has_human_attestation,
    policy_matrix,
    verification_policy_for,
)

def test_policy_matrix_covers_production_kinds():
    m = policy_matrix()
    assert m["MIDI_CLOCK"] == VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT.value
    assert m["CONTROLLER_MAPPING"] == VerificationPolicy.EXPLICIT_OBSERVATION_REQUIRED.value
    assert m["PATCHBAY_UNIT"] == VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT.value

def _clock_plan(*, actor: AnswerActor | None, observation: bool = False) -> Plan:
    from music_rig.models import OpenQuestion, QuestionStatus, QuestionVerification
    from datetime import datetime, timezone
    from music_rig.reconciliation.adapters.midi_clock import MidiClockAdapter

    q = OpenQuestion(
        id="Q-914",
        question="Which device is actually the MIDI clock master?",
        area="MIDI",
        status=QuestionStatus.RESOLVED,
        answer="Ableton is definitely the master clock; nothing else is master currently",
        answer_actor=actor,
        resolved_at=datetime.now(timezone.utc),
        target={"domain": "midi.clock_master"},
        verification=QuestionVerification(
            kind="MIDI_CLOCK",
            prompt="observe master",
            answer_type="ENUM",
            choices=["ableton", "kaoss-replay", "sl-2", "UNKNOWN"],
        ),
        verification_result=(
            {
                "outcome": "CONFIRMED",
                "observed_at": datetime.now(timezone.utc),
                "observed_value": "ableton",
            }
            if observation
            else None
        ),
    )
    # Fake CURRENT via adapter.read is live — use monkeypatched plan details instead
    return Plan(
        artifact_type="question",
        artifact_id="Q-914",
        state=ReconciliationState.READY_TO_APPLY,
        capability=Capability.VERIFY_ONLY,
        current={"master": "ableton", "status": "INTENDED"},
        desired="ableton",
        operations=[{"op": "SET_EVIDENCE_VERIFIED"}],
        blockers=[],
        suggested_commands=[],
        details={
            "verification_policy": VerificationPolicy.ANSWER_ATTESTATION_SUFFICIENT.value,
            "evidence_basis": "HUMAN_ANSWER" if actor is AnswerActor.HUMAN else "NONE",
            "answer_actor": actor.value if actor else None,
        },
    )

def test_controller_mapping_requires_observation():
    from music_rig.models import OpenQuestion, QuestionVerification, QuestionStatus

    q = OpenQuestion(
        id="Q-902",
        question="Does FCB switch 1 trigger the documented action?",
        area="Controls",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CONTROLLER_MAPPING",
            prompt="press the switch",
            answer_type="BOOL",
            choices=["YES", "NO", "UNKNOWN"],
        ),
    )
    assert (
        verification_policy_for(q)
        is VerificationPolicy.EXPLICIT_OBSERVATION_REQUIRED
    )

