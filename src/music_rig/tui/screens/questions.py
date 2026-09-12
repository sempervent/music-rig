"""Editable Questions screen — mutations via question_service only.

Keybindings (Stage 18):
  a = Answer (question stays visible)
  A = Add Question
  r / R = Resolve (answer required; does not invent verification_result)
  V = Verify (open verify flow)
  C = Reconcile (handoff / open reconcile)
  Ctrl+r = Refresh only
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from music_rig import question_service
from music_rig.models import OpenQuestion, QuestionStatus
from music_rig.reconcile import format_reconcile_question
from music_rig.store import StoreError, load_questions
from music_rig.tui.adapters.questions import (
    STATUS_CYCLE,
    filter_questions,
    question_detail_markdown,
)
from music_rig.tui.debug import format_error
from music_rig.tui.dialogs import CommandLineModal, ConfirmModal, HelpScreen, InputModal
from music_rig.tui.header import RigHeader
from music_rig.tui.modes import VIM_HELP_COMMON, EditorMode, ModeController, parse_command
from music_rig.tui.screen_results import AnswerNextAction, AnswerResult
from music_rig.tui.widgets import format_target, truncate


class QuestionsScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "go_top_pending", "gg", show=False),
        Binding("G", "go_bottom", "Bottom", show=False),
        Binding("enter", "inspect", "Inspect", show=False),
        Binding("f", "cycle_filter", "Filter"),
        Binding("slash", "search", "Search"),
        Binding("n", "search_next", "Next", show=False),
        Binding("N", "search_prev", "Prev", show=False),
        Binding("a", "answer", "Answer"),
        Binding("A", "add", "Add"),
        Binding("e", "edit", "Edit"),
        Binding("i", "edit", "Insert/Edit", show=False),
        Binding("r", "resolve", "Resolve"),
        Binding("R", "resolve", "Resolve", show=False),
        Binding("V", "verify", "Verify"),
        Binding("C", "reconcile", "Reconcile"),
        Binding("d", "defer", "Defer"),
        Binding("o", "reopen", "Reopen"),
        Binding("t", "open_target", "Target"),
        Binding("colon", "command_mode", ":", show=False),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "escape", "Esc", show=False, priority=True),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, *, initial_id: str | None = None) -> None:
        super().__init__()
        self._filter = "ACTIVE"
        self._search = ""
        self._row_ids: list[str] = []
        self._initial_id = initial_id.upper() if initial_id else None
        self._modes = ModeController()
        self._search_hits: list[int] = []
        self._search_idx = -1

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static("Questions", id="screen-title")
            yield Static("", id="filter-label")
            yield Static(self._modes.banner(), id="mode-banner")
            with Horizontal(id="split"):
                yield DataTable(id="list-table", cursor_type="row")
                with VerticalScroll(id="detail-pane"):
                    yield Static("Select a question", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.add_columns("ID", "Lifecycle", "Area", "Question")
        table.focus()
        self._set_mode(EditorMode.NORMAL)
        self.reload(select_id=self._initial_id)

    def _set_mode(self, mode: EditorMode) -> None:
        self._modes.set_mode(mode)
        try:
            self.query_one("#mode-banner", Static).update(self._modes.banner())
        except Exception:
            pass

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
            table.add_row(
                q.id,
                question_service.lifecycle_label(q),
                q.area,
                truncate(q.question, 48),
            )
            self._row_ids.append(q.id)
        self.query_one("#filter-label", Static).update(
            f"Filter: {self._filter}  ·  {len(self._row_ids)} shown"
            + (f"  ·  search: {self._search!r}" if self._search else "")
            + "  ·  a Answer · A Add · R Resolve · V Verify · C Reconcile"
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

    def action_go_top_pending(self) -> None:
        if self._modes.handle_g(lambda: self._go_row(0)):
            return

    def action_go_bottom(self) -> None:
        if self._row_ids:
            self._go_row(len(self._row_ids) - 1)

    def _go_row(self, idx: int) -> None:
        table = self.query_one("#list-table", DataTable)
        table.move_cursor(row=idx)
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
            self._rebuild_search_hits()

        self.app.push_screen(
            InputModal("Search questions", default=self._search, allow_empty=True),
            _done,
        )

    def _rebuild_search_hits(self) -> None:
        needle = self._search.casefold().strip()
        self._search_hits = []
        self._search_idx = -1
        if not needle:
            return
        for i, qid in enumerate(self._row_ids):
            try:
                q = question_service.get_question(qid)
            except StoreError:
                continue
            blob = f"{q.id} {q.question} {q.area} {q.answer}".casefold()
            if needle in blob:
                self._search_hits.append(i)

    def action_search_next(self) -> None:
        if not self._search_hits:
            self._rebuild_search_hits()
        if not self._search_hits:
            self.notify("No search hits")
            return
        self._search_idx = (self._search_idx + 1) % len(self._search_hits)
        self._go_row(self._search_hits[self._search_idx])

    def action_search_prev(self) -> None:
        if not self._search_hits:
            self._rebuild_search_hits()
        if not self._search_hits:
            self.notify("No search hits")
            return
        self._search_idx = (self._search_idx - 1) % len(self._search_hits)
        self._go_row(self._search_hits[self._search_idx])

    def action_command_mode(self) -> None:
        self._set_mode(EditorMode.COMMAND)

        def _done(raw: str | None) -> None:
            self._set_mode(EditorMode.NORMAL)
            if raw is None:
                return
            cmd, _ = parse_command(raw)
            if cmd in {"quit", "quit!"}:
                self.app.pop_screen()
            elif cmd == "write":
                self.notify("Nothing staged on list — open edit (e/i) or Answer (a)")
            else:
                self.notify(f"Unknown command :{cmd}", severity="warning")

        self.app.push_screen(CommandLineModal(), _done)

    def action_escape(self) -> None:
        self._modes.clear_pending()
        if self._modes.mode is not EditorMode.NORMAL:
            self._set_mode(EditorMode.NORMAL)
            return
        self.action_back()

    def action_refresh(self) -> None:
        self.reload(select_id=self._selected_id())
        self.notify("Refreshed")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Questions\n\n"
                "a       Answer (Save Draft / Answer & Resolve)\n"
                "A       Add question\n"
                "r / R   Resolve draft → FINAL (answer required)\n"
                "V       Verify (observation / verification_result flow)\n"
                "C       Reconcile handoff\n"
                "e / i   edit fields (Ctrl+S / :w apply)\n"
                "d       defer · o reopen · t target\n"
                "f       cycle ACTIVE/OPEN/RESOLVED/UNRECONCILED/DEFERRED/ALL\n"
                "/ n N   search\n"
                "Ctrl+r  refresh (not Resolve)\n"
                "Esc/q   back\n\n"
                f"{VIM_HELP_COMMON}\n"
                "Labels: OPEN/UNANSWERED · OPEN/DRAFT · "
                "RESOLVED/UNRECONCILED · RESOLVED/RECONCILED\n"
                "ACTIVE includes OPEN + RESOLVED-unreconciled "
                "(excludes RECONCILED/DEFERRED).\n"
                "Resolving does not rewrite CURRENT.\n"
                "Under filter=OPEN, a resolved question leaves the list "
                "but reconciliation may still be pending."
            )
        )

    def action_answer(self) -> None:
        q = self._selected()
        if q is None:
            return
        from music_rig.tui.screens.answer import AnswerScreen

        def _done(result: AnswerResult | None) -> None:
            self._on_answer_result(result)

        self.app.push_screen(AnswerScreen(q.id, resolve_on_save=False), _done)

    def _on_answer_result(self, result: AnswerResult | None) -> None:
        """Handle AnswerScreen result: reload, then optional reconcile navigation."""
        if result is None:
            return
        from music_rig.tui.save_outcome import SaveOutcome

        if result.outcome is not SaveOutcome.SUCCESS or not result.question_id:
            return
        qid = result.question_id
        filter_was_open = self._filter == "OPEN"
        self.reload(select_id=qid)
        fresh = question_service.get_question(qid)
        if (
            filter_was_open
            and fresh.status != QuestionStatus.OPEN
            and qid not in self._row_ids
        ):
            self.notify(
                f"{qid} answered and resolved. "
                "It is hidden because this view shows OPEN Questions. "
                "Reconciliation remains pending."
            )
        if result.next_action is AnswerNextAction.RECONCILE:
            try:
                self.app.open_domain("reconcile", qid)  # type: ignore[attr-defined]
            except Exception:
                self.notify(
                    f"Open reconcile: uv run rig reconcile plan question {qid}"
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
        from music_rig.tui.screens.create import AddQuestionModal

        def _done(new_id: str | None) -> None:
            if not new_id:
                return
            self.notify(f"Added {new_id}")
            self._filter = "OPEN"
            self.reload(select_id=new_id)

        self.app.push_screen(AddQuestionModal(), _done)

    def action_resolve(self) -> None:
        q = self._selected()
        if q is None:
            return
        if q.status == QuestionStatus.RESOLVED:
            self.notify(f"{q.id} already RESOLVED", severity="warning")
            return
        # Prefer promoting existing draft without reopening full editor when possible
        if q.answer.strip():
            def _done(ok: bool | None) -> None:
                if not ok:
                    return
                try:
                    updated = question_service.resolve_question(q.id, render=True)
                except StoreError as exc:
                    self.notify(format_error(exc), severity="error")
                    return
                filter_was_open = self._filter == "OPEN"
                self.reload(select_id=updated.id)
                self.notify(
                    f"{updated.id} resolved (FINAL). "
                    "CURRENT reconciliation still required."
                )
                if filter_was_open and updated.id not in self._row_ids:
                    self.notify(
                        f"{updated.id} answered and resolved. "
                        "It is hidden because this view shows OPEN Questions. "
                        "Reconciliation remains pending."
                    )

            self.app.push_screen(
                ConfirmModal(
                    f"Resolve draft {q.id}?",
                    "Promotes existing draft answer to FINAL (RESOLVED).\n"
                    "Does not invent verification_result.\n"
                    "Enter confirms · Esc cancels.",
                    confirm_label="Resolve",
                ),
                _done,
            )
            return
        from music_rig.tui.screens.answer import AnswerScreen

        def _done_screen(result: AnswerResult | None) -> None:
            self._on_answer_result(result)

        self.app.push_screen(AnswerScreen(q.id, resolve_on_save=True), _done_screen)

    def action_verify(self) -> None:
        q = self._selected()
        if q is None:
            return
        self.app.open_domain("verify", q.id)  # type: ignore[attr-defined]

    def action_reconcile(self) -> None:
        q = self._selected()
        if q is None:
            return
        try:
            suggestion = format_reconcile_question(q.id)
        except StoreError as exc:
            suggestion = format_error(exc)
        self.app.push_screen(
            ConfirmModal(
                f"Reconcile {q.id}",
                "Resolving/answering does not rewrite CURRENT.\n"
                "Open reconcile screen or use CLI:\n\n"
                f"{suggestion[:1200]}",
                confirm_label="Open Reconcile",
            ),
            lambda ok: self.app.open_domain("reconcile", q.id)  # type: ignore[attr-defined]
            if ok
            else None,
        )

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
                self.notify(format_error(exc), severity="error")
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
                self.notify(format_error(exc), severity="error")
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
                        self.notify(format_error(exc), severity="error")
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
