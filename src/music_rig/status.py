"""Read-only planning status dashboard."""

from __future__ import annotations

import subprocess
from collections import Counter

from music_rig.models import InboxStatus, TodoStatus, WishStatus
from music_rig.store import ROOT, load_inbox, load_todo, load_wishlist


def git_summary() -> tuple[str | None, str | None]:
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        tree = "dirty" if dirty else "clean"
        return branch or None, tree
    except Exception:
        return None, None


def build_status_text() -> str:
    todo = load_todo()
    wish = load_wishlist()
    inbox = load_inbox()

    status_counts = Counter(t.status for t in todo.tasks)
    ready_p0 = sum(
        1
        for t in todo.tasks
        if t.status == TodoStatus.READY and t.priority.value == "P0"
    )
    ready_p1 = sum(
        1
        for t in todo.tasks
        if t.status == TodoStatus.READY and t.priority.value == "P1"
    )
    open_inbox = sum(1 for i in inbox.items if i.status == InboxStatus.OPEN)

    wish_p1 = [w for w in wish.items if w.priority and w.priority.value == "P1"]
    wish_p1_status = Counter(w.status for w in wish_p1)

    lines = [
        "MUSIC RIG",
        "",
        f"Next Session       {len(todo.next_session)}",
        f"In Progress        {status_counts.get(TodoStatus.IN_PROGRESS, 0)}",
        f"Ready P0           {ready_p0}",
        f"Ready P1           {ready_p1}",
        f"Blocked            {status_counts.get(TodoStatus.BLOCKED, 0)}",
        f"Waiting            {status_counts.get(TodoStatus.WAITING, 0)}",
        f"Inbox Open         {open_inbox}",
        "",
        "Wishlist P1",
    ]
    if wish_p1_status:
        for status, count in sorted(wish_p1_status.items(), key=lambda x: x[0].value):
            lines.append(f"  {status.value:<16} {count}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Next Session")
    if todo.next_session:
        by_id = todo.task_map()
        for i, tid in enumerate(todo.next_session, start=1):
            task = by_id[tid]
            lines.append(f"  {i}. {tid}  {task.priority.value}  {task.task}")
    else:
        lines.append("  (empty)")

    branch, tree = git_summary()
    if branch is not None:
        lines.append("")
        lines.append(f"Branch: {branch}")
        lines.append(f"Working tree: {tree}")

    return "\n".join(lines) + "\n"
