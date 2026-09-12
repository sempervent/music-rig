"""Tests migrated to integration/question_lifecycle/test_draft_resolve_finalize.py."""

from __future__ import annotations

from fixtures.stage_repos import _clock
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import channel_state, question_service, todo_service
from music_rig.channel_state import propose_set_source, validate_channel_map
from music_rig.cli import app
from music_rig.models import AnswerState, QuestionStatus, ReconciliationState, TodoStatus
from music_rig.reconciliation import service as reconcile_service
from music_rig.store import StoreError, load_questions, load_todo
from music_rig.tui.app import RigApp
from music_rig.tui.screens.answer import AnswerScreen

runner = CliRunner()

def test_draft_and_answer_cli_json(fx19):
    r = runner.invoke(
        app,
        [
            "question",
            "draft",
            "Q-191",
            "--answer",
            "provisional answer",
            "--json",
            "--no-render",
        ],
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["ok"] is True
    assert payload["result"]["answer_state"] == "DRAFT"
    assert payload["result"]["question_status"] == "OPEN"
    assert payload["result"]["resolved_at"] is None
    assert "resolve" in payload["result"]["suggested_next_command"]

    r2 = runner.invoke(
        app,
        [
            "question",
            "answer",
            "Q-191",
            "--answer",
            "final answer",
            "--json",
            "--no-render",
        ],
    )
    assert r2.exit_code == 0, r2.output
    payload2 = json.loads(r2.output)
    assert payload2["result"]["answer_state"] == "FINAL"
    assert payload2["result"]["question_status"] == "RESOLVED"
    assert payload2["result"]["reconciled_at"] is None
    assert payload2["result"]["suggested_next_command"]

def test_resolve_promotes_draft_without_new_answer(fx19):
    question_service.draft_question("Q-191", "keep me", render=False)
    r = runner.invoke(
        app, ["question", "resolve", "Q-191", "--json", "--no-render"]
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["result"]["answer_state"] == "FINAL"
    assert payload["result"]["answer"] == "keep me"
    q = question_service.get_question("Q-191")
    assert q.status == QuestionStatus.RESOLVED
    assert q.verification_result is None

def test_manual_finalize_q001_style(fx19, monkeypatch):
    """Multi-domain CURRENT via services, then finalize --confirm-current-reconciled."""
    answer = (
        "A send → Alesis 2; B send → Alesis 1; Y send → Alesis 3. "
        "Non-clean A/B/Y destinations documented."
    )
    question_service.answer_question("Q-190", answer, render=False, clock=_clock)
    q = question_service.get_question("Q-190")
    assert q.verification_result is None

    preview, data = propose_set_source("alesis", 1, "B send", path=fx19["channels"])
    assert preview.after["status"] == "CURRENT"
    channel_state.save_raw(data, path=fx19["channels"])
    _, data2 = propose_set_source("alesis", 2, "A send", path=fx19["channels"])
    channel_state.save_raw(data2, path=fx19["channels"])
    _, data3 = propose_set_source("alesis", 3, "Y send", path=fx19["channels"])
    channel_state.save_raw(data3, path=fx19["channels"])

    plan = reconcile_service.plan_question("Q-190")
    assert plan.state == ReconciliationState.NEEDS_AGENT_ACTION
    packet = (plan.details or {}).get("action_packet") or {}
    assert packet.get("requires_agent_interpretation") is True
    assert packet.get("manual_finalize_allowed") is True
    assert "--confirm-current-reconciled" in (
        packet.get("required_confirmation") or ""
    )
    assert packet.get("finalize_command_template")

    with pytest.raises(StoreError):
        reconcile_service.finalize_question("Q-190", yes=True, note="")
    with pytest.raises(StoreError, match="note"):
        reconcile_service.finalize_question(
            "Q-190",
            yes=True,
            confirm_current_reconciled=True,
            note="",
        )

    question_service.draft_question("Q-191", "x", render=False)
    with pytest.raises(StoreError, match="RESOLVED"):
        reconcile_service.finalize_question(
            "Q-191",
            yes=True,
            confirm_current_reconciled=True,
            note="nope",
        )

    result = reconcile_service.finalize_question(
        "Q-190",
        yes=True,
        confirm_current_reconciled=True,
        note="Updated alesis channel sources from final human answer",
        complete_linked_todos=True,
        confirm_dod=True,
        clock=_clock,
    )
    assert result["confirm_current_reconciled"] is True
    assert result["verification_result_unchanged"] is True
    assert "RIG-190" in result["completed_todos"]

    q = question_service.get_question("Q-190")
    assert q.reconciled_at is not None
    assert q.verification_result is None
    assert "agent-interpreted" in q.reconciliation_note.casefold()
    todo = load_todo()
    assert todo.task_map()["RIG-190"].status == TodoStatus.DONE
    assert "RIG-190" not in todo.next_session

def test_manual_finalize_cli(fx19):
    question_service.answer_question("Q-190", "destinations set", render=False)
    r = runner.invoke(
        app,
        [
            "reconcile",
            "finalize",
            "question",
            "Q-190",
            "--confirm-current-reconciled",
            "--note",
            "CURRENT updated via CLI from answer",
            "--complete-linked-todos",
            "--confirm-dod",
            "--yes",
            "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["result"]["confirm_current_reconciled"] is True
    q = question_service.get_question("Q-190")
    assert q.reconciled_at is not None
    assert q.verification_result is None

def test_cleanup_draft_and_manual_findings(fx19):
    question_service.draft_question("Q-191", "drafty", render=False)
    question_service.answer_question("Q-190", "needs agent", render=False)

    issues = reconcile_service.cleanup_reconciliation_issues(
        questions_path=fx19["questions"],
        todo_path=fx19["todo"],
    )
    codes = {i["code"] for i in issues}
    assert "question_draft_answer" in codes
    assert "resolved_not_reconciled" in codes
    assert "manual_recon_waiting" in codes
    draft_issue = next(i for i in issues if i["code"] == "question_draft_answer")
    assert any("resolve" in c for c in draft_issue["suggested_commands"])

def test_todo_schema_rejects_terminal_in_next_session(fx19):
    """DONE/CANCELLED cannot remain in Next Session (model + check)."""
    from music_rig.models import TodoDocument
    from music_rig.store import load_todo

    raw = yaml.safe_load(fx19["todo"].read_text())
    raw["next_session"] = ["RIG-191"]  # DONE
    fx19["todo"].write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(Exception):
        load_todo(fx19["todo"])
    with pytest.raises(Exception):
        TodoDocument.model_validate(raw)

def test_todo_done_removes_from_next_session(fx19):
    todo_service.set_todo_status(
        "RIG-190", TodoStatus.DONE, remove_from_next=True, render=False
    )
    tdoc = load_todo()
    assert tdoc.task_map()["RIG-190"].status == TodoStatus.DONE
    assert "RIG-190" not in tdoc.next_session

def test_reconcile_show_exposes_answer_state(fx19):
    question_service.draft_question("Q-191", "x", render=False)
    shown = reconcile_service.show_question("Q-191")
    assert shown["answer_state"] == "DRAFT"
    assert shown["question_status"] == "OPEN"

def test_question_show_json_answer_state(fx19):
    r = runner.invoke(app, ["question", "show", "Q-191", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["result"]["answer_state"] == "UNANSWERED"

def test_skills_mentions_live_data_and_blocking_bug():
    text = Path("SKILLS.md").read_text(encoding="utf-8")
    assert "Live Rig Data Changes During Development" in text
    assert "Blocking code bug during reconciliation workflow" in text
    assert "Do not ask redundant" in text
    assert "confirm-current-reconciled" in text
    assert "question draft" in text

