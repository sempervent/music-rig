"""Typed controller mapping state and mutations for data/controllers.yaml."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from music_rig import ableton_state, midi_state
from music_rig.models import (
    INACTIVE_OWNERSHIP,
    ControlAvailability,
    ControllersDocument,
    ControlTarget,
    CurrentPreview,
    MidiEvidenceStatus,
    MidiMessage,
    PerformanceDocument,
    TargetKind,
    TargetState,
)
from music_rig.store import (
    CONTROLLERS_PATH,
    PERFORMANCE_PATH,
    StoreError,
    _dump_yaml,
    load_inventory,
    parse_existing_yaml,
)

CONTROLLERS_HEADER = (
    "# Canonical controller mapping state (not MIDI topology — see data/midi.yaml).\n"
    "# Evidence: VERIFIED | INTENDED | UNKNOWN\n"
    "# Do not upgrade INTENDED → VERIFIED without explicit verification.\n"
)


def _header(text: str | None) -> str:
    if not text:
        return CONTROLLERS_HEADER
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("#") or (not line.strip() and lines):
            lines.append(line)
        else:
            break
    return "".join(lines) or CONTROLLERS_HEADER


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or CONTROLLERS_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_document(
    path: Path | None = None,
    *,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    performance_path: Path | None = None,
) -> ControllersDocument:
    raw = load_raw(path)
    errors = validate_controllers_doc(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    if errors:
        raise StoreError("Controllers schema validation failed: " + "; ".join(errors))
    return ControllersDocument.model_validate(raw)


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = _header(existing_text)
    if not header.endswith("\n"):
        header += "\n"
    return header + _dump_yaml(data)


def _device_channels(midi_path: Path | None) -> dict[str, int]:
    doc = midi_state.load_document(midi_path)
    return {item.gear_ref: item.channel for item in doc.channels if isinstance(item.channel, int)}


def validate_controllers_doc(
    data: dict[str, Any],
    *,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    performance_path: Path | None = None,
) -> list[str]:
    try:
        doc = ControllersDocument.model_validate(data)
    except Exception as exc:
        return [str(exc)]
    errors: list[str] = []
    try:
        inventory = load_inventory(inventory_path)
        channels = _device_channels(midi_path)
        ableton = ableton_state.load_document(ableton_path)
        performance_raw = parse_existing_yaml(performance_path or PERFORMANCE_PATH)
        performance = PerformanceDocument.model_validate(performance_raw)
    except Exception as exc:
        return [str(exc)]
    tracks = {item.id for item in ableton.tracks}
    sends = {item.id for item in ableton.sends}
    actions = {item.id for item in ableton.actions}
    performance_actions = {item.id for item in performance.actions}
    for controller in doc.controllers:
        item = inventory.resolve(controller.gear_ref)
        if item is None:
            errors.append(f"controller gear_ref {controller.gear_ref!r} is unknown")
        elif item.ownership_status in INACTIVE_OWNERSHIP:
            errors.append(
                f"controller {controller.gear_ref!r} resolves to inactive inventory "
                f"status {item.ownership_status.value}"
            )
        for context in controller.contexts:
            for control in context.controls:
                if any(message.channel == "DEVICE" for message in control.messages):
                    if controller.gear_ref not in channels:
                        errors.append(
                            f"{controller.gear_ref}/{context.id}/{control.id}: DEVICE "
                            "channel has no numeric assignment in data/midi.yaml"
                        )
                target = control.target
                if target.track and target.track not in tracks:
                    errors.append(f"{control.id}: unknown Ableton track {target.track!r}")
                if target.send and target.send not in sends:
                    errors.append(f"{control.id}: unknown Ableton send {target.send!r}")
                if (
                    target.kind == TargetKind.PERFORMANCE_ACTION
                    and target.action not in performance_actions
                ):
                    errors.append(f"{control.id}: unknown performance action {target.action!r}")
                elif target.kind == TargetKind.ABLETON_ACTION and target.action not in actions:
                    errors.append(f"{control.id}: unknown Ableton action {target.action!r}")
    return errors


def resolve_message_channel(
    gear_ref: str, message: MidiMessage, *, midi_path: Path | None = None
) -> int | None:
    if isinstance(message.channel, int) or message.channel is None:
        return message.channel
    channel = _device_channels(midi_path).get(gear_ref)
    if channel is None:
        raise StoreError(f"{gear_ref}: DEVICE channel has no numeric assignment in data/midi.yaml")
    return channel


def _validated(
    raw: dict[str, Any],
    *,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    performance_path: Path | None = None,
) -> ControllersDocument:
    errors = validate_controllers_doc(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    if errors:
        raise StoreError("Controllers validation failed: " + "; ".join(errors))
    return ControllersDocument.model_validate(raw)


def _locate(doc: ControllersDocument, gear: str, context: str, control: str):
    controller = next((item for item in doc.controllers if item.gear_ref == gear), None)
    if controller is None:
        raise StoreError(f"Unknown controller gear_ref {gear!r}.")
    ctx = next((item for item in controller.contexts if item.id == context), None)
    if ctx is None:
        raise StoreError(f"Unknown controller context {gear}/{context}.")
    ctl = next((item for item in ctx.controls if item.id == control), None)
    if ctl is None:
        raise StoreError(f"Unknown control {gear}/{context}/{control}.")
    return controller, ctx, ctl


def _snapshot(value: Any) -> Any:
    return value.model_dump(mode="json", exclude_none=True)


def _replace_control(raw: dict[str, Any], gear: str, context: str, control: str, value) -> None:
    for controller in raw["controllers"]:
        if controller["gear_ref"] != gear:
            continue
        for ctx in controller.get("contexts", []):
            if ctx["id"] != context:
                continue
            ctx["controls"] = [
                _snapshot(value) if item["id"] == control else item
                for item in ctx.get("controls", [])
            ]


def _preview(domain: str, gear: str, context: str, control: str, before, after) -> CurrentPreview:
    target = f"{gear}/{context}/{control}"
    return CurrentPreview(
        domain=domain,
        target=target,
        before=_snapshot(before),
        after=_snapshot(after),
        changed=_snapshot(before) != _snapshot(after),
        affected_files=["data/controllers.yaml", "docs/controller-mappings.md"],
        message=f"{target}: {domain.removeprefix('controls.')} updated",
    )


def _mutate(
    gear_ref: str,
    context_id: str,
    control_id: str,
    update,
    *,
    controllers_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    performance_path: Path | None = None,
    data: dict[str, Any] | None = None,
    domain: str,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(controllers_path))
    doc = _validated(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    _controller, _context, before = _locate(doc, gear_ref, context_id, control_id)
    after = update(before)
    _replace_control(raw, gear_ref, context_id, control_id, after)
    _validated(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    return _preview(domain, gear_ref, context_id, control_id, before, after), raw


def _message(value: MidiMessage | dict[str, Any]) -> MidiMessage:
    return value if isinstance(value, MidiMessage) else MidiMessage.model_validate(value)


def propose_set_message(gear_ref: str, context_id: str, control_id: str, message, **kwargs):
    msg = _message(message)
    return _mutate(
        gear_ref,
        context_id,
        control_id,
        lambda ctl: ctl.model_copy(update={"messages": [msg]}),
        domain="controls.message",
        **kwargs,
    )


def add_message(gear_ref: str, context_id: str, control_id: str, message, **kwargs):
    msg = _message(message)
    return _mutate(
        gear_ref,
        context_id,
        control_id,
        lambda ctl: ctl.model_copy(update={"messages": [*ctl.messages, msg]}),
        domain="controls.message",
        **kwargs,
    )


def remove_message(gear_ref: str, context_id: str, control_id: str, index: int = 0, **kwargs):
    def update(ctl):
        if index < 0 or index >= len(ctl.messages):
            raise StoreError(f"Message index {index} is out of range.")
        return ctl.model_copy(
            update={"messages": [m for i, m in enumerate(ctl.messages) if i != index]}
        )

    return _mutate(
        gear_ref,
        context_id,
        control_id,
        update,
        domain="controls.message",
        **kwargs,
    )


def clear_messages(gear_ref: str, context_id: str, control_id: str, **kwargs):
    return _mutate(
        gear_ref,
        context_id,
        control_id,
        lambda ctl: ctl.model_copy(update={"messages": []}),
        domain="controls.message",
        **kwargs,
    )


clear_message = clear_messages


def propose_set_target(gear_ref: str, context_id: str, control_id: str, target, **kwargs):
    parsed = target if isinstance(target, ControlTarget) else ControlTarget.model_validate(target)

    def update(ctl):
        if ctl.availability == ControlAvailability.BROKEN and parsed.state == TargetState.MAPPED:
            raise StoreError("Cannot map a BROKEN control; set availability first.")
        return ctl.model_copy(update={"target": parsed})

    return _mutate(
        gear_ref,
        context_id,
        control_id,
        update,
        domain="controls.target",
        **kwargs,
    )


def clear_target(gear_ref: str, context_id: str, control_id: str, **kwargs):
    return propose_set_target(
        gear_ref,
        context_id,
        control_id,
        ControlTarget(state=TargetState.UNASSIGNED),
        **kwargs,
    )


def propose_set_evidence(gear_ref: str, context_id: str, control_id: str, evidence, **kwargs):
    status = (
        evidence
        if isinstance(evidence, MidiEvidenceStatus)
        else MidiEvidenceStatus(str(evidence).upper())
    )
    return _mutate(
        gear_ref,
        context_id,
        control_id,
        lambda ctl: ctl.model_copy(update={"evidence": status}),
        domain="controls.evidence",
        **kwargs,
    )


def propose_set_context_evidence(
    gear_ref: str,
    context_id: str,
    evidence,
    *,
    controllers_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    performance_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    """Set ControllerContext.evidence only — not the whole controller."""
    status = (
        evidence
        if isinstance(evidence, MidiEvidenceStatus)
        else MidiEvidenceStatus(str(evidence).upper())
    )
    raw = copy.deepcopy(data if data is not None else load_raw(controllers_path))
    doc = _validated(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    gear = gear_ref.strip()
    cid = context_id.strip()
    controller = next((c for c in doc.controllers if c.gear_ref == gear), None)
    if controller is None:
        raise StoreError(f"Unknown controller gear_ref {gear!r}.")
    ctx = next((c for c in controller.contexts if c.id == cid), None)
    if ctx is None:
        raise StoreError(f"Unknown context {gear}/{cid}.")
    before = _snapshot(ctx)
    updated = ctx.model_copy(update={"evidence": status})
    after = _snapshot(updated)
    for body in raw.get("controllers") or []:
        if isinstance(body, dict) and body.get("gear_ref") == gear:
            contexts = []
            for c in body.get("contexts") or []:
                if isinstance(c, dict) and c.get("id") == cid:
                    contexts.append(after)
                else:
                    contexts.append(c)
            body["contexts"] = contexts
    _validated(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    return (
        CurrentPreview(
            domain="controls.context_evidence",
            target=f"{gear}/{cid}",
            before=before if isinstance(before, dict) else {"value": before},
            after=after if isinstance(after, dict) else {"value": after},
            changed=before != after,
            affected_files=["data/controllers.yaml", "docs/controller-mappings.md"],
            message=f"{gear}/{cid} context evidence → {status.value}",
        ),
        raw,
    )


def propose_set_availability(
    gear_ref: str, context_id: str, control_id: str, availability, **kwargs
):
    status = (
        availability
        if isinstance(availability, ControlAvailability)
        else ControlAvailability(str(availability).upper())
    )

    def update(ctl):
        if status == ControlAvailability.BROKEN and ctl.target.state == TargetState.MAPPED:
            raise StoreError("Cannot mark a MAPPED control BROKEN; clear its target first.")
        return ctl.model_copy(update={"availability": status})

    return _mutate(
        gear_ref,
        context_id,
        control_id,
        update,
        domain="controls.availability",
        **kwargs,
    )


def propose_batch(
    mutations: list[dict[str, Any]],
    *,
    gear_ref: str | None = None,
    controllers_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    performance_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(controllers_path))
    before = _validated(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    operations = {
        "set_message": propose_set_message,
        "add_message": add_message,
        "remove_message": remove_message,
        "clear_messages": clear_messages,
        "clear_message": clear_messages,
        "set_target": propose_set_target,
        "clear_target": clear_target,
        "set_evidence": propose_set_evidence,
        "set_availability": propose_set_availability,
    }
    for mutation in mutations:
        op = mutation.get("op")
        if op not in operations:
            raise StoreError(f"Unknown controls batch op {op!r}.")
        args = {key: value for key, value in mutation.items() if key != "op"}
        if gear_ref is not None:
            args.setdefault("gear_ref", gear_ref)
        _, raw = operations[op](
            data=raw,
            inventory_path=inventory_path,
            midi_path=midi_path,
            ableton_path=ableton_path,
            performance_path=performance_path,
            **args,
        )
    after = _validated(
        raw,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
        performance_path=performance_path,
    )
    before_data = before.model_dump(mode="json", exclude_none=True)
    after_data = after.model_dump(mode="json", exclude_none=True)
    return (
        CurrentPreview(
            domain="controls.verify",
            target=gear_ref or "controllers",
            before=before_data,
            after=after_data,
            changed=before_data != after_data,
            affected_files=["data/controllers.yaml", "docs/controller-mappings.md"],
            message=f"Controller verification batch: {len(mutations)} mutation(s)",
        ),
        raw,
    )


def find_gaps(doc: ControllersDocument) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for controller in doc.controllers:
        if not controller.contexts:
            gaps.append(
                {"gear": controller.gear_ref, "context": "—", "control": "—", "gap": "no contexts"}
            )
        for context in controller.contexts:
            if not context.controls:
                gaps.append(
                    {
                        "gear": controller.gear_ref,
                        "context": context.id,
                        "control": "—",
                        "gap": "no controls modeled",
                    }
                )
            for control in context.controls:
                reasons = []
                if (
                    control.availability == ControlAvailability.BROKEN
                    and control.target.state == TargetState.MAPPED
                ):
                    reasons.append("BROKEN control still targeted")
                elif control.availability == ControlAvailability.BROKEN:
                    # Documented broken/unusable control is not an incompleteness gap.
                    continue
                else:
                    if not control.messages:
                        reasons.append("message unknown")
                    if control.target.state == TargetState.UNKNOWN:
                        reasons.append("target unknown")
                if reasons:
                    gaps.append(
                        {
                            "gear": controller.gear_ref,
                            "context": context.id,
                            "control": control.id,
                            "gap": ", ".join(reasons),
                        }
                    )
    return gaps


def find_conflicts(
    doc: ControllersDocument, *, midi_path: Path | None = None
) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for controller in doc.controllers:
        for context in controller.contexts:
            seen: dict[tuple[str, int, int | None], str] = {}
            for control in context.controls:
                for message in control.messages:
                    key = (
                        message.type.value,
                        message.number,
                        resolve_message_channel(controller.gear_ref, message, midi_path=midi_path),
                    )
                    previous = seen.get(key)
                    if previous and previous != control.id:
                        conflicts.append(
                            {
                                "gear": controller.gear_ref,
                                "context": context.id,
                                "message": f"{key[0]} {key[1]} ch {key[2] or '—'}",
                                "controls": f"{previous}, {control.id}",
                            }
                        )
                    else:
                        seen[key] = control.id
    return conflicts
