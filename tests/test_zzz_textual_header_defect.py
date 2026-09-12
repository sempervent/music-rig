"""Documents Textual 8.2.8 stock Header lifecycle defect (runs last by filename)."""

from __future__ import annotations

import gc
import warnings

import pytest
from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


@pytest.mark.asyncio
async def test_stock_header_race_documents_textual_defect():
    """Stock Textual Header races on title churn (NoMatches and/or unawaited set_title)."""

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
