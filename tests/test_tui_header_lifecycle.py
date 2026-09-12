"""Stage 19 repair — Textual Header lifecycle under rapid screen churn."""

from __future__ import annotations

import gc
import warnings

import pytest
from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from music_rig.tui.app import RigApp
from music_rig.tui.header import RigHeader
from music_rig.tui.screens.home import HomeScreen
from music_rig.tui.screens.questions import QuestionsScreen
from music_rig.tui.screens.reconcile import ReconcileScreen


@pytest.mark.filterwarnings("error::RuntimeWarning")
@pytest.mark.asyncio
async def test_header_title_churn_no_unawaited_warning():
    """Rapid push/pop + title updates must not raise RuntimeWarning/NoMatches."""

    class S(Screen):
        def compose(self) -> ComposeResult:
            yield RigHeader(show_clock=False)
            yield Static("body")
            yield Footer()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(S())

    app = A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        for i in range(80):
            app.push_screen(S())
            app.title = f"title-{i}"
            app.pop_screen()
            app.title = f"after-{i}"
        await pilot.pause()
    gc.collect()


@pytest.mark.filterwarnings("error::RuntimeWarning")
@pytest.mark.asyncio
async def test_rigapp_question_reconcile_churn(tui_fx):
    """Home → Questions → Reconcile → back, repeated; no Header lifecycle failure."""
    app = RigApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        for _ in range(20):
            app.open_domain("question")
            await pilot.pause()
            assert isinstance(app.screen, QuestionsScreen)
            app.open_domain("reconcile")
            await pilot.pause()
            assert isinstance(app.screen, ReconcileScreen)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            app.title = "music-rig"
            await pilot.pause()
        assert list(app.screen.query(RigHeader))
    gc.collect()


@pytest.mark.filterwarnings("error::RuntimeWarning")
@pytest.mark.asyncio
async def test_direct_routes_mount_with_rig_header(tui_fx):
    for route, oid in (
        ("question", None),
        ("reconcile", None),
        ("verify", None),
        ("todo", None),
        ("patchbay", "PB-B"),
    ):
        app = RigApp(route=route, object_id=oid)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert list(app.screen.query(RigHeader)), f"{route} missing RigHeader"
            await pilot.press("escape")
            await pilot.pause()
    gc.collect()


@pytest.mark.filterwarnings("error::RuntimeWarning")
@pytest.mark.asyncio
async def test_reconcile_e2e_return_to_questions(tui_fx):
    """FINAL unreconciled Question → Reconcile screen → back → Questions still alive."""
    from music_rig import question_service

    question_service.answer_question("Q-001", "fixture final", render=False)
    app = RigApp(route="question", object_id="Q-001")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, QuestionsScreen)
        app.open_domain("reconcile")
        await pilot.pause()
        assert isinstance(app.screen, ReconcileScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, QuestionsScreen)
        app.title = "music-rig-reconciled"
        await pilot.pause()
        assert list(app.screen.query(RigHeader))
    gc.collect()


@pytest.mark.asyncio
async def test_stock_header_race_documents_textual_defect():
    """Stock Textual Header races on title churn (NoMatches and/or unawaited set_title).

    Kept last so GC of stock-Header coroutines cannot pollute RigHeader tests.
    """

    class S(Screen):
        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("body")
            yield Footer()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(S())

    app = A()
    saw_defect = False
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", RuntimeWarning)
        try:
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                for i in range(80):
                    app.push_screen(S())
                    app.title = f"title-{i}"
                    app.pop_screen()
                    app.title = f"after-{i}"
                await pilot.pause()
        except NoMatches:
            saw_defect = True
    msgs = [str(w.message) for w in recorded if issubclass(w.category, RuntimeWarning)]
    if any("set_title" in m and "never awaited" in m for m in msgs):
        saw_defect = True
    gc.collect()
    assert saw_defect, "expected stock Header lifecycle defect under title churn"
