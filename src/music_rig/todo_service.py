"""TODO mutation helpers."""

from __future__ import annotations

from copy import deepcopy

from music_rig.models import (
    TERMINAL_FOR_NEXT,
    TodoDocument,
    TodoStatus,
    TodoTask,
)
from music_rig.render import render_docs
from music_rig.store import StoreError, load_todo, save_todo, write_documents


def _replace_task(doc: TodoDocument, task: TodoTask) -> TodoDocument:
    tasks = [task if t.id == task.id else t for t in doc.tasks]
    return TodoDocument(next_session=list(doc.next_session), tasks=tasks)


def get_task(doc: TodoDocument, todo_id: str) -> TodoTask:
    key = todo_id.strip().upper()
    task = doc.task_map().get(key)
    if task is None:
        raise StoreError(f"TODO {key} does not exist.")
    return task


def set_todo_status(
    todo_id: str,
    status: TodoStatus,
    *,
    remove_from_next: bool = False,
    render: bool = True,
    todo_path=None,
    docs_todo=None,
    docs_wishlist=None,
) -> tuple[TodoTask, bool, TodoDocument]:
    """Return (task, changed, doc)."""
    doc = load_todo(todo_path)
    task = get_task(doc, todo_id)
    changed = False
    data = task.model_dump()
    if task.status != status:
        data["status"] = status
        changed = True
    next_session = list(doc.next_session)
    if remove_from_next and task.id in next_session:
        next_session = [tid for tid in next_session if tid != task.id]
        changed = True
    if not changed:
        return task, False, doc
    updated_task = TodoTask.model_validate(data)
    new_doc = TodoDocument(next_session=next_session, tasks=[
        updated_task if t.id == updated_task.id else t for t in doc.tasks
    ])
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return updated_task, True, new_doc


def next_list(doc: TodoDocument | None = None) -> list[TodoTask]:
    doc = doc or load_todo()
    by_id = doc.task_map()
    return [by_id[tid] for tid in doc.next_session]


def next_add(
    todo_id: str,
    *,
    render: bool = True,
    todo_path=None,
    docs_todo=None,
    docs_wishlist=None,
) -> TodoDocument:
    doc = load_todo(todo_path)
    task = get_task(doc, todo_id)
    if task.id in doc.next_session:
        raise StoreError(f"{task.id} is already in Next Session.")
    if len(doc.next_session) >= 3:
        raise StoreError(
            "Next Session already contains 3 tasks.\nRemove or replace one first."
        )
    if task.status.value in TERMINAL_FOR_NEXT:
        raise StoreError(
            f"{task.id} is {task.status.value} and cannot be added to Next Session."
        )
    new_doc = TodoDocument(
        next_session=[*doc.next_session, task.id],
        tasks=list(doc.tasks),
    )
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return new_doc


def next_remove(todo_id: str, *, render: bool = True, todo_path=None, docs_todo=None, docs_wishlist=None) -> TodoDocument:
    doc = load_todo(todo_path)
    task = get_task(doc, todo_id)
    if task.id not in doc.next_session:
        raise StoreError(f"{task.id} is not in Next Session.")
    new_doc = TodoDocument(
        next_session=[tid for tid in doc.next_session if tid != task.id],
        tasks=list(doc.tasks),
    )
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return new_doc


def next_set(ids: list[str], *, render: bool = True, todo_path=None, docs_todo=None, docs_wishlist=None) -> TodoDocument:
    doc = load_todo(todo_path)
    normalized = [i.strip().upper() for i in ids]
    if len(normalized) > 3:
        raise StoreError("Next Session may contain at most 3 tasks.")
    if len(normalized) != len(set(normalized)):
        raise StoreError("Next Session IDs must be unique.")
    by_id = doc.task_map()
    for tid in normalized:
        if tid not in by_id:
            raise StoreError(f"TODO {tid} does not exist.")
        if by_id[tid].status.value in TERMINAL_FOR_NEXT:
            raise StoreError(
                f"{tid} is {by_id[tid].status.value} and cannot be in Next Session."
            )
    new_doc = TodoDocument(next_session=normalized, tasks=list(doc.tasks))
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return new_doc


def next_clear(*, render: bool = True, todo_path=None, docs_todo=None, docs_wishlist=None) -> TodoDocument:
    doc = load_todo(todo_path)
    if not doc.next_session:
        return doc
    new_doc = TodoDocument(next_session=[], tasks=list(doc.tasks))
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return new_doc


def add_todo(
    task: TodoTask,
    *,
    render: bool = True,
    todo_path=None,
    docs_todo=None,
    docs_wishlist=None,
) -> TodoDocument:
    doc = load_todo(todo_path)
    new_doc = TodoDocument(
        next_session=list(doc.next_session),
        tasks=[*doc.tasks, task],
    )
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return new_doc


def migrate_next_status(doc: TodoDocument) -> TodoDocument:
    """Convert legacy NEXT status to READY; preserve next_session."""
    tasks = []
    for task in doc.tasks:
        data = task.model_dump()
        if data.get("status") == "NEXT":
            data["status"] = TodoStatus.READY.value
        tasks.append(TodoTask.model_validate(data))
    return TodoDocument(next_session=list(doc.next_session), tasks=tasks)
