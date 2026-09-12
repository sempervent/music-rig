"""Generic editable list/detail screen driven by EditableDomainAdapter."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from music_rig.store import StoreError
from music_rig.tui.dialogs import ConfirmModal, HelpScreen, InputModal
from music_rig.tui.editable import BaseEditableAdapter
from music_rig.tui.forms import RecordEditScreen


class EditableListScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "inspect", "Inspect", show=False),
        Binding("e", "edit", "Edit"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("slash", "search", "Search"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(
        self,
        adapter: BaseEditableAdapter,
        *,
        initial_id: str | None = None,
    ) -> None:
        super().__init__()
        self.adapter = adapter
        self._initial_id = initial_id
        self._search = ""
        self._row_ids: list[str] = []
        cycle = adapter.filter_cycle()
        self._filter = cycle[0] if cycle else None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(f"{self.adapter.label} ✎", id="screen-title")
            yield Static("", id="filter-label")
            with Horizontal(id="split"):
                yield DataTable(id="list-table", cursor_type="row")
                with VerticalScroll(id="detail-pane"):
                    yield Static("Select a row", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.add_columns(*self.adapter.columns())
        table.focus()
        self.reload(select_id=self._initial_id)

    def on_key(self, event) -> None:
        for action_id, key, _label in self.adapter.semantic_actions():
            if key and event.key == key:
                event.stop()
                self._run_semantic(action_id)
                return

    def reload(self, select_id: str | None = None) -> None:
        table = self.query_one("#list-table", DataTable)
        table.clear()
        self._row_ids = []
        for row in self.adapter.list_records(status_filter=self._filter, search=self._search):
            table.add_row(*row["cells"])
            self._row_ids.append(row["id"])
        filt = self._filter or "ALL"
        self.query_one("#filter-label", Static).update(
            f"Filter: {filt}  ·  {len(self._row_ids)} shown"
            + (f"  ·  search: {self._search!r}" if self._search else "")
            + "  ·  e edit · Ctrl+S in form"
        )
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
        try:
            detail.update(self.adapter.detail_markdown(row_id))
        except StoreError as exc:
            detail.update(str(exc))

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

    def action_cycle_filter(self) -> None:
        cycle = self.adapter.filter_cycle()
        if not cycle:
            self.notify("No filters for this domain")
            return
        assert self._filter is not None
        idx = cycle.index(self._filter) if self._filter in cycle else 0
        self._filter = cycle[(idx + 1) % len(cycle)]
        self.reload()

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

    def action_edit(self) -> None:
        row_id = self._selected_id()
        if row_id is None:
            self.notify("Select a row first", severity="warning")
            return

        def _done(saved: bool | None) -> None:
            if saved:
                self.reload(select_id=row_id)

        self.app.push_screen(RecordEditScreen(self.adapter, row_id), _done)

    def action_refresh(self) -> None:
        self.reload(select_id=self._selected_id())
        self.notify("Refreshed")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        actions = "\n".join(f"{k:<8} {label}" for _id, k, label in self.adapter.semantic_actions())
        self.app.push_screen(
            HelpScreen(
                f"{self.adapter.label} (editable)\n\n"
                "e       edit fields (Ctrl+S review/apply)\n"
                "f       cycle filter\n"
                "/       search\n"
                "Ctrl+r  refresh\n"
                "Esc/q   back\n"
                f"{actions}\n\n"
                "Enter inspects only — does not apply mutations."
            )
        )

    def _run_semantic(self, action_id: str) -> None:
        row_id = self._selected_id()
        if row_id is None:
            self.notify("Select a row first", severity="warning")
            return

        # Changes Mark Applied needs confirm
        needs_confirm = action_id in {"apply", "dismiss", "done", "cancel", "retire"}
        payload: dict = {}

        def _execute(ok: bool | None = True) -> None:
            if needs_confirm and not ok:
                return
            try:
                result = self.adapter.run_semantic(action_id, row_id, payload=payload)
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            msg = result.message
            if result.hidden_by_filter and result.filter_hint:
                msg = f"{msg} {result.filter_hint}"
            self.notify(msg)
            self.reload(select_id=row_id)

        if action_id == "apply" and self.adapter.id == "changes":
            self.app.push_screen(
                ConfirmModal(f"Mark {row_id} APPLIED?", confirm_label="Apply"),
                _execute,
            )
            return
        if needs_confirm:
            self.app.push_screen(
                ConfirmModal(f"{action_id.title()} {row_id}?", confirm_label=action_id.title()),
                _execute,
            )
            return
        _execute(True)
