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
    lines.extend(
        [
            "",
            "## Templates",
            "",
            "| ID | Label | Tracks | Sends | Requirements | Evidence | Notes |",
            "|---|---|---:|---:|---|---|---|",
        ]
    )
    for template in doc.templates:
        lines.append(
            f"| {template.id} | {_cell(template.label)} | {len(template.tracks)} | "
            f"{len(template.sends)} | {_cell(', '.join(template.requirements))} | "
            f"{template.evidence.value} | {_cell(template.notes)} |"
        )
        lines.extend(
            [
                "",
                f"### {template.label} tracks",
                "",
                "| Track | Role | Active | Record ready |",
                "|---|---|---|---|",
            ]
        )
        for track in template.tracks:
            lines.append(
                f"| {track.track_ref} | {_cell(track.role)} | "
                f"{str(track.active).lower()} | {_cell(track.record_ready)} |"
            )
        lines.extend(
            [
                "",
                "| Send | Role | Notes |",
                "|---|---|---|",
            ]
        )
        for send in template.sends:
            lines.append(
                f"| {send.send_ref} | {_cell(send.role)} | {_cell(send.notes)} |"
            )
    if not doc.templates:
        lines.append("| — | — | 0 | 0 | — | UNKNOWN | — |")
    lines.append("")
    return "\n".join(lines)
