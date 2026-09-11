"""Repository consistency checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from music_rig.models import TERMINAL_FOR_NEXT
from music_rig.render import check_render_sync
from music_rig.store import (
    EXISTING_YAML,
    INBOX_PATH,
    StoreError,
    load_inbox,
    load_todo,
    load_wishlist,
    parse_existing_yaml,
)


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def run_checks(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    inbox_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    todo = None
    wishlist = None
    try:
        todo = load_todo(todo_path)
    except StoreError as exc:
        errors.append(str(exc))

    try:
        wishlist = load_wishlist(wishlist_path)
    except StoreError as exc:
        errors.append(str(exc))

    try:
        inbox = load_inbox(inbox_path)
        # schema already validated; extra explicit checks
        for item in inbox.items:
            if not item.text.strip():
                errors.append(f"{item.id} has empty capture text")
    except StoreError as Exc:
        errors.append(str(Exc))

    if todo is not None and wishlist is not None:
        known = {t.id for t in todo.tasks}
        for item in wishlist.items:
            for ref in item.todo_refs:
                if ref not in known:
                    errors.append(
                        f"Wishlist '{item.item}' references unknown TODO {ref}"
                    )

    if todo is not None:
        by_id = todo.task_map()
        if len(todo.next_session) > 3:
            errors.append("next_session has more than 3 tasks")
        if len(todo.next_session) != len(set(todo.next_session)):
            errors.append("next_session has duplicate IDs")
        for tid in todo.next_session:
            task = by_id.get(tid)
            if task and task.status.value in TERMINAL_FOR_NEXT:
                errors.append(f"{tid} is {task.status.value} but still in next_session")

    try:
        stale = check_render_sync(
            todo_path=todo_path,
            wishlist_path=wishlist_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
        )
        for path in stale:
            errors.append(
                f"{path} is out of date with canonical YAML\nRun: uv run rig render"
            )
    except StoreError as exc:
        errors.append(str(exc))

    for path in EXISTING_YAML:
        try:
            parse_existing_yaml(path)
        except StoreError as exc:
            errors.append(str(exc))

    # inbox file optional; if present ensure it parses (already done via load_inbox)
    _ = INBOX_PATH

    return CheckResult(ok=not errors, errors=errors, warnings=warnings)
