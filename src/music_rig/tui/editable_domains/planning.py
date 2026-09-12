"""Wishlist / Inbox / Changes editable adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig import change_service, inbox_service, wishlist_service
from music_rig.models import (
    ChangeCategory,
    ChangeStatus,
    InboxStatus,
    WishPriority,
    WishStatus,
)
from music_rig import store as store_mod
from music_rig.store import (
    StoreError,
    load_changes,
    load_inbox,
    load_wishlist,
    write_documents,
)
from music_rig.models import ChangesDocument, ChangeRecord, InboxDocument, InboxItem, WishlistDocument, WishlistItem
from music_rig.tui.editable import ApplyResult, BaseEditableAdapter, WorkingRecord
from music_rig.tui.fields import FieldSpec, FieldType, enum_spec, readonly_spec, text_spec


class WishlistEditableAdapter(BaseEditableAdapter):
    id = "wish"
    label = "Wishlist"

    def columns(self) -> list[str]:
        return ["Name", "Pri", "Status"]

    def filter_cycle(self) -> tuple[str, ...] | None:
        return ("ACTIVE", "ACQUIRED", "ALL")

    def source_path(self) -> Path | None:
        return store_mod.WISHLIST_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("item", "Item"),
            text_spec("category", "Category", required=True),
            text_spec("problem_capability", "Problem / capability", required=True, multiline=True),
            enum_spec("priority", "Priority", [p.value for p in WishPriority], required=False),
            enum_spec("status", "Status", [s.value for s in WishStatus]),
            text_spec("duplication", "Duplication"),
            text_spec("cost", "Cost"),
            text_spec("friction", "Friction"),
            text_spec("likely_music_impact", "Likely music impact", multiline=True),
            text_spec("notes", "Notes", multiline=True),
            text_spec("details", "Details", multiline=True),
            FieldSpec(name="todo_refs", label="TODO refs", type=FieldType.REF_LIST, ref_domain="todo"),
            text_spec("inventory_ref", "Inventory ref", help="Required when status=ACQUIRED"),
        ]

    def list_records(self, *, status_filter: str | None = None, search: str = "") -> list[dict[str, Any]]:
        needle = search.casefold()
        rows = []
        for w in load_wishlist().items:
            if status_filter == "ACTIVE" and w.status in {WishStatus.REJECTED, WishStatus.ACQUIRED}:
                continue
            if status_filter == "ACQUIRED" and w.status != WishStatus.ACQUIRED:
                continue
            blob = f"{w.item} {w.status.value} {w.notes}"
            if needle and needle not in blob.casefold():
                continue
            rows.append(
                {
                    "id": w.item,
                    "cells": [w.item[:40], w.priority.value if w.priority else "—", w.status.value],
                    "search_text": blob,
                }
            )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        w = wishlist_service.get_item(load_wishlist(), record_id)
        return {
            "item": w.item,
            "category": w.category,
            "problem_capability": w.problem_capability,
            "priority": w.priority.value if w.priority else None,
            "status": w.status.value,
            "duplication": w.duplication,
            "cost": w.cost,
            "friction": w.friction,
            "likely_music_impact": w.likely_music_impact,
            "notes": w.notes,
            "details": w.details,
            "todo_refs": list(w.todo_refs),
            "inventory_ref": w.inventory_ref or "",
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return "\n".join(
            [
                f"# {r['item']}",
                "",
                f"Status: {r['status']}",
                f"Priority: {r['priority'] or '—'}",
                f"Category: {r['category']}",
                f"Notes: {r['notes'] or '—'}",
                f"Inventory: {r['inventory_ref'] or '—'}",
            ]
        )

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        doc = load_wishlist()
        idx = doc.find_index(working.record_id)
        if idx is None:
            raise StoreError(f'Wishlist item "{working.record_id}" does not exist.')
        data = doc.items[idx].model_dump()
        data.update(working.mutations)
        if data.get("priority") in ("", None):
            data["priority"] = None
        if not data.get("inventory_ref"):
            data["inventory_ref"] = None
        if data.get("status") == WishStatus.ACQUIRED.value and not data.get("inventory_ref"):
            raise StoreError("ACQUIRED wishes require inventory_ref")
        updated = WishlistItem.model_validate(data)
        items = list(doc.items)
        items[idx] = updated
        write_documents(wishlist=WishlistDocument(items=items))
        if render:
            from music_rig.render import render_docs

            render_docs(write=True)
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=updated.item, message=f"{updated.item} saved")


class InboxEditableAdapter(BaseEditableAdapter):
    id = "inbox"
    label = "Inbox"

    def columns(self) -> list[str]:
        return ["ID", "Status", "Text"]

    def filter_cycle(self) -> tuple[str, ...] | None:
        return ("OPEN", "DISMISSED", "ALL")

    def source_path(self) -> Path | None:
        return store_mod.INBOX_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("id", "ID"),
            readonly_spec("created_at", "Created"),
            text_spec("text", "Text", required=True, multiline=True),
            enum_spec("status", "Status", [s.value for s in InboxStatus]),
            text_spec("category_hint", "Category hint"),
            text_spec("source", "Source"),
            text_spec("notes", "Notes", multiline=True),
        ]

    def list_records(self, *, status_filter: str | None = None, search: str = "") -> list[dict[str, Any]]:
        needle = search.casefold()
        rows = []
        for i in load_inbox().items:
            if status_filter == "OPEN" and i.status != InboxStatus.OPEN:
                continue
            if status_filter == "DISMISSED" and i.status != InboxStatus.DISMISSED:
                continue
            blob = f"{i.id} {i.text}"
            if needle and needle not in blob.casefold():
                continue
            rows.append(
                {
                    "id": i.id,
                    "cells": [i.id, i.status.value, i.text[:50]],
                    "search_text": blob,
                }
            )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        item = inbox_service.get_capture(record_id)
        return {
            "id": item.id,
            "created_at": item.created_at.isoformat(),
            "text": item.text,
            "status": item.status.value,
            "category_hint": item.category_hint or "",
            "source": item.source or "",
            "notes": item.notes,
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return f"# {r['id']}\n\n{r['text']}\n\nStatus: {r['status']}"

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        return [("dismiss", "x", "Dismiss")]

    def run_semantic(
        self, action_id: str, record_id: str, *, payload: dict[str, Any] | None = None
    ) -> ApplyResult:
        if action_id != "dismiss":
            raise StoreError(f"Unknown action {action_id}")
        item, _ = inbox_service.dismiss_capture(record_id)
        return ApplyResult(
            record_id=item.id,
            message=f"{item.id} dismissed.",
            hidden_by_filter=True,
            filter_hint="Hidden because filter=OPEN. Press f for DISMISSED/ALL.",
        )

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        doc = load_inbox()
        key = working.record_id.upper()
        items = []
        found = None
        for item in doc.items:
            if item.id == key:
                data = item.model_dump()
                data.update({k: v for k, v in working.mutations.items() if k != "created_at"})
                if not data.get("category_hint"):
                    data["category_hint"] = None
                if not data.get("source"):
                    data["source"] = None
                found = InboxItem.model_validate(data)
                items.append(found)
            else:
                items.append(item)
        if found is None:
            raise StoreError(f"Capture {key} does not exist.")
        write_documents(inbox=InboxDocument(items=items))
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=found.id, message=f"{found.id} saved")


class ChangesEditableAdapter(BaseEditableAdapter):
    id = "changes"
    label = "Changes"

    def columns(self) -> list[str]:
        return ["ID", "Status", "Category", "Summary"]

    def filter_cycle(self) -> tuple[str, ...] | None:
        return ("OPEN", "APPLIED", "ALL")

    def source_path(self) -> Path | None:
        return store_mod.CHANGES_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("id", "ID"),
            readonly_spec("created_at", "Created"),
            enum_spec("category", "Category", [c.value for c in ChangeCategory]),
            text_spec("summary", "Summary", required=True),
            text_spec("details", "Details", multiline=True),
            enum_spec("status", "Status", [s.value for s in ChangeStatus]),
            FieldSpec(
                name="affected_areas",
                label="Affected areas",
                type=FieldType.ORDERED_LIST,
            ),
            FieldSpec(
                name="related_questions",
                label="Related questions",
                type=FieldType.REF_LIST,
                ref_domain="question",
            ),
        ]

    def list_records(self, *, status_filter: str | None = None, search: str = "") -> list[dict[str, Any]]:
        needle = search.casefold()
        rows = []
        for c in load_changes().items:
            if status_filter == "OPEN" and c.status != ChangeStatus.OPEN:
                continue
            if status_filter == "APPLIED" and c.status != ChangeStatus.APPLIED:
                continue
            blob = f"{c.id} {c.summary} {c.category.value}"
            if needle and needle not in blob.casefold():
                continue
            rows.append(
                {
                    "id": c.id,
                    "cells": [c.id, c.status.value, c.category.value, c.summary[:40]],
                    "search_text": blob,
                }
            )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        item = change_service.get_change(record_id)
        return {
            "id": item.id,
            "created_at": item.created_at.isoformat(),
            "category": item.category.value,
            "summary": item.summary,
            "details": item.details,
            "status": item.status.value,
            "affected_areas": list(item.affected_areas),
            "related_questions": list(item.related_questions),
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return "\n".join(
            [
                f"# {r['id']}",
                "",
                r["summary"],
                "",
                f"Category: {r['category']}",
                f"Status: {r['status']}",
                f"Details: {r['details'] or '—'}",
            ]
        )

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        return [("apply", "p", "Mark Applied"), ("dismiss", "x", "Dismiss")]

    def run_semantic(
        self, action_id: str, record_id: str, *, payload: dict[str, Any] | None = None
    ) -> ApplyResult:
        if action_id == "apply":
            item, _ = change_service.set_change_status(record_id, ChangeStatus.APPLIED)
            return ApplyResult(
                record_id=item.id,
                message=f"{item.id} -> APPLIED",
                hidden_by_filter=True,
                filter_hint="Hidden because filter=OPEN. Press f for APPLIED/ALL.",
            )
        if action_id == "dismiss":
            item, _ = change_service.set_change_status(record_id, ChangeStatus.DISMISSED)
            return ApplyResult(record_id=item.id, message=f"{item.id} -> DISMISSED")
        raise StoreError(f"Unknown action {action_id}")

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        doc = load_changes()
        key = working.record_id.upper()
        items = []
        found = None
        for item in doc.items:
            if item.id == key:
                data = item.model_dump()
                data.update({k: v for k, v in working.mutations.items() if k != "created_at"})
                found = ChangeRecord.model_validate(data)
                items.append(found)
            else:
                items.append(item)
        if found is None:
            raise StoreError(f"Change {key} does not exist.")
        write_documents(changes=ChangesDocument(items=items))
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=found.id, message=f"{found.id} saved")
