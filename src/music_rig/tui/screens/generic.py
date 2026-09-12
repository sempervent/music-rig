"""Generic read-only list/detail screen driven by DomainAdapter."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from music_rig.store import StoreError
from music_rig.tui.adapters.base import SimpleAdapter
from music_rig.tui.dialogs import HelpScreen, InputModal


class ListDetailScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "inspect", "Inspect", show=False),
        Binding("slash", "search", "Search"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(
        self,
        adapter: SimpleAdapter,
        *,
        initial_id: str | None = None,
    ) -> None:
        super().__init__()
        self.adapter = adapter
        self._initial_id = initial_id
        self._search = ""
        self._row_ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(self.adapter.label, id="screen-title")
            with Horizontal(id="split"):
                yield DataTable(id="list-table", cursor_type="row")
                with VerticalScroll(id="detail-pane"):
                    yield Static("Select a row", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.add_columns(*self.adapter.columns)
        table.focus()
        self.reload(select_id=self._initial_id)

    def on_key(self, event) -> None:
        for action in self.adapter.actions():
            if action.key and event.key == action.key:
                event.stop()
                self._run_adapter_action(action.id)
                return

    def reload(self, select_id: str | None = None) -> None:
        table = self.query_one("#list-table", DataTable)
        table.clear()
        self._row_ids = []
        needle = self._search.casefold()
        for row in self.adapter.rows():
            if needle and needle not in row.search_text.casefold() and needle not in row.id.casefold():
                continue
            table.add_row(*row.cells)
            self._row_ids.append(row.id)
        if select_id and select_id in self._row_ids:
            table.move_cursor(row=self._row_ids.index(select_id))
        self._update_detail()

    def _selected_id(self) -> str | None:
        table = self.query_one("#list-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._row_ids):
            return None
        return self._row_ids[row]

    def _update_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        row_id = self._selected_id()
        if row_id is None:
            detail.update("Select a row")
            return
        detail.update(self.adapter.detail(row_id))

    def action_cursor_down(self) -> None:
        self.query_one("#list-table", DataTable).action_cursor_down()
        self._update_detail()

    def action_cursor_up(self) -> None:
        self.query_one("#list-table", DataTable).action_cursor_up()
        self._update_detail()

    def action_inspect(self) -> None:
        self._update_detail()

    @on(DataTable.RowHighlighted)
    def _on_highlight(self) -> None:
        self._update_detail()

    def action_refresh(self) -> None:
        self.reload(select_id=self._selected_id())
        self.notify("Refreshed")

    def action_search(self) -> None:
        def _done(value: str | None) -> None:
            if value is None:
                return
            self._search = value
            self.reload()

        self.app.push_screen(
            InputModal("Search", placeholder="filter…", default=self._search, allow_empty=True),
            _done,
        )

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        action_lines = "\n".join(
            f"{a.key or '—':<4} {a.label}" for a in self.adapter.actions()
        )
        self.app.push_screen(
            HelpScreen(
                f"{self.adapter.label} (read-only)\n\n"
                "j/k  navigate\n"
                "/    search\n"
                "Ctrl+r refresh\n"
                "Esc/q back\n"
                f"{action_lines}"
            )
        )

    def _run_adapter_action(self, action_id: str) -> None:
        meta = next((a for a in self.adapter.actions() if a.id == action_id), None)
        row_id = self._selected_id()
        if meta and meta.needs_selection and not row_id:
            self.notify("Select a row first", severity="warning")
            return
        try:
            msg = self.adapter.run_action(action_id, row_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        if msg:
            self.notify(msg)
        self.reload(select_id=row_id)
