"""Tests migrated to unit/verification/test_verification_result.py."""

from __future__ import annotations

from fixtures.repo_fixtures import _clock
from music_rig.models import (
    VerificationOutcome,
    VerificationResult,
)
from music_rig.reconciliation.adapters.unsupported import MANUAL_CLASSIFICATION
from music_rig.store import load_questions


def test_verification_result_model_serialization():
    vr = VerificationResult(
        outcome=VerificationOutcome.CONFIRMED,
        observed_at=_clock(),
        observed_value="ableton",
        note="checked",
    )
    data = vr.model_dump(mode="json")
    assert data["outcome"] == "CONFIRMED"
    assert data["source"] == "HUMAN"
    roundtrip = VerificationResult.model_validate(data)
    assert roundtrip.outcome == VerificationOutcome.CONFIRMED


def test_manual_classification_complete():
    assert len(MANUAL_CLASSIFICATION) == 13
    assert MANUAL_CLASSIFICATION["Q-012"] == "STRUCTURABLE_NOW"
    assert MANUAL_CLASSIFICATION["Q-007"] == "NEEDS_SMALL_SERVICE"


def test_production_verification_result_null():
    """Production questions must not have fabricated observations."""
    # Load real production path (not monkeypatched) — skip if fixture polluted

    # Use repo data path explicitly (not relative to this test file's depth)
    from music_rig.store import ROOT

    repo = ROOT / "data" / "open-questions.yaml"
    doc = load_questions(repo)
    for q in doc.questions:
        assert q.verification_result is None, f"{q.id} has fabricated observation"
