"""Pending HUMAN authority requests — proposals until HUMAN accepts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from music_rig.actor import require_human
from music_rig.models import (
    AnswerActor,
    HumanActionRequest,
    HumanActionsDocument,
    HumanActionStatus,
    HumanActionType,
    QuestionStatus,
    TodoStatus,
)
from music_rig.store import (
    StoreError,
    load_human_actions,
    load_questions,
    load_todo,
    save_human_actions,
)

Clock = Callable[[], datetime]


def default_clock() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(UTC)


def _get(
    action_id: str,
    *,
    path: Path | None = None,
) -> tuple[HumanActionsDocument, HumanActionRequest]:
    doc = load_human_actions(path)
    key = action_id.strip().upper()
    item = doc.item_map().get(key)
    if item is None:
        raise StoreError(f"Human action {key} does not exist.")
    return doc, item


def get_action(action_id: str, *, path: Path | None = None) -> HumanActionRequest:
    return _get(action_id, path=path)[1]


def list_actions(
    *,
    pending_only: bool = False,
    path: Path | None = None,
) -> list[HumanActionRequest]:
    doc = load_human_actions(path)
    refresh_stale(path=path)
    doc = load_human_actions(path)
    if pending_only:
        return doc.pending()
    return list(doc.items)


def create_request(
    *,
    action_type: HumanActionType | str,
    artifact_id: str,
    prompt: str,
    proposed_value: str,
    explanation: str,
    consequences: str = "",
    related_ids: list[str] | None = None,
    verification_outcome: str | None = None,
    verification_note: str | None = None,
    clock: Clock = default_clock,
    path: Path | None = None,
) -> HumanActionRequest:
    """BOT (or HUMAN tooling) may prepare proposals. Does not mutate target artifacts."""
    doc = load_human_actions(path)
    kind = (
        action_type
        if isinstance(action_type, HumanActionType)
        else HumanActionType(str(action_type))
    )
    artifact = artifact_id.strip().upper()
    # Supersede older pending requests for same type+artifact.
    items: list[HumanActionRequest] = []
    for existing in doc.items:
        if (
            existing.status is HumanActionStatus.PENDING
            and existing.action_type is kind
            and existing.artifact_id == artifact
        ):
            data = existing.model_dump()
            data["status"] = HumanActionStatus.SUPERSEDED
            data["superseded_reason"] = "replaced by newer proposal"
            items.append(HumanActionRequest.model_validate(data))
        else:
            items.append(existing)

    value = proposed_value.strip()
    if not value:
        raise StoreError("proposed_value cannot be empty.")
    tmp = HumanActionsDocument(items=items)
    req = HumanActionRequest(
        id=tmp.next_id(),
        action_type=kind,
        artifact_id=artifact,
        prompt=prompt.strip(),
        proposed_value=value,
        proposed_value_original=value,
        explanation=explanation.strip(),
        consequences=consequences.strip(),
        related_ids=list(related_ids or []),
        source_actor=AnswerActor.BOT,
        created_at=clock(),
        verification_outcome=(verification_outcome or None),
        verification_note=verification_note,
    )
    new_doc = HumanActionsDocument(items=[*items, req])
    save_human_actions(new_doc, path)
    return req


def format_review(req: HumanActionRequest) -> str:
    """Human-readable review card (no YAML)."""
    lines = [
        f"{req.id} — {req.action_type.value}",
        f"Artifact: {req.artifact_id}",
        "",
        "Prompt:",
        req.prompt,
        "",
        "Proposed value:",
        req.proposed_value,
    ]
    if req.action_type is HumanActionType.VERIFICATION_RESULT:
        lines.extend(
            [
                "",
                f"Observation outcome: {req.verification_outcome}",
            ]
        )
        if req.verification_note:
            lines.append(f"Observation note: {req.verification_note}")
    if req.action_type is HumanActionType.TODO_DOD_CONFIRMATION:
        lines.extend(["", "Definition of Done you are attesting:", req.proposed_value])
    lines.extend(
        [
            "",
            "Why this is pending:",
            req.explanation,
        ]
    )
    if req.consequences.strip():
        lines.extend(["", "Accepting will:", req.consequences])
    lines.extend(
        [
            "",
            f"Proposed by: {req.source_actor.value}",
            f"Status: {req.status.value}",
        ]
    )
    return "\n".join(lines)


def _stale_reason(
    req: HumanActionRequest,
    *,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> str | None:
    """Return reason if request is obsolete vs current artifact state."""
    if req.status is not HumanActionStatus.PENDING:
        return None
    if req.action_type in {
        HumanActionType.QUESTION_ANSWER,
        HumanActionType.VERIFICATION_RESULT,
        HumanActionType.HUMAN_CLARIFICATION,
    }:
        if (
            req.action_type is HumanActionType.HUMAN_CLARIFICATION
            and not req.artifact_id.startswith("Q-")
        ):
            return None
        qdoc = load_questions(questions_path)
        q = qdoc.question_map().get(req.artifact_id)
        if q is None:
            return f"{req.artifact_id} no longer exists"
        if req.action_type is HumanActionType.QUESTION_ANSWER:
            if q.status is QuestionStatus.RESOLVED and q.answer_actor is AnswerActor.HUMAN:
                return f"{req.artifact_id} already has a HUMAN FINAL answer"
        if req.action_type is HumanActionType.VERIFICATION_RESULT:
            if q.verification_result is not None:
                return f"{req.artifact_id} already has a verification_result"
        if req.action_type is HumanActionType.HUMAN_CLARIFICATION:
            if q.status is QuestionStatus.RESOLVED and q.answer_actor is AnswerActor.HUMAN:
                return f"{req.artifact_id} clarification already answered by HUMAN"
    if req.action_type is HumanActionType.TODO_DOD_CONFIRMATION:
        tdoc = load_todo(todo_path)
        task = tdoc.task_map().get(req.artifact_id)
        if task is None:
            return f"{req.artifact_id} no longer exists"
        if task.status is TodoStatus.DONE:
            return f"{req.artifact_id} is already DONE"
    return None


def refresh_stale(
    *,
    path: Path | None = None,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> list[HumanActionRequest]:
    doc = load_human_actions(path)
    changed = False
    items: list[HumanActionRequest] = []
    superseded: list[HumanActionRequest] = []
    for item in doc.items:
        reason = _stale_reason(item, questions_path=questions_path, todo_path=todo_path)
        if reason:
            data = item.model_dump()
            data["status"] = HumanActionStatus.SUPERSEDED
            data["superseded_reason"] = reason
            updated = HumanActionRequest.model_validate(data)
            items.append(updated)
            superseded.append(updated)
            changed = True
        else:
            items.append(item)
    if changed:
        save_human_actions(HumanActionsDocument(items=items), path)
    return superseded


def reject(
    action_id: str,
    *,
    clock: Clock = default_clock,
    path: Path | None = None,
) -> HumanActionRequest:
    require_human(action="reject HUMAN authority requests")
    doc, item = _get(action_id, path=path)
    if item.status is not HumanActionStatus.PENDING:
        raise StoreError(f"{item.id} is {item.status.value}, not PENDING")
    data = item.model_dump()
    data["status"] = HumanActionStatus.REJECTED
    data["rejected_at"] = clock()
    updated = HumanActionRequest.model_validate(data)
    new_doc = HumanActionsDocument(items=[updated if i.id == updated.id else i for i in doc.items])
    save_human_actions(new_doc, path)
    return updated


def accept(
    action_id: str,
    *,
    edited_value: str | None = None,
    clock: Clock = default_clock,
    path: Path | None = None,
    render: bool = True,
    offer_reconcile: bool = True,
) -> dict:
    """HUMAN acceptance — records HUMAN authority via existing services."""
    require_human(action="accept HUMAN authority requests")
    refresh_stale(path=path)
    doc, item = _get(action_id, path=path)
    if item.status is HumanActionStatus.SUPERSEDED:
        raise StoreError(
            f"{item.id} is SUPERSEDED ({item.superseded_reason or 'stale'}). "
            "Do not apply stale proposals."
        )
    if item.status is not HumanActionStatus.PENDING:
        raise StoreError(f"{item.id} is {item.status.value}, not PENDING")

    final_value = (edited_value if edited_value is not None else item.proposed_value).strip()
    if not final_value:
        raise StoreError("Accepted value cannot be empty.")

    apply_result = _dispatch(item, final_value=final_value, render=render)

    data = item.model_dump()
    data.update(
        {
            "status": HumanActionStatus.ACCEPTED,
            "proposed_value": final_value,
            "accepted_value": final_value,
            "accepted_by": AnswerActor.HUMAN,
            "accepted_at": clock(),
        }
    )
    updated = HumanActionRequest.model_validate(data)
    new_doc = HumanActionsDocument(items=[updated if i.id == updated.id else i for i in doc.items])
    save_human_actions(new_doc, path)

    out: dict = {
        "action": updated.model_dump(mode="json"),
        "apply": apply_result,
        "message": f"{updated.id} accepted as HUMAN.",
    }
    if offer_reconcile and updated.action_type in {
        HumanActionType.QUESTION_ANSWER,
        HumanActionType.VERIFICATION_RESULT,
        HumanActionType.HUMAN_CLARIFICATION,
    }:
        out["suggested_next"] = f"uv run rig reconcile plan question {updated.artifact_id} --json"
        out["reconcile_prompt"] = (
            f"{updated.artifact_id} answer recorded. Reconciliation is now possible. "
            f"Review with: uv run rig reconcile plan question {updated.artifact_id}"
        )
    return out


def _dispatch(
    item: HumanActionRequest,
    *,
    final_value: str,
    render: bool,
) -> dict:
    if item.action_type is HumanActionType.QUESTION_ANSWER:
        from music_rig import question_service

        return question_service.answer_question(item.artifact_id, final_value, render=render)

    if item.action_type is HumanActionType.HUMAN_CLARIFICATION:
        from music_rig import question_service

        if item.artifact_id.startswith("Q-"):
            return question_service.answer_question(item.artifact_id, final_value, render=render)
        # Freeform clarification (e.g. Thru5 OUT map): record into MIDI notes only.
        return _apply_freeform_clarification(item, final_value=final_value, render=render)

    if item.action_type is HumanActionType.VERIFICATION_RESULT:
        from music_rig import verification_service

        outcome = (item.verification_outcome or "unknown").strip().lower()
        return verification_service.record_observation(
            item.artifact_id,
            outcome,
            value=final_value,
            note=item.verification_note,
            yes=True,
            render=render,
        )

    if item.action_type is HumanActionType.TODO_DOD_CONFIRMATION:
        from music_rig import todo_service

        task = todo_service.get_task(load_todo(), item.artifact_id)
        current_dod = task.definition_of_done.strip()
        # Accepting attests the CURRENT DoD; edited_value may be YES or the DoD text.
        attested = final_value.strip()
        if attested.upper() not in {"YES", "Y", "ACCEPT", "CONFIRMED"}:
            if attested != current_dod and attested != item.proposed_value_original.strip():
                raise StoreError(
                    f"{item.artifact_id} accepted value must be YES or the exact "
                    "Definition of Done text shown in the request."
                )
        if current_dod and current_dod != item.proposed_value_original.strip():
            raise StoreError(
                f"{item.artifact_id} Definition of Done changed since proposal; "
                "create a fresh request showing the current DoD."
            )
        updated_task, changed, _doc = todo_service.set_todo_status(
            item.artifact_id,
            TodoStatus.DONE,
            remove_from_next=True,
            render=render,
        )
        return {
            "todo_id": updated_task.id,
            "status": updated_task.status.value,
            "changed": changed,
            "definition_of_done": updated_task.definition_of_done,
        }

    raise StoreError(f"Unsupported action type {item.action_type}")


def _apply_freeform_clarification(
    item: HumanActionRequest,
    *,
    final_value: str,
    render: bool,
) -> dict:
    """Apply non-Question clarifications carefully (no invented typed links)."""
    from music_rig import midi_state
    from music_rig.current_service import commit_midi
    from music_rig.models import CurrentPreview
    from music_rig.store import MIDI_PATH

    if item.artifact_id != "THRU5-OUT-MAP":
        raise StoreError(f"Unsupported freeform clarification artifact {item.artifact_id!r}")
    raw = midi_state.load_raw()
    devices = raw.get("devices") or []
    found = False
    for device in devices:
        if device.get("gear_ref") == "cme-midi-thru5-wc":
            note = (device.get("notes") or "").rstrip()
            addition = f"HUMAN OUT map: {final_value.strip()}"
            if addition not in note:
                device["notes"] = f"{note}\n{addition}".strip() if note else addition
            found = True
            break
    if not found:
        raise StoreError("cme-midi-thru5-wc missing from midi.yaml")
    # Still no typed OUT→device links — HUMAN text only until structured links are added.
    unknowns = list(raw.get("unknowns") or [])
    marker = "Thru5 OUT number → device map recorded as HUMAN clarification"
    if marker not in unknowns:
        unknowns = [u for u in unknowns if "OUT port numbers UNKNOWN" not in u]
        unknowns.insert(0, marker)
        raw["unknowns"] = unknowns
    preview = CurrentPreview(
        domain="midi.verify",
        target="cme-midi-thru5-wc",
        before={"notes": "prior"},
        after={"notes": "HUMAN OUT map recorded"},
        changed=True,
        message="Record HUMAN Thru5 OUT clarification (no typed links invented)",
    )
    commit_midi(raw, preview, render=render, midi_path=MIDI_PATH)
    return {
        "artifact_id": item.artifact_id,
        "recorded": final_value.strip(),
        "typed_links_created": False,
        "note": "OUT mapping text stored; create typed MIDI links in a follow-up once verified.",
    }
