"""TUI Agent Plan / unified Reconcile screen."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from music_rig.tui.header import RigHeader
from music_rig.tui.widgets.op_status import OperationStatus


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
        self._cancelled = False
        self._t0 = time.monotonic()

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        yield Static(f"Reconcile — {self.question_id}", id="title")
        yield OperationStatus(id="op-status")
        with VerticalScroll(id="body"):
            yield Static("", id="plan")
        with Horizontal(id="actions"):
            yield Button("Apply", id="apply", disabled=True)
            yield Button("Verify Now", id="verify", disabled=True)
            yield Button("Configure Provider", id="setup", disabled=True)
            yield Button("Cancel", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        status = self.query_one("#op-status", OperationStatus)
        status.set_running("Classifying reconciliation…")
        self._worker = self.run_worker(self._run_plan, exclusive=True, thread=True)
        self.set_interval(0.5, self._tick_elapsed)

    def _tick_elapsed(self) -> None:
        if self._worker is not None and self._worker.is_running:
            status = self.query_one("#op-status", OperationStatus)
            status.tick_elapsed(time.monotonic() - self._t0)

    def _run_plan(self) -> dict:
        from music_rig.reconciliation.run import reconcile_run

        events: list = []

        def on_progress(ev) -> None:
            events.append(ev)
            # Cross-thread: Textual call_from_thread
            try:
                self.app.call_from_thread(self._on_progress_event, ev)
            except Exception:
                pass

        result = reconcile_run(
            self.question_id,
            apply=False,
            yes=False,
            dry_run=True,
            on_progress=on_progress,
        )
        result["_progress_events"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in events]
        return result

    def _on_progress_event(self, ev) -> None:
        if self._cancelled:
            return
        status = self.query_one("#op-status", OperationStatus)
        msg = ev.message
        if ev.provider or ev.model:
            who = " / ".join(x for x in (ev.provider, ev.model) if x)
            msg = f"{who} — {ev.message}"
        status.set_running(
            msg, elapsed_s=ev.elapsed_s, phase=str(getattr(ev.phase, "value", ev.phase))
        )

    def on_worker_state_changed(self, event) -> None:  # noqa: ANN001
        if event.worker is not self._worker:
            return
        if not event.worker.is_finished:
            return
        if self._cancelled:
            return
        try:
            self._result = event.worker.result
        except Exception as exc:  # noqa: BLE001
            self.query_one("#op-status", OperationStatus).set_error(str(exc))
            return
        assert self._result is not None
        if self._result.get("_discarded"):
            return
        self._render_result(self._result)

    def _render_result(self, result: dict) -> None:
        status = self.query_one("#op-status", OperationStatus)
        plan = self.query_one("#plan", Static)
        mode = result.get("mode")
        dispatch = (result.get("dispatch") or {}).get("mode")
        provider = result.get("provider_label") or result.get("provider")

        if mode == "needs_verification" or dispatch == "HUMAN_OBSERVATION":
            status.set_idle("Human verification required")
            plan.update(result.get("message") or "Human verification required")
            self.query_one("#verify", Button).disabled = False
            self.query_one("#apply", Button).disabled = True
            self.query_one("#setup", Button).disabled = True
            return

        if mode == "needs_provider":
            status.set_idle("Provider required")
            plan.update(result.get("message") or "")
            self.query_one("#setup", Button).disabled = False
            self.query_one("#apply", Button).disabled = True
            return

        if mode == "needs_human":
            status.set_idle("Human answer required")
            plan.update(result.get("message") or "")
            return

        if mode == "needs_clarification":
            status.set_idle("Human clarification required")
            plan.update(result.get("message") or "")
            return

        timing = result.get("timing_summary") or ""
        status.set_success(
            f"Mode: {mode}"
            + (f" · Planner: {provider}" if provider else "")
            + f" · {'ok' if result.get('ok') else 'blocked'}"
        )
        body = result.get("plan_review") or result.get("message") or ""
        if timing:
            body = f"{body}\n\n{timing}"
        plan.update(body)
        can_apply = bool(
            result.get("ok")
            and (result.get("prepared_transaction") or result.get("mode") == "deterministic")
        )
        self.query_one("#apply", Button).disabled = not can_apply

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
            return
        if event.button.id == "setup":
            self.app.push_screen(ProviderSetupScreen())
            return
        if event.button.id == "verify":
            self._goto_verify()
            return
        if event.button.id == "apply":
            self._do_apply()

    def _goto_verify(self) -> None:
        self.dismiss(
            {
                "ok": False,
                "mode": "needs_verification",
                "redirect": "verify",
                "artifact_id": self.question_id,
            }
        )

    def _do_apply(self) -> None:
        from music_rig.reconciliation.run import reconcile_run

        self.query_one("#op-status", OperationStatus).set_running("Applying…")
        self.query_one("#apply", Button).disabled = True

        def _work() -> dict:
            return reconcile_run(self.question_id, apply=True, yes=True, dry_run=False)

        self._worker = self.run_worker(_work, exclusive=True, thread=True)

    def action_cancel(self) -> None:
        """Cancel planning: discard later provider response; no canonical writes."""
        self._cancelled = True
        if self._result is not None:
            self._result["_discarded"] = True
        if self._worker is not None and self._worker.is_running:
            try:
                self._worker.cancel()
            except Exception:
                pass
        status = self.query_one("#op-status", OperationStatus)
        status.set_idle("Cancelled — no changes written")
        # Note: blocking HTTP may continue in the worker thread until the socket
        # returns; the response is ignored and no mutation occurs.
        self.dismiss(None)


class ProviderSetupScreen(ModalScreen[None]):
    """Pick Cursor or Ollama; save via local_config service."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        from music_rig.agent.ollama_provider import ollama_model_details
        from music_rig.agent.provider import detect_providers

        detected = detect_providers()
        yield RigHeader(show_clock=False)
        yield Static("Configure Provider", id="title")
        with VerticalScroll():
            c = detected["cursor"]
            o = detected["ollama"]
            lines = [
                f"Cursor: {'✓' if c['available'] else '✗'} {c.get('version') or ''}",
                f"Ollama: {'✓' if o['available'] else '✗'}",
            ]
            for m in ollama_model_details()[:12]:
                size = m.get("size")
                size_s = f" ({size // (1024**3)} GB)" if isinstance(size, int) else ""
                lines.append(f"  • {m['name']}{size_s}")
            yield Static("\n".join(lines))
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
