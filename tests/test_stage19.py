"""Stage 19 — question answer lifecycle, manual finalize, channel invariants.

Fixture-only mutations. Preserve production Q-001 baseline (do not undo).
"""

from __future__ import annotations

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


def _clock():
    return datetime(2026, 9, 12, 4, 0, 0, tzinfo=timezone.utc)


def _write_docs(tmp: Path) -> dict[str, Path]:
    paths = {}
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
        ("inventory.md", "<!-- rig:inventory:start -->", "<!-- rig:inventory:end -->"),
    ]:
        path = tmp / name
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")
        paths[name] = path
    return paths


def test_production_q001_baseline_preserved():
    """Do not undo Stage 18 Q-001 reconciliation during Stage 19."""
    doc = load_questions()
    q1 = doc.question_map()["Q-001"]
    assert q1.status == QuestionStatus.RESOLVED
    assert q1.answer.strip()
    assert q1.resolved_at is not None
    assert q1.reconciled_at is not None
    assert "Alesis 2" in q1.answer and "Alesis 1" in q1.answer
    assert question_service.derive_answer_state(q1) == AnswerState.FINAL
    assert question_service.lifecycle_label(q1) == "RESOLVED/RECONCILED"

    for qid in ("Q-002", "Q-003", "Q-004", "Q-006"):
        q = doc.question_map()[qid]
        assert q.status == QuestionStatus.RESOLVED
        assert q.reconciled_at is not None

    todo = load_todo()
    r3 = todo.task_map()["RIG-003"]
    assert r3.status == TodoStatus.DONE
    assert "RIG-003" not in todo.next_session


@pytest.fixture
def fx19(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    channels = tmp_path / "channel-map.yaml"
    routing = tmp_path / "routing.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-190"],
                "tasks": [
                    {
                        "id": "RIG-190",
                        "task": "Document A/B/Y destinations",
                        "area": "Routing",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "CURRENT matches answer",
                        "notes": "",
                    },
                    {
                        "id": "RIG-191",
                        "task": "Terminal leftover",
                        "area": "Docs",
                        "priority": "P3",
                        "status": "DONE",
                        "depends_on": [],
                        "definition_of_done": "x",
                        "notes": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "fx-gear",
                        "name": "FX Gear",
                        "category": "utility",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-190",
                        "question": "Where do A/B/Y non-clean sends go?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": ["RIG-190"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "target": {"domain": "routing.path", "path": "aby-other"},
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "Observe A/B/Y destinations",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-191",
                        "question": "Simple open unanswered",
                        "area": "Docs",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    channels.write_text(
        yaml.safe_dump(
            {
                "tascam": {
                    1: {"type": "line", "status": "UNASSIGNED", "source": None},
                    2: {"type": "line", "status": "UNASSIGNED", "source": None},
                },
                "alesis": {
                    1: {"status": "UNASSIGNED", "source": None},
                    2: {"status": "UNASSIGNED", "source": None},
                    3: {"status": "UNASSIGNED", "source": None},
                },
            }
        ),
        encoding="utf-8",
    )
    routing.write_text(
        yaml.safe_dump(
            {
                "named_paths": {
                    "aby-other": {
                        "summary": "A/B/Y other",
                        "status": "CURRENT",
                        "branches": {
                            "a": {
                                "nodes": [
                                    {"id": "n1", "label": "A", "gear_ref": "fx-gear"}
                                ]
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text("patchbays: {}\n", encoding="utf-8")

    monkeypatch.setattr("music_rig.store.QUESTIONS_PATH", questions)
    monkeypatch.setattr("music_rig.store.TODO_PATH", todo)
    monkeypatch.setattr("music_rig.store.WISHLIST_PATH", wish)
    monkeypatch.setattr("music_rig.store.INBOX_PATH", inbox)
    monkeypatch.setattr("music_rig.store.CHANGES_PATH", changes)
    monkeypatch.setattr("music_rig.store.CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr("music_rig.store.ROUTING_PATH", routing)
    monkeypatch.setattr("music_rig.store.PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr("music_rig.store.INVENTORY_PATH", inventory)
    monkeypatch.setattr("music_rig.channel_state.CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr("music_rig.routing_state.ROUTING_PATH", routing)

    # Never write production docs from fixture mutations
    from music_rig import render as render_mod
    from music_rig import question_service as qs_mod
    from music_rig import todo_service as ts_mod

    def _noop_render(**kwargs):
        return False, []

    monkeypatch.setattr(render_mod, "render_docs", _noop_render)
    monkeypatch.setattr(qs_mod, "render_docs", _noop_render)
    monkeypatch.setattr(ts_mod, "render_docs", _noop_render)
    monkeypatch.setattr(
        "music_rig.reconciliation.service._render_planning_and_patchbay",
        lambda *a, **k: None,
    )

    return {
        "questions": questions,
        "todo": todo,
        "channels": channels,
        "routing": routing,
        "tmp": tmp_path,
    }


def test_answer_state_derivation_rules(fx19):
    q = question_service.get_question("Q-191")
    assert question_service.derive_answer_state(q) == AnswerState.UNANSWERED
    assert question_service.lifecycle_label(q) == "OPEN/UNANSWERED"

    draft = question_service.draft_question(
        "Q-191", "provisional", render=False, clock=_clock
    )
    assert draft["answer_state"] == "DRAFT"
    assert draft["question_status"] == "OPEN"
    assert draft["resolved_at"] is None
    assert draft["reconciled_at"] is None
    q = question_service.get_question("Q-191")
    assert question_service.derive_answer_state(q) == AnswerState.DRAFT
    assert question_service.lifecycle_label(q) == "OPEN/DRAFT"

    fin = question_service.answer_question(
        "Q-191", "final text", render=False, clock=_clock
    )
    assert fin["answer_state"] == "FINAL"
    assert fin["question_status"] == "RESOLVED"
    assert fin["resolved_at"] is not None
    assert fin["reconciled_at"] is None
    q = question_service.get_question("Q-191")
    assert question_service.derive_answer_state(q) == AnswerState.FINAL
    assert question_service.lifecycle_label(q) == "RESOLVED/UNRECONCILED"
    assert q.verification_result is None


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


def test_verification_result_null_on_answer_alone(fx19):
    question_service.answer_question("Q-190", "A→Alesis2 B→Alesis1", render=False)
    q = question_service.get_question("Q-190")
    assert q.verification_result is None
    assert q.status == QuestionStatus.RESOLVED


def test_draft_not_unqualified_needs_answer(fx19):
    question_service.draft_question("Q-190", "draft destinations", render=False)
    st = reconcile_service.question_state(question_service.get_question("Q-190"))
    assert st == ReconciliationState.DRAFT_ANSWER
    plan = reconcile_service.plan_question("Q-190")
    assert plan.state == ReconciliationState.DRAFT_ANSWER
    assert any("resolve" in c for c in plan.suggested_commands)
    sweep = reconcile_service.sweep(dry_run=True, yes=True)
    assert sweep["counts"]["draft_answer"] >= 1
    assert "Q-190" not in (sweep.get("would_finalize") or [])


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


def test_channel_set_source_status_current(fx19):
    preview, data = propose_set_source("alesis", 1, "B send", path=fx19["channels"])
    assert preview.after["source"] == "B send"
    assert preview.after["status"] == "CURRENT"
    assert validate_channel_map(data) == []


def test_channel_clear_source_unassigned(fx19):
    _, data = propose_set_source("alesis", 1, "B send", path=fx19["channels"])
    channel_state.save_raw(data, path=fx19["channels"])
    preview, data2 = channel_state.clear_source("alesis", 1, path=fx19["channels"])
    assert preview.after["source"] is None
    assert preview.after["status"] == "UNASSIGNED"
    assert validate_channel_map(data2) == []


def test_channel_contradiction_fails_validate_and_cleanup(fx19):
    bad = {
        "tascam": {1: {"type": "line", "status": "UNASSIGNED", "source": "leak"}},
        "alesis": {1: {"status": "CURRENT", "source": None}},
    }
    errs = validate_channel_map(bad)
    assert any("source/status" in e for e in errs)
    fx19["channels"].write_text(yaml.safe_dump(bad), encoding="utf-8")
    issues = reconcile_service.cleanup_reconciliation_issues(
        questions_path=fx19["questions"],
        todo_path=fx19["todo"],
    )
    codes = {i["code"] for i in issues}
    assert "channel_source_status_contradiction" in codes


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


@pytest.mark.asyncio
async def test_tui_save_draft(fx19):
    app_ui = RigApp(route="question", object_id="Q-191")
    async with app_ui.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app_ui.screen, AnswerScreen)
        await pilot.press(*list("draft-from-tui"))
        await pilot.press("ctrl+s")
        await pilot.pause()
    q = load_questions(fx19["questions"]).question_map()["Q-191"]
    assert q.answer == "draft-from-tui"
    assert q.status == QuestionStatus.OPEN
    assert q.resolved_at is None
    assert q.verification_result is None


@pytest.mark.asyncio
async def test_tui_answer_and_resolve(fx19):
    app_ui = RigApp(route="question", object_id="Q-191")
    async with app_ui.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.press(*list("final-from-tui"))
        await pilot.click("#btn-resolve")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    q = load_questions(fx19["questions"]).question_map()["Q-191"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "final-from-tui"
    assert q.resolved_at is not None
    assert q.reconciled_at is None
    assert q.verification_result is None


def test_skills_mentions_live_data_and_blocking_bug():
    text = Path("SKILLS.md").read_text(encoding="utf-8")
    assert "Live Rig Data Changes During Development" in text
    assert "Blocking code bug during reconciliation workflow" in text
    assert "Do not ask redundant" in text
    assert "confirm-current-reconciled" in text
    assert "question draft" in text
