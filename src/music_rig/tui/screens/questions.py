"""Editable Questions screen — mutations via question_service only."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from music_rig import question_service
from music_rig.models import OpenQuestion, QuestionStatus
from music_rig.reconcile import format_reconcile_question
from music_rig.store import StoreError, load_questions
from music_rig.tui.adapters.questions import (
    STATUS_CYCLE,
    filter_questions,
    question_detail_markdown,
)
from music_rig.tui.dialogs import ConfirmModal, HelpScreen, InputModal
from music_rig.tui.widgets import format_target, truncate


class QuestionsScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "inspect", "Inspect", show=False),
        Binding("f", "cycle_filter", "Filter"),
        Binding("slash", "search", "Search"),
        Binding("a", "add", "Add"),
        Binding("e", "edit", "Edit"),
        Binding("r", "resolve", "Resolve"),
        Binding("d", "defer", "Defer"),
        Binding("o", "reopen", "Reopen"),
        Binding("t", "open_target", "Target"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, *, initial_id: str | None = None) -> None:
        super().__init__()
        self._filter = "OPEN"
        self._search = ""
        self._row_ids: list[str] = []
        self._initial_id = initial_id.upper() if initial_id else None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static("Questions", id="screen-title")
            yield Static("", id="filter-label")
            with Horizontal(id="split"):
                yield DataTable(id="list-table", cursor_type="row")
                with VerticalScroll(id="detail-pane"):
                    yield Static("Select a question", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.add_columns("ID", "Status", "Area", "Question")
        table.focus()
        self.reload(select_id=self._initial_id)

    def reload(self, select_id: str | None = None) -> None:
        items = filter_questions(
            list(load_questions().questions),
            self._filter,
            self._search,
        )
        table = self.query_one("#list-table", DataTable)
        table.clear()
        self._row_ids = []
        for q in items:
            table.add_row(q.id, q.status.value, q.area, truncate(q.question, 48))
            self._row_ids.append(q.id)
        self.query_one("#filter-label", Static).update(
            f"Filter: {self._filter}  ·  {len(self._row_ids)} shown"
            + (f"  ·  search: {self._search!r}" if self._search else "")
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

    def _selected(self) -> OpenQuestion | None:
        qid = self._selected_id()
        if qid is None:
            return None
        try:
            return question_service.get_question(qid)
        except StoreError:
            return None

    def _update_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        q = self._selected()
        if q is None:
            detail.update("Select a question")
            return
        detail.update(question_detail_markdown(q))

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
        idx = STATUS_CYCLE.index(self._filter)
        self._filter = STATUS_CYCLE[(idx + 1) % len(STATUS_CYCLE)]
        self.reload()

    def action_search(self) -> None:
        def _done(value: str | None) -> None:
            if value is None:
                return
            self._search = value
            self.reload()

        self.app.push_screen(
            InputModal("Search questions", default=self._search, allow_empty=True),
            _done,
        )

    def action_refresh(self) -> None:
        self.reload(select_id=self._selected_id())
        self.notify("Refreshed")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Questions\n\n"
                "f       cycle filter OPEN/RESOLVED/DEFERRED/ALL\n"
                "/       search\n"
                "a       add question\n"
                "e       edit fields (Ctrl+S apply)\n"
                "r       resolve (answer + confirm)\n"
                "d       defer\n"
                "o       reopen\n"
                "t       open typed target\n"
                "Ctrl+r  refresh\n"
                "Esc/q   back\n\n"
                "Resolving does not automatically rewrite CURRENT.\n"
                "Under filter=OPEN, a resolved question disappears from the list."
            )
        )

    def action_edit(self) -> None:
        q = self._selected()
        if q is None:
            return
        from music_rig.tui.forms import RecordEditScreen
        from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter

        def _done(saved: bool | None) -> None:
            if saved:
                self.reload(select_id=q.id)
                # May have vanished under OPEN filter after status change via form.
                if self._filter == "OPEN":
                    still = self._selected_id()
                    if still != q.id:
                        self.notify(
                            f"{q.id} updated. Hidden because filter=OPEN. "
                            "Press f for RESOLVED/ALL."
                        )

        self.app.push_screen(
            RecordEditScreen(QuestionsEditableAdapter(), q.id),
            _done,
        )

    def action_add(self) -> None:
        def _after_question(question: str | None) -> None:
            if question is None:
                return

            def _after_area(area: str | None) -> None:
                if area is None:
                    return
                try:
                    item = question_service.add_question(question, area=area, render=True)
                except StoreError as exc:
                    self.notify(str(exc), severity="error")
                    return
                self.notify(f"Added {item.id}")
                self._filter = "OPEN"
                self.reload(select_id=item.id)

            self.app.push_screen(InputModal("Area"), _after_area)

        self.app.push_screen(InputModal("New question text"), _after_question)

    def action_resolve(self) -> None:
        q = self._selected()
        if q is None:
            return
        if q.status == QuestionStatus.RESOLVED:
            self.notify(f"{q.id} already RESOLVED", severity="warning")
            return

        def _after_answer(answer: str | None) -> None:
            if answer is None:
                return

            def _after_confirm(ok: bool | None) -> None:
                if not ok:
                    return
                try:
                    updated = question_service.resolve_question(q.id, answer, render=True)
                except StoreError as exc:
                    self.notify(str(exc), severity="error")
                    return
                filter_was_open = self._filter == "OPEN"
                self.reload(select_id=updated.id)
                self.notify(
                    f"{updated.id} resolved. CURRENT reconciliation still required "
                    f"(rig reconcile plan question {updated.id})."
                )
                if filter_was_open:
                    self.notify(
                        "Hidden because filter=OPEN. Press f for RESOLVED/ALL."
                    )

            self.app.push_screen(
                ConfirmModal(
                    f"Resolve {q.id}?",
                    "Recording an answer does not automatically rewrite CURRENT.\n"
                    "Reconcile separately if the answer changes physical truth.\n"
                    "Enter confirms · Esc cancels.",
                    confirm_label="Resolve",
                ),
                _after_confirm,
            )

        self.app.push_screen(InputModal(f"Answer for {q.id}"), _after_answer)

    def action_defer(self) -> None:
        q = self._selected()
        if q is None:
            return

        def _done(ok: bool | None) -> None:
            if not ok:
                return
            try:
                updated = question_service.defer_question(q.id, render=True)
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"{updated.id} -> DEFERRED")
            self.reload(select_id=updated.id)

        self.app.push_screen(
            ConfirmModal(f"Defer {q.id}?", confirm_label="Defer"),
            _done,
        )

    def action_reopen(self) -> None:
        q = self._selected()
        if q is None:
            return

        def _done(ok: bool | None) -> None:
            if not ok:
                return
            try:
                updated = question_service.reopen_question(q.id, render=True)
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"{updated.id} -> OPEN")
            self._filter = "OPEN"
            self.reload(select_id=updated.id)

        self.app.push_screen(
            ConfirmModal(f"Reopen {q.id}?", confirm_label="Reopen"),
            _done,
        )

    def action_open_target(self) -> None:
        q = self._selected()
        if q is None:
            return
        target = q.target
        if target is None:
            self.notify("No typed target on this question", severity="warning")
            return
        # Pair picker when patchbay.mode is missing pair
        if (
            target.domain == "patchbay.mode"
            and target.bay
            and not target.pair
        ):
            from music_rig import patchbay_state
            from music_rig.tui.pickers import ReferencePickerModal

            pairs = patchbay_state.list_pairs(target.bay)
            choices = [
                (
                    (
                        f"{p['upper_n']}/{p['lower_n']}"
                        if p["lower_n"] is not None
                        else str(p["upper_n"])
                    ),
                    f"mode={p['mode']}",
                )
                for p in pairs
            ]
            if choices:

                def _picked(selected: list[str] | None) -> None:
                    if not selected:
                        return
                    try:
                        question_service.set_target(q.id, pair=selected[0], render=True)
                    except StoreError as exc:
                        self.notify(str(exc), severity="error")
                        return
                    self.notify(f"{q.id} target.pair = {selected[0]}")
                    self.reload(select_id=q.id)

                self.app.push_screen(
                    ReferencePickerModal(
                        f"Select pair for {q.id} ({target.bay})",
                        choices,
                        multi=False,
                    ),
                    _picked,
                )
                return
        if target.domain in {"patchbay.mode", "patchbay.model", "patchbay.connection"} and target.bay:
            self.app.open_domain(  # type: ignore[attr-defined]
                "patchbay",
                target.bay,
                pair=target.pair,
            )
            return
        domain_map = {
            "routing": "routing",
            "routing.path": "routing",
            "midi": "midi",
            "midi.channel": "midi",
            "midi.link": "midi",
            "controls": "controls",
            "controls.mapping": "controls",
            "ableton": "ableton",
            "performance": "performance",
            "channel": "channels",
            "channel.source": "channels",
            "inventory": "gear",
            "inventory.gear": "gear",
        }
        route = domain_map.get(target.domain)
        if route:
            oid = target.gear or target.path or target.device or target.context
            self.app.open_domain(route, oid)  # type: ignore[attr-defined]
            return
        try:
            suggestion = format_reconcile_question(q.id)
        except StoreError as exc:
            suggestion = str(exc)
        self.app.push_screen(
            ConfirmModal(
                "No dedicated target editor for this domain",
                f"Typed target: {format_target(target)}\n\n"
                "Use CLI to reconcile:\n"
                f"{suggestion[:1200]}",
                confirm_label="OK",
            ),
            lambda _ok: None,
        )
