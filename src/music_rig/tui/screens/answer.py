"""Question answer screen — keeps question text visible while editing the answer.

Save Draft → OPEN + DRAFT answer_state (resolved_at/reconciled_at null).
Answer & Resolve → FINAL (RESOLVED + resolved_at); reconciled_at stays null.
Answering does NOT invent verification_result (Stage 17).
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, TextArea

from music_rig import question_service
from music_rig.models import OpenQuestion, QuestionStatus
from music_rig.store import StoreError
from music_rig.tui.debug import format_error
from music_rig.tui.dialogs import ConfirmModal, HelpScreen
from music_rig.tui.modes import EditorMode, ModeController
from music_rig.tui.save_outcome import SaveOutcome
from music_rig.tui.widgets import format_target
from music_rig.tui.header import RigHeader


def _answer_context_markdown(q: OpenQuestion) -> str:
    fields = question_service.question_json_fields(q)
    try:
        from music_rig.reconciliation.service import question_state

        recon = question_state(q).value
    except Exception:
        recon = "—"
    lines = [
        f"# {q.id} — {fields['lifecycle_label']}",
        "",
        q.question,
        "",
        f"Area: {q.area}",
        f"Question status: {fields['question_status']}",
        f"Answer state: {fields['answer_state']}",
        f"Draft/final: {'FINAL' if fields['answer_state'] == 'FINAL' else ('DRAFT' if fields['answer_state'] == 'DRAFT' else 'UNANSWERED')}",
        f"Resolved at: {fields['resolved_at'] or '—'}",
        f"Reconciled at: {fields['reconciled_at'] or '— (pending)'}",
        f"Reconciliation state: {recon}",
        f"CURRENT answer: {q.answer.strip() or '—'}",
    ]
    if q.related_todos:
        lines.append(f"Related TODOs: {', '.join(q.related_todos)}")
    if q.target is not None:
        lines.append(f"Target: {format_target(q.target)}")
    v = q.verification
    if v is not None:
        lines.extend(
            [
                "",
                "## Verification prompt",
                "",
                v.prompt or "—",
                f"Kind: {v.kind.value if hasattr(v.kind, 'value') else v.kind}",
                f"Answer type: {v.answer_type.value if hasattr(v.answer_type, 'value') else v.answer_type}",
            ]
        )
        if v.choices:
            lines.append("Choices: " + ", ".join(v.choices))
    vr = q.verification_result
    if vr is not None:
        outcome = vr.outcome.value if hasattr(vr.outcome, "value") else vr.outcome
        lines.extend(
            [
                "",
                "## Last verification_result",
                "",
                f"Outcome: {outcome}",
                f"Observed: {vr.observed_value or '—'}",
                "(Answering does not invent verification_result.)",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Last verification_result",
                "",
                "— (none; use V / verify flow to record observation)",
            ]
        )
    return "\n".join(lines)


class AnswerScreen(Screen[tuple[SaveOutcome, str | None]]):
    """Split: question context stays visible; answer input below.

    Returns (outcome, question_id) so the list can refresh / explain filter hiding.
    """

    BINDINGS = [
        Binding("ctrl+s", "save_draft", "Save Draft", priority=True),
        Binding("ctrl+r", "answer_resolve", "Answer & Resolve", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("i", "enter_insert", "Insert", show=False),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, question_id: str, *, resolve_on_save: bool = False) -> None:
        super().__init__()
        self.question_id = question_id.upper()
        self.resolve_on_save = resolve_on_save
        self._modes = ModeController()
        self._q: OpenQuestion | None = None

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(
                f"{'Answer & Resolve' if self.resolve_on_save else 'Answer'} {self.question_id}",
                id="screen-title",
            )
            yield Static(self._modes.banner(), id="mode-banner")
            with VerticalScroll(id="detail-pane"):
                yield Static("Loading…", id="answer-context")
            yield Static("─" * 40, id="filter-label")
            yield Static(
                "Answer input — Save Draft (provisional) or Answer & Resolve (final)",
                id="dirty-label",
            )
            yield TextArea(id="answer-input")
            with Horizontal(id="modal-buttons"):
                if self.resolve_on_save:
                    yield Button(
                        "Answer & Resolve", variant="primary", id="btn-resolve"
                    )
                    yield Button("Save Draft", id="btn-draft")
                else:
                    yield Button(
                        "Answer & Resolve", variant="primary", id="btn-resolve"
                    )
                    yield Button("Save Draft", id="btn-draft")
                yield Button("Cancel", id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self._q = question_service.get_question(self.question_id)
        except StoreError as exc:
            self.notify(format_error(exc), severity="error")
            self.dismiss((SaveOutcome.FAILED, None))
            return
        self.query_one("#answer-context", Static).update(
            _answer_context_markdown(self._q)
        )
        area = self.query_one("#answer-input", TextArea)
        area.load_text(self._q.answer or "")
        area.focus()
        self._set_mode(EditorMode.INSERT)

    def _set_mode(self, mode: EditorMode) -> None:
        self._modes.set_mode(mode)
        try:
            self.query_one("#mode-banner", Static).update(self._modes.banner())
        except Exception:
            pass

    def action_enter_insert(self) -> None:
        self.query_one("#answer-input", TextArea).focus()
        self._set_mode(EditorMode.INSERT)

    def action_cancel(self) -> None:
        if self._modes.mode is EditorMode.INSERT:
            self._set_mode(EditorMode.NORMAL)
            return
        self.dismiss((SaveOutcome.CANCELLED, None))

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Answer screen\n\n"
                "Question text stays visible above the answer input.\n"
                "Save Draft         OPEN + draft answer (resolved_at null).\n"
                "Answer & Resolve   FINAL: RESOLVED + resolved_at "
                "(reconciled_at still null).\n"
                "Ctrl+S  Save Draft · Ctrl+R Answer & Resolve\n"
                "Does NOT invent verification_result — use V / verify "
                "for observations.\n"
            )
        )

    def _answer_text(self) -> str:
        return self.query_one("#answer-input", TextArea).text.strip()

    def action_save_draft(self) -> None:
        if self.resolve_on_save:
            # Opened as Resolve: Ctrl+S commits FINAL (Stage 18 compat)
            self._do_answer_resolve()
            return
        self._do_save_draft()

    def action_answer_resolve(self) -> None:
        self._do_answer_resolve()

    def action_resolve(self) -> None:
        """Compat alias for Resolve shortcut from Questions list."""
        self._do_answer_resolve()

    def _do_answer_resolve(self) -> None:
        answer = self._answer_text()
        if not answer:
            self.notify("Answer & Resolve requires a non-empty answer", severity="error")
            return

        def _confirm(ok: bool | None) -> None:
            if not ok:
                return
            try:
                updated = question_service.resolve_question(
                    self.question_id, answer, render=True
                )
            except StoreError as exc:
                self.notify(format_error(exc, prefix="FAILED: "), severity="error")
                return
            fresh = question_service.get_question(updated.id)
            assert fresh.answer == answer
            assert fresh.status == QuestionStatus.RESOLVED
            assert fresh.reconciled_at is None
            if fresh.verification_result is not None and (
                self._q is None or self._q.verification_result is None
            ):
                self.notify(
                    "FAILED: answering invented verification_result (bug)",
                    severity="error",
                )
                return

            def _recon(choice: bool | None) -> None:
                # True = Reconcile Now, False/None = Later
                if choice:
                    try:
                        self.app.open_domain("reconcile", updated.id)  # type: ignore[attr-defined]
                    except Exception:
                        self.notify(
                            f"Open reconcile: uv run rig reconcile plan question "
                            f"{updated.id}"
                        )
                self.dismiss((SaveOutcome.SUCCESS, updated.id))

            self.notify(
                f"{updated.id} answered and resolved. "
                "CURRENT reconciliation is still required "
                f"(reconciled_at null)."
            )
            self.app.push_screen(
                ConfirmModal(
                    f"{updated.id} reconciled_at still null",
                    "Answer is FINAL (RESOLVED). CURRENT reconciliation "
                    "is still required.\n\n"
                    "Reconcile Now opens the reconcile screen.\n"
                    "Later leaves reconciliation pending.\n"
                    "Enter = Reconcile Now · Esc = Later.",
                    confirm_label="Reconcile Now",
                ),
                _recon,
            )

        self.app.push_screen(
            ConfirmModal(
                f"Answer & Resolve {self.question_id}?",
                "Records a FINAL answer (RESOLVED + resolved_at).\n"
                "Does not invent verification_result.\n"
                "Does not rewrite CURRENT — reconcile separately.\n"
                "Enter confirms · Esc cancels.",
                confirm_label="Answer & Resolve",
            ),
            _confirm,
        )

    def _do_save_draft(self) -> None:
        answer = self._answer_text()
        if not answer:
            self.notify("Draft answer cannot be empty", severity="warning")
            return
        try:
            result = question_service.draft_question(
                self.question_id, answer, render=True
            )
            updated = result.get("question") or question_service.get_question(
                self.question_id
            )
        except StoreError as exc:
            self.notify(format_error(exc, prefix="FAILED: "), severity="error")
            return
        fresh = question_service.get_question(updated.id)
        if fresh.verification_result is not None and (
            self._q is None or self._q.verification_result is None
        ):
            self.notify(
                "FAILED: drafting invented verification_result (bug)",
                severity="error",
            )
            return
        fields = question_service.question_json_fields(fresh)
        self.notify(
            f"Saved draft {fresh.id}. Status OPEN / answer_state "
            f"{fields['answer_state']}. Resolve when final."
        )
        self.dismiss((SaveOutcome.SUCCESS, fresh.id))

    @on(Button.Pressed, "#btn-draft")
    def _btn_draft(self) -> None:
        self._do_save_draft()

    @on(Button.Pressed, "#btn-resolve")
    def _btn_resolve(self) -> None:
        self._do_answer_resolve()

    @on(Button.Pressed, "#btn-cancel")
    def _btn_cancel(self) -> None:
        self.dismiss((SaveOutcome.CANCELLED, None))
