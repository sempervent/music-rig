"""Typed CURRENT mutations for data/patchbays.yaml."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from music_rig.models import CurrentPreview, PatchbayMode
from music_rig.store import PATCHBAYS_PATH, StoreError, _dump_yaml, parse_existing_yaml

PATCHBAY_MODES = frozenset(m.value for m in PatchbayMode)

PATCHBAY_HEADER = (
    "# Physical patchbay jack map.\n"
    "# Upper jack N pairs with lower jack N+24. Mode is normal/half-normal/thru when known.\n"
    "# Do not infer normalled signal flow from rear connections alone.\n"
    "\n"
)


def parse_mode(raw: str) -> str:
    cleaned = str(raw).strip().lower().replace("_", "-").replace(" ", "-")
    if cleaned not in PATCHBAY_MODES:
        allowed = ", ".join(sorted(PATCHBAY_MODES))
        raise StoreError(f"Invalid patchbay mode {raw!r}. Use one of: {allowed}")
    return cleaned


def _extract_leading_comment_header(text: str) -> str:
    """Preserve leading `#` comment lines (and blank lines among them) before YAML body."""
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
    target = path or PATCHBAYS_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict) or "patchbays" not in raw:
        raise StoreError(f"{target} must contain a patchbays mapping")
    return raw


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = PATCHBAY_HEADER
    if existing_text is not None:
        extracted = _extract_leading_comment_header(existing_text)
        if extracted:
            header = extracted
            if not header.endswith("\n"):
                header += "\n"
    body = _dump_yaml(data)
    return header + body if header else body


def save_raw(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or PATCHBAYS_PATH
    errors = validate_patchbays_doc(data)
    if errors:
        raise StoreError("Patchbay validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    from music_rig.store import write_text_files

    write_text_files([(target, dump_with_header(data, existing_text=existing))])


def apply_data(path: Path, proposed_data: dict[str, Any]) -> None:
    save_raw(proposed_data, path)


def _bay(data: dict[str, Any], bay_id: str) -> dict[str, Any]:
    key = bay_id.strip().upper()
    bays = data.get("patchbays")
    if not isinstance(bays, dict) or key not in bays:
        raise StoreError(f"Unknown patchbay {bay_id!r}.")
    bay = bays[key]
    if not isinstance(bay, dict):
        raise StoreError(f"Patchbay {key} must be a mapping")
    return bay


def _jacks_map(bay: dict[str, Any]) -> dict[Any, Any]:
    jacks = bay.get("jacks")
    if jacks is None:
        return {}
    if not isinstance(jacks, dict):
        raise StoreError("jacks must be a mapping")
    return jacks


def _norm_jack_num(key: Any) -> int | None:
    if isinstance(key, bool):
        return None
    if isinstance(key, int):
        return key
    text = str(key).strip()
    if text.isdigit():
        return int(text)
    return None


def _get_jack(jacks: dict[Any, Any], number: int) -> dict[str, Any] | None:
    if number in jacks and isinstance(jacks[number], dict):
        return jacks[number]
    as_str = str(number)
    if as_str in jacks and isinstance(jacks[as_str], dict):
        return jacks[as_str]
    return None


def _set_jack_field(jacks: dict[Any, Any], number: int, field: str, value: Any) -> None:
    if number in jacks and isinstance(jacks[number], dict):
        jacks[number][field] = value
        return
    as_str = str(number)
    if as_str in jacks and isinstance(jacks[as_str], dict):
        jacks[as_str][field] = value
        return
    raise StoreError(f"Jack {number} is not represented in CURRENT patchbay data.")


def validate_patchbays_doc(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bays = data.get("patchbays")
    if not isinstance(bays, dict):
        return ["patchbays must be a mapping"]

    for bay_id, bay in bays.items():
        if not isinstance(bay, dict):
            errors.append(f"{bay_id}: bay must be a mapping")
            continue
        jacks = bay.get("jacks")
        if jacks is None:
            continue
        if not isinstance(jacks, dict):
            errors.append(f"{bay_id}: jacks must be a mapping")
            continue

        seen_nums: dict[int, list[Any]] = {}
        for key in jacks:
            num = _norm_jack_num(key)
            if num is None:
                errors.append(f"{bay_id}: invalid jack key {key!r}")
                continue
            seen_nums.setdefault(num, []).append(key)
        for num, keys in seen_nums.items():
            if len(keys) > 1:
                errors.append(
                    f"{bay_id}: duplicate jack number {num} as keys {keys}"
                )

        for key, jack in jacks.items():
            if not isinstance(jack, dict):
                errors.append(f"{bay_id} jack {key}: must be a mapping")
                continue
            mode = jack.get("mode")
            if mode is not None:
                try:
                    parse_mode(str(mode))
                except StoreError:
                    errors.append(f"{bay_id} jack {key}: invalid mode {mode!r}")

            paired = jack.get("paired_with")
            if paired is None:
                continue
            paired_n = _norm_jack_num(paired)
            if paired_n is None:
                errors.append(f"{bay_id} jack {key}: invalid paired_with {paired!r}")
                continue
            other = _get_jack(jacks, paired_n)
            if other is None:
                errors.append(
                    f"{bay_id} jack {key}: paired_with {paired_n} does not exist"
                )
                continue
            back = other.get("paired_with")
            if back is not None:
                back_n = _norm_jack_num(back)
                this_n = _norm_jack_num(key)
                if back_n is not None and this_n is not None and back_n != this_n:
                    errors.append(
                        f"{bay_id}: jacks {this_n} and {paired_n} have mismatched paired_with"
                    )
            mode_a = jack.get("mode")
            mode_b = other.get("mode")
            if mode_a is not None and mode_b is not None:
                try:
                    if parse_mode(str(mode_a)) != parse_mode(str(mode_b)):
                        errors.append(
                            f"{bay_id}: mode mismatch on pair {key}/{paired_n} "
                            f"({mode_a!r} vs {mode_b!r})"
                        )
                except StoreError:
                    pass

    return errors


def list_pairs(bay_id: str, data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = data if data is not None else load_raw()
    bay = _bay(doc, bay_id)
    jacks = _jacks_map(bay)
    pairs: list[dict[str, Any]] = []
    seen_lowers: set[int] = set()

    uppers: list[tuple[int, dict[str, Any]]] = []
    for key, jack in jacks.items():
        if not isinstance(jack, dict):
            continue
        num = _norm_jack_num(key)
        if num is None:
            continue
        if str(jack.get("row", "")).lower() == "upper":
            uppers.append((num, jack))

    for upper_n, upper in sorted(uppers, key=lambda x: x[0]):
        lower_n_raw = upper.get("paired_with")
        lower_n = _norm_jack_num(lower_n_raw) if lower_n_raw is not None else None
        lower = _get_jack(jacks, lower_n) if lower_n is not None else None
        if lower_n is not None:
            seen_lowers.add(lower_n)
        mode = upper.get("mode")
        if mode is None and lower is not None:
            mode = lower.get("mode")
        mode_s = parse_mode(str(mode)) if mode is not None else "unknown"
        status = upper.get("status") or (lower or {}).get("status") or ""
        pairs.append(
            {
                "upper_n": upper_n,
                "lower_n": lower_n,
                "upper_conn": upper.get("connection"),
                "lower_conn": None if lower is None else lower.get("connection"),
                "mode": mode_s,
                "status": status,
            }
        )
    return pairs


def resolve_pair(
    bay_id: str,
    jack_spec: str,
    data: dict[str, Any] | None = None,
) -> tuple[int, int | None, dict[str, Any], dict[str, Any] | None]:
    """Resolve jack_spec ('1' or '1/25') to an existing modeled pair.

    Returns (upper_n, lower_n, upper_jack, lower_jack).
    """
    doc = data if data is not None else load_raw()
    bay = _bay(doc, bay_id)
    jacks = _jacks_map(bay)
    bay_key = bay_id.strip().upper()

    spec = jack_spec.strip()
    if "/" in spec:
        left_s, right_s = spec.split("/", 1)
        if not left_s.strip().isdigit() or not right_s.strip().isdigit():
            raise StoreError(f"Invalid jack pair spec {jack_spec!r}.")
        a, b = int(left_s), int(right_s)
        jack_a = _get_jack(jacks, a)
        jack_b = _get_jack(jacks, b)
        if jack_a is None or jack_b is None:
            raise StoreError(
                f"{bay_key} pair {a}/{b} is not represented in CURRENT patchbay data."
            )
        row_a = str(jack_a.get("row", "")).lower()
        row_b = str(jack_b.get("row", "")).lower()
        if row_a == "upper" and row_b == "lower":
            upper_n, lower_n, upper, lower = a, b, jack_a, jack_b
        elif row_a == "lower" and row_b == "upper":
            upper_n, lower_n, upper, lower = b, a, jack_b, jack_a
        elif _norm_jack_num(jack_a.get("paired_with")) == b:
            if row_a == "lower":
                upper_n, lower_n, upper, lower = b, a, jack_b, jack_a
            else:
                upper_n, lower_n, upper, lower = a, b, jack_a, jack_b
        else:
            raise StoreError(
                f"{bay_key} pair {a}/{b} is not represented in CURRENT patchbay data."
            )
        up_pair = _norm_jack_num(upper.get("paired_with"))
        lo_pair = _norm_jack_num(lower.get("paired_with"))
        if up_pair is not None and up_pair != lower_n:
            raise StoreError(
                f"{bay_key} pair {a}/{b} is not represented in CURRENT patchbay data."
            )
        if lo_pair is not None and lo_pair != upper_n:
            raise StoreError(
                f"{bay_key} pair {a}/{b} is not represented in CURRENT patchbay data."
            )
        return upper_n, lower_n, upper, lower

    if not spec.isdigit():
        raise StoreError(f"Invalid jack spec {jack_spec!r}. Use N or N/M.")
    n = int(spec)
    jack = _get_jack(jacks, n)
    if jack is None:
        raise StoreError(
            f"{bay_key} jack {n} is not represented in CURRENT patchbay data."
        )
    paired_raw = jack.get("paired_with")
    paired_n = _norm_jack_num(paired_raw) if paired_raw is not None else None
    other = _get_jack(jacks, paired_n) if paired_n is not None else None
    row = str(jack.get("row", "")).lower()
    if row == "upper":
        return n, paired_n, jack, other
    if row == "lower":
        if paired_n is None or other is None:
            raise StoreError(
                f"{bay_key} jack {n} is not part of a represented pair "
                "in CURRENT patchbay data."
            )
        return paired_n, n, other, jack
    if paired_n is not None and other is not None:
        other_row = str(other.get("row", "")).lower()
        if other_row == "upper":
            return paired_n, n, other, jack
        return n, paired_n, jack, other
    return n, paired_n, jack, other


def _pair_snapshot(
    upper_n: int,
    lower_n: int | None,
    upper: dict[str, Any],
    lower: dict[str, Any] | None,
) -> dict[str, Any]:
    mode = upper.get("mode")
    if mode is None and lower is not None:
        mode = lower.get("mode")
    mode_s = parse_mode(str(mode)) if mode is not None else "unknown"
    return {
        "upper": upper_n,
        "lower": lower_n,
        "upper_connection": upper.get("connection"),
        "lower_connection": None if lower is None else lower.get("connection"),
        "mode": mode_s,
    }


def propose_set_mode(
    bay_id: str,
    jack_spec: str,
    mode: str,
    *,
    data: dict[str, Any] | None = None,
    path: Path | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    doc = copy.deepcopy(data if data is not None else load_raw(path))
    bay_key = bay_id.strip().upper()
    canonical = parse_mode(mode)
    upper_n, lower_n, upper, lower = resolve_pair(bay_key, jack_spec, doc)
    before = _pair_snapshot(upper_n, lower_n, upper, lower)

    bay = _bay(doc, bay_key)
    jacks = _jacks_map(bay)
    _set_jack_field(jacks, upper_n, "mode", canonical)
    if lower_n is not None and _get_jack(jacks, lower_n) is not None:
        _set_jack_field(jacks, lower_n, "mode", canonical)

    upper_after = _get_jack(jacks, upper_n)
    lower_after = _get_jack(jacks, lower_n) if lower_n is not None else None
    assert upper_after is not None
    after = _pair_snapshot(upper_n, lower_n, upper_after, lower_after)

    errors = validate_patchbays_doc(doc)
    if errors:
        raise StoreError("Patchbay validation failed: " + "; ".join(errors))

    pair_label = f"{upper_n}/{lower_n}" if lower_n is not None else str(upper_n)
    changed = before["mode"] != after["mode"]
    rel = "data/patchbays.yaml"
    if changed:
        message = f"Set {bay_key} {pair_label} mode {before['mode']} -> {after['mode']}"
    else:
        message = f"No change: {bay_key} {pair_label} is already {after['mode']}"
    preview = CurrentPreview(
        domain="patchbay.mode",
        target=f"{bay_key} {pair_label}",
        before=before,
        after=after,
        changed=changed,
        affected_files=[rel] if changed else [],
        message=message,
    )
    return preview, doc


def propose_set_model(
    bay_id: str,
    model: str,
    *,
    data: dict[str, Any] | None = None,
    path: Path | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    doc = copy.deepcopy(data if data is not None else load_raw(path))
    bay_key = bay_id.strip().upper()
    cleaned = model.strip()
    if not cleaned:
        raise StoreError("Hardware model cannot be empty.")
    bay = _bay(doc, bay_key)
    before_model = bay.get("hardware_model", "unknown")
    before = {"hardware_model": before_model}
    bay["hardware_model"] = cleaned
    after = {"hardware_model": cleaned}
    errors = validate_patchbays_doc(doc)
    if errors:
        raise StoreError("Patchbay validation failed: " + "; ".join(errors))
    changed = str(before_model) != cleaned
    rel = "data/patchbays.yaml"
    if changed:
        message = f"Set {bay_key} hardware_model {before_model!r} -> {cleaned!r}"
    else:
        message = f"No change: {bay_key} hardware_model is already {cleaned!r}"
    preview = CurrentPreview(
        domain="patchbay.model",
        target=bay_key,
        before=before,
        after=after,
        changed=changed,
        affected_files=[rel] if changed else [],
        message=message,
    )
    return preview, doc


def propose_set_modes_batch(
    bay_id: str,
    updates: list[tuple[str, str]],
    *,
    data: dict[str, Any] | None = None,
    path: Path | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    """Apply multiple mode updates for verify wizard. Empty updates => unchanged."""
    doc = copy.deepcopy(data if data is not None else load_raw(path))
    bay_key = bay_id.strip().upper()
    before_pairs: dict[str, str] = {}
    after_pairs: dict[str, str] = {}
    change_lines: list[str] = []

    for jack_spec, mode in updates:
        upper_n, lower_n, upper, lower = resolve_pair(bay_key, jack_spec, doc)
        pair_label = f"{upper_n}/{lower_n}" if lower_n is not None else str(upper_n)
        snap = _pair_snapshot(upper_n, lower_n, upper, lower)
        before_pairs[pair_label] = snap["mode"]
        canonical = parse_mode(mode)
        bay = _bay(doc, bay_key)
        jacks = _jacks_map(bay)
        _set_jack_field(jacks, upper_n, "mode", canonical)
        if lower_n is not None and _get_jack(jacks, lower_n) is not None:
            _set_jack_field(jacks, lower_n, "mode", canonical)
        upper_after = _get_jack(jacks, upper_n)
        lower_after = _get_jack(jacks, lower_n) if lower_n is not None else None
        assert upper_after is not None
        after_snap = _pair_snapshot(upper_n, lower_n, upper_after, lower_after)
        after_pairs[pair_label] = after_snap["mode"]
        if before_pairs[pair_label] != after_pairs[pair_label]:
            change_lines.append(
                f"{pair_label}  {before_pairs[pair_label]} -> {after_pairs[pair_label]}"
            )

    errors = validate_patchbays_doc(doc)
    if errors:
        raise StoreError("Patchbay validation failed: " + "; ".join(errors))

    changed = bool(change_lines)
    rel = "data/patchbays.yaml"
    if changed:
        message = f"Batch mode update on {bay_key}: {len(change_lines)} pair(s)"
    else:
        message = f"No change: no mode updates for {bay_key}"
    preview = CurrentPreview(
        domain="patchbay.mode",
        target=bay_key,
        before={"modes": before_pairs},
        after={"modes": after_pairs, "changes": change_lines},
        changed=changed,
        affected_files=[rel] if changed else [],
        message=message,
    )
    return preview, doc
