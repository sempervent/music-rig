"""Human-readable projections of canonical MIDI state."""

from __future__ import annotations

import re

from music_rig.models import MidiDocument

BANNER = (
    "<!-- GENERATED FROM data/midi.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)


def _cell(value: object) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace(
        "\n", " "
    )


def render_midi_topology_section(data: dict | MidiDocument) -> str:
    doc = data if isinstance(data, MidiDocument) else MidiDocument.model_validate(data)
    lines = [BANNER, "", "## Endpoints", "", "| ID | Kind | Name |", "|---|---|---|"]
    for endpoint in doc.endpoints:
        lines.append(f"| {endpoint.id} | {endpoint.kind} | {_cell(endpoint.name)} |")
    lines.extend(
        [
            "",
            "## MIDI devices",
            "",
            "| Gear ref | Role | Notes |",
            "|---|---|---|",
        ]
    )
    for device in doc.devices:
        lines.append(
            f"| {device.gear_ref} | {_cell(device.role)} | {_cell(device.notes)} |"
        )
    lines.extend(
        [
            "",
            "## Physical links",
            "",
            "| ID | Source / port | Destination / port | Transport | Evidence | Notes |",
            "|---|---|---|---|---|---|",
        ]
    )
    if not doc.connections:
        lines.append(
            "| — | UNKNOWN | UNKNOWN | — | UNKNOWN | No verified physical links |"
        )
    for link in doc.connections:
        lines.append(
            f"| {link.id} | {link.source} / {_cell(link.source_port)} | "
            f"{link.destination} / {_cell(link.destination_port)} | "
            f"{link.transport.value} | {link.status.value} | {_cell(link.notes)} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_midi_clock_section(data: dict | MidiDocument) -> str:
    doc = data if isinstance(data, MidiDocument) else MidiDocument.model_validate(data)
    lines = [BANNER, "", "## Clock state", ""]
    if doc.clock.master is None:
        lines.append("Master: **UNKNOWN**")
    else:
        master = doc.clock.master
        ref = master.endpoint_ref or master.gear_ref
        lines.append(f"Master: **{ref}** — {master.status.value}")
        if master.notes:
            lines.extend(["", master.notes])
    lines.extend(
        [
            "",
            "| Destination | Enabled | Evidence | Notes |",
            "|---|---|---|---|",
        ]
    )
    if not doc.clock.destinations:
        lines.append("| — | UNKNOWN | UNKNOWN | — |")
    for destination in doc.clock.destinations:
        ref = destination.endpoint_ref or destination.gear_ref
        lines.append(
            f"| {ref} | {destination.enabled.value.upper()} | "
            f"{destination.status.value} | {_cell(destination.notes)} |"
        )
    lines.extend(
        [
            "",
            f"Transport start/stop evidence: **{doc.clock.transport.status.value}**",
            "",
            "## Channel assignments",
            "",
            "| Device | Channel | Evidence | Notes |",
            "|---|---:|---|---|",
        ]
    )
    if not doc.channels:
        lines.append("| — | UNKNOWN | UNKNOWN | — |")
    for assignment in doc.channels:
        lines.append(
            f"| {assignment.gear_ref} | {assignment.channel} | "
            f"{assignment.status.value} | {_cell(assignment.notes)} |"
        )
    lines.extend(
        [
            "",
            "## Ableton MIDI ports",
            "",
            "| Port | Direction | Reference | Track | Sync | Remote | Evidence |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    if not doc.ableton_ports:
        lines.append("| — | — | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |")
    for port in doc.ableton_ports:
        ref = port.endpoint_ref or port.gear_ref or port.port_name
        lines.append(
            f"| {port.id} | {port.direction} | {_cell(ref)} | "
            f"{port.track.value.upper()} | {port.sync.value.upper()} | "
            f"{port.remote.value.upper()} | {port.status.value} |"
        )
    lines.append("")
    return "\n".join(lines)


def _node_id(value: str) -> str:
    return "midi_" + re.sub(r"[^a-zA-Z0-9_]", "_", value)


def _label(value: str) -> str:
    return value.replace('"', "'")


def render_midi_topology_mermaid(data: dict | MidiDocument) -> str:
    doc = data if isinstance(data, MidiDocument) else MidiDocument.model_validate(data)
    lines = [
        "flowchart LR",
        "  %% Generated from data/midi.yaml; do not edit directly.",
    ]
    if not doc.connections:
        lines.append(
            '  midi_unknown["UNKNOWN physical MIDI topology<br/>No verified links"]'
        )
        return "\n".join(lines) + "\n"
    labels = {item.id: item.name for item in doc.endpoints}
    labels.update({item.gear_ref: item.gear_ref for item in doc.devices})
    used = {ref for link in doc.connections for ref in (link.source, link.destination)}
    for ref in sorted(used):
        lines.append(f'  {_node_id(ref)}["{_label(labels.get(ref, ref))}"]')
    for link in doc.connections:
        edge = (
            f"{link.transport.value}: {_label(link.source_port)} → "
            f"{_label(link.destination_port)} [{link.status.value}]"
        )
        lines.append(
            f'  {_node_id(link.source)} -->|"{edge}"| {_node_id(link.destination)}'
        )
    return "\n".join(lines) + "\n"
