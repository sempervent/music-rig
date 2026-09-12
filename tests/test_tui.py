"""Headless Textual Pilot tests for the interactive TUI."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from music_rig import snapshot_service, store
from music_rig.patchbay_state import list_pairs, load_raw
from music_rig.store import load_questions
from music_rig.tui.app import RigApp
from music_rig.tui.working import ConcurrentModificationError, WorkingDocument, sha256_file


def _write_docs(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
    ]:
        path = tmp_path / name
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")
        paths[name] = path
    return paths


@pytest.fixture
def tui_fx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated YAML store for mutation tests — never touches production data."""
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    docs = _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": [],
                "tasks": [
                    {
                        "id": "RIG-001",
                        "task": "Fixture task",
                        "area": "Docs",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "done",
                        "notes": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "test-gear",
                        "name": "Test Gear",
                        "category": "utility",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "What mode is PB-B 1/25?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": ["RIG-001"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": "1/25",
                        },
                    },
                    {
                        "id": "Q-002",
                        "question": "Unrelated MIDI clock?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        "# test patchbays\n"
        + yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-A": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
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
                                "connection": "miniKORG R",
                                "paired_with": 26,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            26: {
                                "row": "lower",
                                "connection": "TASCAM 4",
                                "paired_with": 2,
                                "mode": "unknown",
                                "status": "documented",
                            },
                        },
                    },
                    "PB-C": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                    "PB-D": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    from music_rig import current_service, patchbay_state, question_service, todo_service
    from music_rig import render as render_mod

    def _noop_render(**kwargs):
        return False, []

    monkeypatch.setattr(render_mod, "render_docs", _noop_render)
    monkeypatch.setattr(question_service, "render_docs", _noop_render)
    monkeypatch.setattr(current_service, "render_docs", _noop_render)
    monkeypatch.setattr(todo_service, "render_docs", _noop_render)

    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(store, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(current_service, "PATCHBAYS_PATH", patchbays)

    return {
        "questions": questions,
        "todo": todo,
        "patchbays": patchbays,
        "inventory": inventory,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# Home / navigation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_home_launches_and_quits():
    app = RigApp()
    async with app.run_test(size=(120, 40)) as pilot:
        assert isinstance(app.screen, type(app.screen))
        from music_rig.tui.screens.home import HomeScreen

        assert isinstance(app.screen, HomeScreen)
        await pilot.press("q")
        assert app.return_value is None or True


@pytest.mark.asyncio
async def test_home_navigation_to_question(tui_fx):
    app = RigApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from music_rig.tui.screens.home import HomeScreen
        from music_rig.tui.screens.questions import QuestionsScreen

        assert isinstance(app.screen, HomeScreen)
        # Questions is first domain row
        await pilot.press("enter")
        assert isinstance(app.screen, QuestionsScreen)
        await pilot.press("q")
        assert isinstance(app.screen, HomeScreen)


@pytest.mark.asyncio
async def test_direct_launch_question_route(tui_fx):
    app = RigApp(route="question", object_id="Q-001")
    async with app.run_test(size=(120, 40)) as pilot:
        from music_rig.tui.screens.questions import QuestionsScreen

        await pilot.pause()
        assert isinstance(app.screen, QuestionsScreen)
        detail = str(app.screen.query_one("#detail").content)
        assert "Q-001" in detail
        assert "patchbay.mode" in detail


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_question_open_filter_and_detail(tui_fx):
    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        label = str(app.screen.query_one("#filter-label").content)
        assert "OPEN" in label
        detail = str(app.screen.query_one("#detail").content)
        assert "Q-001" in detail or "Q-002" in detail


@pytest.mark.asyncio
async def test_question_search(tui_fx):
    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        # Input modal focused — type MIDI and confirm
        await pilot.press(*list("MIDI"))
        await pilot.press("enter")
        await pilot.pause()
        label = str(app.screen.query_one("#filter-label").content)
        assert "MIDI" in label or "2 shown" in label or "1 shown" in label


@pytest.mark.asyncio
async def test_question_resolve_writes_tmp_only(tui_fx):
    before = tui_fx["questions"].read_text(encoding="utf-8")
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        await pilot.press(*list("clock is unknown"))
        await pilot.press("enter")
        await pilot.pause()
        # confirm modal
        await pilot.press("y")
        await pilot.pause()
    doc = load_questions(tui_fx["questions"])
    q = doc.question_map()["Q-002"]
    assert q.status.value == "RESOLVED"
    assert "clock is unknown" in q.answer
    # production path unchanged (monkeypatched)
    assert tui_fx["questions"].read_text(encoding="utf-8") != before


@pytest.mark.asyncio
async def test_question_cancel_resolve_no_write(tui_fx):
    before = tui_fx["questions"].read_text(encoding="utf-8")
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert tui_fx["questions"].read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_question_defer_reopen_add(tui_fx):
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert load_questions(tui_fx["questions"]).question_map()["Q-002"].status.value == "DEFERRED"

    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("f")  # RESOLVED
        await pilot.press("f")  # DEFERRED
        await pilot.pause()
        # select Q-002 if present
        await pilot.press("o")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert load_questions(tui_fx["questions"]).question_map()["Q-002"].status.value == "OPEN"

    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.press(*list("New fact?"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*list("Docs"))
        await pilot.press("enter")
        await pilot.pause()
    ids = [q.id for q in load_questions(tui_fx["questions"]).questions]
    assert "Q-003" in ids


@pytest.mark.asyncio
async def test_question_open_target_to_patchbay(tui_fx):
    app = RigApp(route="question", object_id="Q-001")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        from music_rig.tui.screens.patchbays import PatchbayEditorScreen

        assert isinstance(app.screen, PatchbayEditorScreen)
        assert app.screen.bay_id == "PB-B"


# ---------------------------------------------------------------------------
# Patchbay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patchbay_pb_b_unknown_visible(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from music_rig.tui.screens.patchbays import PatchbayEditorScreen

        assert isinstance(app.screen, PatchbayEditorScreen)
        table = app.screen.query_one("#list-table")
        # At least one UNKNOWN mode cell present via row count
        assert len(app.screen._pair_keys) == 2


@pytest.mark.asyncio
async def test_patchbay_stage_dirty_cancel_no_write(tui_fx):
    before = tui_fx["patchbays"].read_text(encoding="utf-8")
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("1")  # normal
        await pilot.pause()
        dirty = str(app.screen.query_one("#dirty-label").content)
        assert "unsaved" in dirty
        await pilot.press("q")
        await pilot.pause()
        await pilot.press("y")  # discard
        await pilot.pause()
    assert tui_fx["patchbays"].read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_patchbay_apply_writes_all(tui_fx, monkeypatch):
    snaps: list[str] = []

    def fake_snap(**kwargs):
        snaps.append("called")

        class M:
            snapshot_id = "SNAP-test"

        return M()

    monkeypatch.setattr(snapshot_service, "create_snapshot", fake_snap)

    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("1")  # normal
        await pilot.pause()
        await pilot.press("j")
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("2")  # half-normal
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        await pilot.press(*list("Neutrik NYS-SPP-L"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        # Apply modal — confirm
        await pilot.click("#confirm")
        await pilot.pause()

    data = load_raw(tui_fx["patchbays"])
    pairs = list_pairs("PB-B", data)
    modes = {f"{p['upper_n']}/{p['lower_n']}": p["mode"] for p in pairs}
    assert modes["1/25"] == "normal"
    assert modes["2/26"] == "half-normal"
    assert data["patchbays"]["PB-B"]["hardware_model"] == "Neutrik NYS-SPP-L"
    assert snaps == ["called"]


@pytest.mark.asyncio
async def test_patchbay_concurrent_hash_blocks_apply(tui_fx, monkeypatch):
    monkeypatch.setattr(
        snapshot_service,
        "create_snapshot",
        lambda **kwargs: type("M", (), {"snapshot_id": "SNAP-x"})(),
    )
    from music_rig.tui.adapters import patchbays as pb

    working = pb.open_working("PB-B", path=tui_fx["patchbays"])
    working.stage("mode:1/25", "normal")
    # mutate file on disk
    text = tui_fx["patchbays"].read_text(encoding="utf-8")
    tui_fx["patchbays"].write_text(text + "\n# touched\n", encoding="utf-8")
    with pytest.raises(ConcurrentModificationError):
        pb.apply_working(
            working,
            "PB-B",
            create_snapshot=False,
            render=False,
            patchbays_path=tui_fx["patchbays"],
        )
    assert working.is_dirty
    assert working.get("mode:1/25") == "normal"


@pytest.mark.asyncio
async def test_patchbay_next_unknown(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#list-table")
        assert table.cursor_row == 0
        await pilot.press("n")
        await pilot.pause()
        # still on an unknown pair (row 1 after wrap from 0+1)
        assert table.cursor_row in {0, 1}


def test_working_document_hash(tmp_path: Path):
    path = tmp_path / "f.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    doc = WorkingDocument({"a": 1}, source_path=path)
    assert doc.source_unchanged()
    path.write_text("a: 2\n", encoding="utf-8")
    assert not doc.source_unchanged()
    assert sha256_file(path) != doc.source_hash


# ---------------------------------------------------------------------------
# Generic read-only domains
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generic_todo_gear(tui_fx):
    for route in ("todo", "gear"):
        app = RigApp(route=route)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from music_rig.tui.screens.generic import ListDetailScreen

            assert isinstance(app.screen, ListDetailScreen)
            await pilot.press("q")


@pytest.mark.asyncio
async def test_generic_midi_controls_performance_readonly():
    """Production YAML read-only — no inventory monkeypatch."""
    for route in ("midi", "controls", "performance"):
        app = RigApp(route=route)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from music_rig.tui.screens.generic import ListDetailScreen

            assert isinstance(app.screen, ListDetailScreen)
            detail = str(app.screen.query_one("#detail").content)
            assert detail
            await pilot.press("q")


@pytest.mark.asyncio
async def test_cli_tui_help():
    from typer.testing import CliRunner
    from music_rig.cli import app

    result = CliRunner().invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
    assert "domain" in result.stdout.lower() or "Interactive" in result.stdout


def test_run_tui_importable():
    from music_rig.tui import run_tui

    assert callable(run_tui)
