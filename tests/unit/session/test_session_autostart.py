"""Stage 28: session notes auto-start; experiments do not touch CURRENT."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from music_rig.actor import ActorKind, reset_actor, set_actor
from music_rig.session_service import add_discovery, add_note, find_active
from music_rig.store import StoreError, load_all_sessions


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now

    def advance(self, *, seconds: int = 0, minutes: int = 0) -> None:
        self._now = self._now + timedelta(seconds=seconds, minutes=minutes)


def test_session_note_autostarts(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    clock = FakeClock(datetime(2026, 9, 12, 19, 0, 0, tzinfo=UTC))
    assert find_active(sessions) is None
    session = add_note(
        "space chain went beautifully feral after 12 minutes",
        clock=clock,
        sessions_dir=sessions,
    )
    assert session.status.value == "ACTIVE"
    assert len(session.events) == 1
    assert session.events[0].type.value == "NOTE"
    assert "feral" in session.events[0].text


def test_bot_can_add_non_authoritative_session_note(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    reset_actor()
    set_actor(ActorKind.BOT)
    try:
        clock = FakeClock(datetime(2026, 9, 12, 19, 5, 0, tzinfo=UTC))
        session = add_note(
            "BOT experiment: tried SY-1 louder",
            clock=clock,
            sessions_dir=sessions,
        )
        assert "BOT experiment" in session.events[0].text
        # Session YAML is history — not CURRENT routing.
        assert (sessions / f"{session.id}.yaml").exists()
    finally:
        reset_actor()


def test_session_note_auto_start_false_still_requires_active(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    clock = FakeClock(datetime(2026, 9, 12, 19, 10, 0, tzinfo=UTC))
    with pytest.raises(StoreError, match="No active session"):
        add_note("blocked", clock=clock, sessions_dir=sessions, auto_start=False)


def test_discovery_autostart(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    clock = FakeClock(datetime(2026, 9, 12, 19, 15, 0, tzinfo=UTC))
    session = add_discovery("keep the wet feral take", clock=clock, sessions_dir=sessions)
    assert session.events[0].type.value == "DISCOVERY"
    assert load_all_sessions(sessions)
