"""Typed CURRENT mutations for data/channel-map.yaml."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from music_rig.models import CurrentPreview
from music_rig.store import CHANNEL_MAP_PATH, StoreError, _dump_yaml, parse_existing_yaml

CHANNEL_MAP_HEADER = (
    "# Interface and mixer channel assignments (CURRENT).\n"
    "# Prefer `uv run rig current channels ...` for source updates.\n"
    "\n"
)

KNOWN_DEVICES = frozenset({"tascam", "alesis"})


def _extract_leading_comment_header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = 0
    saw_comment = False
    while idx < len(lines):
        stripped = lines[idx].lstrip()
        if stripped.startswith("#"):
            saw_comment = True
            idx += 1
            continue
        if stripped == "" and (saw_comment or idx == 0):
            idx += 1
            continue
        break
    if not saw_comment:
        return ""
    return "".join(lines[:idx])


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or CHANNEL_MAP_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = CHANNEL_MAP_HEADER
    if existing_text is not None:
        extracted = _extract_leading_comment_header(existing_text)
        if extracted:
            header = extracted
            if not header.endswith("\n"):
                header += "\n"
    return header + _dump_yaml(data)


def save_raw(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or CHANNEL_MAP_PATH
    errors = validate_channel_map(data)
    if errors:
        raise StoreError("Channel map validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    from music_rig.store import write_text_files

    write_text_files([(target, dump_with_header(data, existing_text=existing))])


def apply_data(path: Path, proposed_data: dict[str, Any]) -> None:
    save_raw(proposed_data, path)


def validate_channel_map(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for device in ("tascam", "alesis"):
        section = data.get(device)
        if section is None:
            continue
        if not isinstance(section, dict):
            errors.append(f"{device} must be a mapping")
            continue
        for key, meta in section.items():
            if not isinstance(meta, dict):
                errors.append(f"{device} channel {key}: must be a mapping")
                continue
            if "status" not in meta:
                errors.append(f"{device} channel {key}: missing status")
            if device == "tascam" and "type" not in meta:
                errors.append(f"{device} channel {key}: missing type")
    return errors


def _device_section(data: dict[str, Any], device: str) -> dict[Any, Any]:
    key = device.strip().lower()
    if key not in KNOWN_DEVICES:
        raise StoreError(f"Unknown device {device!r}. Use tascam or alesis.")
    section = data.get(key)
    if not isinstance(section, dict):
        raise StoreError(f"{key} must be a mapping in channel-map")
    return section


def resolve_channel_key(device: str, channel: str | int, section: dict[Any, Any]) -> Any:
    """Return the existing key in section for channel, or raise StoreError."""
    want = str(channel).strip()
    device_key = device.strip().lower()

    # Exact match on string form of keys
    for key in section:
        if str(key) == want:
            return key

    if device_key == "tascam":
        if want.isdigit():
            as_int = int(want)
            if as_int in section:
                return as_int
            if want in section:
                return want
        raise StoreError(
            f"TASCAM channel {channel!r} is not represented in CURRENT channel-map data."
        )

    # Alesis: support "1", "5_6", maybe "5/6" -> "5_6"
    candidates = [want, want.replace("/", "_"), want.replace("-", "_")]
    if want.isdigit():
        candidates.extend([int(want), want])
    for cand in candidates:
        if cand in section:
            return cand
        for key in section:
            if str(key) == str(cand):
                return key
    raise StoreError(
        f"Alesis channel {channel!r} is not represented in CURRENT channel-map data."
    )


def propose_set_source(
    device: str,
    channel: str | int,
    source: str | None,
    *,
    data: dict[str, Any] | None = None,
    path: Path | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    doc = copy.deepcopy(data if data is not None else load_raw(path))
    device_key = device.strip().lower()
    section = _device_section(doc, device_key)
    key = resolve_channel_key(device_key, channel, section)
    meta = section[key]
    if not isinstance(meta, dict):
        raise StoreError(f"{device_key} channel {key} must be a mapping")

    before_source = meta.get("source")
    new_source: str | None
    if source is None:
        new_source = None
    else:
        cleaned = source.strip()
        new_source = cleaned if cleaned else None

    before_status = meta.get("status")
    before = {
        "device": device_key,
        "channel": str(key),
        "source": before_source,
        "status": before_status,
    }
    meta["source"] = new_source
    # Assigned sources are CURRENT; cleared sources become UNASSIGNED.
    if new_source is None:
        meta["status"] = "UNASSIGNED"
    else:
        meta["status"] = "CURRENT"
    after = {
        "device": device_key,
        "channel": str(key),
        "source": new_source,
        "status": meta.get("status"),
    }

    errors = validate_channel_map(doc)
    if errors:
        raise StoreError("Channel map validation failed: " + "; ".join(errors))

    changed = before_source != new_source or before_status != meta.get("status")
    rel = "data/channel-map.yaml"
    label = f"{device_key} {key}"
    if changed:
        message = (
            f"Set {label} source "
            f"{before_source!r} -> {new_source!r}"
            f" (status {before_status!r} -> {meta.get('status')!r})"
        )
    else:
        message = f"No change: {label} source is already {new_source!r}"
    preview = CurrentPreview(
        domain="channel.source",
        target=label,
        before=before,
        after=after,
        changed=changed,
        affected_files=[rel] if changed else [],
        message=message,
    )
    return preview, doc


def clear_source(
    device: str,
    channel: str | int,
    *,
    data: dict[str, Any] | None = None,
    path: Path | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    return propose_set_source(device, channel, None, data=data, path=path)
