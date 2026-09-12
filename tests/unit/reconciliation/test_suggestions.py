"""Unit coverage for structured ActionSuggestion rendering."""

from __future__ import annotations

from music_rig.actor import ActorKind
from music_rig.models import ReconciliationState
from music_rig.reconciliation.suggestions import (
    SuggestionKind,
    ActionSuggestion,
    render_suggestion,
    suggest_resolve,
)
from music_rig.reconciliation.types import Capability, Plan


def test_render_suggestion_actor_aware():
    s = suggest_resolve("Q-001")
    human = render_suggestion(s, actor=ActorKind.HUMAN)
    bot = render_suggestion(s, actor=ActorKind.BOT)
    assert human.startswith("uv run rig ")
    assert "--am-bot" not in human.split("rig", 1)[0] + "rig"  # prefix check
    assert human.startswith("uv run rig question") or "question resolve" in human
    assert bot.startswith("uv run rig --am-bot")
    assert "Q-001" in human and "Q-001" in bot


def test_plan_to_dict_includes_suggestions_and_compat_commands():
    plan = Plan(
        artifact_type="question",
        artifact_id="Q-001",
        state=ReconciliationState.DRAFT_ANSWER,
        capability=Capability.UNSUPPORTED,
        suggestions=[suggest_resolve("Q-001")],
    )
    data = plan.to_dict()
    assert data["suggestions"]
    assert data["suggestions"][0]["kind"] == SuggestionKind.RESOLVE.value
    assert any("resolve" in c for c in data["suggested_commands"])
    # Attribute compat for tests that read plan.suggested_commands directly.
    assert any("resolve" in c for c in plan.suggested_commands)


def test_legacy_suggested_commands_still_serialize():
    plan = Plan(
        artifact_type="question",
        artifact_id="Q-002",
        state=ReconciliationState.NEEDS_ANSWER,
        capability=Capability.MANUAL,
        suggested_commands=["uv run rig question list --open"],
    )
    data = plan.to_dict()
    assert data["suggestions"] == []
    assert data["suggested_commands"] == ["uv run rig question list --open"]


def test_cli_hint_intent_bot_injects_am_bot():
    s = ActionSuggestion(
        kind=SuggestionKind.CLI_HINT,
        intent="uv run rig question list --open",
    )
    assert "--am-bot" in render_suggestion(s, actor="BOT")
