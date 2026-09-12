"""Read-only planning status dashboard."""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

from music_rig.models import ChangeStatus, InboxStatus, QuestionStatus, TodoStatus
from music_rig.session_service import find_active
from music_rig.store import (
    ROOT,
    load_changes,
    load_inbox,
    load_questions,
    load_todo,
    load_wishlist,
)


def _git_cwd(root: Path | None = None) -> Path:
    return root or ROOT


def git_branch(root: Path | None = None) -> str | None:
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=_git_cwd(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return branch or None
    except Exception:
        return None


def git_working_tree_clean(root: Path | None = None) -> bool | None:
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=_git_cwd(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return not bool(dirty)
    except Exception:
        return None


def git_commit_sha(*, short: bool = True, root: Path | None = None) -> str | None:
    try:
        args = ["git", "rev-parse"]
        if short:
            args.append("--short")
        args.append("HEAD")
        sha = subprocess.check_output(
            args,
            cwd=_git_cwd(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return sha or None
    except Exception:
        return None


def git_summary(root: Path | None = None) -> tuple[str | None, str | None]:
    branch = git_branch(root=root)
    clean = git_working_tree_clean(root=root)
    if branch is None and clean is None:
        return None, None
    tree = None if clean is None else ("clean" if clean else "dirty")
    return branch, tree


def build_status_text() -> str:
    # Intentionally compact: inventory detail/counts live under `rig gear` and doctor.
    todo = load_todo()
    wish = load_wishlist()
    inbox = load_inbox()
    changes = load_changes()
    questions = load_questions()
    active = find_active()

    status_counts = Counter(t.status for t in todo.tasks)
    ready_p0 = sum(
        1 for t in todo.tasks if t.status == TodoStatus.READY and t.priority.value == "P0"
    )
    ready_p1 = sum(
        1 for t in todo.tasks if t.status == TodoStatus.READY and t.priority.value == "P1"
    )
    open_inbox = sum(1 for i in inbox.items if i.status == InboxStatus.OPEN)
    open_changes = sum(1 for c in changes.items if c.status == ChangeStatus.OPEN)
    open_questions = sum(1 for q in questions.questions if q.status == QuestionStatus.OPEN)

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
        "",
        f"Active Session     {active.id if active else 'no'}",
        f"Inbox Open         {open_inbox}",
        f"Open Changes       {open_changes}",
        f"Open Questions     {open_questions}",
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
