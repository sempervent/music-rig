"""Reconcile queue screen — consumes reconciliation.service (not advisory text only)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from music_rig import question_service
from music_rig.reconciliation import service as reconcile_service
from music_rig.models import ReconciliationState
from music_rig.store import StoreError
from music_rig.tui.header import RigHeader


class ReconcileScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "plan", "Plan"),
        Binding("a", "apply", "Apply"),
        Binding("v", "verify", "Verify"),
        Binding("f", "finalize", "Finalize"),
        Binding("g", "agent_plan", "Agent Plan"),
        Binding("o", "open_target", "Open Target"),
        Binding("e", "edit_target", "Edit Target"),
        Binding("l", "open_related", "Related"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, initial_id: str | None = None) -> None:
        super().__init__()
        self._initial_id = initial_id
        self._items: list = []

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        yield Static("Reconcile queue", id="screen-title")
        with Horizontal(id="split"):
            yield DataTable(id="list-table")
            with Vertical(id="detail-pane"):
                yield Static("Select an item", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Type", "ID", "State", "Summary")
        self.action_refresh()

    def action_refresh(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.clear()
        self._items = reconcile_service.build_queue()
        for item in self._items:
            table.add_row(
                item.artifact_type,
                item.artifact_id,
                item.state.value,
                item.summary[:48],
                key=f"{item.artifact_type}:{item.artifact_id}",
            )
        if self._initial_id:
            for idx, item in enumerate(self._items):
                if item.artifact_id == self._initial_id:
                    table.move_cursor(row=idx)
                    break
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
            detail.update("Select an item")
            return
        if item.artifact_type == "question":
            try:
                shown = reconcile_service.show_question(item.artifact_id)
            except StoreError as exc:
                detail.update(str(exc))
                return
            lines = [
                f"# {item.artifact_id} — {item.state.value}",
                "",
                f"**Capability:** {shown.get('capability')}",
                f"**CURRENT:** `{shown.get('current')}`",
                "",
                "## Suggested",
                "",
            ]
            for cmd in shown.get("suggested_commands") or []:
                lines.append(f"- `{cmd}`")
            if item.state == ReconciliationState.NEEDS_AGENT_ACTION:
                lines.append("")
                lines.append("_Press **e** to Edit Target (pair picker when missing)._")
            detail.update("\n".join(lines))
        else:
            detail.update(
                f"# {item.artifact_type} {item.artifact_id}\n\n"
                f"**State:** {item.state.value}\n\n{item.summary}"
            )

    def _enabled_for(self, action: str) -> bool:
        item = self._selected()
        if item is None or item.artifact_type != "question":
            return False
        st = item.state
        if action == "plan":
            return True
        if action == "apply":
            return st == ReconciliationState.READY_TO_APPLY
        if action == "verify":
            return st in {
                ReconciliationState.READY_TO_APPLY,
                ReconciliationState.CURRENT_MATCHES,
                ReconciliationState.READY_TO_FINALIZE,
                ReconciliationState.NEEDS_AGENT_ACTION,
            }
        if action == "finalize":
            return st in {
                ReconciliationState.CURRENT_MATCHES,
                ReconciliationState.READY_TO_FINALIZE,
            }
        return True

    def action_plan(self) -> None:
        item = self._selected()
        if item is None or item.artifact_type != "question":
            self.notify("Select a question", severity="warning")
            return
        try:
            plan = reconcile_service.plan_question(item.artifact_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        self.notify(f"Plan {item.artifact_id}: {plan.state.value}")
        self._update_detail()

    def action_apply(self) -> None:
        if not self._enabled_for("apply"):
            self.notify("Apply not enabled for this state", severity="warning")
            return
        item = self._selected()
        assert item is not None
        from music_rig.tui.dialogs import ConfirmModal

        def _done(ok: bool | None) -> None:
            if not ok:
                return
            try:
                reconcile_service.apply_question(item.artifact_id, dry_run=False, yes=True)
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"Applied {item.artifact_id}")
            self.action_refresh()

        self.app.push_screen(
            ConfirmModal(f"Apply CURRENT for {item.artifact_id}?", confirm_label="Apply"),
            _done,
        )

    def action_verify(self) -> None:
        item = self._selected()
        if item is None or item.artifact_type != "question":
            self.notify("Select a question", severity="warning")
            return
        try:
            result = reconcile_service.verify_question(item.artifact_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        self.notify(f"Verify {item.artifact_id}: {result.get('verification')}")
        self._update_detail()

    def action_finalize(self) -> None:
        if not self._enabled_for("finalize"):
            self.notify("Finalize not enabled for this state", severity="warning")
            return
        item = self._selected()
        assert item is not None
        from music_rig.tui.dialogs import ConfirmModal

        def _done(ok: bool | None) -> None:
            if not ok:
                return
            try:
                reconcile_service.finalize_question(
                    item.artifact_id,
                    dry_run=False,
                    yes=True,
                    complete_linked_todos=True,
                    apply_linked_changes=True,
                    confirm_dod=True,
                    no_current_change=item.state == ReconciliationState.CURRENT_MATCHES,
                    note="TUI finalize",
                )
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"Finalized {item.artifact_id}")
            self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                f"Finalize {item.artifact_id}?",
                "Marks reconciled_at; may complete linked TODOs / apply changes.",
                confirm_label="Finalize",
            ),
            _done,
        )

    def action_agent_plan(self) -> None:
        """Agent Plan — background provider reconcile preview (or CLI fallback)."""
        item = self._selected()
        if item is None or item.artifact_type != "question":
            self.notify("Select a question for Agent Plan", severity="warning")
            return
        from music_rig.agent.provider import provider_status
        from music_rig.tui.dialogs import HelpScreen
        from music_rig.tui.screens.agent_plan import AgentPlanScreen

        if not provider_status().get("configured"):
            try:
                from music_rig.agent import build_agent_packet

                packet = build_agent_packet(item.artifact_id)
            except Exception as exc:  # noqa: BLE001
                self.notify(f"Agent packet failed: {exc}", severity="error")
                return
            body = (
                "No provider configured.\n\n"
                f"Packet hash: {packet.get('packet_hash')}\n"
                f"Answer: {packet.get('final_human_answer') or '—'}\n\n"
                "Use:\n"
                f"  uv run rig agent packet {item.artifact_id} --json\n"
                "  uv run rig agent validate proposal.json\n"
                "  uv run rig agent apply proposal.json --dry-run\n"
            )
            self.app.push_screen(HelpScreen(body))
            return

        def _done(result: dict | None) -> None:
            if result and result.get("ok") and result.get("applied"):
                self.notify(f"Applied agent plan for {item.artifact_id}")
                self.action_refresh()
            elif result is not None:
                self.notify(
                    result.get("message") or "Agent plan finished",
                    severity="information",
                )

        self.app.push_screen(AgentPlanScreen(item.artifact_id), _done)

    def action_agent_packet(self) -> None:
        """Back-compat alias."""
        self.action_agent_plan()

    def action_open_target(self) -> None:
        item = self._selected()
        if item is None or item.artifact_type != "question":
            return
        try:
            q = reconcile_service.show_question(item.artifact_id)["question"]
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        target = q.get("target") or {}
        domain = target.get("domain") or ""
        if domain.startswith("patchbay"):
            bay = target.get("bay")
            if bay:
                self.app.open_domain("patchbay", bay, pair=target.get("pair"))  # type: ignore[attr-defined]
                return
        self.app.open_domain("question", item.artifact_id)  # type: ignore[attr-defined]

    def action_edit_target(self) -> None:
        """Edit typed target — pair picker when patchbay.mode is missing pair."""
        item = self._selected()
        if item is None or item.artifact_type != "question":
            self.notify("Select a question", severity="warning")
            return
        try:
            q = question_service.get_question(item.artifact_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        target = q.target
        if (
            target is not None
            and target.domain == "patchbay.mode"
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
                    f"mode={p['mode']} {p.get('upper_conn') or ''} / {p.get('lower_conn') or ''}",
                )
                for p in pairs
            ]
            if not choices:
                self.notify(f"No pairs on {target.bay}", severity="warning")
                return

            def _picked(selected: list[str] | None) -> None:
                if not selected:
                    return
                pair = selected[0]
                try:
                    question_service.set_target(
                        q.id, pair=pair, dry_run=False, render=True
                    )
                except StoreError as exc:
                    self.notify(str(exc), severity="error")
                    return
                self.notify(f"{q.id} target.pair = {pair}")
                self.action_refresh()

            self.app.push_screen(
                ReferencePickerModal(
                    f"Select pair for {q.id} ({target.bay})",
                    choices,
                    multi=False,
                ),
                _picked,
            )
            return
        self.app.open_domain("question", item.artifact_id)  # type: ignore[attr-defined]

    def action_open_related(self) -> None:
        item = self._selected()
        if item is None:
            return
        related = item.related or {}
        for key in ("questions", "todos", "changes"):
            refs = related.get(key) or []
            if refs:
                domain = {"questions": "question", "todos": "todo", "changes": "changes"}[key]
                self.app.open_domain(domain, refs[0])  # type: ignore[attr-defined]
                return
        self.notify("No related artifacts", severity="warning")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        from music_rig.tui.dialogs import HelpScreen

        self.app.push_screen(
            HelpScreen(
                "p plan · a apply · v verify · f finalize\n"
                "o open target · e edit target (pair picker)\n"
                "l related · r refresh · Esc back\n"
                "Actions enable based on reconciliation state."
            )
        )
