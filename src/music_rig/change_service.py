"""Structured physical/logical change capture (not automatic CURRENT updates)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from music_rig.inbox_service import default_clock
from music_rig.models import (
    ChangeCategory,
    ChangeRecord,
    ChangeStatus,
    ChangesDocument,
)
from music_rig import session_service
from music_rig.store import StoreError, load_changes, save_changes, write_documents

Clock = Callable[[], datetime]


def get_change(chg_id: str, *, changes_path: Path | None = None) -> ChangeRecord:
    doc = load_changes(changes_path)
    key = chg_id.strip().upper()
    item = doc.item_map().get(key)
    if item is None:
        raise StoreError(f"Change {key} does not exist.")
    return item


def create_change(
    summary: str,
    *,
    category: ChangeCategory,
    details: str = "",
    affected_areas: list[str] | None = None,
    clock: Clock = default_clock,
    changes_path: Path | None = None,
    sessions_dir: Path | None = None,
    link_session: bool = True,
) -> ChangeRecord:
    cleaned = summary.strip()
    if not cleaned:
        raise StoreError("Change summary cannot be empty.")
    doc = load_changes(changes_path)
    active = session_service.find_active(sessions_dir) if link_session else None
    record = ChangeRecord(
        id=doc.next_id(),
        created_at=clock(),
        category=category,
        summary=cleaned,
        details=details.strip(),
        status=ChangeStatus.OPEN,
        session_id=active.id if active else None,
        affected_areas=[a.strip() for a in (affected_areas or []) if a.strip()],
    )
    new_doc = ChangesDocument(items=[*doc.items, record])
    # Validate before write; use write_documents for atomicity with schema check
    try:
        write_documents(changes=new_doc, changes_path=changes_path)
    except Exception as exc:
        raise StoreError(f"Failed to write changes: {exc}") from exc
    if active is not None:
        session_service.link_change(
            record.id,
            cleaned,
            clock=clock,
            sessions_dir=sessions_dir,
        )
    return record


def list_changes(
    *,
    all_items: bool = False,
    changes_path: Path | None = None,
) -> list[ChangeRecord]:
    doc = load_changes(changes_path)
    if all_items:
        return list(doc.items)
    return [item for item in doc.items if item.status == ChangeStatus.OPEN]


def set_change_status(
    chg_id: str,
    status: ChangeStatus,
    *,
    changes_path: Path | None = None,
) -> tuple[ChangeRecord, bool]:
    doc = load_changes(changes_path)
    key = chg_id.strip().upper()
    items: list[ChangeRecord] = []
    found: ChangeRecord | None = None
    changed = False
    for item in doc.items:
        if item.id == key:
            if item.status == status:
                found = item
                items.append(item)
            else:
                updated = ChangeRecord(
                    id=item.id,
                    created_at=item.created_at,
                    category=item.category,
                    summary=item.summary,
                    details=item.details,
                    status=status,
                    session_id=item.session_id,
                    affected_areas=list(item.affected_areas),
                    related_questions=list(item.related_questions),
                )
                found = updated
                changed = True
                items.append(updated)
        else:
            items.append(item)
    if found is None:
        raise StoreError(f"Change {key} does not exist.")
    if changed:
        save_changes(ChangesDocument(items=items), changes_path)
    return found, changed


def open_change_count(*, changes_path: Path | None = None) -> int:
    return sum(1 for item in load_changes(changes_path).items if item.status == ChangeStatus.OPEN)


def parse_category(raw: str) -> ChangeCategory:
    cleaned = raw.strip().upper().replace(" ", "_").replace("-", "_")
    try:
        return ChangeCategory(cleaned)
    except ValueError as exc:
        names = ", ".join(c.value for c in ChangeCategory)
        raise StoreError(f"Invalid category {raw!r}. Use one of: {names}") from exc
