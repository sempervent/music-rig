"""Scrollable text view for doctor/status/reconcile (also usable standalone)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static
from music_rig.tui.header import RigHeader


class TextViewScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, title: str, text_fn) -> None:
        super().__init__()
        self._title = title
        self._text_fn = text_fn

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        with VerticalScroll():
            yield Static(self._title, id="screen-title")
            yield Static("", id="text-body")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()

    def action_refresh(self) -> None:
        self.query_one("#text-body", Static).update(self._text_fn())

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        from music_rig.tui.dialogs import HelpScreen

        self.app.push_screen(HelpScreen("r refresh · Esc/q back"))
