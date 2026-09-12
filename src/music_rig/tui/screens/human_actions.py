"""Pending HUMAN authority review — accept/edit/reject via human_action_service."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from music_rig import human_action_service
from music_rig.models import HumanActionStatus
from music_rig.store import StoreError
from music_rig.tui.dialogs import ConfirmModal, HelpScreen, InputModal
from music_rig.tui.header import RigHeader


class HumanActionsScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("a", "accept", "Accept"),
        Binding("e", "edit", "Edit"),
        Binding("x", "reject", "Reject"),
        Binding("l", "later", "Later"),
        Binding("n", "next", "Next"),
        Binding("c", "reconcile_hint", "Reconcile hint"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, initial_id: str | None = None) -> None:
        super().__init__()
        self._initial_id = initial_id
        self._items: list = []
        self._later: set[str] = set()

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        yield Static("Human actions — pending review", id="screen-title")
        with Horizontal(id="split"):
            yield DataTable(id="list-table")
            with Vertical(id="detail-pane"):
                yield Static("Select a request", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Type", "Artifact")
        self.action_refresh()

    def action_refresh(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.clear()
        try:
            self._items = [
                i
                for i in human_action_service.list_actions(pending_only=True)
                if i.id not in self._later
            ]
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            self._items = []
            return
        for item in self._items:
            table.add_row(
                item.id,
                item.action_type.value[:18],
                item.artifact_id,
                key=item.id,
            )
        title = self.query_one("#screen-title", Static)
        title.update(f"Human actions — pending review ({len(self._items)})")
        if self._initial_id:
            for idx, item in enumerate(self._items):
                if item.id == self._initial_id:
                    table.move_cursor(row=idx)
                    break
            self._initial_id = None
        self._update_detail()

    def _selected(self):
        table = self.query_one("#list-table", DataTable)
        if not self._items or table.cursor_row is None:
            return None
        if table.cursor_row < 0 or table.cursor_row >= len(self._items):
            return None
        return self._items[table.cursor_row]

    def on_data_table_row_highlighted(self, _event) -> None:
        self._update_detail()

    def _update_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        item = self._selected()
        if item is None:
            detail.update("No pending human actions.")
            return
        detail.update(human_action_service.format_review(item))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_later(self) -> None:
        item = self._selected()
        if item is None:
            return
        self._later.add(item.id)
        self.notify(f"{item.id} deferred for later (still pending)")
        self.action_refresh()

    def action_next(self) -> None:
        table = self.query_one("#list-table", DataTable)
        if not self._items:
            return
        nxt = (table.cursor_row or 0) + 1
        if nxt >= len(self._items):
            nxt = 0
        table.move_cursor(row=nxt)
        self._update_detail()

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Human actions\n\n"
                "a Accept · e Edit then accept · x Reject · l Later · "
                "n Next · r Refresh · Esc Back\n\n"
                "Accepting records HUMAN authority via the same services as "
                "direct CLI/TUI. BOT cannot accept."
            )
        )

    def action_reject(self) -> None:
        item = self._selected()
        if item is None:
            return

        def _done(ok: bool) -> None:
            if not ok:
                return
            try:
                human_action_service.reject(item.id)
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"{item.id} rejected")
            self.action_refresh()

        self.app.push_screen(
            ConfirmModal(f"Reject {item.id} without changing {item.artifact_id}?"),
            _done,
        )

    def action_accept(self) -> None:
        item = self._selected()
        if item is None:
            return
        self._do_accept(item.id, None)

    def action_edit(self) -> None:
        item = self._selected()
        if item is None:
            return

        def _done(value: str | None) -> None:
            if value is None:
                return
            self._do_accept(item.id, value)

        self.app.push_screen(
            InputModal("Edit proposed value", default=item.proposed_value),
            _done,
        )

    def _do_accept(self, action_id: str, edited: str | None) -> None:
        item = human_action_service.get_action(action_id)
        if item.status is not HumanActionStatus.PENDING:
            self.notify(f"{action_id} is {item.status.value}", severity="warning")
            self.action_refresh()
            return

        def _done(ok: bool) -> None:
            if not ok:
                return
            try:
                result = human_action_service.accept(action_id, edited_value=edited, render=True)
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(result["message"])
            if result.get("reconcile_prompt"):
                self.notify(result["reconcile_prompt"])
            self.action_refresh()

        label = "Accept as HUMAN"
        if edited is not None:
            label = "Accept edited value as HUMAN"
        self.app.push_screen(ConfirmModal(f"{label} for {item.artifact_id}?"), _done)

    def action_reconcile_hint(self) -> None:
        item = self._selected()
        if item is None:
            return
        self.notify(f"After accept: uv run rig reconcile plan question {item.artifact_id}")
