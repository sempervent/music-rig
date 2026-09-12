"""Home screen — sectioned domain navigation with live counts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from music_rig.tui.navigation import home_rows


class HomeScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "open", "Open"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("q", "quit_app", "Quit"),
        Binding("question_mark", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="home-body"):
            yield Static("music-rig — Interactive TUI", id="home-title")
            yield Static(
                "✎ editable · derived views read-only · mutations via services · Ctrl+S apply",
                id="home-subtitle",
            )
            yield DataTable(id="home-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#home-table", DataTable)
        table.add_columns("Section", "Domain", "Count")
        table.focus()
        self._reload()

    def _reload(self) -> None:
        table = self.query_one("#home-table", DataTable)
        table.clear()
        self._keys: list[str] = []
        last_section = None
        for section, key, label, count in home_rows():
            section_cell = section if section != last_section else ""
            last_section = section
            table.add_row(section_cell, label, count)
            self._keys.append(key)

    def action_refresh(self) -> None:
        self._reload()
        self.notify("Refreshed")

    def action_cursor_down(self) -> None:
        self.query_one("#home-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#home-table", DataTable).action_cursor_up()

    def action_open(self) -> None:
        table = self.query_one("#home-table", DataTable)
        if not self._keys:
            return
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._keys):
            return
        self.app.open_domain(self._keys[row])  # type: ignore[attr-defined]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_open()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_help(self) -> None:
        from music_rig.tui.dialogs import HelpScreen

        self.app.push_screen(
            HelpScreen(
                "j/k or arrows  navigate\n"
                "Enter          open domain\n"
                "Ctrl+r / r     refresh counts\n"
                "?              help\n"
                "q              quit\n\n"
                "✎ marks editable domains. Derived: Doctor/Status/Reconcile/Automation.\n"
                "In editors: e edit, Ctrl+S review/apply. Questions: r=Resolve."
            )
        )
