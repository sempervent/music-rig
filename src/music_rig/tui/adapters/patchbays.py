"""Patchbay view helpers; mutations go through propose_* + commit_patchbay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig import current_service, snapshot_service
from music_rig.models import CurrentPreview, QuestionStatus
from music_rig.patchbay_state import (
    list_pairs,
    load_raw,
    propose_set_model,
    propose_set_modes_batch,
)
from music_rig.store import load_questions
from music_rig import store as store_mod
from music_rig.tui.working import ConcurrentModificationError, WorkingDocument


def bay_summaries(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = data if data is not None else load_raw()
    rows: list[dict[str, Any]] = []
    for bay_id, bay in (doc.get("patchbays") or {}).items():
        pairs = list_pairs(bay_id, doc)
        unknown = sum(1 for p in pairs if str(p.get("mode", "unknown")).lower() == "unknown")
        populated = sum(
            1
            for p in pairs
            if (p.get("upper_conn") not in (None, "")) or (p.get("lower_conn") not in (None, ""))
        )
        rows.append(
            {
                "id": bay_id,
                "model": str(bay.get("hardware_model") or "unknown"),
                "pairs": len(pairs),
                "populated": populated,
                "unknown": unknown,
                "status": str(bay.get("status") or ""),
            }
        )
    return rows


def pair_key(pair: dict[str, Any]) -> str:
    upper = pair["upper_n"]
    lower = pair.get("lower_n")
    if lower is None:
        return str(upper)
    return f"{upper}/{lower}"


def related_open_questions(bay_id: str, pair: str | None = None) -> list:
    """OPEN questions whose typed target points at this bay (and optional pair)."""
    bay = bay_id.upper()
    items = []
    for q in load_questions().questions:
        if q.status != QuestionStatus.OPEN:
            continue
        t = q.target
        if t is None or not t.bay or t.bay.upper() != bay:
            continue
        if pair and t.pair and t.pair not in {pair, pair.split("/", 1)[0]}:
            continue
        items.append(q)
    return items


def open_working(bay_id: str, *, path: Path | None = None) -> WorkingDocument[dict[str, Any]]:
    target = path or store_mod.PATCHBAYS_PATH
    data = load_raw(target)
    return WorkingDocument(data, source_path=target)


def staged_mode_for(
    working: WorkingDocument[dict[str, Any]],
    bay_id: str,
    pair: dict[str, Any],
) -> tuple[str, str | None]:
    """Return (effective_mode, baseline_mode_if_staged)."""
    key = f"mode:{pair_key(pair)}"
    baseline = str(pair.get("mode") or "unknown").lower()
    if working.has(key):
        return str(working.get(key)).lower(), baseline
    return baseline, None


def staged_model(working: WorkingDocument[dict[str, Any]], bay_id: str) -> tuple[str, str | None]:
    bay = (working.baseline.get("patchbays") or {}).get(bay_id.upper()) or {}
    baseline = str(bay.get("hardware_model") or "unknown")
    if working.has("model"):
        return str(working.get("model")), baseline
    return baseline, None


def change_summary(working: WorkingDocument[dict[str, Any]], bay_id: str) -> str:
    lines: list[str] = [f"Bay {bay_id.upper()}", ""]
    model_now, model_base = staged_model(working, bay_id)
    if model_base is not None and model_now != model_base:
        lines.append(f"hardware_model: {model_base!r} -> {model_now!r}")
    pairs = list_pairs(bay_id, working.baseline)
    for pair in pairs:
        key = f"mode:{pair_key(pair)}"
        if not working.has(key):
            continue
        before = str(pair.get("mode") or "unknown")
        after = str(working.get(key))
        lines.append(f"{pair_key(pair)}: {before} -> {after}")
    if len(lines) == 2:
        lines.append("(no changes)")
    lines.append("")
    lines.append("Endpoint (upper/lower connection) editing is not available in Stage 12.")
    lines.append("Mode + hardware_model only.")
    return "\n".join(lines)


def apply_working(
    working: WorkingDocument[dict[str, Any]],
    bay_id: str,
    *,
    create_snapshot: bool = True,
    render: bool = True,
    patchbays_path: Path | None = None,
) -> CurrentPreview:
    """Commit staged mode/model via propose_* + commit_patchbay. Optional snapshot first."""

    def _commit(doc: WorkingDocument[dict[str, Any]]) -> None:
        nonlocal result
        if create_snapshot:
            snapshot_service.create_snapshot()
        data = doc.baseline
        bay = bay_id.upper()
        mode_updates: list[tuple[str, str]] = []
        for key, value in doc.mutations.items():
            if key.startswith("mode:"):
                pair = key.removeprefix("mode:")
                upper = pair.split("/", 1)[0]
                mode_updates.append((upper, str(value)))
        preview_modes = None
        if mode_updates:
            preview_modes, data = propose_set_modes_batch(bay, mode_updates, data=data)
        preview_model = None
        if doc.has("model"):
            preview_model, data = propose_set_model(bay, str(doc.get("model")), data=data)

        changed = False
        messages: list[str] = []
        affected: list[str] = []
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        if preview_modes is not None:
            changed = changed or preview_modes.changed
            messages.append(preview_modes.message)
            affected.extend(preview_modes.affected_files)
            before["modes"] = preview_modes.before
            after["modes"] = preview_modes.after
        if preview_model is not None:
            changed = changed or preview_model.changed
            messages.append(preview_model.message)
            affected.extend(preview_model.affected_files)
            before["model"] = preview_model.before
            after["model"] = preview_model.after

        preview = CurrentPreview(
            domain="patchbay",
            target=bay,
            before=before,
            after=after,
            changed=changed,
            affected_files=list(dict.fromkeys(affected)),
            message="; ".join(messages) or f"No change on {bay}",
        )
        result = current_service.commit_patchbay(
            data,
            preview,
            render=render,
            patchbays_path=patchbays_path or doc.source_path,
        )
        doc.discard()
        doc.baseline = data
        doc.refresh_source_hash()

    result: CurrentPreview | None = None
    try:
        working.apply(_commit)
    except ConcurrentModificationError:
        raise
    assert result is not None
    return result
