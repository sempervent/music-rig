"""Commit CURRENT-state previews with optional question/change reconciliation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from music_rig.inbox_service import default_clock
from music_rig.models import (
    ChangeRecord,
    ChangeStatus,
    ChangesDocument,
    CurrentPreview,
    OpenQuestion,
    OpenQuestionsDocument,
    QuestionStatus,
    InventoryDocument,
    TodoDocument,
    WishlistDocument,
)
from music_rig.render import render_docs
from music_rig.store import (
    ABLETON_PATH,
    CHANGES_PATH,
    CHANNEL_MAP_PATH,
    PATCHBAYS_PATH,
    QUESTIONS_PATH,
    ROUTING_PATH,
    INVENTORY_PATH,
    MIDI_PATH,
    CONTROLLERS_PATH,
    PERFORMANCE_PATH,
    TODO_PATH,
    WISHLIST_PATH,
    StoreError,
    _dump_yaml,
    load_changes,
    load_questions,
    load_todo,
    write_text_files,
)
from music_rig import (
    ableton_state,
    channel_state,
    control_state,
    inventory_state,
    midi_state,
    patchbay_state,
    performance_state,
    routing_state,
)

Clock = Callable[[], datetime]


def _validate_evidence(
    *,
    question_id: str | None,
    change_id: str | None,
    resolve_q: bool,
    apply_chg: bool,
    answer: str,
    questions_path: Path | None,
    changes_path: Path | None,
) -> tuple[OpenQuestionsDocument | None, ChangesDocument | None, str | None, str | None]:
    """Load and validate referenced Q/CHG. Return docs only when mutation needed."""
    q_key = question_id.strip().upper() if question_id else None
    c_key = change_id.strip().upper() if change_id else None
    qdoc: OpenQuestionsDocument | None = None
    cdoc: ChangesDocument | None = None

    if q_key is not None or resolve_q:
        if q_key is None:
            raise StoreError("resolve_q requires question_id")
        qdoc = load_questions(questions_path)
        if q_key not in qdoc.question_map():
            raise StoreError(f"Question {q_key} does not exist.")
        if resolve_q and not answer.strip():
            raise StoreError("Resolving a question requires a non-empty answer.")

    if c_key is not None or apply_chg:
        if c_key is None:
            raise StoreError("apply_chg requires change_id")
        cdoc = load_changes(changes_path)
        if c_key not in cdoc.item_map():
            raise StoreError(f"Change {c_key} does not exist.")

    return qdoc, cdoc, q_key, c_key


def _with_resolved_question(
    qdoc: OpenQuestionsDocument,
    q_key: str,
    answer: str,
    *,
    change_id: str | None,
    clock: Clock,
) -> OpenQuestionsDocument:
    current = qdoc.question_map()[q_key]
    change_ids = list(current.related_changes)
    if change_id and change_id not in change_ids:
        change_ids.append(change_id)
    data = current.model_dump()
    data.update(
        {
            "status": QuestionStatus.RESOLVED,
            "related_changes": change_ids,
            "answer": answer.strip(),
            "resolved_at": clock(),
            "reconciled_at": None,
            "reconciliation_note": "",
        }
    )
    updated = OpenQuestion.model_validate(data)
    return OpenQuestionsDocument(
        questions=[updated if q.id == q_key else q for q in qdoc.questions]
    )


def _dump_questions_yaml(qdoc: OpenQuestionsDocument) -> str:
    payload = qdoc.model_dump(mode="json")
    for item in payload.get("questions", []):
        if item.get("target") is None:
            item.pop("target", None)
    return _dump_yaml(payload)


def _with_applied_change(
    cdoc: ChangesDocument,
    c_key: str,
    *,
    question_id: str | None,
) -> ChangesDocument:
    items: list[ChangeRecord] = []
    for item in cdoc.items:
        if item.id != c_key:
            items.append(item)
            continue
        qrefs = list(item.related_questions)
        if question_id and question_id not in qrefs:
            qrefs.append(question_id)
        items.append(
            ChangeRecord(
                id=item.id,
                created_at=item.created_at,
                category=item.category,
                summary=item.summary,
                details=item.details,
                status=ChangeStatus.APPLIED,
                session_id=item.session_id,
                affected_areas=list(item.affected_areas),
                related_questions=qrefs,
            )
        )
    return ChangesDocument(items=items)


def _commit(
    *,
    preview: CurrentPreview,
    primary_path: Path,
    primary_text: str,
    dry_run: bool,
    render: bool,
    question_id: str | None,
    change_id: str | None,
    resolve_q: bool,
    apply_chg: bool,
    answer: str,
    clock: Clock,
    questions_path: Path | None,
    changes_path: Path | None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    qdoc, cdoc, q_key, c_key = _validate_evidence(
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        questions_path=questions_path,
        changes_path=changes_path,
    )

    if dry_run:
        return preview

    if not preview.changed:
        # Idempotent: do not resolve questions or apply changes.
        return preview

    payloads: list[tuple[Path, str]] = [(primary_path, primary_text)]

    if resolve_q and qdoc is not None and q_key is not None:
        qdoc = _with_resolved_question(
            qdoc, q_key, answer, change_id=c_key, clock=clock
        )
        payloads.append(
            (questions_path or QUESTIONS_PATH, _dump_questions_yaml(qdoc))
        )

    if apply_chg and cdoc is not None and c_key is not None:
        # If we also resolved a question, refresh cdoc for bidirectional link first
        if resolve_q and q_key is not None:
            # reload base changes if qdoc path already mutated related_changes only
            base = cdoc
            cdoc = _with_applied_change(base, c_key, question_id=q_key)
        else:
            cdoc = _with_applied_change(cdoc, c_key, question_id=q_key)
        payloads.append(
            (
                changes_path or CHANGES_PATH,
                _dump_yaml(cdoc.model_dump(mode="json")),
            )
        )
    elif resolve_q and q_key is not None and c_key is not None and cdoc is not None:
        # Question linked a change but change not applied — still bidirectional link
        updated_items: list[ChangeRecord] = []
        for item in cdoc.items:
            if item.id == c_key:
                qrefs = list(item.related_questions)
                if q_key not in qrefs:
                    qrefs.append(q_key)
                    updated_items.append(
                        ChangeRecord(
                            **{**item.model_dump(), "related_questions": qrefs}
                        )
                    )
                else:
                    updated_items.append(item)
            else:
                updated_items.append(item)
        linked = ChangesDocument(items=updated_items)
        if linked.model_dump(mode="json") != cdoc.model_dump(mode="json"):
            payloads.append(
                (
                    changes_path or CHANGES_PATH,
                    _dump_yaml(linked.model_dump(mode="json")),
                )
            )

    write_text_files(payloads)

    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return preview


def commit_patchbay(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    patchbays_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = patchbays_path or PATCHBAYS_PATH
    errors = patchbay_state.validate_patchbays_doc(proposed_data)
    if errors:
        raise StoreError("Patchbay validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = patchbay_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_channel(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    channel_map_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = channel_map_path or CHANNEL_MAP_PATH
    errors = channel_state.validate_channel_map(proposed_data)
    if errors:
        raise StoreError("Channel map validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = channel_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_routing(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    routing_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = routing_path or ROUTING_PATH
    errors = routing_state.validate_routing_doc(proposed_data)
    if errors:
        raise StoreError("Routing validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = routing_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_inventory(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    inventory_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = inventory_path or INVENTORY_PATH
    errors = inventory_state.validate_inventory_doc(proposed_data)
    if errors:
        raise StoreError("Inventory validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = inventory_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_midi(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    midi_path: Path | None = None,
    inventory_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = midi_path or MIDI_PATH
    errors = midi_state.validate_midi_doc(
        proposed_data, inventory_path=inventory_path
    )
    if errors:
        raise StoreError("MIDI validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = midi_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_controllers(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    controllers_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
    ableton_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = controllers_path or CONTROLLERS_PATH
    errors = control_state.validate_controllers_doc(
        proposed_data,
        inventory_path=inventory_path,
        midi_path=midi_path,
        ableton_path=ableton_path,
    )
    if errors:
        raise StoreError("Controllers validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = control_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_ableton(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    ableton_path: Path | None = None,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> CurrentPreview:
    target = ableton_path or ABLETON_PATH
    errors = ableton_state.validate_ableton_doc(proposed_data)
    if errors:
        raise StoreError("Ableton validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = ableton_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        clock=clock,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )


def commit_performance(
    proposed_data: dict,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    performance_path: Path | None = None,
    controllers_path: Path | None = None,
    surfaces_path: Path | None = None,
    ableton_path: Path | None = None,
    inventory_path: Path | None = None,
    midi_path: Path | None = None,
) -> CurrentPreview:
    target = performance_path or PERFORMANCE_PATH
    errors = performance_state.validate_performance_doc(
        proposed_data,
        controllers_path=controllers_path,
        surfaces_path=surfaces_path,
        ableton_path=ableton_path,
        inventory_path=inventory_path,
        midi_path=midi_path,
    )
    if errors:
        raise StoreError("Performance validation failed: " + "; ".join(errors))
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    text = performance_state.dump_with_header(proposed_data, existing_text=existing)
    return _commit(
        preview=preview,
        primary_path=target,
        primary_text=text,
        dry_run=dry_run,
        render=render,
        question_id=None,
        change_id=None,
        resolve_q=False,
        apply_chg=False,
        answer="",
        clock=default_clock,
        questions_path=None,
        changes_path=None,
    )


def commit_acquisition(
    proposed_inventory: dict,
    proposed_wishlist: WishlistDocument,
    proposed_todo: TodoDocument,
    preview: CurrentPreview,
    *,
    dry_run: bool = False,
    render: bool = True,
    inventory_path: Path | None = None,
    wishlist_path: Path | None = None,
    todo_path: Path | None = None,
    question_id: str | None = None,
    change_id: str | None = None,
    resolve_q: bool = False,
    apply_chg: bool = False,
    answer: str = "",
    clock: Clock = default_clock,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
) -> CurrentPreview:
    """Atomically cross the wishlist → owned-inventory boundary."""
    errors = inventory_state.validate_inventory_doc(proposed_inventory)
    if errors:
        raise StoreError("Inventory validation failed: " + "; ".join(errors))
    WishlistDocument.model_validate(proposed_wishlist.model_dump())
    TodoDocument.model_validate(proposed_todo.model_dump())
    qdoc, cdoc, q_key, c_key = _validate_evidence(
        question_id=question_id,
        change_id=change_id,
        resolve_q=resolve_q,
        apply_chg=apply_chg,
        answer=answer,
        questions_path=questions_path,
        changes_path=changes_path,
    )
    if dry_run or not preview.changed:
        return preview
    inv_target = inventory_path or INVENTORY_PATH
    existing = inv_target.read_text(encoding="utf-8") if inv_target.exists() else None
    payloads = [
        (
            inv_target,
            inventory_state.dump_with_header(
                proposed_inventory, existing_text=existing
            ),
        ),
        (
            wishlist_path or WISHLIST_PATH,
            _dump_yaml(proposed_wishlist.model_dump(mode="json", exclude_none=True)),
        ),
    ]
    todo_target = todo_path or TODO_PATH
    todo_text = _dump_yaml(proposed_todo.model_dump(mode="json", exclude_none=True))
    current_todo = load_todo(todo_path)
    if current_todo.model_dump(mode="json") != proposed_todo.model_dump(mode="json"):
        payloads.append((todo_target, todo_text))
    if resolve_q and qdoc is not None and q_key is not None:
        qdoc = _with_resolved_question(
            qdoc, q_key, answer, change_id=c_key, clock=clock
        )
        payloads.append((questions_path or QUESTIONS_PATH, _dump_questions_yaml(qdoc)))
    if apply_chg and cdoc is not None and c_key is not None:
        cdoc = _with_applied_change(cdoc, c_key, question_id=q_key)
        payloads.append(
            (
                changes_path or CHANGES_PATH,
                _dump_yaml(cdoc.model_dump(mode="json")),
            )
        )
    write_text_files(payloads)
    if render:
        render_docs(write=True)
    return preview
