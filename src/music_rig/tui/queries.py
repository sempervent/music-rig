"""Home-screen count helpers — call services/store, never scrape CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from music_rig.models import (
    ChangeStatus,
    HumanActionStatus,
    InboxStatus,
    QuestionStatus,
    WishStatus,
)
from music_rig.patchbay_state import list_pairs, load_raw
from music_rig.session_service import find_active, list_sessions
from music_rig.snapshot_service import list_snapshots
from music_rig.store import (
    load_changes,
    load_human_actions,
    load_inbox,
    load_inventory,
    load_questions,
    load_todo,
    load_wishlist,
)


@dataclass(frozen=True)
class HomeCounts:
    open_questions: int
    todo_total: int
    todo_in_progress: int
    next_session: int
    wishlist: int
    inbox_open: int
    human_pending: int
    changes_open: int
    patchbay_bays: int
    patchbay_unknown_modes: int
    gear: int
    snapshots: int
    sessions: int
    active_session: str | None


def home_counts(
    *,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    inbox_path: Path | None = None,
    changes_path: Path | None = None,
    patchbays_path: Path | None = None,
    inventory_path: Path | None = None,
    sessions_dir: Path | None = None,
    snapshots_dir: Path | None = None,
) -> HomeCounts:
    questions = load_questions(questions_path)
    todo = load_todo(todo_path)
    wish = load_wishlist(wishlist_path)
    inbox = load_inbox(inbox_path)
    changes = load_changes(changes_path)
    inventory = load_inventory(inventory_path)

    open_q = sum(1 for q in questions.questions if q.status == QuestionStatus.OPEN)
    in_progress = sum(1 for t in todo.tasks if t.status.value == "IN PROGRESS")
    wish_active = sum(
        1 for w in wish.items if w.status not in {WishStatus.REJECTED, WishStatus.ACQUIRED}
    )
    inbox_open = sum(1 for i in inbox.items if i.status == InboxStatus.OPEN)
    human_doc = load_human_actions()
    human_pending = sum(1 for i in human_doc.items if i.status is HumanActionStatus.PENDING)
    changes_open = sum(1 for c in changes.items if c.status == ChangeStatus.OPEN)

    unknown_modes = 0
    bays = 0
    try:
        pb = load_raw(patchbays_path)
        bays = len(pb.get("patchbays") or {})
        for bay_id in pb.get("patchbays") or {}:
            for pair in list_pairs(bay_id, pb):
                if str(pair.get("mode", "unknown")).lower() == "unknown":
                    unknown_modes += 1
    except Exception:
        bays = 0
        unknown_modes = 0

    active = find_active(sessions_dir)
    sessions = list_sessions(limit=50, sessions_dir=sessions_dir)
    snaps = list_snapshots(snapshots_dir)

    return HomeCounts(
        open_questions=open_q,
        todo_total=len(todo.tasks),
        todo_in_progress=in_progress,
        next_session=len(todo.next_session),
        wishlist=wish_active,
        inbox_open=inbox_open,
        human_pending=human_pending,
        changes_open=changes_open,
        patchbay_bays=bays,
        patchbay_unknown_modes=unknown_modes,
        gear=len(inventory.items),
        snapshots=len(snaps),
        sessions=len(sessions),
        active_session=active.id if active else None,
    )
