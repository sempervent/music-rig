"""Studio session logging."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from music_rig import inbox_service, todo_service
from music_rig.inbox_service import default_clock
from music_rig.models import (
    SessionEvent,
    SessionEventType,
    SessionLog,
    SessionStatus,
    TodoStatus,
)
from music_rig.store import (
    StoreError,
    load_all_sessions,
    load_todo,
    save_session,
    session_path,
)

Clock = Callable[[], datetime]


def format_duration(started: datetime, ended: datetime | None, *, now: datetime) -> str:
    end = ended or now
    seconds = max(0, int((end - started).total_seconds()))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def session_id_for(started_at: datetime) -> str:
    local = started_at
    return f"SES-{local.strftime('%Y%m%d-%H%M%S')}"


def find_active(sessions_dir: Path | None = None) -> SessionLog | None:
    for session in load_all_sessions(sessions_dir):
        if session.status == SessionStatus.ACTIVE:
            return session
    return None


def require_active(sessions_dir: Path | None = None) -> SessionLog:
    active = find_active(sessions_dir)
    if active is None:
        raise StoreError("No active session.\nStart one with: uv run rig session start")
    return active


def ensure_active(
    *,
    focus: str = "",
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
) -> tuple[SessionLog, bool]:
    """Return the active session, starting a lightweight one if needed.

    Notes / discoveries / captures should not require a prior ceremony.
    Returns (session, started_now).
    """
    active = find_active(sessions_dir)
    if active is not None:
        return active, False
    return start_session(focus=focus, clock=clock, sessions_dir=sessions_dir), True


def start_session(
    focus: str = "",
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
) -> SessionLog:
    existing = find_active(sessions_dir)
    if existing is not None:
        raise StoreError(
            f"{existing.id} is already active.\nUse `rig session status` or end it first."
        )
    started = clock()
    session = SessionLog(
        id=session_id_for(started),
        started_at=started,
        ended_at=None,
        status=SessionStatus.ACTIVE,
        focus=focus.strip(),
        events=[],
    )
    # Collision guard if same second
    path = session_path(session.id, sessions_dir)
    if path.exists():
        raise StoreError(f"Session file already exists: {path.name}")
    save_session(session, sessions_dir)
    return session


def append_event(
    event_type: SessionEventType,
    text: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
    todo_id: str | None = None,
    capture_id: str | None = None,
    change_id: str | None = None,
) -> SessionLog:
    cleaned = text.strip()
    if not cleaned:
        raise StoreError("Event text cannot be empty.")
    session = require_active(sessions_dir)
    event = SessionEvent(
        timestamp=clock(),
        type=event_type,
        text=cleaned,
        todo_id=todo_id,
        capture_id=capture_id,
        change_id=change_id,
    )
    updated = SessionLog(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        focus=session.focus,
        events=[*session.events, event],
    )
    save_session(updated, sessions_dir)
    return updated


def add_note(
    text: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
    auto_start: bool = True,
) -> SessionLog:
    """Append a NOTE. By default auto-starts a session when none is active."""
    if auto_start:
        ensure_active(focus="ad-hoc note", clock=clock, sessions_dir=sessions_dir)
    return append_event(SessionEventType.NOTE, text, clock=clock, sessions_dir=sessions_dir)


def add_discovery(
    text: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
    auto_start: bool = True,
) -> SessionLog:
    """Append a DISCOVERY. By default auto-starts a session when none is active."""
    if auto_start:
        ensure_active(focus="ad-hoc discovery", clock=clock, sessions_dir=sessions_dir)
    return append_event(SessionEventType.DISCOVERY, text, clock=clock, sessions_dir=sessions_dir)


def start_task(
    todo_id: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
    todo_path=None,
    render: bool = True,
) -> tuple[SessionLog, object]:
    task, _changed, _doc = todo_service.set_todo_status(
        todo_id,
        TodoStatus.IN_PROGRESS,
        render=render,
        todo_path=todo_path,
    )
    session = append_event(
        SessionEventType.TODO_STARTED,
        f"Started {task.id}: {task.task}",
        clock=clock,
        sessions_dir=sessions_dir,
        todo_id=task.id,
    )
    return session, task


def complete_task(
    todo_id: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
    todo_path=None,
    render: bool = True,
) -> tuple[SessionLog, object]:
    task, _changed, _doc = todo_service.set_todo_status(
        todo_id,
        TodoStatus.DONE,
        remove_from_next=True,
        render=render,
        todo_path=todo_path,
    )
    session = append_event(
        SessionEventType.TODO_COMPLETED,
        f"Completed {task.id}: {task.task}",
        clock=clock,
        sessions_dir=sessions_dir,
        todo_id=task.id,
    )
    return session, task


def session_capture(
    text: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
    inbox_path=None,
    auto_start: bool = True,
) -> tuple[SessionLog, object]:
    if auto_start:
        ensure_active(focus="ad-hoc capture", clock=clock, sessions_dir=sessions_dir)
    item = inbox_service.capture_text(text, clock=clock, inbox_path=inbox_path, render=False)
    session = append_event(
        SessionEventType.CAPTURE,
        item.text,
        clock=clock,
        sessions_dir=sessions_dir,
        capture_id=item.id,
    )
    return session, item


def link_change(
    change_id: str,
    summary: str,
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
) -> SessionLog | None:
    active = find_active(sessions_dir)
    if active is None:
        return None
    return append_event(
        SessionEventType.CHANGE,
        summary,
        clock=clock,
        sessions_dir=sessions_dir,
        change_id=change_id,
    )


def summarize(session: SessionLog) -> dict[str, int | list[str]]:
    notes = discoveries = todos_done = captures = changes = 0
    open_caps: list[str] = []
    change_ids: list[str] = []
    for event in session.events:
        if event.type == SessionEventType.NOTE:
            notes += 1
        elif event.type == SessionEventType.DISCOVERY:
            discoveries += 1
        elif event.type == SessionEventType.TODO_COMPLETED:
            todos_done += 1
        elif event.type == SessionEventType.CAPTURE:
            captures += 1
            if event.capture_id:
                open_caps.append(event.capture_id)
        elif event.type == SessionEventType.CHANGE:
            changes += 1
            if event.change_id:
                change_ids.append(event.change_id)
    return {
        "notes": notes,
        "discoveries": discoveries,
        "todos_done": todos_done,
        "captures": captures,
        "changes": changes,
        "capture_ids": open_caps,
        "change_ids": change_ids,
    }


def end_session(
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
) -> SessionLog:
    session = require_active(sessions_dir)
    updated = SessionLog(
        id=session.id,
        started_at=session.started_at,
        ended_at=clock(),
        status=SessionStatus.COMPLETED,
        focus=session.focus,
        events=list(session.events),
    )
    save_session(updated, sessions_dir)
    return updated


def abort_session(
    *,
    clock: Clock = default_clock,
    sessions_dir: Path | None = None,
) -> SessionLog:
    session = require_active(sessions_dir)
    updated = SessionLog(
        id=session.id,
        started_at=session.started_at,
        ended_at=clock(),
        status=SessionStatus.ABORTED,
        focus=session.focus,
        events=list(session.events),
    )
    save_session(updated, sessions_dir)
    return updated


def list_sessions(
    *,
    limit: int = 10,
    sessions_dir: Path | None = None,
) -> list[SessionLog]:
    sessions = load_all_sessions(sessions_dir)
    return sessions[: max(0, limit)]


def focus_label(focus: str, *, todo_path=None) -> str:
    cleaned = focus.strip()
    if not cleaned:
        return "(none)"
    if cleaned.upper().startswith("RIG-"):
        try:
            task = todo_service.get_task(load_todo(todo_path), cleaned)
            return f"{task.id} — {task.task}"
        except StoreError:
            return cleaned
    return cleaned
