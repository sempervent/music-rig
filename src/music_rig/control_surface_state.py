"""Typed non-MIDI control-surface state from data/control-surfaces.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig.models import INACTIVE_OWNERSHIP, ControlSurfacesDocument
from music_rig.store import (
    CONTROL_SURFACES_PATH,
    StoreError,
    load_inventory,
    parse_existing_yaml,
)


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or CONTROL_SURFACES_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def validate_control_surfaces_doc(
    data: dict[str, Any], *, inventory_path: Path | None = None
) -> list[str]:
    try:
        doc = ControlSurfacesDocument.model_validate(data)
        inventory = load_inventory(inventory_path)
    except Exception as exc:
        return [str(exc)]
    errors: list[str] = []
    for surface in doc.surfaces:
        item = inventory.resolve(surface.gear_ref)
        if item is None:
            errors.append(f"surface gear_ref {surface.gear_ref!r} is unknown")
        elif item.ownership_status in INACTIVE_OWNERSHIP:
            errors.append(
                f"surface {surface.gear_ref!r} resolves to inactive inventory "
                f"status {item.ownership_status.value}"
            )
    return errors


def load_document(
    path: Path | None = None, *, inventory_path: Path | None = None
) -> ControlSurfacesDocument:
    raw = load_raw(path)
    errors = validate_control_surfaces_doc(raw, inventory_path=inventory_path)
    if errors:
        raise StoreError("Control surfaces validation failed: " + "; ".join(errors))
    return ControlSurfacesDocument.model_validate(raw)
