"""Markdown projections and text views for controller mappings."""

from __future__ import annotations

from music_rig.control_state import resolve_message_channel
from music_rig.models import ControllersDocument

BANNER = (
    "<!-- GENERATED FROM data/controllers.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)


def _cell(value: object) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def _target(control) -> str:
    target = control.target
    if target.state.value != "MAPPED":
        return target.state.value
    ref = target.track or target.send or target.action or target.notes or "—"
    return f"{target.kind.value}: {ref}"


def _messages(gear_ref: str, control, *, resolve_device: bool = False) -> str:
    values = []
    for message in control.messages:
        channel = message.channel
        if resolve_device and channel == "DEVICE":
            channel = resolve_message_channel(gear_ref, message)
        values.append(
            f"{message.type.value} {message.number} ch {channel or '—'} "
            f"({message.value_behavior.value})"
        )
    return "; ".join(values) or "—"


def render_controller_mappings_section(doc: ControllersDocument) -> str:
    lines = [
        BANNER,
        "",
        "## Coverage",
        "",
        "| Controller | Coverage | Contexts | Modeled controls | Evidence |",
        "|---|---|---:|---:|---|",
    ]
    for controller in doc.controllers:
        controls = [control for context in controller.contexts for control in context.controls]
        evidence = sorted(
            {
                context.evidence.value
                for context in controller.contexts
            }
            | {control.evidence.value for control in controls}
        )
        lines.append(
            f"| {controller.gear_ref} | {controller.coverage.value} | "
            f"{len(controller.contexts)} | {len(controls)} | {_cell(', '.join(evidence))} |"
        )
    for controller in doc.controllers:
        lines.extend(["", f"## {controller.gear_ref}", "", controller.notes, ""])
        lines.extend(
            [
                "| Context | Kind | Control | Type | Availability | Message | Target | Evidence | Notes |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        rows = 0
        for context in controller.contexts:
            if not context.controls:
                lines.append(
                    f"| {context.id} | {context.kind.value} | — | — | — | — | "
                    f"UNKNOWN | {context.evidence.value} | {_cell(context.notes)} |"
                )
                rows += 1
            for control in context.controls:
                lines.append(
                    f"| {context.id} | {context.kind.value} | {control.id} | "
                    f"{control.physical_type.value} | {control.availability.value} | "
                    f"{_cell(_messages(controller.gear_ref, control))} | "
                    f"{_cell(_target(control))} | {control.evidence.value} | "
                    f"{_cell(control.notes)} |"
                )
                rows += 1
        if not rows:
            lines.append("| — | — | — | — | — | — | UNKNOWN | UNKNOWN | No contexts modeled |")
    lines.append("")
    return "\n".join(lines)

