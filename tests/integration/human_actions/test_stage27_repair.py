"""Stage 27 repair regressions: freeform review + Thru5 device fanout."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from music_rig.actor import ActorKind, reset_actor, set_actor
from music_rig.models import (
    AnswerActor,
    HumanActionType,
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
)
from music_rig.store import StoreError


@pytest.fixture(autouse=True)
def _reset_actor():
    reset_actor()
    yield
    reset_actor()


def test_interpret_review_freeform_is_not_unrecognized():
    from music_rig import human_action_service

    prose = (
        "They don't have an OUT just a THRU and I don't feel like doing this now. "
        "I just want you to accept that those outputs come from it"
    )
    parsed = human_action_service.interpret_review_input(
        prose, action_type=HumanActionType.HUMAN_CLARIFICATION
    )
    assert parsed["decision"] == "freeform"
    assert "THRU" in parsed["value"]


def test_interpret_review_dod_prose_not_silent_yes():
    from music_rig import human_action_service

    parsed = human_action_service.interpret_review_input(
        "sure whatever looks fine",
        action_type=HumanActionType.TODO_DOD_CONFIRMATION,
    )
    assert parsed["decision"] == "need_explicit_dod"


def test_freeform_accept_does_not_suggest_question_reconcile(tmp_path, monkeypatch):
    from music_rig import human_action_service
    from music_rig import store as store_mod
    from music_rig.models import HumanActionType

    har = tmp_path / "human-actions.yaml"
    har.write_text("items: []\n", encoding="utf-8")
    monkeypatch.setattr(store_mod, "HUMAN_ACTIONS_PATH", har)

    # Minimal midi/inventory so freeform apply can run against tmp if needed —
    # use production paths but accept only checks reconcile prompt shape with dry path.
    # Create request then patch _dispatch to avoid writing production midi.
    req = human_action_service.create_request(
        action_type=HumanActionType.HUMAN_CLARIFICATION,
        artifact_id="THRU5-OUT-MAP",
        prompt="fanout",
        proposed_value="Thru5 feeds SL-2 SR-18 miniKORG KAOSS",
        explanation="device-level",
        path=har,
        clock=lambda: datetime(2026, 9, 12, tzinfo=UTC),
    )

    def _fake_dispatch(item, *, final_value, render):
        return {"recorded": final_value, "typed_links_created": []}

    monkeypatch.setattr(human_action_service, "_dispatch", _fake_dispatch)
    set_actor(ActorKind.HUMAN)
    result = human_action_service.accept(req.id, path=har, render=False)
    assert "reconcile plan question THRU5-OUT-MAP" not in (result.get("suggested_next") or "")
    assert "not a Question" in (result.get("reconcile_prompt") or "")


def test_create_request_rejects_duplicate_human_final(tmp_path, monkeypatch):
    from music_rig import human_action_service
    from music_rig import store as store_mod

    har = tmp_path / "human-actions.yaml"
    qpath = tmp_path / "open-questions.yaml"
    har.write_text("items: []\n", encoding="utf-8")
    q = OpenQuestion(
        id="Q-908",
        question="done?",
        area="Test",
        status=QuestionStatus.RESOLVED,
        answer="already",
        answer_actor=AnswerActor.HUMAN,
        resolved_at=datetime(2026, 9, 12, tzinfo=UTC),
        reconciled_at=datetime(2026, 9, 12, tzinfo=UTC),
        verification=QuestionVerification(kind="PATCHBAY_MODE", answer_type="TEXT", prompt="p"),
    )
    qpath.write_text(
        yaml.safe_dump({"questions": [q.model_dump(mode="json")]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(store_mod, "HUMAN_ACTIONS_PATH", har)
    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", qpath)
    with pytest.raises(StoreError, match="already has a HUMAN FINAL"):
        human_action_service.create_request(
            action_type=HumanActionType.QUESTION_ANSWER,
            artifact_id="Q-908",
            prompt="again?",
            proposed_value="duplicate",
            explanation="should fail",
            path=har,
        )


def test_superseded_har_cannot_accept(tmp_path, monkeypatch):
    from music_rig import human_action_service
    from music_rig import store as store_mod
    from music_rig.models import HumanActionRequest, HumanActionsDocument, HumanActionStatus

    har = tmp_path / "human-actions.yaml"
    req = HumanActionRequest(
        id="HAR-099",
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-099",
        prompt="p",
        proposed_value="v",
        explanation="e",
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
        status=HumanActionStatus.SUPERSEDED,
        superseded_reason="no longer needed",
    )
    store_mod.save_human_actions(HumanActionsDocument(items=[req]), har)
    monkeypatch.setattr(store_mod, "HUMAN_ACTIONS_PATH", har)
    set_actor(ActorKind.HUMAN)
    with pytest.raises(StoreError, match="SUPERSEDED"):
        human_action_service.accept("HAR-099", path=har, render=False)
