"""Question answer screen — keeps question text visible while editing the answer.

Save Answer (via update_question_fields) may keep status OPEN.
Resolve (status → RESOLVED) requires a non-empty answer and confirm.
Answering does NOT invent verification_result (Stage 17).
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static, TextArea

from music_rig import question_service
from music_rig.models import OpenQuestion, QuestionStatus
from music_rig.store import StoreError
from music_rig.tui.debug import format_error
from music_rig.tui.dialogs import ConfirmModal, HelpScreen
from music_rig.tui.modes import EditorMode, ModeController
from music_rig.tui.save_outcome import SaveOutcome
from music_rig.tui.widgets import format_target


def _answer_context_markdown(q: OpenQuestion) -> str:
    lines = [
        f"# {q.id} — {q.status.value}",
        "",
        q.question,
        "",
        f"Area: {q.area}",
        f"Status: {q.status.value}",
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
        Binding("ctrl+s", "save_answer", "Save Answer", priority=True),
        Binding("ctrl+r", "resolve", "Resolve", priority=True),
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
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(
                f"{'Resolve' if self.resolve_on_save else 'Answer'} {self.question_id}",
                id="screen-title",
            )
            yield Static(self._modes.banner(), id="mode-banner")
            with VerticalScroll(id="detail-pane"):
                yield Static("Loading…", id="answer-context")
            yield Static("─" * 40, id="filter-label")
            yield Static("Answer input (question text stays visible above)", id="dirty-label")
            yield TextArea(id="answer-input")
            with Horizontal(id="modal-buttons"):
                if self.resolve_on_save:
                    yield Button("Resolve", variant="primary", id="btn-resolve")
                else:
                    yield Button("Save Answer", variant="primary", id="btn-save")
                    yield Button("Resolve…", id="btn-resolve")
                yield Button("Cancel", id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self._q = question_service.get_question(self.question_id)
        except StoreError as exc:
            self.notify(format_error(exc), severity="error")
            self.dismiss((SaveOutcome.FAILED, None))
            return
        self.query_one("#answer-context", Static).update(_answer_context_markdown(self._q))
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
                "Save Answer  writes answer via update_question_fields (may stay OPEN).\n"
                "Resolve      requires answer; sets status RESOLVED (not reconciled).\n"
                "Ctrl+S      Save Answer (or Resolve when opened as Resolve).\n"
                "Does NOT invent verification_result — use V / verify for observations.\n"
            )
        )

    def _answer_text(self) -> str:
        return self.query_one("#answer-input", TextArea).text.strip()

    def action_save_answer(self) -> None:
        if self.resolve_on_save:
            self.action_resolve()
            return
        self._do_save_answer()

    def action_resolve(self) -> None:
        answer = self._answer_text()
        if not answer:
            self.notify("Resolve requires a non-empty answer", severity="error")
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
            # Preserve Stage 17: resolve must not invent verification_result
            fresh = question_service.get_question(updated.id)
            assert fresh.answer == answer
            self.notify(
                f"Saved {updated.id}. Resolved. CURRENT reconciliation still required "
                f"(rig reconcile plan question {updated.id})."
            )
            self.dismiss((SaveOutcome.SUCCESS, updated.id))

        self.app.push_screen(
            ConfirmModal(
                f"Resolve {self.question_id}?",
                "Recording an answer does not automatically rewrite CURRENT.\n"
                "Does not invent verification_result.\n"
                "Reconcile separately if the answer changes physical truth.\n"
                "Enter confirms · Esc cancels.",
                confirm_label="Resolve",
            ),
            _confirm,
        )

    def _do_save_answer(self) -> None:
        answer = self._answer_text()
        if not answer:
            self.notify("Answer cannot be empty", severity="warning")
            return
        try:
            updated = question_service.update_question_fields(
                self.question_id, answer=answer, render=True
            )
        except StoreError as exc:
            self.notify(format_error(exc, prefix="FAILED: "), severity="error")
            return
        # Must not invent verification_result
        fresh = question_service.get_question(updated.id)
        if fresh.verification_result is not None and (
            self._q is None or self._q.verification_result is None
        ):
            # Should never happen — guard for tests / regressions
            self.notify(
                "FAILED: answering invented verification_result (bug)",
                severity="error",
            )
            return
        status_note = (
            f"Status remains {updated.status.value}."
            if updated.status != QuestionStatus.RESOLVED
            else "Status is RESOLVED."
        )
        self.notify(f"Saved {updated.id}. Answer recorded. {status_note}")
        self.dismiss((SaveOutcome.SUCCESS, updated.id))

    @on(Button.Pressed, "#btn-save")
    def _btn_save(self) -> None:
        self._do_save_answer()

    @on(Button.Pressed, "#btn-resolve")
    def _btn_resolve(self) -> None:
        self.action_resolve()

    @on(Button.Pressed, "#btn-cancel")
    def _btn_cancel(self) -> None:
        self.dismiss((SaveOutcome.CANCELLED, None))
