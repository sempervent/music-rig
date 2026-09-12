"""TODO editable adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig import store as store_mod
from music_rig import todo_service
from music_rig.models import TodoPriority, TodoStatus
from music_rig.store import StoreError, load_todo
from music_rig.tui.editable import ApplyResult, BaseEditableAdapter, WorkingRecord
from music_rig.tui.fields import FieldSpec, FieldType, enum_spec, readonly_spec, text_spec

TODO_FIELDS: list[FieldSpec] = [
    readonly_spec("id", "ID"),
    text_spec("task", "Task", required=True, multiline=True),
    text_spec("area", "Area", required=True),
    enum_spec("priority", "Priority", [p.value for p in TodoPriority]),
    enum_spec("status", "Status", [s.value for s in TodoStatus]),
    text_spec("definition_of_done", "Definition of done", required=True, multiline=True),
    text_spec("notes", "Notes", multiline=True),
    FieldSpec(
        name="depends_on",
        label="Depends on",
        type=FieldType.REF_LIST,
        ref_domain="todo",
    ),
    text_spec("waiting_on", "Waiting on"),
    text_spec("next_session_why", "Next session why"),
    FieldSpec(
        name="in_next_session",
        label="In Next Session",
        type=FieldType.BOOL,
        help="Max 3 tasks in Next Session",
    ),
]


class TodoEditableAdapter(BaseEditableAdapter):
    id = "todo"
    label = "TODO"

    def columns(self) -> list[str]:
        return ["ID", "Pri", "Status", "Next", "Task"]

    def filter_cycle(self) -> tuple[str, ...] | None:
        return ("ACTIVE", "DONE", "ALL")

    def source_path(self) -> Path | None:
        return store_mod.TODO_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return list(TODO_FIELDS)

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        doc = load_todo()
        needle = search.casefold()
        rows = []
        for t in doc.tasks:
            if status_filter == "ACTIVE" and t.status in {TodoStatus.DONE, TodoStatus.CANCELLED}:
                continue
            if status_filter == "DONE" and t.status != TodoStatus.DONE:
                continue
            blob = f"{t.id} {t.task} {t.area} {t.status.value}"
            if needle and needle not in blob.casefold():
                continue
            mark = "★" if t.id in doc.next_session else ""
            rows.append(
                {
                    "id": t.id,
                    "cells": [t.id, t.priority.value, t.status.value, mark, t.task[:50]],
                    "search_text": blob,
                }
            )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        doc = load_todo()
        t = todo_service.get_task(doc, record_id)
        return {
            "id": t.id,
            "task": t.task,
            "area": t.area,
            "priority": t.priority.value,
            "status": t.status.value,
            "definition_of_done": t.definition_of_done,
            "notes": t.notes,
            "depends_on": list(t.depends_on),
            "waiting_on": t.waiting_on or "",
            "next_session_why": t.next_session_why or "",
            "in_next_session": t.id in doc.next_session,
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        lines = [
            f"# {r['id']}",
            "",
            r["task"],
            "",
            f"Area: {r['area']}",
            f"Priority: {r['priority']}",
            f"Status: {r['status']}",
            f"Next Session: {'yes' if r['in_next_session'] else 'no'}",
            f"DoD: {r['definition_of_done']}",
            f"Notes: {r['notes'] or '—'}",
            f"Depends: {', '.join(r['depends_on']) or '—'}",
            "",
            "## Linked reconciliation",
            "",
        ]
        try:
            from music_rig.reconciliation.service import question_state
            from music_rig.store import load_changes, load_questions

            qdoc = load_questions()
            cdoc = load_changes()
            linked = False
            for q in qdoc.questions:
                if record_id not in q.related_todos:
                    continue
                linked = True
                st = question_state(q)
                rec = q.reconciled_at.isoformat() if q.reconciled_at is not None else "—"
                lines.append(f"- {q.id}: recon_state={st.value} reconciled_at={rec}")
                for cid in q.related_changes:
                    chg = cdoc.item_map().get(cid)
                    chg_st = chg.status.value if chg else "?"
                    lines.append(f"  - change {cid}: {chg_st}")
            if not linked:
                lines.append("_no linked questions_")
        except Exception as exc:
            lines.append(f"_unavailable: {exc}_")
        return "\n".join(lines)

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        return [
            ("start", "s", "Start"),
            ("ready", "y", "Ready"),
            ("done", "d", "Done"),
            ("block", "b", "Block"),
            ("cancel", "x", "Cancel"),
        ]

    def run_semantic(
        self, action_id: str, record_id: str, *, payload: dict[str, Any] | None = None
    ) -> ApplyResult:
        mapping = {
            "start": TodoStatus.IN_PROGRESS,
            "ready": TodoStatus.READY,
            "done": TodoStatus.DONE,
            "block": TodoStatus.BLOCKED,
            "cancel": TodoStatus.CANCELLED,
        }
        if action_id not in mapping:
            raise StoreError(f"Unknown action {action_id}")
        status = mapping[action_id]
        task, _changed, _doc = todo_service.set_todo_status(
            record_id,
            status,
            remove_from_next=status in {TodoStatus.DONE, TodoStatus.CANCELLED},
            render=True,
        )
        hidden = status in {TodoStatus.DONE, TodoStatus.CANCELLED}
        return ApplyResult(
            record_id=task.id,
            message=f"{task.id} -> {status.value}",
            hidden_by_filter=hidden,
            filter_hint="Hidden because filter=ACTIVE. Press f for DONE/ALL." if hidden else "",
        )

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        m = working.mutations
        kwargs: dict[str, Any] = {"render": render}
        for key in (
            "task",
            "area",
            "priority",
            "status",
            "definition_of_done",
            "notes",
            "depends_on",
            "waiting_on",
            "next_session_why",
        ):
            if key in m:
                kwargs[key] = m[key]
        if len(kwargs) > 1:
            updated = todo_service.update_todo_fields(working.record_id, **kwargs)
        else:
            updated = todo_service.get_task(load_todo(), working.record_id)

        if "in_next_session" in m:
            doc = load_todo()
            in_next = updated.id in doc.next_session
            want = bool(m["in_next_session"])
            if want and not in_next:
                todo_service.next_add(updated.id, render=render)
            elif not want and in_next:
                todo_service.next_remove(updated.id, render=render)

        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=updated.id, message=f"{updated.id} saved")
