"""Integration: BOT prepares → HUMAN accepts → authority recorded via services."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from helpers.cli import invoke_rig_bot
from music_rig.actor import ActorKind, reset_actor, set_actor
from music_rig.models import (
    AnswerActor,
    HumanActionType,
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
    TodoDocument,
    TodoPriority,
    TodoStatus,
    TodoTask,
)
from music_rig.store import StoreError, load_todo


@pytest.fixture(autouse=True)
def _reset_actor():
    reset_actor()
    yield
    reset_actor()


def _clock():
    return datetime(2026, 9, 12, 18, 0, 0, tzinfo=UTC)


def _write_questions(path, questions: list[OpenQuestion]) -> None:
    path.write_text(
        yaml.safe_dump(
            {"questions": [q.model_dump(mode="json") for q in questions]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def fx(tmp_path, monkeypatch):
    from music_rig import store as store_mod

    har = tmp_path / "human-actions.yaml"
    har.write_text("items: []\n", encoding="utf-8")
    qpath = tmp_path / "open-questions.yaml"
    qpath.write_text("questions: []\n", encoding="utf-8")
    todo_path = tmp_path / "todo.yaml"
    todo_path.write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    monkeypatch.setattr(store_mod, "HUMAN_ACTIONS_PATH", har)
    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", qpath)
    monkeypatch.setattr(store_mod, "TODO_PATH", todo_path)
    return {"har": har, "questions": qpath, "todo": todo_path, "tmp": tmp_path}


def test_human_accept_question_sets_answer_actor_human(fx, monkeypatch):
    from music_rig import human_action_service, question_service

    q = OpenQuestion(
        id="Q-908",
        question="PB-B modes?",
        area="Patchbay",
        status=QuestionStatus.OPEN,
        answer="draft",
        answer_actor=AnswerActor.BOT,
        verification=QuestionVerification(
            kind="PATCHBAY_MODE",
            answer_type="TEXT",
            prompt="Observe modes",
        ),
    )
    _write_questions(fx["questions"], [q])
    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-908",
        prompt="PB-B modes?",
        proposed_value="All represented PB-B pairs are normal",
        explanation="BOT prepared",
        path=fx["har"],
        clock=_clock,
    )
    set_actor(ActorKind.HUMAN)
    result = human_action_service.accept(
        req.id, path=fx["har"], render=False, offer_reconcile=False
    )
    assert result["action"]["accepted_by"] == "HUMAN"
    assert result["action"]["proposed_value_original"] == ("All represented PB-B pairs are normal")
    fresh = question_service.get_question("Q-908", questions_path=fx["questions"])
    assert fresh.status is QuestionStatus.RESOLVED
    assert fresh.answer_actor is AnswerActor.HUMAN
    assert fresh.answer == "All represented PB-B pairs are normal"


def test_human_edit_before_accept_preserves_original(fx):
    from music_rig import human_action_service, question_service

    q = OpenQuestion(
        id="Q-917",
        question="Templates?",
        area="MIDI",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CONTROLS_VERIFY",
            answer_type="TEXT",
            prompt="Read templates",
        ),
    )
    _write_questions(fx["questions"], [q])
    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-917",
        prompt="Templates?",
        proposed_value="UNKNOWN — templates have no names",
        explanation="BOT prepared",
        path=fx["har"],
        clock=_clock,
    )
    human_action_service.accept(
        req.id,
        edited_value="UNKNOWN — no named templates are loaded",
        path=fx["har"],
        render=False,
        offer_reconcile=False,
    )
    accepted = human_action_service.get_action(req.id, path=fx["har"])
    assert accepted.proposed_value_original == "UNKNOWN — templates have no names"
    assert accepted.accepted_value == "UNKNOWN — no named templates are loaded"
    fresh = question_service.get_question("Q-917", questions_path=fx["questions"])
    assert fresh.answer == "UNKNOWN — no named templates are loaded"
    assert fresh.answer_actor is AnswerActor.HUMAN


def test_bot_cli_accept_rejected(fx):
    from music_rig import human_action_service

    q = OpenQuestion(
        id="Q-909",
        question="x?",
        area="Test",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CONTROLS_VERIFY",
            answer_type="TEXT",
            prompt="p",
        ),
    )
    _write_questions(fx["questions"], [q])
    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-909",
        prompt="x?",
        proposed_value="yes",
        explanation="prep",
        path=fx["har"],
        clock=_clock,
    )
    result = invoke_rig_bot("human", "accept", req.id)
    assert result.exit_code != 0
    assert "cannot accept HUMAN authority" in result.stdout + result.stderr


def test_verification_unknown_via_accept(fx, monkeypatch):
    from music_rig import human_action_service, question_service

    q = OpenQuestion(
        id="Q-918",
        question="Templates loaded?",
        area="MIDI",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CONTROLS_VERIFY",
            answer_type="TEXT",
            prompt="Observe device",
        ),
    )
    _write_questions(fx["questions"], [q])
    req = human_action_service.create_request(
        action_type=HumanActionType.VERIFICATION_RESULT,
        artifact_id="Q-918",
        prompt="Observe ZeRO templates",
        proposed_value="no named templates loaded",
        explanation="EXPLICIT_OBSERVATION_REQUIRED",
        verification_outcome="unknown",
        verification_note="no named templates loaded",
        path=fx["har"],
        clock=_clock,
    )
    human_action_service.accept(req.id, path=fx["har"], render=False, offer_reconcile=False)
    fresh = question_service.get_question("Q-918", questions_path=fx["questions"])
    assert fresh.verification_result is not None
    assert fresh.verification_result.outcome.value == "UNKNOWN"


def test_dod_accept_marks_todo_done(fx):
    from music_rig import human_action_service, todo_service
    from music_rig.store import save_todo

    dod = "midi-clock.md states verified CURRENT behavior, not only intent"
    save_todo(
        TodoDocument(
            next_session=[],
            tasks=[
                TodoTask(
                    id="RIG-931",
                    task="Confirm clock",
                    area="MIDI",
                    priority=TodoPriority.P2,
                    status=TodoStatus.READY,
                    definition_of_done=dod,
                )
            ],
        ),
        fx["todo"],
    )
    req = human_action_service.create_request(
        action_type=HumanActionType.TODO_DOD_CONFIRMATION,
        artifact_id="RIG-931",
        prompt="Confirm Definition of Done for RIG-931?",
        proposed_value=dod,
        explanation="HUMAN DoD attestation required",
        consequences="Marks RIG-931 DONE",
        path=fx["har"],
        clock=_clock,
    )
    human_action_service.accept(
        req.id, edited_value="YES", path=fx["har"], render=False, offer_reconcile=False
    )
    task = todo_service.get_task(load_todo(fx["todo"]), "RIG-931")
    assert task.status is TodoStatus.DONE


def test_stale_superseded_when_human_already_answered(fx):
    from music_rig import human_action_service

    q = OpenQuestion(
        id="Q-910",
        question="Done?",
        area="Test",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CONTROLS_VERIFY",
            answer_type="TEXT",
            prompt="p",
        ),
    )
    _write_questions(fx["questions"], [q])
    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-910",
        prompt="Done?",
        proposed_value="stale proposal",
        explanation="too late",
        path=fx["har"],
        clock=_clock,
    )
    # HUMAN answers independently → request becomes stale
    q_final = OpenQuestion(
        id="Q-910",
        question="Done?",
        area="Test",
        status=QuestionStatus.RESOLVED,
        answer="already",
        answer_actor=AnswerActor.HUMAN,
        resolved_at=_clock(),
        verification=QuestionVerification(
            kind="CONTROLS_VERIFY",
            answer_type="TEXT",
            prompt="p",
        ),
    )
    _write_questions(fx["questions"], [q_final])
    superseded = human_action_service.refresh_stale(path=fx["har"], questions_path=fx["questions"])
    assert any(s.id == req.id for s in superseded)
    with pytest.raises(StoreError, match="SUPERSEDED"):
        human_action_service.accept(req.id, path=fx["har"], render=False)


def test_human_reject_leaves_target(fx):
    from music_rig import human_action_service, question_service

    q = OpenQuestion(
        id="Q-911",
        question="x?",
        area="Test",
        status=QuestionStatus.OPEN,
        verification=QuestionVerification(
            kind="CONTROLS_VERIFY",
            answer_type="TEXT",
            prompt="p",
        ),
    )
    _write_questions(fx["questions"], [q])
    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-911",
        prompt="x?",
        proposed_value="nope",
        explanation="prep",
        path=fx["har"],
        clock=_clock,
    )
    human_action_service.reject(req.id, path=fx["har"], clock=_clock)
    fresh = question_service.get_question("Q-911", questions_path=fx["questions"])
    assert fresh.status is QuestionStatus.OPEN
    assert fresh.answer == ""


def test_human_prepare_cli_bot_ok(fx):
    from music_rig import human_action_service
    from music_rig.actor import ActorKind, set_actor

    set_actor(ActorKind.BOT)
    req = human_action_service.create_request(
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-999",
        prompt="Prompt text",
        proposed_value="proposed",
        explanation="Because BOT cannot finalize",
        path=fx["har"],
        clock=_clock,
    )
    assert req.id.startswith("HAR-")
    assert req.source_actor is AnswerActor.BOT
