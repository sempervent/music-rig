"""Typed durable Ableton targets from data/ableton.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig.models import AbletonDocument
from music_rig.store import ABLETON_PATH, StoreError, _dump_yaml, parse_existing_yaml

ABLETON_HEADER = (
    "# Durable Ableton Live targets for controller mapping.\n"
    "# Not a full Live Set dump — only stable references needed by mappings.\n"
    "# Evidence: VERIFIED | INTENDED | UNKNOWN\n"
)


def _header(text: str | None) -> str:
    if not text:
        return ABLETON_HEADER
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("#") or (not line.strip() and lines):
            lines.append(line)
        else:
            break
    return "".join(lines) or ABLETON_HEADER


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or ABLETON_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_document(path: Path | None = None) -> AbletonDocument:
    raw = load_raw(path)
    errors = validate_ableton_doc(raw)
    if errors:
        raise StoreError("Ableton schema validation failed: " + "; ".join(errors))
    return AbletonDocument.model_validate(raw)


def validate_ableton_doc(data: dict[str, Any]) -> list[str]:
    try:
        AbletonDocument.model_validate(data)
    except Exception as exc:
        return [str(exc)]
    return []


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = _header(existing_text)
    if not header.endswith("\n"):
        header += "\n"
    return header + _dump_yaml(data)
