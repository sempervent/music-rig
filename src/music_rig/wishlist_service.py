"""Wishlist mutation helpers."""

from __future__ import annotations

from music_rig.models import (
    TodoDocument,
    TodoTask,
    WishlistDocument,
    WishlistItem,
    WishStatus,
)
from music_rig.render import render_docs
from music_rig.store import StoreError, load_todo, load_wishlist, write_documents


def get_item(doc: WishlistDocument, name: str) -> WishlistItem:
    item = doc.find(name)
    if item is None:
        raise StoreError(f'Wishlist item "{name}" does not exist.')
    return item


def set_wish_status(
    name: str,
    status: WishStatus,
    *,
    render: bool = True,
    wishlist_path=None,
) -> tuple[WishlistItem, bool]:
    doc = load_wishlist(wishlist_path)
    idx = doc.find_index(name)
    if idx is None:
        raise StoreError(f'Wishlist item "{name}" does not exist.')
    item = doc.items[idx]
    if item.status == status:
        return item, False
    data = item.model_dump()
    data["status"] = status
    updated = WishlistItem.model_validate(data)
    items = list(doc.items)
    items[idx] = updated
    new_doc = WishlistDocument(items=items)
    write_documents(wishlist=new_doc, wishlist_path=wishlist_path)
    if render and wishlist_path is None:
        render_docs(write=True)
    return updated, True


def promote_wish(
    name: str,
    new_task: TodoTask,
    *,
    keep_wish_status: bool = True,
    new_wish_status: WishStatus | None = None,
    render: bool = True,
    todo_path=None,
    wishlist_path=None,
) -> tuple[WishlistItem, TodoTask]:
    todo_doc = load_todo(todo_path)
    wish_doc = load_wishlist(wishlist_path)
    idx = wish_doc.find_index(name)
    if idx is None:
        raise StoreError(f'Wishlist item "{name}" does not exist.')
    item = wish_doc.items[idx]

    # Ensure allocated ID matches document next_id if caller passed one already set
    if new_task.id != todo_doc.next_id():
        # Allow explicit ID only if unused; otherwise force next
        if new_task.id in todo_doc.task_map():
            raise StoreError(f"TODO {new_task.id} already exists.")
    new_todo_doc = TodoDocument(
        next_session=list(todo_doc.next_session),
        tasks=[*todo_doc.tasks, new_task],
    )

    data = item.model_dump()
    refs = list(data.get("todo_refs") or [])
    if new_task.id not in refs:
        refs.append(new_task.id)
    data["todo_refs"] = refs
    if not keep_wish_status and new_wish_status is not None:
        data["status"] = new_wish_status
    updated_item = WishlistItem.model_validate(data)
    items = list(wish_doc.items)
    items[idx] = updated_item
    new_wish_doc = WishlistDocument(items=items)

    # Cross-validate todo_refs against the new todo document
    known = {t.id for t in new_todo_doc.tasks}
    for wish_item in new_wish_doc.items:
        for ref in wish_item.todo_refs:
            if ref not in known:
                raise StoreError(f"Wishlist '{wish_item.item}' references unknown TODO {ref}")

    write_documents(
        todo=new_todo_doc,
        wishlist=new_wish_doc,
        todo_path=todo_path,
        wishlist_path=wishlist_path,
    )
    if render and todo_path is None and wishlist_path is None:
        render_docs(write=True)
    return updated_item, new_task


def add_wish(
    item: WishlistItem,
    *,
    render: bool = True,
    wishlist_path=None,
) -> WishlistDocument:
    doc = load_wishlist(wishlist_path)
    if doc.find(item.item) is not None:
        raise StoreError(f'Wishlist item "{item.item}" already exists.')
    new_doc = WishlistDocument(items=[*doc.items, item])
    write_documents(wishlist=new_doc, wishlist_path=wishlist_path)
    if render and wishlist_path is None:
        render_docs(write=True)
    return new_doc
