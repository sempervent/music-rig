"""Reference / ordered-list picker modals."""

from __future__ import annotations

from typing import Callable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static


class ReferencePickerModal(ModalScreen[list[str] | None]):
    """Searchable single or multi reference picker.

    Returns the selected id list, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "toggle_or_confirm", "Select", show=False),
        Binding("space", "toggle", "Toggle", show=False),
    ]

    def __init__(
        self,
        title: str,
        choices: list[tuple[str, str]],
        *,
        selected: list[str] | None = None,
        multi: bool = True,
        max_items: int | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._choices = choices  # (id, label)
        self._selected = set(selected or [])
        self._multi = multi
        self._max_items = max_items
        self._row_ids: list[str] = []
        self._search = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(self._title, id="modal-title")
            yield Static(
                "Space toggle · Enter confirm · Esc cancel"
                + (" · multi" if self._multi else " · single"),
                id="modal-body",
            )
            yield Input(placeholder="filter…", id="picker-search")
            yield DataTable(id="picker-table", cursor_type="row")
            yield Static("", id="picker-selected")
            with Horizontal(id="modal-buttons"):
                yield Button("OK", variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        table = self.query_one("#picker-table", DataTable)
        table.add_columns("Sel", "ID", "Label")
        self._reload_table()
        self.query_one("#picker-search", Input).focus()

    def _reload_table(self) -> None:
        table = self.query_one("#picker-table", DataTable)
        table.clear()
        self._row_ids = []
        needle = self._search.casefold()
        for rid, label in self._choices:
            blob = f"{rid} {label}".casefold()
            if needle and needle not in blob:
                continue
            mark = "✓" if rid in self._selected else ""
            table.add_row(mark, rid, label[:60])
            self._row_ids.append(rid)
        self.query_one("#picker-selected", Static).update(
            f"Selected: {', '.join(sorted(self._selected)) or '—'}"
        )

    @on(Input.Changed, "#picker-search")
    def _on_search(self, event: Input.Changed) -> None:
        self._search = event.value
        self._reload_table()

    def _cursor_id(self) -> str | None:
        table = self.query_one("#picker-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._row_ids):
            return None
        return self._row_ids[row]

    def action_toggle(self) -> None:
        rid = self._cursor_id()
        if rid is None:
            return
        if not self._multi:
            self._selected = {rid}
            self.dismiss(list(self._selected))
            return
        if rid in self._selected:
            self._selected.discard(rid)
        else:
            if self._max_items is not None and len(self._selected) >= self._max_items:
                self.notify(f"Max {self._max_items} items", severity="warning")
                return
            self._selected.add(rid)
        self._reload_table()

    def action_toggle_or_confirm(self) -> None:
        if self._multi:
            self.action_toggle()
        else:
            rid = self._cursor_id()
            if rid:
                self.dismiss([rid])

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#confirm")
    def _ok(self) -> None:
        self.dismiss(sorted(self._selected) if self._multi else list(self._selected))

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class OrderedListEditorModal(ModalScreen[list[str] | None]):
    """Simple ordered list editor: add / remove / move."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("a", "add", "Add", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("J", "move_down", "Down", show=False),
        Binding("K", "move_up", "Up", show=False),
        Binding("enter", "confirm", "OK", show=False, priority=True),
    ]

    def __init__(
        self,
        title: str,
        items: list[str],
        *,
        max_items: int | None = None,
        choices: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._items = list(items)
        self._max_items = max_items
        self._choices = choices

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(self._title, id="modal-title")
            yield Static(
                "a add · d delete · Shift+J/K reorder · Enter OK · Esc cancel",
                id="modal-body",
            )
            yield DataTable(id="olist-table", cursor_type="row")
            with Horizontal(id="modal-buttons"):
                yield Button("OK", variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        table = self.query_one("#olist-table", DataTable)
        table.add_columns("#", "Item")
        self._reload()
        table.focus()

    def _reload(self) -> None:
        table = self.query_one("#olist-table", DataTable)
        row = table.cursor_row or 0
        table.clear()
        for i, item in enumerate(self._items):
            table.add_row(str(i + 1), item)
        if self._items and 0 <= row < len(self._items):
            table.move_cursor(row=row)

    def action_add(self) -> None:
        if self._max_items is not None and len(self._items) >= self._max_items:
            self.notify(f"Max {self._max_items} items", severity="warning")
            return
        if self._choices:

            def _picked(ids: list[str] | None) -> None:
                if not ids:
                    return
                for rid in ids:
                    if rid not in self._items:
                        if self._max_items is not None and len(self._items) >= self._max_items:
                            break
                        self._items.append(rid)
                self._reload()

            self.app.push_screen(
                ReferencePickerModal(
                    "Add item",
                    self._choices,
                    multi=True,
                    max_items=(
                        None
                        if self._max_items is None
                        else max(0, self._max_items - len(self._items))
                    ),
                ),
                _picked,
            )
            return
        from music_rig.tui.dialogs import InputModal

        def _done(value: str | None) -> None:
            if value:
                self._items.append(value)
                self._reload()

        self.app.push_screen(InputModal("New item"), _done)

    def action_delete(self) -> None:
        table = self.query_one("#olist-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._items):
            return
        del self._items[row]
        self._reload()

    def action_move_up(self) -> None:
        table = self.query_one("#olist-table", DataTable)
        row = table.cursor_row
        if row is None or row <= 0:
            return
        self._items[row - 1], self._items[row] = self._items[row], self._items[row - 1]
        self._reload()
        table.move_cursor(row=row - 1)

    def action_move_down(self) -> None:
        table = self.query_one("#olist-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._items) - 1:
            return
        self._items[row + 1], self._items[row] = self._items[row], self._items[row + 1]
        self._reload()
        table.move_cursor(row=row + 1)

    def action_confirm(self) -> None:
        self.dismiss(list(self._items))

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#confirm")
    def _ok(self) -> None:
        self.dismiss(list(self._items))

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


def load_ref_choices(domain: str) -> list[tuple[str, str]]:
    """Load (id, label) choices for a reference domain."""
    from music_rig.store import (
        load_changes,
        load_inbox,
        load_inventory,
        load_questions,
        load_todo,
        load_wishlist,
    )

    key = domain.strip().lower()
    if key in {"todo", "todos"}:
        return [(t.id, t.task[:60]) for t in load_todo().tasks]
    if key in {"change", "changes"}:
        return [(c.id, c.summary[:60]) for c in load_changes().items]
    if key in {"question", "questions"}:
        return [(q.id, q.question[:60]) for q in load_questions().questions]
    if key in {"gear", "inventory"}:
        return [(g.id, g.name[:60]) for g in load_inventory().items]
    if key in {"wish", "wishlist"}:
        return [(w.item, w.item[:60]) for w in load_wishlist().items]
    if key == "inbox":
        return [(i.id, i.text[:60]) for i in load_inbox().items]
    return []
