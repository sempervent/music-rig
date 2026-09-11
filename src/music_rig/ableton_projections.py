"""Markdown projection for durable Ableton controller targets."""

from __future__ import annotations

from music_rig.models import AbletonDocument

BANNER = (
    "<!-- GENERATED FROM data/ableton.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)


def _cell(value: object) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def render_ableton_section(doc: AbletonDocument) -> str:
    lines = [BANNER]
    for title, items, name_field in (
        ("Tracks", doc.tracks, "name"),
        ("Sends", doc.sends, "label"),
        ("Actions", doc.actions, "label"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| ID | Label | Evidence | Notes |",
                "|---|---|---|---|",
            ]
        )
        for item in items:
            lines.append(
                f"| {item.id} | {_cell(getattr(item, name_field))} | "
                f"{item.evidence.value} | {_cell(item.notes)} |"
            )
        if not items:
            lines.append("| — | — | UNKNOWN | — |")
    lines.append("")
    return "\n".join(lines)
