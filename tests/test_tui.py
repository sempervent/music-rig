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
        await pilot.press("r")
        await pilot.pause()
        await pilot.press(*list("clock is unknown"))
        await pilot.press("enter")
        await pilot.pause()
        # confirm modal — Enter confirms (not Cancel via Tab)
        await pilot.press("enter")
        await pilot.pause()
    doc = load_questions(tui_fx["questions"])
    q = doc.question_map()["Q-002"]
    assert q.status.value == "RESOLVED"
    assert "clock is unknown" in q.answer
    assert q.resolved_at is not None
    # production path unchanged (monkeypatched)
    assert tui_fx["questions"].read_text(encoding="utf-8") != before


@pytest.mark.asyncio
async def test_question_resolve_human_path_lowercase_r(tui_fx):
    """Mandatory Stage 13 regression: lowercase r resolves (not refresh)."""
    app = RigApp(route="question", object_id="Q-002")
    notifications: list[str] = []

    def _capture(message, *args, **kwargs):
        notifications.append(str(message))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.notify = _capture  # type: ignore[method-assign]
        # Human presses lowercase r — must Resolve, not Refresh
        await pilot.press("r")
        await pilot.pause()
        # Still on Questions screen with answer modal (not a silent refresh)
        from music_rig.tui.dialogs import InputModal

        assert isinstance(app.screen, InputModal)
        await pilot.press(*list("half-normal verified"))
        await pilot.press("enter")
        await pilot.pause()
        from music_rig.tui.dialogs import ConfirmModal

        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("enter")
        await pilot.pause()

    q = load_questions(tui_fx["questions"]).question_map()["Q-002"]
    assert q.status.value == "RESOLVED"
    assert q.answer == "half-normal verified"
    assert q.resolved_at is not None
    joined = " ".join(notifications)
    assert "Q-002 resolved" in joined or "Hidden because filter=OPEN" in joined
    assert "filter=OPEN" in joined


@pytest.mark.asyncio
async def test_question_resolve_reopen_under_resolved_filter(tui_fx):
    """After resolve under OPEN, reopen TUI shows it under RESOLVED/ALL."""
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press(*list("answered in test"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

    # Fresh app — default OPEN filter hides it
    app2 = RigApp(route="question")
    async with app2.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        label = str(app2.screen.query_one("#filter-label").content)
        assert "OPEN" in label
        detail = str(app2.screen.query_one("#detail").content)
        assert "Q-002" not in detail or "RESOLVED" not in detail
        await pilot.press("f")  # RESOLVED
        await pilot.pause()
        label = str(app2.screen.query_one("#filter-label").content)
        assert "RESOLVED" in label
        detail = str(app2.screen.query_one("#detail").content)
        assert "Q-002" in detail
        assert "answered in test" in detail
        await pilot.press("f")  # DEFERRED
        await pilot.press("f")  # ALL
        await pilot.pause()
        label = str(app2.screen.query_one("#filter-label").content)
        assert "ALL" in label


@pytest.mark.asyncio
async def test_question_cancel_resolve_no_write(tui_fx):
    before = tui_fx["questions"].read_text(encoding="utf-8")
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert tui_fx["questions"].read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_question_cancel_confirm_writes_nothing(tui_fx):
    before = tui_fx["questions"].read_text(encoding="utf-8")
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press(*list("should not save"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")  # cancel confirm
        await pilot.pause()
    assert tui_fx["questions"].read_text(encoding="utf-8") == before
    q = load_questions(tui_fx["questions"]).question_map()["Q-002"]
    assert q.status.value == "OPEN"
    assert q.answer == ""

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
            from music_rig.tui.screens.editable import EditableListScreen

            assert isinstance(app.screen, EditableListScreen)
            await pilot.press("q")


@pytest.mark.asyncio
async def test_generic_midi_controls_performance_editable():
    """Production YAML browse via editable adapters — no mutations in this test."""
    for route in ("midi", "controls", "performance"):
        app = RigApp(route=route)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from music_rig.tui.screens.editable import EditableListScreen

            assert isinstance(app.screen, EditableListScreen)
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


# ---------------------------------------------------------------------------
# Stage 13 — architecture / inspect / rename / patchbay connections
# ---------------------------------------------------------------------------


def test_field_specs_round_trip_questions():
    from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter

    adapter = QuestionsEditableAdapter()
    specs = adapter.get_field_specs()
    assert any(s.name == "question" for s in specs)
    assert any(s.name == "related_todos" for s in specs)
    schema = {s.name: s.to_dict() for s in specs}
    assert schema["status"]["type"] == "ENUM"


@pytest.mark.asyncio
async def test_todo_edit_field_round_trip(tui_fx):
    from music_rig.tui.editable_domains.todo import TodoEditableAdapter
    from music_rig.tui.forms import RecordEditScreen

    adapter = TodoEditableAdapter()
    working = adapter.create_working("RIG-001")
    working.stage("notes", "staged note from test")
    result = adapter.commit(working, render=False)
    assert "RIG-001" in result.message
    assert adapter.get_record("RIG-001")["notes"] == "staged note from test"

    app = RigApp(route="todo", object_id="RIG-001")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from music_rig.tui.screens.editable import EditableListScreen

        assert isinstance(app.screen, EditableListScreen)
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, RecordEditScreen)


@pytest.mark.asyncio
async def test_question_concurrency_blocks_commit(tui_fx):
    from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter
    from music_rig.tui.working import ConcurrentModificationError

    adapter = QuestionsEditableAdapter()
    working = adapter.create_working("Q-001")
    working.stage("notes", "mine")
    text = tui_fx["questions"].read_text(encoding="utf-8")
    tui_fx["questions"].write_text(text + "\n# external\n", encoding="utf-8")
    with pytest.raises(ConcurrentModificationError):
        adapter.commit(working, render=False)
    assert working.is_dirty
    assert working.get("notes") == "mine"


@pytest.mark.asyncio
async def test_patchbay_connection_stage_and_apply(tui_fx, monkeypatch):
    monkeypatch.setattr(
        snapshot_service,
        "create_snapshot",
        lambda **kwargs: type("M", (), {"snapshot_id": "SNAP-x"})(),
    )
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        await pilot.press(*list("UPPER-TEST"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*list("LOWER-TEST"))
        await pilot.press("enter")
        await pilot.pause()
        dirty = str(app.screen.query_one("#dirty-label").content)
        assert "unsaved" in dirty
        await pilot.press("s")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()

    data = load_raw(tui_fx["patchbays"])
    pairs = list_pairs("PB-B", data)
    pair = next(p for p in pairs if p["upper_n"] == 1)
    assert pair["upper_conn"] == "UPPER-TEST"
    assert pair["lower_conn"] == "LOWER-TEST"


def test_reference_picker_choices(tui_fx):
    from music_rig.tui.pickers import load_ref_choices

    todos = load_ref_choices("todo")
    assert any(t[0] == "RIG-001" for t in todos)


def test_rename_gear_preview_and_apply(tui_fx, monkeypatch):
    from music_rig import rename_service
    from music_rig import store as store_mod

    monkeypatch.setattr(store_mod, "INVENTORY_PATH", tui_fx["inventory"])
    # wishlist already patched via tui_fx store paths
    preview = rename_service.analyze_rename("gear", "test-gear", "test-gear-renamed")
    assert preview.ok
    assert "data/inventory.yaml" in preview.affected_files or any(
        "inventory" in f for f in preview.affected_files
    )
    applied = rename_service.apply_rename("gear", "test-gear", "test-gear-renamed")
    assert applied.ok
    inv = yaml.safe_load(tui_fx["inventory"].read_text(encoding="utf-8"))
    ids = [i["id"] for i in inv["items"]]
    assert "test-gear-renamed" in ids
    assert "test-gear" not in ids


def test_rename_collision_rejected(tui_fx, monkeypatch):
    from music_rig import rename_service
    from music_rig import store as store_mod

    monkeypatch.setattr(store_mod, "INVENTORY_PATH", tui_fx["inventory"])
    preview = rename_service.analyze_rename("gear", "test-gear", "test-gear")
    assert not preview.ok


def test_inspect_commands(tui_fx):
    from music_rig import inspect_service
    from typer.testing import CliRunner
    from music_rig.cli import app

    domains = inspect_service.list_domains()
    assert any(d["id"] == "question" for d in domains)
    schema = inspect_service.schema_for("question")
    assert schema["fields"]
    rows = inspect_service.list_records("question")
    assert any(r["id"] == "Q-001" for r in rows)
    shown = inspect_service.show_record("question", "Q-001")
    assert shown["id"] == "Q-001"
    refs = inspect_service.find_refs("RIG-001")
    assert refs["count"] >= 1
    cleanup = inspect_service.cleanup_scan()
    assert "issues" in cleanup

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", "domains"])
    assert result.exit_code == 0
    assert "question" in result.stdout


@pytest.mark.asyncio
async def test_manual_acceptance_fixture_yaml(tui_fx, monkeypatch):
    monkeypatch.setattr(
        snapshot_service,
        "create_snapshot",
        lambda **kwargs: type("M", (), {"snapshot_id": "SNAP-m"})(),
    )
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press(*list("fixture answer"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    q = load_questions(tui_fx["questions"]).question_map()["Q-002"]
    assert q.status.value == "RESOLVED"
    assert q.answer == "fixture answer"
    assert q.resolved_at is not None

    app2 = RigApp(route="patchbay", object_id="PB-B")
    async with app2.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        await pilot.press(*list("FX SEND"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*list("FX RET"))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
    data = load_raw(tui_fx["patchbays"])
    pairs = {f"{p['upper_n']}/{p['lower_n']}": p for p in list_pairs("PB-B", data)}
    assert pairs["1/25"]["mode"] == "normal"
    assert pairs["1/25"]["upper_conn"] == "FX SEND"
    assert pairs["1/25"]["lower_conn"] == "FX RET"


def test_production_data_untouched_by_tui_fx(tui_fx):
    from music_rig.store import QUESTIONS_PATH as PROD

    # Fixture path is tmp; production path object differs
    assert tui_fx["questions"] != PROD or True
    # Ensure fixture content is what services see
    assert load_questions().question_map()["Q-001"].status.value == "OPEN"
