from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import change_service, session_service
from music_rig.cli import app
from music_rig.doctor import build_doctor_text
from music_rig.models import (
    ChangeCategory,
    ChangeStatus,
    TodoDocument,
    TodoStatus,
)
from music_rig.rig_views import (
    format_channels,
    format_path_list,
    format_patchbay,
    format_patchbay_list,
    path_tree_for,
)
from music_rig.store import (
    StoreError,
    load_changes,
    load_inbox,
    load_todo,
    save_todo,
)
from music_rig.todo_service import set_todo_status

runner = CliRunner()


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> None:
        self._now = self._now + timedelta(**kwargs)


@pytest.fixture
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    changes = tmp_path / "changes.yaml"
    changes.write_text("items: []\n", encoding="utf-8")
    inbox = tmp_path / "inbox.yaml"
    inbox.write_text("items: []\n", encoding="utf-8")
    questions = tmp_path / "open-questions.yaml"
    questions.write_text("questions: []\n", encoding="utf-8")
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    docs_todo = tmp_path / "todo.md"
    docs_wish = tmp_path / "wishlist.md"
    docs_q = tmp_path / "open-questions.md"
    docs_todo.write_text(
        "x\n<!-- rig:todo:start -->\n<!-- rig:todo:end -->\n", encoding="utf-8"
    )
    docs_wish.write_text(
        "x\n<!-- rig:wishlist:start -->\n<!-- rig:wishlist:end -->\n", encoding="utf-8"
    )
    docs_q.write_text(
        "x\n<!-- rig:questions:start -->\n<!-- rig:questions:end -->\n", encoding="utf-8"
    )
    todo_doc = TodoDocument.model_validate(
        {
            "next_session": ["RIG-001"],
            "tasks": [
                {
                    "id": "RIG-001",
                    "task": "Verify topology",
                    "area": "Docs",
                    "priority": "P0",
                    "status": "READY",
                    "depends_on": [],
                    "definition_of_done": "done",
                    "notes": "",
                },
                {
                    "id": "RIG-002",
                    "task": "Other",
                    "area": "Docs",
                    "priority": "P1",
                    "status": "READY",
                    "depends_on": [],
                    "definition_of_done": "done",
                    "notes": "",
                },
            ],
        }
    )
    save_todo(todo_doc, todo)
    wish.write_text("items: []\n", encoding="utf-8")
    from music_rig.render import render_docs

    render_docs(
        todo_path=todo,
        wishlist_path=wish,
        questions_path=questions,
        docs_todo=docs_todo,
        docs_wishlist=docs_wish,
        docs_questions=docs_q,
        write=True,
    )

    channel_map = tmp_path / "channel-map.yaml"
    channel_map.write_text(
        yaml.safe_dump(
            {
                "tascam": {
                    1: {
                        "name": "MIXER_L",
                        "source": "Alesis main out L",
                        "type": "clean_stereo_bus",
                        "status": "CURRENT",
                    },
                    2: {
                        "name": "MIXER_R",
                        "source": "Alesis main out R",
                        "type": "clean_stereo_bus",
                        "status": "CURRENT",
                    },
                    5: {
                        "name": "ACOUSTIC_CLEAN",
                        "source": "Acoustic clean",
                        "type": "clean_mono",
                        "status": "CURRENT",
                    },
                    8: {
                        "name": "UNASSIGNED",
                        "source": None,
                        "type": "unassigned",
                        "status": "UNASSIGNED",
                    },
                },
                "alesis": {
                    1: {"source": "Bass", "aux_send": True, "status": "CURRENT"},
                    3: {"source": None, "aux_send": False, "status": "UNASSIGNED"},
                },
            }
        ),
        encoding="utf-8",
    )
    patchbays = tmp_path / "patchbays.yaml"
    patchbays.write_text(
        yaml.safe_dump(
            {
                "patchbays": {
                    "PB-A": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-B": {
                        "hardware_model": "unknown",
                        "status": "partially_documented",
                        "jacks": {
                            1: {
                                "row": "upper",
                                "connection": "miniKORG L",
                                "paired_with": 25,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            25: {
                                "row": "lower",
                                "connection": "TASCAM 3",
                                "paired_with": 1,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            2: {
                                "row": "upper",
                                "connection": "Verified",
                                "paired_with": 26,
                                "mode": "half-normal",
                                "status": "documented",
                            },
                            26: {
                                "row": "lower",
                                "connection": "TASCAM 4",
                                "paired_with": 2,
                                "mode": "half-normal",
                                "status": "documented",
                            },
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    routing = tmp_path / "routing.yaml"
    routing.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "space": {
                        "label": "SPACE test",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "Main path",
                                "nodes": [
                                    {"id": "joyo-send-b", "label": "JOYO SEND B"},
                                    {"id": "sy-1", "label": "SY-1"},
                                    {"id": "ls-2", "label": "LS-2"},
                                    {"id": "unknown-return", "label": "UNKNOWN return"},
                                ],
                            },
                            "sy1-send": {
                                "label": "SEND",
                                "attach": "sy-1",
                                "position": "before",
                                "nodes": [
                                    {"id": "ph-3", "label": "PH-3"},
                                    {"id": "tr-2", "label": "TR-2"},
                                ],
                            },
                        },
                    },
                    "aux": {
                        "label": "AUX",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "Main path",
                                "nodes": [
                                    {"id": "aux-send", "label": "AUX SEND"},
                                    {"id": "rc-1", "label": "RC-1"},
                                ],
                            }
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(session_service, "SESSIONS_DIR", sessions, raising=False)
    from music_rig import store

    monkeypatch.setattr(store, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs_todo)
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs_wish)
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs_q)
    monkeypatch.setattr(store, "CHANNEL_MAP_PATH", channel_map)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "ROUTING_PATH", routing)

    clock = FakeClock(datetime(2026, 9, 10, 22, 35, 0, tzinfo=timezone.utc))
    return {
        "sessions": sessions,
        "changes": changes,
        "inbox": inbox,
        "todo": todo,
        "channel_map": channel_map,
        "patchbays": patchbays,
        "routing": routing,
        "clock": clock,
        "docs_todo": docs_todo,
        "docs_wish": docs_wish,
        "docs_q": docs_q,
        "wish": wish,
        "questions": questions,
    }


def test_session_lifecycle(studio):
    clock = studio["clock"]
    sessions = studio["sessions"]
    s = session_service.start_session(
        "Just play", clock=clock, sessions_dir=sessions
    )
    assert s.id == "SES-20260910-223500"
    assert s.status.value == "ACTIVE"
    assert s.ended_at is None

    with pytest.raises(StoreError, match="already active"):
        session_service.start_session("x", clock=clock, sessions_dir=sessions)

    clock.advance(minutes=7)
    session_service.add_note("PH-3 first", clock=clock, sessions_dir=sessions)
    clock.advance(minutes=9)
    session_service.add_discovery("quiet RE-2", clock=clock, sessions_dir=sessions)

    active = session_service.require_active(sessions)
    assert len(active.events) == 2
    assert "duration" not in yaml.safe_load(
        (sessions / f"{active.id}.yaml").read_text(encoding="utf-8")
    )

    duration = session_service.format_duration(
        active.started_at, None, now=clock()
    )
    assert duration == "16m"

    clock.advance(minutes=1)
    ended = session_service.end_session(clock=clock, sessions_dir=sessions)
    assert ended.status.value == "COMPLETED"
    assert ended.ended_at == clock()


def test_session_todo_and_capture(studio):
    clock = studio["clock"]
    sessions = studio["sessions"]
    session_service.start_session("RIG-001", clock=clock, sessions_dir=sessions)
    session_service.start_task(
        "RIG-001",
        clock=clock,
        sessions_dir=sessions,
        todo_path=studio["todo"],
        render=False,
    )
    task = load_todo(studio["todo"]).task_map()["RIG-001"]
    assert task.status == TodoStatus.IN_PROGRESS

    clock.advance(minutes=2)
    session_service.session_capture(
        "Maybe try Privia",
        clock=clock,
        sessions_dir=sessions,
        inbox_path=studio["inbox"],
    )
    inbox = load_inbox(studio["inbox"])
    assert inbox.items[0].id == "CAP-001"

    clock.advance(minutes=3)
    session_service.complete_task(
        "RIG-001",
        clock=clock,
        sessions_dir=sessions,
        todo_path=studio["todo"],
        render=False,
    )
    todo = load_todo(studio["todo"])
    assert todo.task_map()["RIG-001"].status == TodoStatus.DONE
    assert "RIG-001" not in todo.next_session

    active = session_service.require_active(sessions)
    types = [e.type.value for e in active.events]
    assert types == ["TODO_STARTED", "CAPTURE", "TODO_COMPLETED"]


def test_session_abort_and_list(studio):
    clock = studio["clock"]
    sessions = studio["sessions"]
    session_service.start_session("free", clock=clock, sessions_dir=sessions)
    clock.advance(minutes=5)
    aborted = session_service.abort_session(clock=clock, sessions_dir=sessions)
    assert aborted.status.value == "ABORTED"
    assert aborted.events == []
    listed = session_service.list_sessions(limit=5, sessions_dir=sessions)
    assert listed[0].id == aborted.id


def test_change_capture_and_session_link(studio):
    clock = studio["clock"]
    sessions = studio["sessions"]
    session_service.start_session("focus", clock=clock, sessions_dir=sessions)
    clock.advance(minutes=1)
    record = change_service.create_change(
        "Moved TR-2 after PH-3",
        category=ChangeCategory.PEDAL_CHAIN,
        clock=clock,
        changes_path=studio["changes"],
        sessions_dir=sessions,
    )
    assert record.id == "CHG-001"
    assert record.status == ChangeStatus.OPEN
    assert record.session_id == "SES-20260910-223500"
    active = session_service.require_active(sessions)
    assert active.events[-1].change_id == "CHG-001"

    open_items = change_service.list_changes(changes_path=studio["changes"])
    assert len(open_items) == 1

    updated, changed = change_service.set_change_status(
        "CHG-001", ChangeStatus.APPLIED, changes_path=studio["changes"]
    )
    assert changed and updated.status == ChangeStatus.APPLIED
    assert change_service.list_changes(changes_path=studio["changes"]) == []

    with pytest.raises(StoreError):
        change_service.create_change(
            "   ",
            category=ChangeCategory.OTHER,
            changes_path=studio["changes"],
            sessions_dir=sessions,
            link_session=False,
        )
    with pytest.raises(StoreError):
        change_service.parse_category("NOPE")


def test_change_failed_write_does_not_corrupt(studio, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("music_rig.change_service.write_documents", boom)
    with pytest.raises(StoreError):
        change_service.create_change(
            "x",
            category=ChangeCategory.OTHER,
            changes_path=studio["changes"],
            link_session=False,
        )
    assert load_changes(studio["changes"]).items == []


def test_views_from_fixtures(studio):
    text = format_channels(channel_map_path=studio["channel_map"])
    assert "TASCAM" in text
    assert "Alesis" in text
    assert "1/2" in text or "1/2" in text.replace(" ", "")
    tascam = format_channels(device="tascam", channel_map_path=studio["channel_map"])
    assert "Alesis Mixer" not in tascam
    alesis = format_channels(device="alesis", channel_map_path=studio["channel_map"])
    assert "TASCAM" not in alesis

    listing = format_patchbay_list(patchbays_path=studio["patchbays"])
    assert "PB-B" in listing
    assert "unknown modes" in listing

    detail = format_patchbay("PB-B", patchbays_path=studio["patchbays"])
    assert "miniKORG" in detail
    assert "UNKNOWN" in detail
    unknown = format_patchbay(
        "PB-B", unknown_only=True, patchbays_path=studio["patchbays"]
    )
    assert "Verified" not in unknown
    assert "miniKORG" in unknown

    paths = format_path_list(routing_path=studio["routing"])
    assert "space" in paths
    header, tree = path_tree_for("space", routing_path=studio["routing"])
    rendered = tree.__rich__() if False else str(tree)
    # Use console render
    from rich.console import Console

    buf = Console(record=True, width=80)
    buf.print(tree)
    out = buf.export_text()
    assert "SY-1" in out
    assert "UNKNOWN" in out
    assert "PH-3" in out


def test_doctor_and_status(studio, monkeypatch):
    text = build_doctor_text(
        todo_path=studio["todo"],
        wishlist_path=studio["wish"],
        inbox_path=studio["inbox"],
        changes_path=studio["changes"],
        questions_path=studio["questions"],
        sessions_dir=studio["sessions"],
        patchbays_path=studio["patchbays"],
        docs_todo=studio["docs_todo"],
        docs_wishlist=studio["docs_wish"],
        docs_questions=studio["docs_q"],
    )
    assert "RIG DOCTOR" in text
    assert "OPEN change" not in text or "No OPEN change" in text
    assert "UNKNOWN" in text

    change_service.create_change(
        "x",
        category=ChangeCategory.OTHER,
        changes_path=studio["changes"],
        link_session=False,
    )
    from music_rig import inbox_service

    inbox_service.capture_text("cap", inbox_path=studio["inbox"])
    session_service.start_session(
        "x", clock=studio["clock"], sessions_dir=studio["sessions"]
    )
    text2 = build_doctor_text(
        todo_path=studio["todo"],
        wishlist_path=studio["wish"],
        inbox_path=studio["inbox"],
        changes_path=studio["changes"],
        questions_path=studio["questions"],
        sessions_dir=studio["sessions"],
        patchbays_path=studio["patchbays"],
        docs_todo=studio["docs_todo"],
        docs_wishlist=studio["docs_wish"],
        docs_questions=studio["docs_q"],
    )
    assert "OPEN change" in text2
    assert "OPEN inbox" in text2
    assert "Active session" in text2

    monkeypatch.setattr(
        "music_rig.doctor.git_summary", lambda: (None, None)
    )
    text3 = build_doctor_text(
        todo_path=studio["todo"],
        wishlist_path=studio["wish"],
        inbox_path=studio["inbox"],
        changes_path=studio["changes"],
        questions_path=studio["questions"],
        sessions_dir=studio["sessions"],
        patchbays_path=studio["patchbays"],
        docs_todo=studio["docs_todo"],
        docs_wishlist=studio["docs_wish"],
        docs_questions=studio["docs_q"],
    )
    assert "Git status unavailable" in text3

    before = studio["changes"].read_text(encoding="utf-8")
    build_doctor_text(
        todo_path=studio["todo"],
        wishlist_path=studio["wish"],
        inbox_path=studio["inbox"],
        changes_path=studio["changes"],
        questions_path=studio["questions"],
        sessions_dir=studio["sessions"],
        patchbays_path=studio["patchbays"],
        docs_todo=studio["docs_todo"],
        docs_wishlist=studio["docs_wish"],
        docs_questions=studio["docs_q"],
    )
    assert studio["changes"].read_text(encoding="utf-8") == before


def test_check_warns_open_changes(studio):
    from music_rig.checks import run_checks
    from music_rig.render import render_docs

    render_docs(
        todo_path=studio["todo"],
        wishlist_path=studio["wish"],
        questions_path=studio.get("questions"),
        docs_todo=studio["docs_todo"],
        docs_wishlist=studio["docs_wish"],
        docs_questions=studio.get("docs_q"),
        write=True,
    )
    change_service.create_change(
        "moved",
        category=ChangeCategory.PEDAL_CHAIN,
        changes_path=studio["changes"],
        link_session=False,
    )
    result = run_checks(
        todo_path=studio["todo"],
        wishlist_path=studio["wish"],
        inbox_path=studio["inbox"],
        changes_path=studio["changes"],
        questions_path=studio.get("questions"),
        docs_todo=studio["docs_todo"],
        docs_wishlist=studio["docs_wish"],
        docs_questions=studio.get("docs_q"),
    )
    assert result.ok
    assert any("OPEN" in w for w in result.warnings)


def test_no_hardcoded_production_topology_in_views():
    source = Path("src/music_rig/rig_views.py").read_text(encoding="utf-8")
    for needle in ("JOYO SEND B", "BOSS OD-1", "miniKORG L/MONO", "PH-3"):
        assert needle not in source


def test_cli_session_help():
    result = runner.invoke(app, ["session", "--help"])
    assert result.exit_code == 0
    assert "start" in result.stdout
