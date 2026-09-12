"""Tests migrated to unit/verification/test_verification_result.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import (
    ableton_state,
    midi_state,
    question_service,
    store,
    verification_service,
)
from music_rig.cli import app
from music_rig.models import (
    MidiEvidenceStatus,
    QuestionStatus,
    ReconciliationState,
    VerificationOutcome,
    VerificationResult,
)
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.adapters import get_adapter
from music_rig.reconciliation.adapters.unsupported import MANUAL_CLASSIFICATION
from music_rig.reconciliation.types import Capability, PlanOperationKind, VerificationStatus
from music_rig.store import StoreError, load_changes, load_questions
from fixtures.stage_repos import _clock

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
    from music_rig.store import QUESTIONS_PATH

    # Use repo data path explicitly (not relative to this test file's depth)
    from music_rig.store import ROOT

    repo = ROOT / "data" / "open-questions.yaml"
    doc = load_questions(repo)
    for q in doc.questions:
        assert q.verification_result is None, f"{q.id} has fabricated observation"

