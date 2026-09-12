"""Guided verification screen — queue + detail; mutations via verification_service."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from music_rig import verification_service
from music_rig.presentation import blocker_message
from music_rig.reconciliation import service as reconcile_service
from music_rig.store import StoreError
from music_rig.tui.dialogs import ConfirmModal, HelpScreen, InputModal
from music_rig.tui.pickers import ReferencePickerModal


class VerifyScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("v", "verify", "Worked/Answer"),
        Binding("f", "fail", "Failed"),
        Binding("u", "unknown", "Unknown"),
        Binding("s", "skip", "Skip"),
        Binding("n", "next", "Next"),
        Binding("o", "open_target", "Open Target"),
        Binding("e", "edit_target", "Edit Target"),
        Binding("c", "reconcile", "Reconcile"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, initial_id: str | None = None) -> None:
        super().__init__()
        self._initial_id = initial_id
        self._items: list = []
        self._skipped: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("Verify queue", id="screen-title")
        with Horizontal(id="split"):
            yield DataTable(id="list-table")
            with Vertical(id="detail-pane"):
                yield Static("Select a question", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Area", "Kind", "Next")
        self.action_refresh()

    def action_refresh(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.clear()
        try:
            self._items = [
                i
                for i in verification_service.list_verify_queue()
                if i.question_id not in self._skipped
            ]
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            self._items = []
            return
        for item in self._items:
            table.add_row(
                item.question_id,
                item.area[:18],
                item.kind[:18],
                item.next_hint[:28],
                key=item.question_id,
            )
        if self._initial_id:
            for idx, item in enumerate(self._items):
                if item.question_id == self._initial_id:
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
            detail.update("Select a question")
            return
        try:
            card = verification_service.build_card(item.question_id)
        except StoreError as exc:
            detail.update(str(exc))
            return
        v = card.get("verification") or {}
        recon = card.get("reconciliation") or {}
        accepted = card.get("accepted") or {}
        lines = [
            f"# {card['question_id']} — {v.get('kind', '—')}",
            "",
            card.get("question") or "",
            "",
            f"**Area:** {card.get('area')}",
            f"**Answer:** `{card.get('answer') or '—'}`",
            f"**CURRENT:** `{card.get('current')}`",
            f"**Evidence:** `{card.get('evidence')}`",
        ]
        vr = card.get("verification_result")
        if vr:
            lines.append(
                f"**Observed:** {vr.get('outcome')} `{vr.get('observed_value')}` "
                f"@ {vr.get('observed_at')}"
            )
        else:
            lines.append("**Observed:** (none — not VERIFIED from inference)")
        lines.extend(
            [
                "",
                f"**How to check:** {card.get('prompt') or '—'}",
                "",
                f"**Accepted:** {accepted.get('answer_type')} "
                f"{accepted.get('choices') or '(TEXT / UNKNOWN)'}",
                "",
                f"**Reconcile:** {recon.get('capability')} / {recon.get('state')} "
                f"/ {recon.get('after_answer_bucket')} / "
                f"obs={recon.get('after_observation_bucket')}",
            ]
        )
        for op_item in recon.get("operations") or []:
            lines.append(f"- op: `{op_item}`")
        for b in recon.get("blockers") or []:
            lines.append(f"- blocker: {blocker_message(b)}")
        related = card.get("related_work") or []
        if related:
            lines.append("")
            lines.append("**Related**")
            for w in related:
                lines.append(
                    f"- {w.get('id')} {w.get('priority')} {w.get('status')}"
                )
        lines.append("")
        lines.append(
            "v Worked/Answer · f Failed · u Unknown · s Skip · n Next · c Reconcile"
        )
        detail.update("\n".join(lines))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Verify\n\n"
                "v  worked / answer (structured picker)\n"
                "f  failed test (FAILED_TEST — no VERIFIED)\n"
                "u  could not determine (UNKNOWN)\n"
                "s  skip for this session\n"
                "n  jump to next recommended\n"
                "o  open typed target domain\n"
                "e  edit target fields\n"
                "c  open reconcile for this question\n"
                "r  refresh\n"
                "Esc/q  back\n\n"
                "Documented ≠ Observed ≠ VERIFIED.\n"
                "Never invent observation from manuals.\n"
                "Answers → question_service; observations → verify record;\n"
                "CURRENT → reconcile."
            )
        )

    def action_fail(self) -> None:
        item = self._selected()
        if item is None:
            return
        self._record_outcome(item.question_id, "failed_test")

    def action_unknown(self) -> None:
        item = self._selected()
        if item is None:
            return
        self._record_outcome(item.question_id, "unknown", value="UNKNOWN")

    def _record_outcome(
        self, question_id: str, outcome: str, *, value: str | None = None
    ) -> None:
        def _confirmed(ok: bool | None) -> None:
            if not ok:
                return
            try:
                verification_service.record_observation(
                    question_id,
                    outcome,
                    value=value,
                    render=False,
                )
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"{question_id}: {outcome}")
            self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                f"Record {outcome} for {question_id}?",
                "Explicit human observation only. Does not invent VERIFIED.",
                confirm_label="Record",
            ),
            _confirmed,
        )

    def action_skip(self) -> None:
        item = self._selected()
        if item is None:
            return
        self._skipped.add(item.question_id)
        self.notify(f"Skipped {item.question_id}")
        self.action_refresh()

    def action_next(self) -> None:
        rec = verification_service.recommend_next()
        if rec is None:
            self.notify("Queue empty", severity="warning")
            return
        qid = rec["question_id"]
        for idx, item in enumerate(self._items):
            if item.question_id == qid:
                self.query_one("#list-table", DataTable).move_cursor(row=idx)
                self._update_detail()
                self.notify(f"Next: {qid} — {rec.get('why')}")
                return
        self.notify(f"Next {qid} not in filtered list", severity="warning")

    def action_open_target(self) -> None:
        item = self._selected()
        if item is None:
            return
        try:
            card = verification_service.build_card(item.question_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        target = card.get("target") or {}
        domain = (target.get("domain") or "").split(".", 1)[0]
        if not domain:
            self.notify("No typed target", severity="warning")
            return
        # Map reconcile domains → TUI routes
        route_map = {
            "patchbay": "patchbay",
            "inventory": "gear",
            "routing": "routing",
            "midi": "midi",
            "controls": "controls",
            "ableton": "ableton",
        }
        route = route_map.get(domain)
        if route is None:
            self.notify(f"No TUI route for {domain}", severity="warning")
            return
        object_id = (
            target.get("bay")
            or target.get("gear")
            or target.get("path")
            or None
        )
        self.app.open_domain(route, object_id)

    def action_edit_target(self) -> None:
        item = self._selected()
        if item is None:
            return
        self.app.open_domain("question", item.question_id)

    def action_reconcile(self) -> None:
        item = self._selected()
        if item is None:
            return
        self.app.open_domain("reconcile", item.question_id)

    def action_verify(self) -> None:
        item = self._selected()
        if item is None:
            return
        try:
            card = verification_service.build_card(item.question_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        if card.get("status") != "OPEN":
            self.notify(f"{item.question_id} is {card.get('status')}", severity="warning")
            return
        accepted = card.get("accepted") or {}
        choices = list(accepted.get("choices") or [])
        at = accepted.get("answer_type")

        def _after_value(value: str | None) -> None:
            if value is None:
                return
            self._commit_answer(item.question_id, value)

        if at in {"ENUM", "BOOL", "REF"} and choices:
            # Always include UNKNOWN
            if "UNKNOWN" not in choices and "unknown" not in [c.casefold() for c in choices]:
                choices = [*choices, "UNKNOWN"]
            picker_choices = [(c, c) for c in choices]
            self.app.push_screen(
                ReferencePickerModal(
                    f"Answer {item.question_id}",
                    picker_choices,
                    multi=False,
                ),
                lambda selected: _after_value(
                    selected[0] if selected else None
                ),
            )
            return

        self.app.push_screen(
            InputModal(
                f"Answer {item.question_id}",
                hint=card.get("prompt") or "Free-text observation; UNKNOWN allowed",
                allow_empty=False,
            ),
            _after_value,
        )

    def _commit_answer(self, question_id: str, value: str) -> None:
        def _confirmed(ok: bool | None) -> None:
            if not ok:
                return
            try:
                from music_rig.models import VerificationOutcome

                q = None
                try:
                    from music_rig import question_service

                    q = question_service.get_question(question_id)
                    outcome = verification_service._infer_outcome_vs_current(  # noqa: SLF001
                        q, value
                    )
                except StoreError:
                    outcome = VerificationOutcome.CORRECTED
                if value.strip().casefold() == "unknown":
                    outcome = VerificationOutcome.UNKNOWN
                result = verification_service.record_observation(
                    question_id, outcome, value=value, render=False
                )
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            normalized = (result.get("verification_result") or {}).get(
                "observed_value"
            ) or result.get("answer")
            self.notify(f"Observed {question_id} = {normalized!r}")
            try:
                plan = reconcile_service.plan_question(question_id)
                state = plan.state.value
                if state == "READY_TO_APPLY":
                    self.notify(f"{question_id}: READY_TO_APPLY")
                elif plan.blockers:
                    self.notify(
                        f"{question_id}: {state} — {blocker_message(plan.blockers[0])}",
                        severity="warning",
                    )
                else:
                    self.notify(f"{question_id}: {state}")
            except StoreError:
                pass
            self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                f"Record observation for {question_id}?",
                f"Value: {value!r}\nSets verification_result (human observation).",
                confirm_label="Record",
            ),
            _confirmed,
        )
