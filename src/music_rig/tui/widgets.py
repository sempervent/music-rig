"""Shared TUI widget helpers."""

from __future__ import annotations

from rich.text import Text


def mode_cell(mode: str, *, staged_from: str | None = None) -> Text:
    """Render a patchbay mode cell; UNKNOWN is visually obvious."""
    raw = (mode or "unknown").strip().lower()
    display = raw.upper() if raw == "unknown" else raw
    if staged_from is not None and staged_from != raw:
        from_disp = staged_from.upper() if staged_from == "unknown" else staged_from
        text = Text(f"{from_disp} -> {display} *")
        text.stylize("bold yellow", 0, len(from_disp))
        return text
    if raw == "unknown":
        return Text(display, style="bold yellow")
    return Text(display)


def truncate(text: str, width: int = 60) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= width:
        return cleaned
    return cleaned[: max(0, width - 1)] + "…"


def format_target(target) -> str:
    if target is None:
        return "—"
    parts = [f"domain={target.domain}"]
    for attr in ("bay", "pair", "device", "channel", "path", "branch", "node", "gear", "context"):
        value = getattr(target, attr, None)
        if value:
            parts.append(f"{attr}={value}")
    return " ".join(parts)
