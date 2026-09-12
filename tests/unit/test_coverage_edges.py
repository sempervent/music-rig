"""Extra high-miss edge coverage to clear 80.5%."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from music_rig.channel_state import apply_data, save_raw, validate_channel_map
from music_rig.models import (
    AnswerActor,
    ChangesDocument,
    InboxDocument,
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
    VerificationOutcome,
    VerificationResult,
)
from music_rig.reconciliation.operation_registry import prepare_operation
from music_rig.reconciliation.operations import OperationMutability, RigOperation
from music_rig.actor import EvidenceBasis
from music_rig.store import StoreError, save_changes, save_inbox
from music_rig.verification_policy import evidence_basis_for, has_human_attestation


def test_rig_operation_from_dict_kind_only_and_invalid():
    op = RigOperation.from_dict(
        {
            "kind": "path.move",
            "args": {"path_id": "dirty", "node": "a"},
            "mutability": "mutating",
        }
    )
    assert op.namespace == "path" and op.action == "move"
    assert op.mutability is OperationMutability.MUTATING
    with pytest.raises(ValueError, match="invalid operation kind"):
        RigOperation.from_dict({"kind": "nosplit", "args": {}})


def test_prepare_verified_failed_test_and_duplicate_clarification(fx21):
    ctx = fx21["ctx"]
    qpath = fx21["questions"]
    data = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    for q in data["questions"]:
        if q["id"] == "Q-200":
            q["verification_result"] = {
                "outcome": "FAILED_TEST",
                "observed_at": "2026-09-12T12:00:00+00:00",
                "observed_value": "nope",
            }
            break
    qpath.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(StoreError, match="FAILED_TEST"):
        prepare_operation(
            RigOperation(
                namespace="path",
                action="set_evidence",
                args={
                    "path_id": "dirty",
                    "evidence": "VERIFIED",
                    "question_id": "Q-200",
                },
            ),
            ctx,
            {},
        )

    working: dict = {}
    text = "Which ART unit is PB-A specifically?"
    prepare_operation(
        RigOperation(
            namespace="question",
            action="open_clarification",
            args={"parent_question_id": "Q-200", "clarification": text},
        ),
        ctx,
        working,
    )
    with pytest.raises(StoreError, match="already exists"):
        prepare_operation(
            RigOperation(
                namespace="question",
                action="open_clarification",
                args={"parent_question_id": "Q-200", "clarification": text},
            ),
            ctx,
            working,
        )


def test_prepare_finalize_applies_linked_change(fx21):
    ctx = fx21["ctx"]
    changes = fx21["tmp"] / "changes.yaml"
    changes.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "CHG-200",
                        "created_at": "2026-09-12T12:00:00+00:00",
                        "category": "PATCHBAY",
                        "summary": "note models",
                        "status": "OPEN",
                        "related_questions": ["Q-200"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    qpath = fx21["questions"]
    data = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    for q in data["questions"]:
        if q["id"] == "Q-200":
            q["related_changes"] = ["CHG-200"]
            break
    qpath.write_text(yaml.safe_dump(data), encoding="utf-8")

    prep = prepare_operation(
        RigOperation(
            namespace="question",
            action="finalize_manual",
            args={"question_id": "Q-200", "note": "models confirmed"},
        ),
        ctx,
        {},
    )
    assert "CHG-200" in (prep.after.get("applied_changes") or [])


def test_channel_save_and_unknown_device(fx21, tmp_path):
    path = fx21["channels"]
    raw = {
        "alesis": {
            "1": {"source": None, "status": "UNASSIGNED"},
            "2": {"source": None, "status": "UNASSIGNED"},
            "3": {"source": None, "status": "UNASSIGNED"},
        }
    }
    assert validate_channel_map(raw) == []
    save_raw(raw, path)
    apply_data(path, raw)
    with pytest.raises(StoreError, match="Unknown device"):
        from music_rig.channel_state import propose_set_source

        propose_set_source("moog", "1", "x", path=path)


def test_save_inbox_and_changes(tmp_path, monkeypatch):
    from music_rig import store as store_mod

    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    monkeypatch.setattr(store_mod, "INBOX_PATH", inbox)
    monkeypatch.setattr(store_mod, "CHANGES_PATH", changes)
    save_inbox(InboxDocument(items=[]), inbox)
    save_changes(ChangesDocument(items=[]), changes)
    assert inbox.exists() and changes.exists()


def test_has_human_attestation_empty_via_construct():
    q = OpenQuestion.model_construct(
        id="Q-950",
        question="x?",
        area="Docs",
        status=QuestionStatus.RESOLVED,
        answer="",
        answer_actor=AnswerActor.HUMAN,
        resolved_at=datetime.now(UTC),
        related_todos=[],
        related_changes=[],
        notes="",
        reconciled_at=None,
        reconciliation_note="",
        target=None,
        verification=None,
        verification_note="",
        verification_result=None,
        clarifies_question=None,
    )
    assert has_human_attestation(q) is False


def test_evidence_basis_unknown_observation_without_attestation():
    q = OpenQuestion(
        id="Q-951",
        question="map?",
        area="Controls",
        status=QuestionStatus.RESOLVED,
        answer="yes",
        answer_actor=AnswerActor.BOT,
        resolved_at=datetime.now(UTC),
        verification=QuestionVerification(
            kind="CONTROLLER_MAPPING",
            prompt="press",
            answer_type="BOOL",
            choices=["YES", "NO", "UNKNOWN"],
        ),
        verification_result=VerificationResult(
            outcome=VerificationOutcome.UNKNOWN,
            observed_at=datetime.now(UTC),
            observed_value="UNKNOWN",
        ),
    )
    assert evidence_basis_for(q) is EvidenceBasis.NONE
