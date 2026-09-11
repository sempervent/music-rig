"""Typed PFL performance orchestration state, readiness, and mutations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from music_rig import ableton_state, control_state, control_surface_state
from music_rig.models import (
    ControlAvailability,
    CurrentPreview,
    MidiEvidenceStatus,
    PerformanceBinding,
    PerformanceCriticality,
    PerformanceDocument,
    PerformanceEffectKind,
    ReadinessResult,
)
from music_rig.store import (
    ABLETON_PATH,
    CONTROLLERS_PATH,
    CONTROL_SURFACES_PATH,
    PERFORMANCE_PATH,
    StoreError,
    _dump_yaml,
    parse_existing_yaml,
)

PERFORMANCE_HEADER = (
    "# Canonical PFL performance orchestration (semantic contracts).\n"
    "# Evidence: VERIFIED | INTENDED | UNKNOWN\n"
    "# Structural readiness ≠ live Ableton/OBS/hardware telemetry.\n"
    "# Do not upgrade INTENDED → VERIFIED without explicit physical/software verification.\n"
)


@dataclass(frozen=True)
class PerformanceReadiness:
    result: ReadinessResult
    reasons: list[str]


def _header(text: str | None) -> str:
    if not text:
        return PERFORMANCE_HEADER
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("#") or (not line.strip() and lines):
            lines.append(line)
        else:
            break
    return "".join(lines) or PERFORMANCE_HEADER


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or PERFORMANCE_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = _header(existing_text)
    if not header.endswith("\n"):
        header += "\n"
    return header + _dump_yaml(data)


def _control_maps(controllers, surfaces):
    controller_map = {
        (record.gear_ref, context.id, control.id): control
        for record in controllers.controllers
        for context in record.contexts
        for control in context.controls
    }
    surface_map = {
        (record.gear_ref, context.id, control.id): control
        for record in surfaces.surfaces
        for context in record.contexts
        for control in context.controls
    }
    return controller_map, surface_map


def validate_performance_doc(
    data: dict[str, Any],
    *,
    controllers_path: Path | None = None,
    surfaces_path: Path | None = None,
    ableton_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
) -> list[str]:
    try:
        doc = PerformanceDocument.model_validate(data)
        controllers = control_state.load_document(
            controllers_path,
            inventory_path=inventory_path,
            midi_path=midi_path,
            ableton_path=ableton_path,
        )
        surfaces = control_surface_state.load_document(
            surfaces_path, inventory_path=inventory_path
        )
        ableton = ableton_state.load_document(ableton_path)
    except Exception as exc:
        return [str(exc)]
    errors: list[str] = []
    controller_map, surface_map = _control_maps(controllers, surfaces)
    ableton_actions = {item.id for item in ableton.actions}
    requirements = {item.id for item in doc.requirements}
    for action in doc.actions:
        for effect in action.effects:
            if effect.action_ref and effect.action_ref not in ableton_actions:
                errors.append(
                    f"{action.id}: unknown Ableton action {effect.action_ref!r}"
                )
    for binding in doc.bindings:
        key = (
            binding.controller_ref or binding.surface_ref or "",
            binding.context_ref,
            binding.control_ref,
        )
        controls = controller_map if binding.controller_ref else surface_map
        if key not in controls:
            source = "controller" if binding.controller_ref else "surface"
            errors.append(
                f"{binding.id}: unknown {source} control {'/'.join(key)}"
            )
    for template in ableton.templates:
        for requirement in template.requirements:
            if requirement not in requirements:
                errors.append(
                    f"Ableton template {template.id}: unknown performance requirement "
                    f"{requirement!r}"
                )
    return errors


def load_document(
    path: Path | None = None,
    *,
    controllers_path: Path | None = None,
    surfaces_path: Path | None = None,
    ableton_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
) -> PerformanceDocument:
    raw = load_raw(path)
    errors = validate_performance_doc(
        raw,
        controllers_path=controllers_path,
        surfaces_path=surfaces_path,
        ableton_path=ableton_path,
        inventory_path=inventory_path,
        midi_path=midi_path,
    )
    if errors:
        raise StoreError("Performance validation failed: " + "; ".join(errors))
    return PerformanceDocument.model_validate(raw)


def _binding_control(binding, controller_map, surface_map):
    key = (
        binding.controller_ref or binding.surface_ref or "",
        binding.context_ref,
        binding.control_ref,
    )
    return (controller_map if binding.controller_ref else surface_map).get(key)


def evaluate_readiness(
    doc: PerformanceDocument,
    mode_id: str = "pfl-jam",
    *,
    controllers_path: Path | None = None,
    surfaces_path: Path | None = None,
    ableton_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
) -> PerformanceReadiness:
    mode = next((item for item in doc.modes if item.id == mode_id), None)
    if mode is None:
        return PerformanceReadiness(
            ReadinessResult.NOT_READY, [f"required mode {mode_id!r} is missing"]
        )
    controllers = control_state.load_document(
        controllers_path,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
    )
    surfaces = control_surface_state.load_document(
        surfaces_path, inventory_path=inventory_path
    )
    controller_map, surface_map = _control_maps(controllers, surfaces)
    actions = {item.id: item for item in doc.actions}
    bindings_by_action: dict[str, list[PerformanceBinding]] = {}
    for binding in doc.bindings:
        bindings_by_action.setdefault(binding.action_ref, []).append(binding)

    fatal: list[str] = []
    partial: list[str] = []
    for action_id in mode.required_actions:
        action = actions.get(action_id)
        if action is None:
            fatal.append(f"{action_id}: required action missing")
            continue
        bindings = bindings_by_action.get(action_id, [])
        if not bindings:
            procedural = any(
                effect.kind
                in {
                    PerformanceEffectKind.HARDWARE_PROCEDURE,
                    PerformanceEffectKind.MANUAL_STEP,
                }
                for effect in action.effects
            )
            effect_ids = {
                effect.effect_id for effect in action.effects if effect.effect_id
            }
            indirect = any(
                other.id != action_id
                and bindings_by_action.get(other.id)
                and any(
                    effect.effect_id in effect_ids
                    for effect in other.effects
                    if effect.effect_id
                )
                for other in doc.actions
            )
            if procedural:
                partial.append(
                    f"{action_id}: procedure exists but has zero control bindings"
                )
                if action.evidence != MidiEvidenceStatus.VERIFIED:
                    partial.append(
                        f"{action_id}: action evidence is {action.evidence.value}"
                    )
                continue
            if indirect:
                partial.append(
                    f"{action_id}: reachable only through another bound action"
                )
                if action.evidence != MidiEvidenceStatus.VERIFIED:
                    partial.append(
                        f"{action_id}: action evidence is {action.evidence.value}"
                    )
                continue
            fatal.append(f"{action_id}: required action has zero bindings")
            continue
        controls = [
            _binding_control(binding, controller_map, surface_map)
            for binding in bindings
        ]
        if len(bindings) == 1 and controls[0] is not None and (
            controls[0].availability == ControlAvailability.BROKEN
        ):
            fatal.append(f"{action_id}: sole binding uses a BROKEN control")
            continue
        available = [
            binding
            for binding, control in zip(bindings, controls)
            if control is not None
            and control.availability == ControlAvailability.AVAILABLE
        ]
        if not available:
            partial.append(f"{action_id}: no AVAILABLE binding")
        if action.evidence != MidiEvidenceStatus.VERIFIED:
            partial.append(f"{action_id}: action evidence is {action.evidence.value}")
        if not any(
            binding.evidence == MidiEvidenceStatus.VERIFIED for binding in available
        ):
            partial.append(f"{action_id}: missing VERIFIED AVAILABLE binding")
        if any("imperfect" in binding.notes.casefold() for binding in bindings):
            partial.append(f"{action_id}: binding has known imperfect behavior")
        if action.criticality == PerformanceCriticality.EMERGENCY and any(
            effect.evidence != MidiEvidenceStatus.VERIFIED for effect in action.effects
        ):
            partial.append(f"{action_id}: emergency effects are not fully VERIFIED")

    for action in doc.actions:
        if action.criticality == PerformanceCriticality.NORMAL:
            continue
        reason = f"{action.id}: critical action is not VERIFIED"
        if action.evidence != MidiEvidenceStatus.VERIFIED and reason not in partial:
            partial.append(reason)
        if any(
            effect.evidence != MidiEvidenceStatus.VERIFIED
            for effect in action.effects
        ):
            reason = f"{action.id}: critical effects are not fully VERIFIED"
            if reason not in partial:
                partial.append(reason)

    for scenario in doc.recovery:
        if scenario.severity == PerformanceCriticality.NORMAL:
            continue
        if scenario.evidence != MidiEvidenceStatus.VERIFIED:
            partial.append(f"{scenario.id}: critical recovery is not VERIFIED")
        if scenario.severity != PerformanceCriticality.EMERGENCY:
            continue
        if scenario.keyboard_mouse_required is True:
            partial.append(f"{scenario.id}: emergency recovery requires keyboard/mouse")
        elif scenario.keyboard_mouse_required == "unknown":
            partial.append(
                f"{scenario.id}: emergency keyboard/mouse requirement is unknown"
            )

    if fatal:
        return PerformanceReadiness(ReadinessResult.NOT_READY, fatal + partial)
    if partial:
        return PerformanceReadiness(ReadinessResult.PARTIAL, partial)
    return PerformanceReadiness(ReadinessResult.READY, [])


def find_gaps(
    doc: PerformanceDocument,
    *,
    controllers_path: Path | None = None,
    surfaces_path: Path | None = None,
    ableton_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
) -> list[dict[str, str]]:
    readiness = evaluate_readiness(
        doc,
        controllers_path=controllers_path,
        surfaces_path=surfaces_path,
        ableton_path=ableton_path,
        inventory_path=inventory_path,
        midi_path=midi_path,
    )
    return [{"scope": "pfl-jam", "gap": reason} for reason in readiness.reasons]


def find_conflicts(
    doc: PerformanceDocument,
    *,
    controllers_path: Path | None = None,
    surfaces_path: Path | None = None,
    ableton_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
) -> list[dict[str, str]]:
    controllers = control_state.load_document(
        controllers_path,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
    )
    surfaces = control_surface_state.load_document(
        surfaces_path, inventory_path=inventory_path
    )
    controller_map, surface_map = _control_maps(controllers, surfaces)
    conflicts = []
    for binding in doc.bindings:
        control = _binding_control(binding, controller_map, surface_map)
        if control and control.availability == ControlAvailability.BROKEN:
            conflicts.append(
                {"binding": binding.id, "conflict": "binding uses BROKEN control"}
            )
    return conflicts


def _validated(raw: dict[str, Any], **kwargs) -> PerformanceDocument:
    errors = validate_performance_doc(raw, **kwargs)
    if errors:
        raise StoreError("Performance validation failed: " + "; ".join(errors))
    return PerformanceDocument.model_validate(raw)


def _snapshot(value: Any) -> Any:
    return value.model_dump(mode="json", exclude_none=True)


def _preview(domain: str, target: str, before: Any, after: Any) -> CurrentPreview:
    before_data = _snapshot(before) if hasattr(before, "model_dump") else before
    after_data = _snapshot(after) if hasattr(after, "model_dump") else after
    return CurrentPreview(
        domain=domain,
        target=target,
        before=before_data if isinstance(before_data, dict) else {"value": before_data},
        after=after_data if isinstance(after_data, dict) else {"value": after_data},
        changed=before_data != after_data,
        affected_files=[
            "data/performance.yaml",
            "docs/performance.md",
            "docs/live-recovery.md",
        ],
        message=f"{target}: {domain.removeprefix('performance.')} updated",
    )


def propose_bind(
    action_ref: str,
    context_ref: str,
    control_ref: str,
    *,
    controller_ref: str | None = None,
    surface_ref: str | None = None,
    evidence: MidiEvidenceStatus | str = MidiEvidenceStatus.INTENDED,
    notes: str = "",
    binding_id: str | None = None,
    data: dict[str, Any] | None = None,
    performance_path: Path | None = None,
    **kwargs,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(performance_path))
    doc = _validated(raw, **kwargs)
    source = controller_ref or surface_ref
    if bool(controller_ref) == bool(surface_ref):
        raise StoreError("Specify exactly one controller or surface.")
    if action_ref not in {item.id for item in doc.actions}:
        raise StoreError(f"Unknown performance action {action_ref!r}.")
    candidate = PerformanceBinding(
        id=binding_id or f"{source}-{context_ref}-{control_ref}-{action_ref}",
        action_ref=action_ref,
        controller_ref=controller_ref,
        surface_ref=surface_ref,
        context_ref=context_ref,
        control_ref=control_ref,
        evidence=(
            evidence
            if isinstance(evidence, MidiEvidenceStatus)
            else MidiEvidenceStatus(str(evidence).upper())
        ),
        notes=notes,
    )
    controllers = control_state.load_document(
        kwargs.get("controllers_path"),
        inventory_path=kwargs.get("inventory_path"),
        midi_path=kwargs.get("midi_path"),
        ableton_path=kwargs.get("ableton_path"),
    )
    surfaces = control_surface_state.load_document(
        kwargs.get("surfaces_path"), inventory_path=kwargs.get("inventory_path")
    )
    controller_map, surface_map = _control_maps(controllers, surfaces)
    control = _binding_control(candidate, controller_map, surface_map)
    if control is None:
        raise StoreError(f"Unknown control {source}/{context_ref}/{control_ref}.")
    if control.availability == ControlAvailability.BROKEN:
        raise StoreError("Cannot bind a BROKEN control.")
    if any(item.id == candidate.id for item in doc.bindings):
        raise StoreError(f"Binding ID {candidate.id!r} already exists.")
    raw.setdefault("bindings", []).append(_snapshot(candidate))
    _validated(raw, **kwargs)
    return _preview("performance.bind", candidate.id, {}, candidate), raw


def propose_unbind(
    binding_id: str,
    *,
    data: dict[str, Any] | None = None,
    performance_path: Path | None = None,
    **kwargs,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(performance_path))
    doc = _validated(raw, **kwargs)
    before = next((item for item in doc.bindings if item.id == binding_id), None)
    if before is None:
        raise StoreError(f"Unknown performance binding {binding_id!r}.")
    raw["bindings"] = [item for item in raw.get("bindings", []) if item["id"] != binding_id]
    _validated(raw, **kwargs)
    return _preview("performance.unbind", binding_id, before, {}), raw


def _set_item_evidence(
    collection: str,
    item_id: str,
    evidence: MidiEvidenceStatus | str,
    *,
    data: dict[str, Any] | None = None,
    performance_path: Path | None = None,
    **kwargs,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(performance_path))
    doc = _validated(raw, **kwargs)
    values = getattr(doc, collection)
    before = next((item for item in values if item.id == item_id), None)
    if before is None:
        raise StoreError(f"Unknown {collection.rstrip('s')} {item_id!r}.")
    status = (
        evidence
        if isinstance(evidence, MidiEvidenceStatus)
        else MidiEvidenceStatus(str(evidence).upper())
    )
    after = before.model_copy(update={"evidence": status})
    for index, value in enumerate(raw[collection]):
        if value["id"] == item_id:
            raw[collection][index] = _snapshot(after)
            break
    _validated(raw, **kwargs)
    return _preview(f"performance.{collection}.evidence", item_id, before, after), raw


def propose_set_evidence(binding_id: str, evidence, **kwargs):
    return _set_item_evidence("bindings", binding_id, evidence, **kwargs)


def propose_set_recovery_evidence(recovery_id: str, evidence, **kwargs):
    return _set_item_evidence("recovery", recovery_id, evidence, **kwargs)


def propose_batch(
    mutations: list[dict[str, Any]],
    *,
    data: dict[str, Any] | None = None,
    performance_path: Path | None = None,
    **kwargs,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(performance_path))
    before = _validated(raw, **kwargs)
    operations = {
        "bind": propose_bind,
        "unbind": propose_unbind,
        "set_evidence": propose_set_evidence,
        "set_recovery_evidence": propose_set_recovery_evidence,
    }
    for mutation in mutations:
        op = mutation.get("op")
        if op not in operations:
            raise StoreError(f"Unknown performance batch op {op!r}.")
        args = {key: value for key, value in mutation.items() if key != "op"}
        _, raw = operations[op](data=raw, **kwargs, **args)
    after = _validated(raw, **kwargs)
    return (
        _preview("performance.verify", "performance", before, after),
        raw,
    )
