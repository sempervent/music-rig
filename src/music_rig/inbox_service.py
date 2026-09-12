"""Inbox capture helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from music_rig.models import (
    InboxDocument,
    InboxItem,
    InboxStatus,
    TodoDocument,
    TodoTask,
    WishlistDocument,
    WishlistItem,
)
from music_rig.render import render_docs
from music_rig.store import (
    StoreError,
    load_inbox,
    load_todo,
    load_wishlist,
    write_documents,
)

Clock = Callable[[], datetime]


def default_clock() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(UTC)


def capture_text(
    text: str,
    *,
    clock: Clock = default_clock,
    render: bool = False,
    inbox_path=None,
) -> InboxItem:
    cleaned = text.strip()
    if not cleaned:
        raise StoreError("Capture text cannot be empty.")
    doc = load_inbox(inbox_path)
    item = InboxItem(
        id=doc.next_id(),
        created_at=clock(),
        text=cleaned,
        status=InboxStatus.OPEN,
    )
    new_doc = InboxDocument(items=[*doc.items, item])
    write_documents(inbox=new_doc, inbox_path=inbox_path)
    return item


def get_capture(cap_id: str, *, inbox_path=None) -> InboxItem:
    doc = load_inbox(inbox_path)
    key = cap_id.strip().upper()
    item = doc.item_map().get(key)
    if item is None:
        raise StoreError(f"Capture {key} does not exist.")
    return item


def dismiss_capture(
    cap_id: str,
    *,
    inbox_path=None,
) -> tuple[InboxItem, bool]:
    doc = load_inbox(inbox_path)
    key = cap_id.strip().upper()
    items = []
    found = None
    changed = False
    for item in doc.items:
        if item.id == key:
            if item.status == InboxStatus.DISMISSED:
                found = item
                items.append(item)
            else:
                data = item.model_dump()
                data["status"] = InboxStatus.DISMISSED
                found = InboxItem.model_validate(data)
                items.append(found)
                changed = True
        else:
            items.append(item)
    if found is None:
        raise StoreError(f"Capture {key} does not exist.")
    if changed:
        write_documents(inbox=InboxDocument(items=items), inbox_path=inbox_path)
    return found, changed


def triage_to_todo(
    cap_id: str,
    new_task: TodoTask,
    *,
    render: bool = True,
    inbox_path=None,
    todo_path=None,
) -> tuple[InboxItem, TodoTask]:
    inbox = load_inbox(inbox_path)
    todo = load_todo(todo_path)
    key = cap_id.strip().upper()
    cap = inbox.item_map().get(key)
    if cap is None:
        raise StoreError(f"Capture {key} does not exist.")
    if new_task.id in todo.task_map():
        raise StoreError(f"TODO {new_task.id} already exists.")

    new_todo = TodoDocument(
        next_session=list(todo.next_session),
        tasks=[*todo.tasks, new_task],
    )
    items = []
    for item in inbox.items:
        if item.id == key:
            data = item.model_dump()
            data["status"] = InboxStatus.TRIAGED
            items.append(InboxItem.model_validate(data))
        else:
            items.append(item)
    new_inbox = InboxDocument(items=items)
    write_documents(
        todo=new_todo,
        inbox=new_inbox,
        todo_path=todo_path,
        inbox_path=inbox_path,
    )
    if render and todo_path is None:
        render_docs(write=True)
    return new_inbox.item_map()[key], new_task


def triage_to_wish(
    cap_id: str,
    new_item: WishlistItem,
    *,
    render: bool = True,
    inbox_path=None,
    wishlist_path=None,
) -> tuple[InboxItem, WishlistItem]:
    inbox = load_inbox(inbox_path)
    wish = load_wishlist(wishlist_path)
    key = cap_id.strip().upper()
    cap = inbox.item_map().get(key)
    if cap is None:
        raise StoreError(f"Capture {key} does not exist.")
    if wish.find(new_item.item) is not None:
        raise StoreError(f'Wishlist item "{new_item.item}" already exists.')

    new_wish = WishlistDocument(items=[*wish.items, new_item])
    items = []
    for item in inbox.items:
        if item.id == key:
            data = item.model_dump()
            data["status"] = InboxStatus.TRIAGED
            items.append(InboxItem.model_validate(data))
        else:
            items.append(item)
    new_inbox = InboxDocument(items=items)
    write_documents(
        wishlist=new_wish,
        inbox=new_inbox,
        wishlist_path=wishlist_path,
        inbox_path=inbox_path,
    )
    if render and wishlist_path is None:
        render_docs(write=True)
    return new_inbox.item_map()[key], new_item
