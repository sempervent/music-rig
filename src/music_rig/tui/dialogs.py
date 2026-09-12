"""Modal dialogs for the music-rig TUI.

Result ownership: each modal completes its result exactly once via ``complete()``.
Keyboard bindings and button activation converge on the same semantic handlers;
buttons use Textual ``action=`` so Enter-on-focused-button does not also fire a
separate ``Button.Pressed`` dismiss path alongside a screen Enter binding.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from music_rig.tui.screen_results import SingleShotMixin


class ConfirmModal(SingleShotMixin, ModalScreen[bool]):
    """Yes/No confirmation. Result True on confirm.

    Enter always confirms (explicit binding), regardless of Tab focus.
    Confirm is focused by default so keyboard users do not cancel by accident.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False, priority=True),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]

    def __init__(
        self, title: str, body: str = "", *, confirm_label: str = "Confirm"
    ) -> None:
        super().__init__()
        self._title = title
        self._body = body
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(self._title, id="modal-title")
            if self._body:
                yield Static(self._body, id="modal-body")
            with Horizontal(id="modal-buttons"):
                yield Button(
                    self._confirm_label,
                    variant="primary",
                    id="confirm",
                    action="screen.confirm",
                )
                yield Button("Cancel", id="cancel", action="screen.cancel")

    def on_mount(self) -> None:
        self.query_one("#confirm", Button).focus()

    def action_confirm(self) -> None:
        self.complete(True)

    def action_cancel(self) -> None:
        self.complete(False)


class DiscardModal(ConfirmModal):
    def __init__(self, dirty_count: int) -> None:
        super().__init__(
            "Discard unsaved changes?",
            f"{dirty_count} staged change(s) will be lost.",
            confirm_label="Discard",
        )


class InputModal(SingleShotMixin, ModalScreen[str | None]):
    """Single-line input. Returns stripped text, or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        title: str,
        *,
        placeholder: str = "",
        default: str = "",
        hint: str = "",
        allow_empty: bool = False,
        password: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._default = default
        self._hint = hint
        self._allow_empty = allow_empty
        self._password = password

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(self._title, id="modal-title")
            if self._hint:
                yield Static(self._hint, id="modal-body")
            yield Input(
                value=self._default,
                placeholder=self._placeholder,
                password=self._password,
                id="modal-input",
            )
            with Horizontal(id="modal-buttons"):
                yield Button("OK", variant="primary", id="confirm", action="screen.submit")
                yield Button("Cancel", id="cancel", action="screen.cancel")

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    def action_cancel(self) -> None:
        self.complete(None)

    def action_submit(self) -> None:
        value = self.query_one("#modal-input", Input).value
        self._finish(value)

    @on(Input.Submitted, "#modal-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        self._finish(event.value)

    def _finish(self, value: str) -> None:
        cleaned = value.strip()
        if not cleaned and not self._allow_empty:
            self.notify("Value cannot be empty", severity="warning")
            return
        self.complete(cleaned)


class SelectModeModal(SingleShotMixin, ModalScreen[str | None]):
    """Pick a canonical patchbay mode. Focus primary; Enter confirms; 1–4 keys."""

    MODES = ("normal", "half-normal", "thru", "unknown")
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm_focused", "Confirm", show=False, priority=True),
        Binding("1", "pick_normal", show=False),
        Binding("2", "pick_half", show=False),
        Binding("3", "pick_thru", show=False),
        Binding("4", "pick_unknown", show=False),
    ]

    def __init__(self, pair_label: str, current: str) -> None:
        super().__init__()
        self._pair_label = pair_label
        self._current = current
        self._selected = "normal"

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(f"Set mode for {self._pair_label}", id="modal-title")
            yield Static(
                f"Current: {self._current}\n"
                "Enter confirms focused button · 1–4 pick · Esc cancel",
                id="modal-body",
            )
            with Vertical(id="mode-choices"):
                yield Button(
                    "1 normal",
                    variant="primary",
                    id="mode-normal",
                    action="screen.pick_normal",
                )
                yield Button(
                    "2 half-normal", id="mode-half-normal", action="screen.pick_half"
                )
                yield Button("3 thru", id="mode-thru", action="screen.pick_thru")
                yield Button(
                    "4 unknown", id="mode-unknown", action="screen.pick_unknown"
                )
                yield Button("Cancel", id="cancel", action="screen.cancel")

    def on_mount(self) -> None:
        self.query_one("#mode-normal", Button).focus()
        self._selected = "normal"

    def action_cancel(self) -> None:
        self.complete(None)

    def action_confirm_focused(self) -> None:
        focused = self.focused
        if isinstance(focused, Button):
            bid = focused.id or ""
            if bid.startswith("mode-"):
                self.complete(bid.removeprefix("mode-"))
                return
            if bid == "cancel":
                self.complete(None)
                return
        self.complete(self._selected)

    def action_pick_normal(self) -> None:
        self.complete("normal")

    def action_pick_half(self) -> None:
        self.complete("half-normal")

    def action_pick_thru(self) -> None:
        self.complete("thru")

    def action_pick_unknown(self) -> None:
        self.complete("unknown")


class CommandLineModal(SingleShotMixin, ModalScreen[str | None]):
    """Vim COMMAND mode line (:w, :q, :wq, :q!)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False, priority=True),
    ]

    def __init__(self, *, prompt: str = ":") -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label("Command", id="modal-title")
            yield Static(
                ":w / :write  apply · :q quit (dirty refuses) · :wq apply+quit · :q! discard",
                id="modal-body",
            )
            yield Input(value=self._prompt, id="modal-input")

    def on_mount(self) -> None:
        inp = self.query_one("#modal-input", Input)
        inp.cursor_position = len(inp.value)
        inp.focus()

    def action_cancel(self) -> None:
        self.complete(None)

    @on(Input.Submitted, "#modal-input")
    def _submit(self, event: Input.Submitted) -> None:
        self.complete(event.value)


class ApplyPatchbayModal(SingleShotMixin, ModalScreen[tuple[bool, bool] | None]):
    """Apply staged patchbay changes. Returns (confirmed, create_snapshot) or None."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Apply", show=False, priority=True),
    ]

    def __init__(self, summary: str) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label("Apply patchbay changes?", id="modal-title")
            yield Static(self._summary, id="modal-body")
            yield Checkbox(
                "Create rig snapshot before applying",
                value=True,
                id="snap-check",
            )
            with Horizontal(id="modal-buttons"):
                yield Button(
                    "Apply", variant="primary", id="confirm", action="screen.confirm"
                )
                yield Button("Cancel", id="cancel", action="screen.cancel")

    def on_mount(self) -> None:
        self.query_one("#confirm", Button).focus()

    def action_confirm(self) -> None:
        snap = self.query_one("#snap-check", Checkbox).value
        self.complete((True, snap))

    def action_cancel(self) -> None:
        self.complete(None)


class HelpScreen(SingleShotMixin, ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("q", "close", "Close", show=False),
        Binding("?", "close", "Close", show=False),
    ]

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label("Keyboard help", id="modal-title")
            yield Static(self._text, id="modal-body")
            yield Button("Close", id="close", action="screen.close")

    def action_close(self) -> None:
        self.complete(None)
