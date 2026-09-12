"""Shared TUI operation-status widget for long-running work."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from music_rig.progress import format_elapsed


class OperationStatus(Static):
    """Persistent status: message, phase, elapsed, success/failure."""

    DEFAULT_CSS = """
    OperationStatus {
        height: auto;
        padding: 0 1;
        color: $text;
    }
    OperationStatus.-running {
        color: $secondary;
    }
    OperationStatus.-error {
        color: $error;
    }
    OperationStatus.-success {
        color: $success;
    }
    """

    message: reactive[str] = reactive("")
    phase: reactive[str] = reactive("")
    elapsed_s: reactive[float] = reactive(0.0)
    state: reactive[str] = reactive("idle")

    def set_running(
        self,
        message: str,
        *,
        elapsed_s: float | None = None,
        phase: str | None = None,
    ) -> None:
        self.state = "running"
        self.message = message
        if elapsed_s is not None:
            self.elapsed_s = elapsed_s
        if phase is not None:
            self.phase = phase
        self.remove_class("-error", "-success")
        self.add_class("-running")
        self._refresh_label()

    def tick_elapsed(self, elapsed_s: float) -> None:
        if self.state != "running":
            return
        self.elapsed_s = elapsed_s
        self._refresh_label()

    def set_success(self, message: str) -> None:
        self.state = "success"
        self.message = message
        self.remove_class("-running", "-error")
        self.add_class("-success")
        self.update(message)

    def set_error(self, message: str) -> None:
        self.state = "error"
        self.message = message
        self.remove_class("-running", "-success")
        self.add_class("-error")
        self.update(f"Failed: {message}")

    def set_idle(self, message: str = "") -> None:
        self.state = "idle"
        self.message = message
        self.remove_class("-running", "-error", "-success")
        self.update(message)

    def _refresh_label(self) -> None:
        bits = [self.message]
        if self.phase:
            bits.append(f"Phase: {self.phase}")
        bits.append(f"Elapsed: {format_elapsed(self.elapsed_s)}")
        self.update("\n".join(bits))
