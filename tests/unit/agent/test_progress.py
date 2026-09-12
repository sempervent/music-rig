"""Unit coverage for provider-neutral progress helpers."""

from __future__ import annotations

from io import StringIO

from music_rig.progress import (
    CallbackProgress,
    CollectingProgress,
    NullProgress,
    ProgressEvent,
    ProgressPhase,
    ProgressTracker,
    RichCliProgress,
    cli_progress,
    format_elapsed,
)


def test_progress_event_to_dict_handles_str_phase():
    ev = ProgressEvent(phase="CUSTOM", message="hi", elapsed_s=1.2345, detail={"k": 1})
    data = ev.to_dict()
    assert data["phase"] == "CUSTOM"
    assert data["elapsed_s"] == 1.234
    assert data["detail"] == {"k": 1}


def test_progress_event_enum_phase():
    ev = ProgressEvent(phase=ProgressPhase.APPLYING, message="go", elapsed_s=0.0)
    assert ev.to_dict()["phase"] == "APPLYING"


def test_null_and_collecting_and_callback():
    NullProgress().emit(ProgressEvent(phase=ProgressPhase.DONE, message="x", elapsed_s=0.0))
    collect = CollectingProgress()
    collect.emit(ProgressEvent(phase=ProgressPhase.ERROR, message="e", elapsed_s=0.1))
    assert len(collect.events) == 1

    seen: list[str] = []
    cb = CallbackProgress(lambda e: seen.append(e.message))
    cb.emit(ProgressEvent(phase=ProgressPhase.DONE, message="ok", elapsed_s=0.0))
    assert seen == ["ok"]
    CallbackProgress(None).emit(
        ProgressEvent(phase=ProgressPhase.DONE, message="noop", elapsed_s=0.0)
    )


def test_format_elapsed():
    assert format_elapsed(0) == "00:00"
    assert format_elapsed(65) == "01:05"
    assert format_elapsed(-3) == "00:00"


def test_rich_cli_progress_disabled_non_tty():
    buf = StringIO()
    with RichCliProgress(enabled=True, file=buf, quiet=False) as prog:
        prog.emit(
            ProgressEvent(
                phase=ProgressPhase.CONTACTING_PROVIDER,
                message="calling",
                elapsed_s=2.0,
                provider="ollama",
                model="m",
                timeout_s=30.0,
            )
        )
        assert prog._last is not None
        assert "calling" in prog._label(prog._last)
    # non-TTY StringIO → emit returns early after recording
    assert prog._status is None


def test_rich_cli_progress_quiet_and_disabled():
    prog = RichCliProgress(enabled=False, quiet=True)
    prog.emit(ProgressEvent(phase=ProgressPhase.DONE, message="x", elapsed_s=0.0))
    prog.stop()
    assert prog.enabled is False


def test_progress_tracker_emits_to_sink():
    sink = CollectingProgress()
    tracker = ProgressTracker(sink=sink, provider="p", model="m", timeout_s=5.0)
    tracker.emit(ProgressPhase.VALIDATING_PROPOSAL, "check", detail={"n": 1})
    assert len(sink.events) == 1
    assert sink.events[0].provider == "p"
    assert sink.events[0].detail == {"n": 1}
    assert tracker.elapsed() >= 0.0


def test_rich_cli_progress_tty_path(monkeypatch):
    class _TTY(StringIO):
        def isatty(self) -> bool:
            return True

    started = {"n": 0}
    updated = {"n": 0}

    class FakeStatus:
        def __init__(self, *a, **k):
            pass

        def start(self):
            started["n"] += 1

        def update(self, label):
            updated["n"] += 1

        def stop(self):
            pass

    class FakeConsole:
        def __init__(self, *a, **k):
            pass

    import types

    rich_console = types.ModuleType("rich.console")
    rich_console.Console = FakeConsole
    rich_status = types.ModuleType("rich.status")
    rich_status.Status = FakeStatus
    monkeypatch.setitem(__import__("sys").modules, "rich.console", rich_console)
    monkeypatch.setitem(__import__("sys").modules, "rich.status", rich_status)

    buf = _TTY()
    with RichCliProgress(enabled=True, file=buf) as prog:
        prog.emit(
            ProgressEvent(
                phase=ProgressPhase.PROVIDER_GENERATING,
                message="gen",
                elapsed_s=1.0,
                provider="ollama",
                timeout_s=10.0,
            )
        )
        prog.emit(
            ProgressEvent(phase=ProgressPhase.PARSING_RESPONSE, message="parse", elapsed_s=2.0)
        )
    assert started["n"] == 1
    assert updated["n"] == 1


def test_cli_progress_context_json_disables():
    with cli_progress(as_json=True) as prog:
        assert prog.enabled is False
    with cli_progress(quiet=True) as prog:
        assert prog.enabled is False
