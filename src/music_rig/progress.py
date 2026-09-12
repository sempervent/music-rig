"""Provider/reconciliation-neutral progress events."""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator, Protocol


class ProgressPhase(str, Enum):
    INSPECTING = "INSPECTING"
    BUILDING_PACKET = "BUILDING_PACKET"
    CLASSIFYING = "CLASSIFYING"
    CONTACTING_PROVIDER = "CONTACTING_PROVIDER"
    PROVIDER_LOADING = "PROVIDER_LOADING"
    PROVIDER_GENERATING = "PROVIDER_GENERATING"
    PARSING_RESPONSE = "PARSING_RESPONSE"
    REQUESTING_CONTEXT = "REQUESTING_CONTEXT"
    VALIDATING_PROPOSAL = "VALIDATING_PROPOSAL"
    PREPARING_TRANSACTION = "PREPARING_TRANSACTION"
    APPLYING = "APPLYING"
    RENDERING = "RENDERING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    phase: ProgressPhase | str
    message: str
    elapsed_s: float
    provider: str | None = None
    model: str | None = None
    timeout_s: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        phase = self.phase.value if isinstance(self.phase, ProgressPhase) else str(self.phase)
        return {
            "phase": phase,
            "message": self.message,
            "elapsed_s": round(self.elapsed_s, 3),
            "provider": self.provider,
            "model": self.model,
            "timeout_s": self.timeout_s,
            "detail": dict(self.detail),
        }


ProgressCallback = Callable[[ProgressEvent], None]


class ProgressSink(Protocol):
    def emit(self, event: ProgressEvent) -> None: ...


class NullProgress:
    def emit(self, event: ProgressEvent) -> None:
        return None


class CollectingProgress:
    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def emit(self, event: ProgressEvent) -> None:
        self.events.append(event)


class CallbackProgress:
    def __init__(self, callback: ProgressCallback | None) -> None:
        self._callback = callback

    def emit(self, event: ProgressEvent) -> None:
        if self._callback:
            self._callback(event)


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


class RichCliProgress:
    """Indeterminate Rich spinner + elapsed; never writes to stdout JSON streams."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        file=None,
        quiet: bool = False,
    ) -> None:
        self.enabled = enabled and not quiet
        self.file = file if file is not None else sys.stderr
        self._status = None
        self._started = time.monotonic()
        self._last: ProgressEvent | None = None

    def emit(self, event: ProgressEvent) -> None:
        self._last = event
        if not self.enabled:
            return
        if not getattr(self.file, "isatty", lambda: False)():
            return
        label = self._label(event)
        if self._status is None:
            try:
                from rich.console import Console
                from rich.status import Status

                console = Console(file=self.file, stderr=True)
                self._status = Status(label, console=console, spinner="dots")
                self._status.start()
            except Exception:
                self.enabled = False
                return
        else:
            self._status.update(label)

    def _label(self, event: ProgressEvent) -> str:
        bits = []
        if event.provider or event.model:
            bits.append(
                " / ".join(x for x in (event.provider, event.model) if x)
            )
        bits.append(event.message)
        elapsed = format_elapsed(event.elapsed_s)
        timeout = ""
        if event.timeout_s:
            timeout = f" · timeout {format_elapsed(event.timeout_s)}"
        return f"{' — '.join(bits)}    {elapsed}{timeout}"

    def stop(self) -> None:
        if self._status is not None:
            try:
                self._status.stop()
            except Exception:
                pass
            self._status = None

    def __enter__(self) -> RichCliProgress:
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


@dataclass
class ProgressTracker:
    """Stopwatch + sink helper used by orchestration."""

    sink: ProgressSink = field(default_factory=NullProgress)
    provider: str | None = None
    model: str | None = None
    timeout_s: float | None = None
    _t0: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def emit(
        self,
        phase: ProgressPhase | str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.sink.emit(
            ProgressEvent(
                phase=phase,
                message=message,
                elapsed_s=self.elapsed(),
                provider=self.provider,
                model=self.model,
                timeout_s=self.timeout_s,
                detail=detail or {},
            )
        )


@contextmanager
def cli_progress(
    *,
    as_json: bool = False,
    quiet: bool = False,
) -> Iterator[RichCliProgress]:
    """TTY stderr progress; disabled for --json / --quiet / non-TTY."""
    enabled = (not as_json) and (not quiet) and sys.stderr.isatty()
    prog = RichCliProgress(enabled=enabled, quiet=quiet)
    try:
        yield prog
    finally:
        prog.stop()
