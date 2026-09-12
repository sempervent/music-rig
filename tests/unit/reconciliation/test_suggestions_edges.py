"""Additional suggestion serialization / render edge coverage."""

from __future__ import annotations

from music_rig.actor import ActorKind
from music_rig.reconciliation.operations import RigOperation
from music_rig.reconciliation.suggestions import (
    ActionSuggestion,
    SuggestionKind,
    legacy_command_to_suggestion,
    render_suggestion,
    render_suggestions,
    suggest_answer,
    suggest_changes_apply,
    suggest_finalize,
    suggest_plan,
    suggest_target_pair,
    suggest_todo_done,
    suggest_verify_record,
    suggestions_asdicts,
)


def test_action_suggestion_from_dict_roundtrip_and_unknown_kind():
    op = RigOperation(namespace="question", action="resolve", args={"question_id": "Q-1"})
    raw = ActionSuggestion(
        kind=SuggestionKind.RESOLVE,
        intent="question resolve",
        operation=op,
        code="x",
    ).to_dict()
    back = ActionSuggestion.from_dict(raw)
    assert back.operation is not None
    assert back.kind is SuggestionKind.RESOLVE

    weird = ActionSuggestion.from_dict(
        {"kind": "custom_thing", "intent": "do stuff", "params": {"a": 1}}
    )
    assert weird.kind == "custom_thing"
    assert weird.params["a"] == 1


def test_render_intent_variants():
    full = ActionSuggestion(kind=SuggestionKind.CLI_HINT, intent="uv run rig todo list")
    assert render_suggestion(full, actor=ActorKind.HUMAN) == "uv run rig todo list"
    bot = render_suggestion(full, actor=ActorKind.BOT)
    assert bot.startswith("uv run rig --am-bot")

    short = ActionSuggestion(kind=SuggestionKind.CLI_HINT, intent="rig question list --open")
    assert render_suggestion(short, actor=ActorKind.HUMAN).startswith("uv run rig question")

    body = ActionSuggestion(
        kind=SuggestionKind.ADVISORY,
        intent="todo done",
        params={"todo_id": "RIG-1"},
    )
    text = render_suggestion(body, actor=ActorKind.HUMAN)
    assert "todo done" in text and "--todo-id" in text


def test_convenience_constructors_and_legacy():
    assert suggest_answer("Q-1").kind is SuggestionKind.ANSWER
    assert "reconcile plan" in suggest_plan("Q-1").intent
    fin = suggest_finalize("Q-1", no_current_change=True, note="n")
    assert fin.operation is None
    assert "--no-current-change" in fin.intent
    assert "verify record" in suggest_verify_record("Q-1").intent
    assert suggest_target_pair("Q-1", "1/25").params["pair"] == "1/25"
    assert suggest_todo_done("RIG-1").code == "todo_done"
    assert suggest_changes_apply("CHG-1").code == "changes_apply"
    leg = legacy_command_to_suggestion("uv run rig status")
    assert leg.kind is SuggestionKind.CLI_HINT
    dicts = suggestions_asdicts([leg])
    assert dicts[0]["code"] == "legacy_cli"
    assert len(render_suggestions([leg], actor=ActorKind.BOT)) == 1
