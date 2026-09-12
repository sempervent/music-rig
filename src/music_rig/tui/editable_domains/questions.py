"""Questions editable-domain adapter (FieldSpecs + question_service)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig import question_service
from music_rig.models import QuestionStatus
from music_rig import store as store_mod
from music_rig.store import StoreError, load_questions
from music_rig.tui.adapters.questions import filter_questions, question_detail_markdown
from music_rig.tui.editable import ApplyResult, BaseEditableAdapter, WorkingRecord
from music_rig.tui.fields import (
    FieldSpec,
    FieldType,
    enum_spec,
    readonly_spec,
    ref_list_spec,
    text_spec,
)
from music_rig.tui.working import ConcurrentModificationError


QUESTION_FIELDS: list[FieldSpec] = [
    readonly_spec("id", "ID"),
    text_spec("question", "Question", required=True, multiline=True),
    text_spec("area", "Area", required=True),
    enum_spec(
        "status",
        "Status",
        [s.value for s in QuestionStatus],
        help="Prefer r/d/o semantic actions; editing status here requires answer/resolved_at rules.",
    ),
    text_spec("answer", "Answer", multiline=True),
    text_spec("notes", "Notes", multiline=True),
    ref_list_spec("related_todos", "Related TODOs", "todo"),
    ref_list_spec("related_changes", "Related Changes", "changes"),
    FieldSpec(
        name="target",
        label="Typed target",
        type=FieldType.NESTED,
        help="domain + optional bay/pair/device/channel/path/branch/node/gear/context",
        nested_fields=(
            FieldSpec(name="domain", label="Domain", type=FieldType.TEXT, required=True),
            FieldSpec(name="bay", label="Bay", type=FieldType.TEXT),
            FieldSpec(name="pair", label="Pair", type=FieldType.TEXT),
            FieldSpec(name="device", label="Device", type=FieldType.TEXT),
            FieldSpec(name="channel", label="Channel", type=FieldType.TEXT),
            FieldSpec(name="path", label="Path", type=FieldType.TEXT),
            FieldSpec(name="branch", label="Branch", type=FieldType.TEXT),
            FieldSpec(name="node", label="Node", type=FieldType.TEXT),
            FieldSpec(name="gear", label="Gear", type=FieldType.TEXT),
            FieldSpec(name="context", label="Context", type=FieldType.TEXT),
        ),
    ),
    FieldSpec(name="resolved_at", label="Resolved at", type=FieldType.TIMESTAMP, read_only=True),
    FieldSpec(
        name="reconciled_at",
        label="Reconciled at",
        type=FieldType.TIMESTAMP,
        read_only=True,
        help="Set by rig reconcile finalize — not by resolve",
    ),
    text_spec(
        "reconciliation_note",
        "Reconciliation note",
        multiline=True,
        help="Required when finalizing with --no-current-change",
    ),
]


class QuestionsEditableAdapter(BaseEditableAdapter):
    id = "question"
    label = "Questions"

    def columns(self) -> list[str]:
        return ["ID", "Status", "Area", "Question"]

    def filter_cycle(self) -> tuple[str, ...] | None:
        return ("OPEN", "RESOLVED", "DEFERRED", "ALL")

    def source_path(self) -> Path | None:
        return store_mod.QUESTIONS_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return list(QUESTION_FIELDS)

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        items = filter_questions(
            list(load_questions().questions),
            status_filter or "ALL",
            search,
        )
        return [
            {
                "id": q.id,
                "cells": [q.id, q.status.value, q.area, q.question[:48]],
                "search_text": f"{q.id} {q.question} {q.area} {q.answer} {q.notes}",
            }
            for q in items
        ]

    def get_record(self, record_id: str) -> dict[str, Any]:
        q = question_service.get_question(record_id)
        target = None
        if q.target is not None:
            target = {k: v for k, v in q.target.model_dump().items() if v is not None}
        return {
            "id": q.id,
            "question": q.question,
            "area": q.area,
            "status": q.status.value,
            "answer": q.answer,
            "notes": q.notes,
            "related_todos": list(q.related_todos),
            "related_changes": list(q.related_changes),
            "target": target,
            "resolved_at": q.resolved_at.isoformat() if q.resolved_at else None,
            "reconciled_at": q.reconciled_at.isoformat() if q.reconciled_at else None,
            "reconciliation_note": q.reconciliation_note,
        }

    def detail_markdown(self, record_id: str) -> str:
        return question_detail_markdown(question_service.get_question(record_id))

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        return [
            ("resolve", "r", "Resolve"),
            ("defer", "d", "Defer"),
            ("reopen", "o", "Reopen"),
        ]

    def run_semantic(
        self,
        action_id: str,
        record_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> ApplyResult:
        payload = payload or {}
        if action_id == "resolve":
            answer = str(payload.get("answer") or "").strip()
            if not answer:
                raise StoreError("Resolved questions require a non-empty answer.")
            updated = question_service.resolve_question(record_id, answer, render=True)
            return ApplyResult(
                record_id=updated.id,
                message=f"{updated.id} resolved.",
                hidden_by_filter=True,
                filter_hint="Hidden because filter=OPEN. Press f for RESOLVED/ALL.",
            )
        if action_id == "defer":
            updated = question_service.defer_question(record_id, render=True)
            return ApplyResult(record_id=updated.id, message=f"{updated.id} -> DEFERRED")
        if action_id == "reopen":
            updated = question_service.reopen_question(record_id, render=True)
            return ApplyResult(record_id=updated.id, message=f"{updated.id} -> OPEN")
        raise StoreError(f"Unknown action {action_id}")

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        merged = working.merged()
        # Status transitions via dedicated services when status mutates
        baseline_status = working.baseline.get("status")
        new_status = merged.get("status")
        if new_status != baseline_status:
            if new_status == QuestionStatus.RESOLVED.value:
                question_service.resolve_question(
                    working.record_id,
                    str(merged.get("answer") or ""),
                    render=render,
                )
            elif new_status == QuestionStatus.DEFERRED.value:
                question_service.defer_question(working.record_id, render=render)
            elif new_status == QuestionStatus.OPEN.value:
                question_service.reopen_question(working.record_id, render=render)
            else:
                raise StoreError(f"Unsupported status {new_status}")
            # Refresh baseline for remaining field patches after lifecycle
            working.refresh_source_hash()
            current = self.get_record(working.record_id)
            working.baseline = current
            # Drop status from remaining mutations; keep other staged fields
            working.mutations.pop("status", None)
            working.mutations.pop("resolved_at", None)

        kwargs: dict[str, Any] = {"render": render}
        for key in ("question", "area", "notes", "answer", "related_todos", "related_changes"):
            if key in working.mutations:
                kwargs[key] = working.mutations[key]
        if "target" in working.mutations:
            tgt = working.mutations["target"]
            if tgt is None or tgt == {}:
                kwargs["clear_target"] = True
            else:
                kwargs["target"] = tgt
        if len(kwargs) > 1:  # more than just render
            try:
                updated = question_service.update_question_fields(working.record_id, **kwargs)
            except ConcurrentModificationError:
                raise
        else:
            updated = question_service.get_question(working.record_id)
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(
            record_id=updated.id,
            message=f"{updated.id} saved",
        )
