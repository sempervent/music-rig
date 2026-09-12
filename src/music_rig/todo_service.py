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


def update_todo_fields(
    todo_id: str,
    *,
    task: str | None = None,
    area: str | None = None,
    priority: str | None = None,
    status: TodoStatus | str | None = None,
    definition_of_done: str | None = None,
    notes: str | None = None,
    depends_on: list[str] | None = None,
    waiting_on: str | None = None,
    next_session_why: str | None = None,
    render: bool = True,
    todo_path=None,
    docs_todo=None,
    docs_wishlist=None,
) -> TodoTask:
    """Patch mutable TODO fields. Status may also be set via set_todo_status."""
    from music_rig.models import TodoPriority

    doc = load_todo(todo_path)
    current = get_task(doc, todo_id)
    data = current.model_dump()
    if task is not None:
        cleaned = task.strip()
        if not cleaned:
            raise StoreError("Task text cannot be empty.")
        data["task"] = cleaned
    if area is not None:
        cleaned_area = area.strip()
        if not cleaned_area:
            raise StoreError("Area cannot be empty.")
        data["area"] = cleaned_area
    if priority is not None:
        data["priority"] = TodoPriority(str(priority).strip().upper())
    if status is not None:
        data["status"] = TodoStatus(status) if isinstance(status, str) else status
    if definition_of_done is not None:
        cleaned_dod = definition_of_done.strip()
        if not cleaned_dod:
            raise StoreError("Definition of done cannot be empty.")
        data["definition_of_done"] = cleaned_dod
    if notes is not None:
        data["notes"] = notes
    if depends_on is not None:
        deps = [d.strip().upper() for d in depends_on if d.strip()]
        known = doc.task_map()
        for dep in deps:
            if dep not in known:
                raise StoreError(f"Dependency {dep} does not exist.")
        data["depends_on"] = deps
    if waiting_on is not None:
        data["waiting_on"] = waiting_on.strip() or None
    if next_session_why is not None:
        data["next_session_why"] = next_session_why.strip() or None
    updated = TodoTask.model_validate(data)
    new_doc = _replace_task(doc, updated)
    # Drop from next_session if terminal
    if updated.status.value in TERMINAL_FOR_NEXT and updated.id in new_doc.next_session:
        new_doc = TodoDocument(
            next_session=[t for t in new_doc.next_session if t != updated.id],
            tasks=list(new_doc.tasks),
        )
    save_todo(new_doc, todo_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            write=True,
        )
    return updated


def migrate_next_status(doc: TodoDocument) -> TodoDocument:
    """Convert legacy NEXT status to READY; preserve next_session."""
    tasks = []
    for task in doc.tasks:
        data = task.model_dump()
        if data.get("status") == "NEXT":
            data["status"] = TodoStatus.READY.value
        tasks.append(TodoTask.model_validate(data))
    return TodoDocument(next_session=list(doc.next_session), tasks=tasks)
