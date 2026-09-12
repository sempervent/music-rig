"""TUI Agent Plan / unified Reconcile screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from music_rig.tui.header import RigHeader


class AgentPlanScreen(ModalScreen[dict | None]):
    """Reconcile planning: deterministic or Cursor/Ollama, then optional Apply."""

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
        yield Static(f"Reconcile — {self.question_id}", id="title")
        with VerticalScroll(id="body"):
            yield Static("Planning…", id="status")
            yield Static("", id="plan")
        yield Button("Apply", id="apply", disabled=True)
        yield Button("Configure Provider", id="setup", disabled=True)
        yield Button("Cancel", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        self._worker = self.run_worker(self._run_plan, exclusive=True, thread=True)

    def _run_plan(self) -> dict:
        from music_rig.reconciliation.run import reconcile_run

        return reconcile_run(self.question_id, apply=False, yes=False, dry_run=True)

    def on_worker_state_changed(self, event) -> None:  # noqa: ANN001
        if event.worker is not self._worker:
            return
        if not event.worker.is_finished:
            label = "Planning…"
            self.query_one("#status", Static).update(label)
            return
        try:
            self._result = event.worker.result
        except Exception as exc:  # noqa: BLE001
            self.query_one("#status", Static).update(f"Failed: {exc}")
            return
        assert self._result is not None
        status = self.query_one("#status", Static)
        plan = self.query_one("#plan", Static)
        mode = self._result.get("mode")
        provider = self._result.get("provider_label") or self._result.get("provider")
        if mode == "needs_provider":
            status.update("Agent reconciliation is required.")
            plan.update(self._result.get("message") or "")
            self.query_one("#setup", Button).disabled = False
            self.query_one("#apply", Button).disabled = True
            return
        status.update(
            f"Mode: {mode}"
            + (f" · Planner: {provider}" if provider else "")
            + f" · {'ok' if self._result.get('ok') else 'blocked'}"
        )
        plan.update(
            self._result.get("plan_review")
            or self._result.get("message")
            or ""
        )
        can_apply = bool(
            self._result.get("ok")
            and (
                self._result.get("prepared_transaction")
                or self._result.get("mode") == "deterministic"
            )
        )
        self.query_one("#apply", Button).disabled = not can_apply

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
            return
        if event.button.id == "setup":
            self.app.push_screen(ProviderSetupScreen())
            return
        if event.button.id == "apply":
            self._do_apply()

    def _do_apply(self) -> None:
        from music_rig.reconciliation.run import reconcile_run

        self.query_one("#status", Static).update("Applying…")
        self.query_one("#apply", Button).disabled = True

        def _work() -> dict:
            return reconcile_run(
                self.question_id, apply=True, yes=True, dry_run=False
            )

        self._worker = self.run_worker(_work, exclusive=True, thread=True)

    def action_cancel(self) -> None:
        if self._worker is not None and self._worker.is_running:
            try:
                self._worker.cancel()
            except Exception:
                pass
        self.dismiss(None)


class ProviderSetupScreen(ModalScreen[None]):
    """Pick Cursor or Ollama; save via local_config service."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        from music_rig.agent.provider import detect_providers

        detected = detect_providers()
        yield RigHeader(show_clock=False)
        yield Static("Configure Provider", id="title")
        with VerticalScroll():
            c = detected["cursor"]
            o = detected["ollama"]
            yield Static(
                f"Cursor: {'✓' if c['available'] else '✗'} {c.get('version') or ''}\n"
                f"Ollama: {'✓' if o['available'] else '✗'} "
                f"{', '.join((o.get('models') or [])[:5])}"
            )
        yield Button("Use Cursor", id="cursor", disabled=not c["available"])
        ollama_ok = bool(o.get("models")) and len(o.get("models") or []) == 1
        yield Button(
            "Use Ollama" + ("" if ollama_ok else " (use CLI for multi-model)"),
            id="ollama",
            disabled=not ollama_ok,
        )
        yield Button("Cancel", id="cancel")
        yield Footer()
        self._detected = detected

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from music_rig.local_config import update_agent_config

        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "cursor":
            update_agent_config(provider="cursor")
            self.notify("Provider set to Cursor")
            self.dismiss(None)
            return
        if event.button.id == "ollama":
            models = (self._detected.get("ollama") or {}).get("models") or []
            if len(models) != 1:
                self.notify(
                    "Multiple Ollama models — run: "
                    "uv run rig agent provider use ollama --model <name>",
                    severity="warning",
                )
                return
            update_agent_config(provider="ollama", ollama_model=models[0])
            self.notify(f"Provider set to Ollama / {models[0]}")
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
