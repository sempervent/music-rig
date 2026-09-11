"""Typed CURRENT MIDI state and mutations for data/midi.yaml."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from music_rig.models import (
    CurrentPreview,
    INACTIVE_OWNERSHIP,
    MidiAbletonPort,
    MidiChannelAssignment,
    MidiClockDestination,
    MidiClockMaster,
    MidiDocument,
    MidiEvidenceStatus,
    MidiTransport,
    MidiTriState,
)
from music_rig.store import MIDI_PATH, StoreError, _dump_yaml, load_inventory, parse_existing_yaml

MIDI_HEADER = (
    "# Canonical CURRENT MIDI topology (not audio routing).\n"
    "# Evidence statuses: VERIFIED | INTENDED | UNKNOWN\n"
    "# Do not treat INTENDED design as VERIFIED CURRENT fact.\n"
)
_LINK_RE = re.compile(r"^midi-link-(\d{3})$")


def _extract_leading_comment_header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    index = 0
    saw_comment = False
    while index < len(lines):
        stripped = lines[index].lstrip()
        if stripped.startswith("#"):
            saw_comment = True
            index += 1
        elif not stripped.strip() and (saw_comment or index == 0):
            index += 1
        else:
            break
    return "".join(lines[:index]) if saw_comment else ""


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or MIDI_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_document(
    path: Path | None = None, *, inventory_path: Path | None = None
) -> MidiDocument:
    raw = load_raw(path)
    errors = validate_midi_doc(raw, inventory_path=inventory_path)
    if errors:
        raise StoreError("MIDI schema validation failed: " + "; ".join(errors))
    return MidiDocument.model_validate(raw)


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = (
        _extract_leading_comment_header(existing_text)
        if existing_text is not None
        else ""
    ) or MIDI_HEADER
    if not header.endswith("\n"):
        header += "\n"
    return header + _dump_yaml(data)


def _known_refs(doc: MidiDocument) -> set[str]:
    return {item.id for item in doc.endpoints} | {
        item.gear_ref for item in doc.devices
    }


def validate_midi_doc(
    data: dict[str, Any], *, inventory_path: Path | None = None
) -> list[str]:
    if not isinstance(data, dict):
        return ["MIDI document must be a mapping"]
    try:
        doc = MidiDocument.model_validate(data)
    except Exception as exc:
        return [str(exc)]

    errors: list[str] = []
    endpoint_refs = {item.id for item in doc.endpoints}
    device_refs = {item.gear_ref for item in doc.devices}
    known = endpoint_refs | device_refs
    inventory = None
    try:
        inventory = load_inventory(inventory_path)
    except StoreError as exc:
        errors.append(str(exc))

    if inventory is not None:
        for ref in sorted(device_refs):
            item = inventory.resolve(ref)
            if item is None:
                errors.append(f"MIDI device gear_ref {ref!r} does not resolve in inventory")
            elif item.ownership_status in INACTIVE_OWNERSHIP:
                errors.append(
                    f"MIDI device gear_ref {ref!r} resolves to inactive inventory "
                    f"status {item.ownership_status.value}"
                )

    for link in doc.connections:
        for field, ref in (("source", link.source), ("destination", link.destination)):
            if ref not in known:
                errors.append(f"MIDI link {link.id} {field} {ref!r} is unknown")
    for assignment in doc.channels:
        if assignment.gear_ref not in device_refs:
            errors.append(
                f"MIDI channel gear_ref {assignment.gear_ref!r} is not in devices"
            )
    if doc.clock.master is not None:
        ref = doc.clock.master.endpoint_ref or doc.clock.master.gear_ref or ""
        if ref not in known:
            errors.append(f"MIDI clock master ref {ref!r} is unknown")
    for destination in doc.clock.destinations:
        ref = destination.endpoint_ref or destination.gear_ref or ""
        if ref not in known:
            errors.append(f"MIDI clock destination ref {ref!r} is unknown")
    for port in doc.ableton_ports:
        ref = port.endpoint_ref or port.gear_ref
        if ref and ref not in known:
            errors.append(f"Ableton port {port.id} ref {ref!r} is unknown")
    return errors


def _validated(
    raw: dict[str, Any], *, inventory_path: Path | None = None
) -> MidiDocument:
    errors = validate_midi_doc(raw, inventory_path=inventory_path)
    if errors:
        raise StoreError("MIDI validation failed: " + "; ".join(errors))
    return MidiDocument.model_validate(raw)


def _assert_active_gear(ref: str, *, inventory_path: Path | None = None) -> None:
    inventory = load_inventory(inventory_path)
    item = inventory.resolve(ref)
    if item is None:
        raise StoreError(f"Unknown inventory gear_ref {ref!r}.")
    if item.ownership_status in INACTIVE_OWNERSHIP:
        raise StoreError(
            f"Cannot reference inactive gear {ref!r} "
            f"({item.ownership_status.value})."
        )


def _snapshot(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def _preview(
    domain: str,
    target: str,
    before: dict,
    after: dict,
    *,
    message: str,
) -> CurrentPreview:
    return CurrentPreview(
        domain=domain,
        target=target,
        before=before,
        after=after,
        changed=before != after,
        affected_files=["data/midi.yaml"],
        message=message,
    )


def _channel_value(channel: int | str) -> int | str:
    raw: int | str = channel
    if isinstance(channel, str):
        cleaned = channel.strip().upper()
        raw = int(cleaned) if cleaned.isdigit() else cleaned
    return MidiChannelAssignment(
        gear_ref="placeholder",
        channel=raw,
        status=MidiEvidenceStatus.VERIFIED,
    ).channel


def propose_set_channel(
    gear_ref: str,
    channel: int | str,
    *,
    status: MidiEvidenceStatus | None = None,
    notes: str | None = None,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    doc = _validated(raw, inventory_path=inventory_path)
    ref = gear_ref.strip()
    if ref not in {device.gear_ref for device in doc.devices}:
        raise StoreError(f"Unknown MIDI device gear_ref {ref!r}.")
    _assert_active_gear(ref, inventory_path=inventory_path)
    value = _channel_value(channel)
    evidence = (
        status
        if status is not None
        else MidiEvidenceStatus.UNKNOWN
        if value == "UNKNOWN"
        else MidiEvidenceStatus.VERIFIED
    )
    existing = next((item for item in doc.channels if item.gear_ref == ref), None)
    before = _snapshot(existing) if existing else {}
    updated = MidiChannelAssignment(
        gear_ref=ref,
        channel=value,
        status=evidence,
        notes=existing.notes if notes is None and existing else (notes or ""),
    )
    raw["channels"] = [
        _snapshot(updated) if item.gear_ref == ref else _snapshot(item)
        for item in doc.channels
    ]
    if existing is None:
        raw["channels"].append(_snapshot(updated))
    after = _snapshot(updated)
    return (
        _preview(
            "midi.channel",
            ref,
            before,
            after,
            message=f"{ref}: MIDI channel {value} ({evidence.value})",
        ),
        raw,
    )


def _next_link_id(connections: list) -> str:
    numbers = [
        int(match.group(1))
        for item in connections
        if (match := _LINK_RE.fullmatch(item.id))
    ]
    return f"midi-link-{(max(numbers) + 1 if numbers else 1):03d}"


def propose_add_link(
    *,
    source: str,
    source_port: str,
    destination: str,
    destination_port: str,
    transport: MidiTransport | str,
    status: MidiEvidenceStatus = MidiEvidenceStatus.VERIFIED,
    notes: str = "",
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    doc = _validated(raw, inventory_path=inventory_path)
    src, dst = source.strip(), destination.strip()
    known = _known_refs(doc)
    for label, ref in (("source", src), ("destination", dst)):
        if ref not in known:
            raise StoreError(f"Unknown MIDI {label} {ref!r}.")
        if ref in {device.gear_ref for device in doc.devices}:
            _assert_active_gear(ref, inventory_path=inventory_path)
    try:
        tx = transport if isinstance(transport, MidiTransport) else MidiTransport(transport.strip().upper())
    except ValueError as exc:
        raise StoreError("Transport must be DIN, USB, or VIRTUAL.") from exc
    exact = next(
        (
            link
            for link in doc.connections
            if (
                link.source,
                link.source_port,
                link.destination,
                link.destination_port,
                link.transport,
            )
            == (src, source_port.strip(), dst, destination_port.strip(), tx)
        ),
        None,
    )
    if exact is not None:
        snap = _snapshot(exact)
        return (
            _preview(
                "midi.link",
                exact.id,
                snap,
                snap,
                message=f"{exact.id}: exact MIDI link already exists.",
            ),
            raw,
        )
    link_id = _next_link_id(doc.connections)
    after = {
        "id": link_id,
        "source": src,
        "source_port": source_port.strip(),
        "destination": dst,
        "destination_port": destination_port.strip(),
        "transport": tx.value,
        "status": status.value,
        "notes": notes.strip(),
    }
    raw.setdefault("connections", []).append(after)
    _validated(raw, inventory_path=inventory_path)
    return (
        _preview(
            "midi.link",
            link_id,
            {},
            after,
            message=f"Add {link_id}: {src} -> {dst} ({tx.value}, {status.value})",
        ),
        raw,
    )


def propose_remove_link(
    link_id: str,
    *,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    doc = _validated(raw, inventory_path=inventory_path)
    key = link_id.strip().lower()
    existing = next((link for link in doc.connections if link.id.lower() == key), None)
    if existing is None:
        raise StoreError(f"Unknown MIDI link {link_id!r}.")
    before = _snapshot(existing)
    raw["connections"] = [
        _snapshot(link) for link in doc.connections if link.id.lower() != key
    ]
    return (
        _preview(
            "midi.link",
            existing.id,
            before,
            {},
            message=f"Remove {existing.id}",
        ),
        raw,
    )


def _propose_verify_link(
    link_id: str,
    *,
    inventory_path: Path | None = None,
    data: dict[str, Any],
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data)
    doc = _validated(raw, inventory_path=inventory_path)
    existing = next((item for item in doc.connections if item.id == link_id), None)
    if existing is None:
        raise StoreError(f"Unknown MIDI link {link_id!r}.")
    before = _snapshot(existing)
    after = {**before, "status": MidiEvidenceStatus.VERIFIED.value}
    raw["connections"] = [
        after if item.id == link_id else _snapshot(item) for item in doc.connections
    ]
    return (
        _preview(
            "midi.link",
            link_id,
            before,
            after,
            message=f"{link_id}: evidence VERIFIED",
        ),
        raw,
    )


def _ref_payload(ref: str, doc: MidiDocument) -> dict[str, str]:
    if ref in {item.id for item in doc.endpoints}:
        return {"endpoint_ref": ref}
    if ref in {item.gear_ref for item in doc.devices}:
        return {"gear_ref": ref}
    raise StoreError(f"Unknown MIDI endpoint or gear_ref {ref!r}.")


def propose_set_clock_master(
    ref: str,
    *,
    status: MidiEvidenceStatus = MidiEvidenceStatus.VERIFIED,
    notes: str | None = None,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    doc = _validated(raw, inventory_path=inventory_path)
    clean = ref.strip()
    payload = _ref_payload(clean, doc)
    if "gear_ref" in payload:
        _assert_active_gear(clean, inventory_path=inventory_path)
    existing = doc.clock.master
    updated = MidiClockMaster(
        **payload,
        status=status,
        notes=existing.notes if notes is None and existing else (notes or ""),
    )
    before = _snapshot(existing) if existing else {}
    after = _snapshot(updated)
    raw["clock"]["master"] = after
    return (
        _preview(
            "midi.clock_master",
            clean,
            before,
            after,
            message=f"MIDI clock master: {clean} ({status.value})",
        ),
        raw,
    )


def propose_set_clock_destination(
    ref: str,
    enabled: MidiTriState | str,
    *,
    status: MidiEvidenceStatus | None = None,
    notes: str | None = None,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    doc = _validated(raw, inventory_path=inventory_path)
    clean = ref.strip()
    payload = _ref_payload(clean, doc)
    if "gear_ref" in payload:
        _assert_active_gear(clean, inventory_path=inventory_path)
    try:
        state = enabled if isinstance(enabled, MidiTriState) else MidiTriState(enabled.strip().lower())
    except ValueError as exc:
        raise StoreError("Clock state must be on, off, or unknown.") from exc
    existing = next(
        (
            item
            for item in doc.clock.destinations
            if (item.endpoint_ref or item.gear_ref) == clean
        ),
        None,
    )
    evidence = (
        status
        if status is not None
        else MidiEvidenceStatus.UNKNOWN
        if state == MidiTriState.UNKNOWN
        else MidiEvidenceStatus.VERIFIED
    )
    updated = MidiClockDestination(
        **payload,
        enabled=state,
        status=evidence,
        notes=existing.notes if notes is None and existing else (notes or ""),
    )
    before = _snapshot(existing) if existing else {}
    after = _snapshot(updated)
    raw["clock"]["destinations"] = [
        after if (item.endpoint_ref or item.gear_ref) == clean else _snapshot(item)
        for item in doc.clock.destinations
    ]
    if existing is None:
        raw["clock"]["destinations"].append(after)
    return (
        _preview(
            "midi.clock_destination",
            clean,
            before,
            after,
            message=f"MIDI clock destination {clean}: {state.value} ({evidence.value})",
        ),
        raw,
    )


def propose_ableton_set(
    port_id: str,
    *,
    track: MidiTriState | str | None = None,
    sync: MidiTriState | str | None = None,
    remote: MidiTriState | str | None = None,
    status: MidiEvidenceStatus | None = None,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    doc = _validated(raw, inventory_path=inventory_path)
    existing = next(
        (port for port in doc.ableton_ports if port.id == port_id.strip()), None
    )
    if existing is None:
        raise StoreError(
            f"Unknown Ableton port {port_id!r}; add ports to midi.yaml only from "
            "verified Ableton Preferences evidence."
        )
    if track is sync is remote is None:
        raise StoreError("Specify at least one of --track, --sync, or --remote.")

    def parsed(value: MidiTriState | str | None, current: MidiTriState) -> MidiTriState:
        if value is None:
            return current
        try:
            return value if isinstance(value, MidiTriState) else MidiTriState(value.strip().lower())
        except ValueError as exc:
            raise StoreError("Ableton state must be on, off, or unknown.") from exc

    states = (
        parsed(track, existing.track),
        parsed(sync, existing.sync),
        parsed(remote, existing.remote),
    )
    evidence = (
        status
        if status is not None
        else MidiEvidenceStatus.UNKNOWN
        if MidiTriState.UNKNOWN in states
        else MidiEvidenceStatus.VERIFIED
    )
    updated = MidiAbletonPort(
        **{
            **existing.model_dump(),
            "track": states[0],
            "sync": states[1],
            "remote": states[2],
            "status": evidence,
        }
    )
    before, after = _snapshot(existing), _snapshot(updated)
    raw["ableton_ports"] = [
        after if port.id == existing.id else _snapshot(port)
        for port in doc.ableton_ports
    ]
    return (
        _preview(
            "midi.ableton",
            existing.id,
            before,
            after,
            message=f"Ableton MIDI port {existing.id} updated ({evidence.value})",
        ),
        raw,
    )


def propose_batch(
    mutations: list[dict[str, Any]],
    *,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(midi_path))
    before_doc = _validated(raw, inventory_path=inventory_path)
    for mutation in mutations:
        op = mutation.get("op")
        kwargs = {key: value for key, value in mutation.items() if key != "op"}
        if op == "set_channel":
            _, raw = propose_set_channel(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        elif op == "add_link":
            _, raw = propose_add_link(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        elif op == "remove_link":
            _, raw = propose_remove_link(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        elif op == "verify_link":
            _, raw = _propose_verify_link(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        elif op == "set_clock_master":
            _, raw = propose_set_clock_master(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        elif op == "set_clock_destination":
            _, raw = propose_set_clock_destination(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        elif op == "ableton_set":
            _, raw = propose_ableton_set(
                data=raw, inventory_path=inventory_path, **kwargs
            )
        else:
            raise StoreError(f"Unknown MIDI batch op {op!r}.")
    after_doc = _validated(raw, inventory_path=inventory_path)
    before = before_doc.model_dump(mode="json", exclude_none=True)
    after = after_doc.model_dump(mode="json", exclude_none=True)
    return (
        _preview(
            "midi.verify",
            "midi",
            before,
            after,
            message=f"MIDI verification batch: {len(mutations)} mutation(s)",
        ),
        raw,
    )
