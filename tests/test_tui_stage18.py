"""Stage 18 — TUI reliability, Answer UX, patchbay MODE, Vim modes, Add, round-trips.

Fixture-only mutations. Never touches production data/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from music_rig import store
from music_rig.patchbay_state import list_pairs, load_raw
from music_rig.store import StoreError, load_questions
from music_rig.tui.app import RigApp
from music_rig.tui.editable_domains import registry
from music_rig.tui.modes import EditorMode, parse_command
from music_rig.tui.save_outcome import SaveOutcome
from music_rig.tui.working import ConcurrentModificationError, WorkingDocument


# ---------------------------------------------------------------------------
# Question answer persistence + visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_answer_persists_and_question_visible(tui_fx):
    """Mandatory: answer → YAML; reopen shows answer; question text visible during answer."""
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        from music_rig.tui.screens.answer import AnswerScreen

        assert isinstance(app.screen, AnswerScreen)
        ctx = str(app.screen.query_one("#answer-context").content)
        assert "Unrelated MIDI clock?" in ctx
        assert "Q-002" in ctx
        await pilot.press(*list("visible-answer-persist"))
        await pilot.press("ctrl+s")
        await pilot.pause()

    q = load_questions(tui_fx["questions"]).question_map()["Q-002"]
    assert q.answer == "visible-answer-persist"
    assert q.status.value == "OPEN"
    assert q.verification_result is None

    app2 = RigApp(route="question", object_id="Q-002")
    async with app2.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        detail = str(app2.screen.query_one("#detail").content)
        assert "visible-answer-persist" in detail
        assert "Unrelated MIDI clock?" in detail


@pytest.mark.asyncio
async def test_resolve_does_not_invent_verification_result(tui_fx):
    app = RigApp(route="question", object_id="Q-002")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press(*list("resolved-only"))
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    q = load_questions(tui_fx["questions"]).question_map()["Q-002"]
    assert q.status.value == "RESOLVED"
    assert q.answer == "resolved-only"
    assert q.verification_result is None


# ---------------------------------------------------------------------------
# Patchbay MODE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patchbay_mode_persist_and_reopen(tui_fx, monkeypatch):
    monkeypatch.setattr(
        "music_rig.snapshot_service.create_snapshot",
        lambda **kwargs: type("M", (), {"snapshot_id": "SNAP-x"})(),
    )
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        from music_rig.tui.dialogs import SelectModeModal

        assert isinstance(app.screen, SelectModeModal)
        await pilot.press("enter")
        await pilot.pause()
        dirty = str(app.screen.query_one("#dirty-label").content)
        assert "unsaved" in dirty
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()

    data = load_raw(tui_fx["patchbays"])
    pairs = {f"{p['upper_n']}/{p['lower_n']}": p for p in list_pairs("PB-B", data)}
    assert pairs["1/25"]["mode"] == "normal"

    app2 = RigApp(route="patchbay", object_id="PB-B")
    async with app2.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        detail = str(app2.screen.query_one("#detail").content)
        assert "normal" in detail.lower()


@pytest.mark.asyncio
async def test_patchbay_space_cycles_mode_staged(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        before = tui_fx["patchbays"].read_text(encoding="utf-8")
        await pilot.press("space")
        await pilot.pause()
        dirty = str(app.screen.query_one("#dirty-label").content)
        assert "unsaved" in dirty
        assert tui_fx["patchbays"].read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_select_mode_modal_enter_esc(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        from music_rig.tui.dialogs import SelectModeModal

        assert isinstance(app.screen, SelectModeModal)
        await pilot.press("escape")
        await pilot.pause()
        from music_rig.tui.screens.patchbays import PatchbayEditorScreen

        assert isinstance(app.screen, PatchbayEditorScreen)


@pytest.mark.asyncio
async def test_patchbay_related_question_shows_text(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        detail = str(app.screen.query_one("#detail").content)
        assert "Q-001" in detail
        assert "What mode is PB-B 1/25?" in detail


# ---------------------------------------------------------------------------
# Generic edit round-trips
# ---------------------------------------------------------------------------


def test_round_trip_todo_wishlist_gear(tui_fx):
    from music_rig.tui.editable_domains.todo import TodoEditableAdapter
    from music_rig.tui.editable_domains.planning import WishlistEditableAdapter
    from music_rig.tui.editable_domains.current import GearEditableAdapter
    from music_rig.models import WishPriority, WishStatus, WishlistItem
    from music_rig import wishlist_service

    todo = TodoEditableAdapter()
    w = todo.create_working("RIG-001")
    w.stage("notes", "stage18-todo-note")
    todo.commit(w, render=False)
    assert todo.get_record("RIG-001")["notes"] == "stage18-todo-note"

    wishlist_service.add_wish(
        WishlistItem(
            item="Stage18 Wish",
            category="test",
            problem_capability="round-trip",
            priority=WishPriority.P2,
            status=WishStatus.IDEA,
        ),
        render=False,
    )
    wish = WishlistEditableAdapter()
    ww = wish.create_working("Stage18 Wish")
    ww.stage("notes", "stage18-wish-note")
    wish.commit(ww, render=False)
    assert wish.get_record("Stage18 Wish")["notes"] == "stage18-wish-note"

    gear = GearEditableAdapter()
    gw = gear.create_working("test-gear")
    gw.stage("notes", "stage18-gear-note")
    gear.commit(gw, render=False)
    assert gear.get_record("test-gear")["notes"] == "stage18-gear-note"


def test_round_trip_controller_ableton_performance_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fixture copies under tmp — assert production hashes unchanged."""
    root = Path(__file__).resolve().parents[1]
    prod_hashes = {
        name: (root / "data" / name).read_bytes()
        for name in (
            "controllers.yaml",
            "ableton.yaml",
            "performance.yaml",
            "backups.yaml",
            "inventory.yaml",
            "midi.yaml",
        )
    }
    for name in prod_hashes:
        shutil.copy(root / "data" / name, tmp_path / name)

    import music_rig.control_state as cs
    import music_rig.performance_state as ps
    import music_rig.backup_state as bs
    import music_rig.current_service as cur
    import music_rig.inventory_state as inv_state
    import music_rig.midi_state as midi_state

    path_map = {
        "CONTROLLERS_PATH": tmp_path / "controllers.yaml",
        "ABLETON_PATH": tmp_path / "ableton.yaml",
        "PERFORMANCE_PATH": tmp_path / "performance.yaml",
        "BACKUPS_PATH": tmp_path / "backups.yaml",
        "INVENTORY_PATH": tmp_path / "inventory.yaml",
        "MIDI_PATH": tmp_path / "midi.yaml",
    }
    for attr, path in path_map.items():
        monkeypatch.setattr(store, attr, path)
    monkeypatch.setattr(cs, "CONTROLLERS_PATH", path_map["CONTROLLERS_PATH"])
    monkeypatch.setattr(ps, "PERFORMANCE_PATH", path_map["PERFORMANCE_PATH"])
    monkeypatch.setattr(bs, "BACKUPS_PATH", path_map["BACKUPS_PATH"])
    monkeypatch.setattr(cur, "CONTROLLERS_PATH", path_map["CONTROLLERS_PATH"])
    monkeypatch.setattr(cur, "PERFORMANCE_PATH", path_map["PERFORMANCE_PATH"])
    monkeypatch.setattr(cur, "INVENTORY_PATH", path_map["INVENTORY_PATH"])
    monkeypatch.setattr(cur, "MIDI_PATH", path_map["MIDI_PATH"], raising=False)
    monkeypatch.setattr(inv_state, "INVENTORY_PATH", path_map["INVENTORY_PATH"], raising=False)
    monkeypatch.setattr(midi_state, "MIDI_PATH", path_map["MIDI_PATH"], raising=False)
    monkeypatch.setattr("music_rig.render.render_docs", lambda **kw: (False, []))

    from music_rig.tui.editable_domains.current import (
        AbletonEditableAdapter,
        BackupEditableAdapter,
        ControllersEditableAdapter,
        PerformanceEditableAdapter,
    )

    controls = ControllersEditableAdapter()
    rows = controls.list_records()
    assert rows
    rid = rows[0]["id"]
    w = controls.create_working(rid)
    before_ev = w.baseline.get("evidence") or "INTENDED"
    after_ev = "UNKNOWN" if before_ev != "UNKNOWN" else "INTENDED"
    w.stage("evidence", after_ev)
    controls.commit(w, render=False)
    assert controls.get_record(rid)["evidence"] == after_ev

    ableton_ad = AbletonEditableAdapter()
    arows = ableton_ad.list_records()
    assert arows
    aid = arows[0]["id"]
    aw = ableton_ad.create_working(aid)
    aw.stage("notes", "stage18-abl")
    ableton_ad.commit(aw, render=False)
    assert ableton_ad.get_record(aid)["notes"] == "stage18-abl"

    perf = PerformanceEditableAdapter()
    prows = [r for r in perf.list_records() if str(r["id"]).startswith("bindings:")]
    assert prows
    pid = prows[0]["id"]
    pw = perf.create_working(pid)
    before_pev = str(pw.baseline.get("evidence") or "INTENDED")
    after_pev = "VERIFIED" if "VERIFIED" not in before_pev else "INTENDED"
    pw.stage("evidence", after_pev)
    perf.commit(pw, render=False)
    assert after_pev in str(perf.get_record(pid)["evidence"])

    backup = BackupEditableAdapter()
    brows = backup.list_records()
    assert brows
    bid = brows[0]["id"]
    bw = backup.create_working(bid)
    bw.stage("notes", "stage18-bak")
    backup.commit(bw, render=False)
    assert backup.get_record(bid)["notes"] == "stage18-bak"

    for name, before in prod_hashes.items():
        assert (root / "data" / name).read_bytes() == before, f"production {name} mutated"



# ---------------------------------------------------------------------------
# Add flows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_question_todo_wish_inbox_change_gear(tui_fx):
    from music_rig.tui.screens.create import (
        AddChangeModal,
        AddGearModal,
        AddInboxModal,
        AddQuestionModal,
        AddTodoModal,
        AddWishModal,
    )

    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        assert isinstance(app.screen, AddQuestionModal)
        await pilot.press(*list("Added via Stage18?"))
        await pilot.click("#confirm")
        await pilot.pause()
    assert "Q-003" in load_questions().question_map()

    app = RigApp(route="todo")
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        assert isinstance(app.screen, AddTodoModal)
        await pilot.press(*list("Stage18 todo task"))
        await pilot.click("#confirm")
        await pilot.pause()
    todo_ids = [
        t["id"]
        for t in yaml.safe_load(tui_fx["todo"].read_text(encoding="utf-8"))["tasks"]
    ]
    assert "RIG-002" in todo_ids

    app = RigApp(route="wish")
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        assert isinstance(app.screen, AddWishModal)
        await pilot.press(*list("Wish Stage18"))
        app.screen.query_one("#add-problem_capability").value = "capability"
        await pilot.click("#confirm")
        await pilot.pause()
    wish_names = [
        i["item"]
        for i in yaml.safe_load(tui_fx["wish"].read_text(encoding="utf-8"))["items"]
    ]
    assert "Wish Stage18" in wish_names

    app = RigApp(route="inbox")
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        assert isinstance(app.screen, AddInboxModal)
        await pilot.press(*list("inbox capture stage18"))
        await pilot.click("#confirm")
        await pilot.pause()
    inbox = yaml.safe_load(tui_fx["inbox"].read_text(encoding="utf-8"))
    assert any("inbox capture stage18" in (i.get("text") or "") for i in inbox.get("items") or [])

    app = RigApp(route="changes")
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        assert isinstance(app.screen, AddChangeModal)
        await pilot.press(*list("Changed something stage18"))
        await pilot.click("#confirm")
        await pilot.pause()
    changes = yaml.safe_load(tui_fx["changes"].read_text(encoding="utf-8"))
    assert any(str(i.get("id", "")).startswith("CHG-") for i in changes.get("items") or [])

    app = RigApp(route="gear")
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        assert isinstance(app.screen, AddGearModal)
        await pilot.press(*list("Stage18 Widget"))
        await pilot.click("#confirm")
        await pilot.pause()
    inv = yaml.safe_load(tui_fx["inventory"].read_text(encoding="utf-8"))
    assert any("Stage18 Widget" in (i.get("name") or "") for i in inv.get("items") or [])


# ---------------------------------------------------------------------------
# Vim modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vim_navigation_and_modes(tui_fx):
    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        banner = str(app.screen.query_one("#mode-banner").content)
        assert "NORMAL" in banner
        await pilot.press("j")
        await pilot.press("k")
        await pilot.press("G")
        await pilot.pause()
        await pilot.press("g")
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        from music_rig.tui.screens.answer import AnswerScreen

        assert isinstance(app.screen, AnswerScreen)
        assert "INSERT" in str(app.screen.query_one("#mode-banner").content)
        await pilot.press("j")
        assert "j" in app.screen.query_one("#answer-input").text
        await pilot.press("escape")
        await pilot.pause()
        assert "NORMAL" in str(app.screen.query_one("#mode-banner").content)


@pytest.mark.asyncio
async def test_vim_command_q_refuses_dirty_qbang_discards(tui_fx):
    before = tui_fx["patchbays"].read_text(encoding="utf-8")
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        from music_rig.tui.dialogs import CommandLineModal

        assert isinstance(app.screen, CommandLineModal)
        app.screen.query_one("#modal-input").value = ":q"
        await pilot.press("enter")
        await pilot.pause()
        from music_rig.tui.screens.patchbays import PatchbayEditorScreen

        assert isinstance(app.screen, PatchbayEditorScreen)
        await pilot.press("colon")
        await pilot.pause()
        app.screen.query_one("#modal-input").value = ":q!"
        await pilot.press("enter")
        await pilot.pause()
    assert tui_fx["patchbays"].read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_vim_undo_staged(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert "unsaved" in str(app.screen.query_one("#dirty-label").content)
        await pilot.press("u")
        await pilot.pause()
        dirty = str(app.screen.query_one("#dirty-label").content)
        assert "unsaved" not in dirty


def test_working_document_undo_redo():
    doc = WorkingDocument({"a": 1})
    doc.stage("x", 1)
    doc.stage("y", 2)
    assert doc.undo()
    assert "y" not in doc.mutations
    assert doc.redo()
    assert doc.get("y") == 2


def test_parse_command_aliases():
    assert parse_command(":w")[0] == "write"
    assert parse_command(":q!")[0] == "quit!"
    assert parse_command(":wq")[0] == "wq"


# ---------------------------------------------------------------------------
# Failed save + concurrent modification
# ---------------------------------------------------------------------------


def test_failed_commit_retains_mutations(tui_fx, monkeypatch):
    from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter

    adapter = QuestionsEditableAdapter()
    working = adapter.create_working("Q-001")
    working.stage("notes", "keep-me")

    def boom(*a, **k):
        raise StoreError("simulated failure")

    monkeypatch.setattr("music_rig.question_service.update_question_fields", boom)
    with pytest.raises(StoreError):
        adapter.commit(working, render=False)
    assert working.is_dirty
    assert working.get("notes") == "keep-me"


def test_concurrent_modification_retains(tui_fx):
    from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter

    adapter = QuestionsEditableAdapter()
    working = adapter.create_working("Q-001")
    working.stage("notes", "mine")
    text = tui_fx["questions"].read_text(encoding="utf-8")
    tui_fx["questions"].write_text(text + "\n# external\n", encoding="utf-8")
    with pytest.raises(ConcurrentModificationError):
        adapter.commit(working, render=False)
    assert working.is_dirty
    assert working.get("notes") == "mine"


# ---------------------------------------------------------------------------
# Registry / bindings / debug
# ---------------------------------------------------------------------------


def test_registry_every_editable_has_adapter_and_coverage():
    domains = registry.editable_domains_with_adapters()
    for key in domains:
        cov = registry.coverage_for(key)
        assert cov is not None, f"missing coverage marker for {key}"
        assert cov["view"] == "yes"
        assert cov["round_trip"] in {"yes", "partial"}
        assert cov["vim_modal"] == "yes"
        if key == "patchbay":
            continue
        assert registry.get_adapter(key) is not None, f"missing adapter for {key}"


def test_save_outcome_enum():
    assert SaveOutcome.SUCCESS.ok
    assert not SaveOutcome.FAILED.ok


def test_ctrl_s_binding_has_priority():
    from music_rig.tui.forms import RecordEditScreen
    from music_rig.tui.editable_domains.todo import TodoEditableAdapter

    bindings = RecordEditScreen(TodoEditableAdapter(), "RIG-001").BINDINGS
    ctrl_s = [b for b in bindings if getattr(b, "key", None) == "ctrl+s"]
    assert ctrl_s and ctrl_s[0].priority is True


@pytest.mark.asyncio
async def test_mode_banner_on_editable(tui_fx):
    app = RigApp(route="todo")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        banner = str(app.screen.query_one("#mode-banner").content)
        assert EditorMode.NORMAL.value in banner


def test_debug_format_error():
    from music_rig.tui.debug import format_error, set_debug, is_debug

    set_debug(False)
    assert "boom" in format_error(RuntimeError("boom"))
    set_debug(True)
    assert is_debug()
    assert "boom" in format_error(RuntimeError("boom"))
    set_debug(False)


def test_cli_tui_debug_flag():
    from typer.testing import CliRunner
    from music_rig.cli import app

    result = CliRunner().invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
    assert "--debug" in result.stdout
