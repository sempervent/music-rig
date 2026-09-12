"""Typed durable Ableton targets from data/ableton.yaml."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from music_rig.models import AbletonDocument, CurrentPreview, MidiEvidenceStatus
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


def _snapshot(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def propose_set_template_evidence(
    template_id: str,
    evidence: MidiEvidenceStatus | str,
    *,
    ableton_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    """Set AbletonTemplate.evidence only (does not invent Live Set contents)."""
    status = (
        evidence
        if isinstance(evidence, MidiEvidenceStatus)
        else MidiEvidenceStatus(str(evidence).strip().upper())
    )
    tid = template_id.strip()
    if not tid:
        raise StoreError("template_id is required")
    raw = copy.deepcopy(data if data is not None else load_raw(ableton_path))
    doc = AbletonDocument.model_validate(raw)
    template = next((t for t in doc.templates if t.id == tid), None)
    if template is None:
        known = ", ".join(t.id for t in doc.templates) or "(none)"
        raise StoreError(f"Unknown Ableton template {tid!r}; known: {known}")
    before = _snapshot(template)
    updated = template.model_copy(update={"evidence": status})
    after = _snapshot(updated)
    templates = []
    for t in raw.get("templates") or []:
        if isinstance(t, dict) and t.get("id") == tid:
            templates.append(after)
        else:
            templates.append(t)
    raw["templates"] = templates
    AbletonDocument.model_validate(raw)
    preview = CurrentPreview(
        domain="ableton.template_evidence",
        target=tid,
        before=before if isinstance(before, dict) else {"value": before},
        after=after if isinstance(after, dict) else {"value": after},
        changed=before != after,
        affected_files=["data/ableton.yaml", "docs/ableton-track-map.md"],
        message=f"Ableton template {tid} evidence → {status.value}",
    )
    return preview, raw
