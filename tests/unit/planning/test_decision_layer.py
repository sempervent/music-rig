from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from music_rig import change_service, question_service, session_service
from music_rig.models import (
    ChangeCategory,
    NowKind,
    QuestionStatus,
    TodoDocument,
    TodoPriority,
    TodoStatus,
    TodoTask,
)
from music_rig.now_service import format_now, recommend_now
from music_rig.reconcile import (
    build_reconcile_summary,
    format_reconcile_change,
    format_reconcile_question,
    likely_files_for_category,
    reconciliation_advisories,
)
from music_rig.render import check_render_sync, render_docs, render_questions_section
from music_rig.store import (
    StoreError,
    load_changes,
    load_questions,
    load_todo,
    save_todo,
)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now


@pytest.fixture
def decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    changes = tmp_path / "changes.yaml"
    changes.write_text("items: []\n", encoding="utf-8")
    inbox = tmp_path / "inbox.yaml"
    inbox.write_text("items: []\n", encoding="utf-8")
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    wish.write_text("items: []\n", encoding="utf-8")
    docs_todo = tmp_path / "todo.md"
    docs_wish = tmp_path / "wishlist.md"
    docs_q = tmp_path / "open-questions.md"
    for path, start, end in [
        (docs_todo, "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        (docs_wish, "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        (docs_q, "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
    ]:
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")

    todo_doc = TodoDocument.model_validate(
        {
            "next_session": ["RIG-010", "RIG-020"],
            "tasks": [
                {
                    "id": "RIG-010",
                    "task": "Next first",
                    "area": "Docs",
                    "priority": "P1",
                    "status": "READY",
                    "depends_on": [],
                    "definition_of_done": "done-10",
                    "notes": "",
                },
                {
                    "id": "RIG-020",
                    "task": "Next second",
                    "area": "Docs",
                    "priority": "P0",
                    "status": "READY",
                    "depends_on": [],
                    "definition_of_done": "done-20",
                    "notes": "",
                },
                {
                    "id": "RIG-001",
                    "task": "Ready P0 early",
                    "area": "Docs",
                    "priority": "P0",
                    "status": "READY",
                    "depends_on": [],
                    "definition_of_done": "done-1",
                    "notes": "",
                },
                {
                    "id": "RIG-002",
                    "task": "Blocked",
                    "area": "Docs",
                    "priority": "P0",
                    "status": "BLOCKED",
                    "depends_on": [],
                    "definition_of_done": "x",
                    "notes": "",
                },
                {
                    "id": "RIG-003",
                    "task": "Waiting",
                    "area": "Docs",
                    "priority": "P0",
                    "status": "WAITING",
                    "depends_on": [],
                    "definition_of_done": "x",
                    "notes": "",
                    "waiting_on": "parts",
                },
                {
                    "id": "RIG-004",
                    "task": "Deferred",
                    "area": "Docs",
                    "priority": "P0",
                    "status": "DEFERRED",
                    "depends_on": [],
                    "definition_of_done": "x",
                    "notes": "",
                },
            ],
        }
    )
    save_todo(todo_doc, todo)
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "What mode is PB-B 1/25?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": ["RIG-010"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from music_rig import store

    monkeypatch.setattr(store, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs_todo)
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs_wish)
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs_q)

    render_docs(
        todo_path=todo,
        wishlist_path=wish,
        questions_path=questions,
        docs_todo=docs_todo,
        docs_wishlist=docs_wish,
        docs_questions=docs_q,
        write=True,
    )

    return {
        "sessions": sessions,
        "changes": changes,
        "questions": questions,
        "todo": todo,
        "wish": wish,
        "inbox": inbox,
        "docs_todo": docs_todo,
        "docs_wish": docs_wish,
        "docs_q": docs_q,
        "clock": FakeClock(datetime(2026, 9, 10, 22, 0, 0, tzinfo=UTC)),
    }


def test_production_questions_migrated():
    doc = load_questions()
    assert len(doc.questions) == 20
    assert doc.questions[0].id == "Q-001"
    assert doc.questions[-1].id == "Q-020"
    todo = load_todo()
    known = todo.task_map()
    for q in doc.questions:
        for tid in q.related_todos:
            assert tid in known
    section = render_questions_section(doc)
    assert "Q-001" in section
    assert check_render_sync() == []


def test_question_lifecycle(decision):
    q = question_service.add_question(
        "Which supply powers RE-2?",
        area="Pedals / power",
        related_todos=["RIG-001"],
        notes="fixture",
        render=False,
        questions_path=decision["questions"],
        todo_path=decision["todo"],
    )
    assert q.id == "Q-002"
    open_items = question_service.list_questions(questions_path=decision["questions"])
    assert any(i.id == "Q-002" for i in open_items)

    resolved = question_service.resolve_question(
        "Q-002",
        "Isolated brick A",
        clock=decision["clock"],
        render=False,
        questions_path=decision["questions"],
        changes_path=decision["changes"],
    )
    assert resolved.status == QuestionStatus.RESOLVED
    assert resolved.answer == "Isolated brick A"

    with pytest.raises(StoreError):
        question_service.resolve_question(
            "Q-001",
            "   ",
            render=False,
            questions_path=decision["questions"],
        )

    deferred = question_service.defer_question(
        "Q-001", render=False, questions_path=decision["questions"]
    )
    assert deferred.status == QuestionStatus.DEFERRED

    reopened = question_service.reopen_question(
        "Q-002", render=False, questions_path=decision["questions"]
    )
    assert reopened.status == QuestionStatus.OPEN
    assert reopened.resolved_at is None
    assert "Prior answer" in reopened.notes


def test_question_todo_and_links(decision):
    task = TodoTask(
        id="RIG-099",
        task="Inspect PB-C",
        area="Patchbay",
        priority=TodoPriority.P1,
        status=TodoStatus.READY,
        depends_on=[],
        definition_of_done="documented",
        notes="",
    )
    q, created = question_service.create_todo_for_question(
        "Q-001",
        task,
        render=False,
        questions_path=decision["questions"],
        todo_path=decision["todo"],
    )
    assert created.id == "RIG-099"
    assert "RIG-099" in q.related_todos
    assert load_todo(decision["todo"]).task_map()["RIG-099"].task == "Inspect PB-C"

    with pytest.raises(StoreError, match="already linked"):
        question_service.link_todo(
            "Q-001",
            "RIG-010",
            render=False,
            questions_path=decision["questions"],
            todo_path=decision["todo"],
        )

    chg = change_service.create_change(
        "PB-B 1/25 looks half-normal",
        category=ChangeCategory.PATCHBAY,
        changes_path=decision["changes"],
        sessions_dir=decision["sessions"],
        link_session=False,
    )
    linked = question_service.link_change(
        "Q-001",
        chg.id,
        render=False,
        questions_path=decision["questions"],
        changes_path=decision["changes"],
    )
    assert chg.id in linked.related_changes
    assert "Q-001" in load_changes(decision["changes"]).item_map()[chg.id].related_questions

    with pytest.raises(StoreError, match="already linked"):
        question_service.link_change(
            "Q-001",
            chg.id,
            render=False,
            questions_path=decision["questions"],
            changes_path=decision["changes"],
        )


def test_failed_link_does_not_partial_write(decision, monkeypatch):
    chg = change_service.create_change(
        "x",
        category=ChangeCategory.OTHER,
        changes_path=decision["changes"],
        link_session=False,
    )
    before_q = decision["questions"].read_text(encoding="utf-8")
    before_c = decision["changes"].read_text(encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("nope")

    monkeypatch.setattr("music_rig.question_service.write_documents", boom)
    with pytest.raises(OSError):
        question_service.link_change(
            "Q-001",
            chg.id,
            render=False,
            questions_path=decision["questions"],
            changes_path=decision["changes"],
        )
    assert decision["questions"].read_text(encoding="utf-8") == before_q
    assert decision["changes"].read_text(encoding="utf-8") == before_c


def test_now_hierarchy(decision):
    # Next Session wins over higher-priority READY outside queue
    rec = recommend_now(todo_path=decision["todo"], sessions_dir=decision["sessions"])
    assert rec.kind == NowKind.NEXT_SESSION
    assert rec.primary_reference == "RIG-010"
    assert "Next Session" in rec.reason

    # IN PROGRESS wins when no active session
    from music_rig.todo_service import set_todo_status

    set_todo_status(
        "RIG-001",
        TodoStatus.IN_PROGRESS,
        render=False,
        todo_path=decision["todo"],
    )
    rec2 = recommend_now(todo_path=decision["todo"], sessions_dir=decision["sessions"])
    assert rec2.kind == NowKind.IN_PROGRESS
    assert rec2.primary_reference == "RIG-001"

    # Active session wins over everything
    session_service.start_session(
        "Just play", clock=decision["clock"], sessions_dir=decision["sessions"]
    )
    rec3 = recommend_now(
        todo_path=decision["todo"],
        sessions_dir=decision["sessions"],
        clock=decision["clock"],
    )
    assert rec3.kind == NowKind.ACTIVE_SESSION
    assert "SES-" in rec3.primary_reference

    play = recommend_now(play=True)
    assert play.kind == NowKind.PLAY
    assert "Just play" in play.suggested_commands[0]
    text = format_now(play)
    assert text.startswith("PLAY")


def test_now_ready_fallback_and_skips(decision):
    # Clear next session and in progress
    doc = load_todo(decision["todo"])
    new_tasks = []
    for t in doc.tasks:
        data = t.model_dump()
        if t.status == TodoStatus.IN_PROGRESS:
            data["status"] = TodoStatus.READY
        new_tasks.append(TodoTask.model_validate(data))
    save_todo(TodoDocument(next_session=[], tasks=new_tasks), decision["todo"])
    rec = recommend_now(todo_path=decision["todo"], sessions_dir=decision["sessions"])
    assert rec.kind == NowKind.READY
    assert rec.primary_reference == "RIG-020"  # P0, first in YAML among P0 READY
    assert "BLOCKED" in " ".join(rec.skipped_summary)
    assert "WAITING" in " ".join(rec.skipped_summary)
    assert "DEFERRED" in " ".join(rec.skipped_summary)
    text = format_now(rec, extra_why=True)
    assert "Why:" in text
    assert "Skipped:" in text


def test_now_no_action_play(decision):
    # Terminal-only tasks
    save_todo(
        TodoDocument(
            next_session=[],
            tasks=[
                TodoTask(
                    id="RIG-001",
                    task="done",
                    area="x",
                    priority=TodoPriority.P0,
                    status=TodoStatus.DONE,
                    depends_on=[],
                    definition_of_done="x",
                )
            ],
        ),
        decision["todo"],
    )
    rec = recommend_now(todo_path=decision["todo"], sessions_dir=decision["sessions"])
    assert rec.kind == NowKind.PLAY


def test_reconcile(decision):
    chg = change_service.create_change(
        "Moved TR-2",
        category=ChangeCategory.PEDAL_CHAIN,
        changes_path=decision["changes"],
        link_session=False,
    )
    summary = build_reconcile_summary(
        changes_path=decision["changes"],
        questions_path=decision["questions"],
        inbox_path=decision["inbox"],
    )
    assert "Open Changes:   1" in summary
    assert "Open Questions: 1" in summary
    detail = format_reconcile_change(
        chg.id,
        changes_path=decision["changes"],
        questions_path=decision["questions"],
        todo_path=decision["todo"],
    )
    assert "docs/pedal-chains.md" in detail
    assert "NOT been automatically modified" in detail
    qdetail = format_reconcile_question("Q-001", questions_path=decision["questions"])
    assert "PB-B" in qdetail
    assert "rig question resolve" in qdetail
    assert "data/patchbays.yaml" in "\n".join(likely_files_for_category(ChangeCategory.PATCHBAY))
    assert ChangeCategory.OTHER in ChangeCategory

    # resolved question + open change advisory
    question_service.link_change(
        "Q-001",
        chg.id,
        render=False,
        questions_path=decision["questions"],
        changes_path=decision["changes"],
    )
    question_service.resolve_question(
        "Q-001",
        "half-normal",
        clock=decision["clock"],
        render=False,
        questions_path=decision["questions"],
        changes_path=decision["changes"],
    )
    advisories = reconciliation_advisories(
        changes_path=decision["changes"],
        questions_path=decision["questions"],
        todo_path=decision["todo"],
    )
    assert any("RESOLVED question" in a for a in advisories)

    # done TODO + open question
    q2 = question_service.add_question(
        "Another?",
        area="Routing",
        related_todos=["RIG-010"],
        render=False,
        questions_path=decision["questions"],
        todo_path=decision["todo"],
    )
    from music_rig.todo_service import set_todo_status

    set_todo_status(
        "RIG-010",
        TodoStatus.DONE,
        remove_from_next=True,
        render=False,
        todo_path=decision["todo"],
    )
    advisories2 = reconciliation_advisories(
        changes_path=decision["changes"],
        questions_path=decision["questions"],
        todo_path=decision["todo"],
    )
    assert any("DONE TODO" in a for a in advisories2)
    # reconcile does not modify CURRENT routing files — fixture paths only
    assert q2.status == QuestionStatus.OPEN
