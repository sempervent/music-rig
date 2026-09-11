"""Deterministic next-action recommendations (`rig now`)."""

from __future__ import annotations

from pathlib import Path

from music_rig.inbox_service import default_clock
from music_rig.models import (
    NowKind,
    NowRecommendation,
    TodoPriority,
    TodoStatus,
    TodoTask,
)
from music_rig.session_service import find_active, format_duration
from music_rig.store import load_todo

PRIORITY_RANK = {
    TodoPriority.P0: 0,
    TodoPriority.P1: 1,
    TodoPriority.P2: 2,
    TodoPriority.P3: 3,
}


def _rig_number(todo_id: str) -> int:
    return int(todo_id.split("-")[1])


def _best_in_progress(tasks: list[TodoTask]) -> TodoTask:
    return sorted(
        tasks,
        key=lambda t: (PRIORITY_RANK[t.priority], _rig_number(t.id)),
    )[0]


def _best_ready(tasks: list[TodoTask]) -> TodoTask | None:
    ready = [t for t in tasks if t.status == TodoStatus.READY]
    if not ready:
        return None
    # Prefer YAML order among same priority: stable sort by priority then list index
    indexed = list(enumerate(ready))
    indexed.sort(key=lambda pair: (PRIORITY_RANK[pair[1].priority], pair[0]))
    return indexed[0][1]


def _skipped_summary(tasks: list[TodoTask]) -> list[str]:
    counts: dict[str, int] = {}
    for task in tasks:
        if task.status in {
            TodoStatus.BLOCKED,
            TodoStatus.WAITING,
            TodoStatus.DEFERRED,
            TodoStatus.DONE,
            TodoStatus.CANCELLED,
        }:
            key = task.status.value
            counts[key] = counts.get(key, 0) + 1
    lines = []
    for status in ("BLOCKED", "WAITING", "DEFERRED", "DONE", "CANCELLED"):
        if status in counts:
            n = counts[status]
            label = "task" if n == 1 else "tasks"
            lines.append(f"{n} {status} {label}")
    return lines


def recommend_now(
    *,
    play: bool = False,
    todo_path: Path | None = None,
    sessions_dir: Path | None = None,
    clock=default_clock,
) -> NowRecommendation:
    if play:
        return NowRecommendation(
            kind=NowKind.PLAY,
            primary_reference="PLAY",
            title="Start a freeform studio session",
            reason="No infrastructure task selected (--play).",
            suggested_commands=[
                'uv run rig session start --focus "Just play"',
                "uv run rig performance mode pfl-jam",
            ],
        )

    active = find_active(sessions_dir)
    if active is not None:
        now = clock()
        recent = ""
        if active.events:
            last = active.events[-1]
            recent = f"{last.type.value} — {last.text}"
        return NowRecommendation(
            kind=NowKind.ACTIVE_SESSION,
            primary_reference=active.id,
            title=f"Continue active session {active.id}",
            reason="A studio session is already ACTIVE.",
            focus=active.focus or "(none)",
            duration=format_duration(active.started_at, active.ended_at, now=now),
            recent_event=recent,
            suggested_commands=[
                "uv run rig session status",
                "uv run rig session end",
            ],
        )

    todo = load_todo(todo_path)
    skipped = _skipped_summary(todo.tasks)

    in_progress = [t for t in todo.tasks if t.status == TodoStatus.IN_PROGRESS]
    if in_progress:
        task = _best_in_progress(in_progress)
        return NowRecommendation(
            kind=NowKind.IN_PROGRESS,
            primary_reference=task.id,
            title=task.task,
            reason="Highest-priority IN PROGRESS task (tie-break: lowest RIG number).",
            priority=task.priority.value,
            definition_of_done=task.definition_of_done,
            suggested_commands=[
                f"uv run rig session start --focus {task.id}",
                f"uv run rig todo show {task.id}",
            ],
            skipped_summary=skipped,
        )

    by_id = todo.task_map()
    for tid in todo.next_session:
        task = by_id.get(tid)
        if task is None:
            continue
        if task.status in {
            TodoStatus.BLOCKED,
            TodoStatus.WAITING,
            TodoStatus.DEFERRED,
            TodoStatus.DONE,
            TodoStatus.CANCELLED,
        }:
            continue
        return NowRecommendation(
            kind=NowKind.NEXT_SESSION,
            primary_reference=task.id,
            title=task.task,
            reason="First actionable item in your explicit Next Session queue.",
            priority=task.priority.value,
            definition_of_done=task.definition_of_done,
            suggested_commands=[
                f"uv run rig todo start {task.id}",
                f"uv run rig session start --focus {task.id}",
            ],
            skipped_summary=skipped,
        )

    ready = _best_ready(todo.tasks)
    if ready is not None:
        return NowRecommendation(
            kind=NowKind.READY,
            primary_reference=ready.id,
            title=ready.task,
            reason=(
                "No active session or Next Session item; "
                "highest-priority READY task "
                "(tie-break: YAML order among equal priority)."
            ),
            priority=ready.priority.value,
            definition_of_done=ready.definition_of_done,
            suggested_commands=[
                f"uv run rig todo start {ready.id}",
                f"uv run rig session start --focus {ready.id}",
            ],
            skipped_summary=skipped,
        )

    return NowRecommendation(
        kind=NowKind.PLAY,
        primary_reference="PLAY",
        title="Start a freeform studio session",
        reason="No actionable TODOs; play music instead of inventing chores.",
        suggested_commands=[
            'uv run rig session start --focus "Just play"',
            "uv run rig performance mode pfl-jam",
        ],
        skipped_summary=skipped,
    )


def format_now(rec: NowRecommendation, *, extra_why: bool = False) -> str:
    lines: list[str] = []
    if rec.kind == NowKind.PLAY and rec.primary_reference == "PLAY":
        if "--play" in rec.reason or "No infrastructure" in rec.reason:
            lines.append("PLAY")
            lines.append("")
            lines.append("No infrastructure task selected.")
            lines.append("")
            lines.append("Performance mode: PFL JAM (`pfl-jam`)")
            lines.append("Readiness is advisory and does not gate play.")
            lines.append("")
            lines.append("Start:")
            for cmd in rec.suggested_commands:
                lines.append(f"  {cmd}")
            return "\n".join(lines) + "\n"

    if rec.kind == NowKind.ACTIVE_SESSION:
        lines.append("DO THIS NEXT")
        lines.append("")
        lines.append(f"Continue active session {rec.primary_reference}")
        lines.append(f"Focus: {rec.focus}")
        lines.append(f"Duration: {rec.duration}")
        if rec.recent_event:
            lines.append("")
            lines.append("Recent event:")
            lines.append(f"  {rec.recent_event}")
        lines.append("")
        lines.append("Continue:")
        for cmd in rec.suggested_commands:
            lines.append(f"  {cmd}")
        return "\n".join(lines) + "\n"

    if rec.kind == NowKind.PLAY:
        lines.append("DO THIS NEXT")
        lines.append("")
        lines.append(rec.title)
        lines.append("")
        lines.append("Why:")
        lines.append(rec.reason)
        lines.append("")
        lines.append("Start:")
        for cmd in rec.suggested_commands:
            lines.append(f"  {cmd}")
        if extra_why and rec.skipped_summary:
            lines.append("")
            lines.append("Skipped:")
            for item in rec.skipped_summary:
                lines.append(f"- {item}")
        return "\n".join(lines) + "\n"

    lines.append("DO THIS NEXT")
    lines.append("")
    pri = f"  {rec.priority}" if rec.priority else ""
    lines.append(f"{rec.primary_reference}{pri}")
    lines.append(rec.title)
    lines.append("")
    lines.append("Why:")
    lines.append(rec.reason)
    if rec.definition_of_done:
        lines.append("")
        lines.append("Definition of Done:")
        lines.append(rec.definition_of_done)
    lines.append("")
    if rec.kind == NowKind.IN_PROGRESS:
        lines.append("Continue:")
    else:
        lines.append("Start:")
    for cmd in rec.suggested_commands:
        lines.append(f"  {cmd}")
    lines.append("")
    lines.append("Want to ignore infrastructure and play?")
    lines.append('  uv run rig session start --focus "Just play"')
    if extra_why and rec.skipped_summary:
        lines.append("")
        lines.append("Skipped:")
        for item in rec.skipped_summary:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"
