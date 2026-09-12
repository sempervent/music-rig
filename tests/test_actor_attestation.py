"""Actor provenance, attestation, and clarification tests."""

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

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_actor():
    reset_actor()
    yield
    reset_actor()


def test_root_am_bot_sets_bot_actor():
    r = runner.invoke(app, ["--am-bot", "agent", "capabilities", "--json"])
    assert r.exit_code == 0, r.output
    assert get_actor() is ActorKind.BOT


def test_root_help_documents_am_bot():
    import re

    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0, r.output
    # Rich may inject ANSI / wrap cells; strip SGR before substring checks.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", r.output)
    assert "--am-bot" in plain



def test_human_default_actor():
    assert get_actor() is ActorKind.HUMAN
    set_actor(ActorKind.BOT)
    assert get_actor() is ActorKind.BOT
    reset_actor()
    assert get_actor() is ActorKind.HUMAN


def test_am_bot_tui_rejected():
    r = runner.invoke(app, ["--am-bot", "tui"])
    assert r.exit_code != 0
    assert "not supported" in (r.output + str(r.exception)).casefold()


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


def test_q014_shaped_human_attestation_is_deterministic(monkeypatch, tmp_path):
    from music_rig.models import (
        OpenQuestion,
        QuestionStatus,
        QuestionTarget,
        QuestionVerification,
    )
    from datetime import datetime, timezone
    from music_rig.reconciliation.adapters.midi_clock import MidiClockAdapter
    import yaml

    midi = {
        "endpoints": [{"id": "ableton", "kind": "software", "name": "Ableton"}],
        "devices": [],
        "connections": [],
        "channels": [],
        "clock": {"master": {"endpoint_ref": "ableton", "status": "INTENDED", "notes": ""}},
        "ableton_ports": [],
        "routes": [],
        "unknowns": [],
    }
    midi_path = tmp_path / "midi.yaml"
    midi_path.write_text(yaml.safe_dump(midi), encoding="utf-8")
    q = OpenQuestion(
        id="Q-914",
        question="master?",
        area="MIDI",
        status=QuestionStatus.RESOLVED,
        answer="Ableton is definitely the master clock; nothing else is master currently",
        answer_actor=AnswerActor.HUMAN,
        resolved_at=datetime.now(timezone.utc),
        target=QuestionTarget(domain="midi.clock_master"),
        verification=QuestionVerification(
            kind="MIDI_CLOCK",
            prompt="x",
            answer_type="ENUM",
            choices=["ableton", "kaoss-replay", "sl-2", "UNKNOWN"],
        ),
    )
    assert has_human_attestation(q)
    assert has_evidence_authority(q)
    plan = MidiClockAdapter().plan(q, paths={"midi": midi_path})
    assert plan.state is ReconciliationState.READY_TO_APPLY
    assert not any(
        isinstance(b, dict) and b.get("code") == "needs_human_observation"
        for b in plan.blockers
    )
    d = classify_reconciliation_dispatch(plan)
    assert d.mode is DispatchMode.DETERMINISTIC
    assert d.provider_eligible is False


def test_q014_shaped_bot_answer_not_authority(monkeypatch, tmp_path):
    from music_rig.models import (
        OpenQuestion,
        QuestionStatus,
        QuestionTarget,
        QuestionVerification,
    )
    from datetime import datetime, timezone
    from music_rig.reconciliation.adapters.midi_clock import MidiClockAdapter
    import yaml

    midi = {
        "endpoints": [{"id": "ableton", "kind": "software", "name": "Ableton"}],
        "devices": [],
        "connections": [],
        "channels": [],
        "clock": {"master": {"endpoint_ref": "ableton", "status": "INTENDED", "notes": ""}},
        "ableton_ports": [],
        "routes": [],
        "unknowns": [],
    }
    midi_path = tmp_path / "midi.yaml"
    midi_path.write_text(yaml.safe_dump(midi), encoding="utf-8")
    q = OpenQuestion(
        id="Q-915",
        question="master?",
        area="MIDI",
        status=QuestionStatus.RESOLVED,
        answer="Ableton is definitely the master clock; nothing else is master currently",
        answer_actor=AnswerActor.BOT,
        resolved_at=datetime.now(timezone.utc),
        target=QuestionTarget(domain="midi.clock_master"),
        verification=QuestionVerification(
            kind="MIDI_CLOCK",
            prompt="x",
            answer_type="ENUM",
            choices=["ableton", "kaoss-replay", "sl-2", "UNKNOWN"],
        ),
    )
    assert not has_human_attestation(q)
    assert not has_evidence_authority(q)
    plan = MidiClockAdapter().plan(q, paths={"midi": midi_path})
    assert plan.state is ReconciliationState.NEEDS_ANSWER
    d = classify_reconciliation_dispatch(plan)
    assert d.mode is DispatchMode.HUMAN_ANSWER


def test_bot_cannot_final_answer(monkeypatch, tmp_path):
    from music_rig import question_service
    from music_rig import store as store_mod
    from music_rig.models import OpenQuestion, OpenQuestionsDocument, QuestionStatus
    import yaml

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
        question_service.answer_question(
            "Q-900", "something", questions_path=qpath, render=False
        )
    assert "HUMAN answer" in str(exc.value)


def test_bot_cannot_verify_record(monkeypatch, tmp_path):
    from music_rig import verification_service
    from music_rig import store as store_mod
    from music_rig.models import OpenQuestion, OpenQuestionsDocument, QuestionStatus
    import yaml

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


def test_open_clarification_creates_child(tmp_path, monkeypatch):
    from music_rig import question_service
    from music_rig.models import OpenQuestion, OpenQuestionsDocument, QuestionStatus
    import yaml

    qpath = tmp_path / "open-questions.yaml"
    doc = OpenQuestionsDocument(
        questions=[
            OpenQuestion(
                id="Q-910",
                question="Which physical patchbay is PB-A?",
                area="Patchbay",
                status=QuestionStatus.RESOLVED,
                answer="The ART one.",
                answer_actor=AnswerActor.HUMAN,
                resolved_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
        ]
    )
    qpath.write_text(
        yaml.safe_dump({"questions": [q.model_dump(mode="json") for q in doc.questions]}),
        encoding="utf-8",
    )
    result = question_service.open_clarification_question(
        "Q-910",
        "When you said 'the ART one', did you mean PB-A or rack position?",
        questions_path=qpath,
        render=False,
    )
    assert result["parent_id"] == "Q-910"
    child = question_service.get_question(result["question_id"], questions_path=qpath)
    assert child.clarifies_question == "Q-910"
    assert child.status is QuestionStatus.OPEN
    assert child.answer == ""
