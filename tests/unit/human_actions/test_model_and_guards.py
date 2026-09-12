"""Unit tests for HumanActionRequest model and pending queue."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from music_rig.actor import ActorKind, reset_actor, set_actor
from music_rig.models import (
    AnswerActor,
    HumanActionRequest,
    HumanActionsDocument,
    HumanActionStatus,
    HumanActionType,
)
from music_rig.store import StoreError


@pytest.fixture(autouse=True)
def _reset_actor():
    reset_actor()
    yield
    reset_actor()


def test_model_preserves_original_on_create():
    req = HumanActionRequest(
        id="HAR-001",
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-008",
        prompt="Modes?",
        proposed_value="all normal",
        explanation="bot draft",
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
    )
    assert req.proposed_value_original == "all normal"
    assert req.status is HumanActionStatus.PENDING
    assert req.source_actor is AnswerActor.BOT


def test_verification_requires_outcome():
    with pytest.raises(ValueError, match="verification_outcome"):
        HumanActionRequest(
            id="HAR-002",
            action_type=HumanActionType.VERIFICATION_RESULT,
            artifact_id="Q-017",
            prompt="Observe",
            proposed_value="no names",
            explanation="need observation",
            created_at=datetime(2026, 9, 12, tzinfo=UTC),
        )


def test_document_next_id_and_pending():
    doc = HumanActionsDocument(items=[])
    assert doc.next_id() == "HAR-001"
    req = HumanActionRequest(
        id="HAR-001",
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-008",
        prompt="p",
        proposed_value="v",
        explanation="e",
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
        status=HumanActionStatus.REJECTED,
    )
    doc2 = HumanActionsDocument(items=[req])
    assert doc2.next_id() == "HAR-002"
    assert doc2.pending() == []


def test_create_and_bot_cannot_accept(tmp_path, monkeypatch):
    from music_rig import human_action_service
    from music_rig import store as store_mod

    har = tmp_path / "human-actions.yaml"
    har.write_text("items: []\n", encoding="utf-8")
    monkeypatch.setattr(store_mod, "HUMAN_ACTIONS_PATH", har)

    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-008",
        prompt="What modes?",
        proposed_value="All normal",
        explanation="BOT prepared from Stage 25",
        path=har,
    )
    assert req.id == "HAR-001"
    set_actor(ActorKind.BOT)
    with pytest.raises(StoreError, match="cannot accept HUMAN authority"):
        human_action_service.accept(req.id, path=har, render=False)


def test_format_review_shows_dod():
    from music_rig import human_action_service

    req = HumanActionRequest(
        id="HAR-010",
        action_type=HumanActionType.TODO_DOD_CONFIRMATION,
        artifact_id="RIG-031",
        prompt="Confirm DoD?",
        proposed_value="midi-clock.md states verified CURRENT behavior",
        explanation="needs human DoD",
        consequences="Marks RIG-031 DONE",
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
    )
    text = human_action_service.format_review(req)
    assert "Definition of Done" in text
    assert "midi-clock.md" in text
    assert "HAR-010" in text
