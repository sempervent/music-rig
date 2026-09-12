"""Tests migrated to integration/question_lifecycle/test_bot_guards.py."""

from __future__ import annotations

import pytest

from music_rig.actor import ActorKind, reset_actor, set_actor


@pytest.fixture(autouse=True)
def _reset_actor():
    reset_actor()
    yield
    reset_actor()


def test_bot_cannot_final_answer(monkeypatch, tmp_path):
    import yaml

    from music_rig import question_service
    from music_rig import store as store_mod
    from music_rig.models import OpenQuestion, OpenQuestionsDocument, QuestionStatus

    qpath = tmp_path / "open-questions.yaml"
    doc = OpenQuestionsDocument(
        questions=[
            OpenQuestion(
                id="Q-900",
                question="What is connected?",
                area="Test",
                status=QuestionStatus.OPEN,
            )
        ]
    )
    qpath.write_text(
        yaml.safe_dump({"questions": [q.model_dump(mode="json") for q in doc.questions]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", qpath)
    set_actor(ActorKind.BOT)
    with pytest.raises(Exception) as exc:
        question_service.answer_question("Q-900", "something", questions_path=qpath, render=False)
    assert "HUMAN answer" in str(exc.value)


def test_bot_cannot_verify_record(monkeypatch, tmp_path):
    import yaml

    from music_rig import verification_service
    from music_rig.models import OpenQuestion, OpenQuestionsDocument, QuestionStatus

    qpath = tmp_path / "open-questions.yaml"
    doc = OpenQuestionsDocument(
        questions=[
            OpenQuestion(
                id="Q-901",
                question="Does the switch work?",
                area="Test",
                status=QuestionStatus.OPEN,
            )
        ]
    )
    qpath.write_text(
        yaml.safe_dump({"questions": [q.model_dump(mode="json") for q in doc.questions]}),
        encoding="utf-8",
    )
    set_actor(ActorKind.BOT)
    with pytest.raises(Exception) as exc:
        verification_service.record_observation(
            "Q-901",
            "confirmed",
            value="yes",
            questions_path=qpath,
            render=False,
        )
    assert "HUMAN observation" in str(exc.value)
