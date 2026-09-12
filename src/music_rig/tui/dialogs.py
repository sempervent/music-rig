"""Modal dialogs for the music-rig TUI."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static


class ConfirmModal(ModalScreen[bool]):
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

    def __init__(self, title: str, body: str = "", *, confirm_label: str = "Confirm") -> None:
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
                yield Button(self._confirm_label, variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#confirm", Button).focus()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def _on_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)


class DiscardModal(ConfirmModal):
    def __init__(self, dirty_count: int) -> None:
        super().__init__(
            "Discard unsaved changes?",
            f"{dirty_count} staged change(s) will be lost.",
            confirm_label="Discard",
        )


class InputModal(ModalScreen[str | None]):
    """Single-line input. Returns stripped text, or None on cancel. Empty cancel if allow_empty=False."""

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
                yield Button("OK", variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#modal-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        self._finish(event.value)

    @on(Button.Pressed, "#confirm")
    def _on_confirm(self) -> None:
        value = self.query_one("#modal-input", Input).value
        self._finish(value)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def _finish(self, value: str) -> None:
        cleaned = value.strip()
        if not cleaned and not self._allow_empty:
            self.notify("Value cannot be empty", severity="warning")
            return
        self.dismiss(cleaned)


class SelectModeModal(ModalScreen[str | None]):
    """Pick a canonical patchbay mode."""

    MODES = ("normal", "half-normal", "thru", "unknown")
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("1", "pick_normal", show=False),
        Binding("2", "pick_half", show=False),
        Binding("3", "pick_thru", show=False),
        Binding("4", "pick_unknown", show=False),
    ]

    def __init__(self, pair_label: str, current: str) -> None:
        super().__init__()
        self._pair_label = pair_label
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(f"Set mode for {self._pair_label}", id="modal-title")
            yield Static(f"Current: {self._current}", id="modal-body")
            with Vertical(id="mode-choices"):
                yield Button("1 normal", id="mode-normal")
                yield Button("2 half-normal", id="mode-half-normal")
                yield Button("3 thru", id="mode-thru")
                yield Button("4 unknown", id="mode-unknown")
                yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_pick_normal(self) -> None:
        self.dismiss("normal")

    def action_pick_half(self) -> None:
        self.dismiss("half-normal")

    def action_pick_thru(self) -> None:
        self.dismiss("thru")

    def action_pick_unknown(self) -> None:
        self.dismiss("unknown")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed)
    def _on_mode(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("mode-"):
            self.dismiss(bid.removeprefix("mode-"))


class ApplyPatchbayModal(ModalScreen[tuple[bool, bool] | None]):
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
                yield Button("Apply", variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#confirm", Button).focus()

    def action_confirm(self) -> None:
        snap = self.query_one("#snap-check", Checkbox).value
        self.dismiss((True, snap))

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#confirm")
    def _on_confirm(self) -> None:
        snap = self.query_one("#snap-check", Checkbox).value
        self.dismiss((True, snap))

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
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
            yield Button("Close", id="close")

    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#close")
    def _on_close(self) -> None:
        self.dismiss(None)
