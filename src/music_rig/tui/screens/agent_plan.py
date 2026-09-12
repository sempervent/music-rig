"""TUI Agent Plan screen — background provider planning, no event-loop freeze."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from music_rig.tui.header import RigHeader


class AgentPlanScreen(ModalScreen[dict | None]):
    """Show autonomous reconcile plan; Apply only after human confirmation."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
    ]

    def __init__(self, question_id: str) -> None:
        super().__init__()
        self.question_id = question_id.upper()
        self._result: dict | None = None
        self._worker = None

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        yield Static(f"Agent Plan — {self.question_id}", id="title")
        with VerticalScroll(id="body"):
            yield Static("Starting provider…", id="status")
            yield Static("", id="plan")
        yield Button("Apply (--yes)", id="apply", disabled=True)
        yield Button("Cancel", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        self._worker = self.run_worker(self._run_plan, exclusive=True, thread=True)

    def _run_plan(self) -> dict:
        from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile
        from music_rig.agent.provider import provider_status

        status = provider_status()
        if not status.get("configured"):
            return {
                "ok": False,
                "provider_configured": False,
                "message": (
                    "No provider configured.\n\n"
                    f"Use:\n  uv run rig agent packet {self.question_id} --json"
                ),
            }
        return autonomous_reconcile(
            self.question_id,
            autonomy=AutonomyLevel.PLAN_ONLY,
            apply=False,
            yes=False,
            dry_run=True,
        )

    def on_worker_state_changed(self, event) -> None:  # noqa: ANN001
        if event.worker is not self._worker:
            return
        if not event.worker.is_finished:
            self.query_one("#status", Static).update("Provider running…")
            return
        try:
            self._result = event.worker.result
        except Exception as exc:  # noqa: BLE001
            self.query_one("#status", Static).update(f"Failed: {exc}")
            return
        assert self._result is not None
        status = self.query_one("#status", Static)
        plan = self.query_one("#plan", Static)
        if not self._result.get("provider_configured", True) and not self._result.get(
            "plan_review"
        ):
            status.update(self._result.get("message") or "No provider configured.")
            plan.update("")
            return
        status.update(
            f"Status: {self._result.get('status') or ('ok' if self._result.get('ok') else 'failed')}"
        )
        plan.update(self._result.get("plan_review") or self._result.get("message") or "")
        can_apply = bool(self._result.get("ok") and self._result.get("prepared_transaction"))
        self.query_one("#apply", Button).disabled = not can_apply

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
            return
        if event.button.id == "apply":
            self._do_apply()

    def _do_apply(self) -> None:
        from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile

        self.query_one("#status", Static).update("Applying atomic transaction…")
        self.query_one("#apply", Button).disabled = True

        def _work() -> dict:
            return autonomous_reconcile(
                self.question_id,
                autonomy=AutonomyLevel.APPLY_SAFE,
                apply=True,
                yes=True,
                dry_run=False,
            )

        self._worker = self.run_worker(_work, exclusive=True, thread=True)

    def action_cancel(self) -> None:
        if self._worker is not None and self._worker.is_running:
            try:
                self._worker.cancel()
            except Exception:
                pass
        self.dismiss(None)
