"""Open question lifecycle helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from music_rig.inbox_service import default_clock
from music_rig.models import (
    AnswerState,
    ChangeRecord,
    ChangesDocument,
    OpenQuestion,
    OpenQuestionsDocument,
    QuestionStatus,
    TodoDocument,
    TodoTask,
)
from music_rig.render import render_docs
from music_rig.store import (
    StoreError,
    load_changes,
    load_questions,
    load_todo,
    write_documents,
)
from music_rig import todo_service

Clock = Callable[[], datetime]


def derive_answer_state(question: OpenQuestion) -> AnswerState:
    """Derived answer lifecycle (not persisted).

    OPEN + empty answer = UNANSWERED
    OPEN + non-empty answer = DRAFT
    RESOLVED + non-empty answer = FINAL
    """
    if question.status == QuestionStatus.RESOLVED and question.answer.strip():
        return AnswerState.FINAL
    if question.status == QuestionStatus.OPEN and question.answer.strip():
        return AnswerState.DRAFT
    return AnswerState.UNANSWERED


def lifecycle_label(question: OpenQuestion) -> str:
    """Human list label combining status + answer/recon state."""
    ans = derive_answer_state(question)
    if question.status == QuestionStatus.OPEN:
        if ans == AnswerState.DRAFT:
            return "OPEN/DRAFT"
        return "OPEN/UNANSWERED"
    if question.status == QuestionStatus.RESOLVED:
        if question.reconciled_at is not None:
            return "RESOLVED/RECONCILED"
        return "RESOLVED/UNRECONCILED"
    return question.status.value


def question_json_fields(question: OpenQuestion) -> dict:
    """Stable agent-facing fields including derived answer_state."""
    from music_rig.verification_policy import (
        effective_answer_actor,
        evidence_basis_for,
        verification_policy_for,
    )

    actor = effective_answer_actor(question)
    return {
        "id": question.id,
        "question_status": question.status.value,
        "answer_state": derive_answer_state(question).value,
        "answer": question.answer,
        "answer_actor": actor.value if actor is not None else None,
        "answer_source": actor.value if actor is not None else None,
        "clarifies_question": question.clarifies_question,
        "verification_policy": verification_policy_for(question).value,
        "evidence_basis": evidence_basis_for(question).value,
        "resolved_at": (
            question.resolved_at.isoformat() if question.resolved_at else None
        ),
        "reconciled_at": (
            question.reconciled_at.isoformat() if question.reconciled_at else None
        ),
        "lifecycle_label": lifecycle_label(question),
    }


def get_question(
    question_id: str, *, questions_path: Path | None = None
) -> OpenQuestion:
    doc = load_questions(questions_path)
    key = question_id.strip().upper()
    item = doc.question_map().get(key)
    if item is None:
        raise StoreError(f"Question {key} does not exist.")
    return item


def list_questions(
    *,
    all_items: bool = False,
    open_only: bool = False,
    unreconciled_only: bool = False,
    area: str | None = None,
    questions_path: Path | None = None,
) -> list[OpenQuestion]:
    """List questions.

    Default (no flags): ACTIVE = OPEN + RESOLVED with reconciled_at null.
    --open: OPEN only
    --unreconciled: RESOLVED with reconciled_at null
    --all: every status
    """
    doc = load_questions(questions_path)
    items = list(doc.questions)
    if all_items:
        pass
    elif open_only:
        items = [q for q in items if q.status == QuestionStatus.OPEN]
    elif unreconciled_only:
        items = [
            q
            for q in items
            if q.status == QuestionStatus.RESOLVED and q.reconciled_at is None
        ]
    else:
        # ACTIVE
        items = [
            q
            for q in items
            if q.status == QuestionStatus.OPEN
            or (q.status == QuestionStatus.RESOLVED and q.reconciled_at is None)
        ]
    if area:
        needle = area.casefold()
        items = [q for q in items if needle in q.area.casefold()]
    return items


def add_question(
    question: str,
    *,
    area: str,
    related_todos: list[str] | None = None,
    notes: str = "",
    render: bool = True,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    cleaned = question.strip()
    if not cleaned:
        raise StoreError("Question text cannot be empty.")
    area_clean = area.strip()
    if not area_clean:
        raise StoreError("Area cannot be empty.")
    todo_ids = [t.strip().upper() for t in (related_todos or []) if t.strip()]
    todo_doc = load_todo(todo_path)
    known = todo_doc.task_map()
    for tid in todo_ids:
        if tid not in known:
            raise StoreError(f"Related TODO {tid} does not exist.")
    doc = load_questions(questions_path)
    item = OpenQuestion(
        id=doc.next_id(),
        question=cleaned,
        area=area_clean,
        status=QuestionStatus.OPEN,
        related_todos=todo_ids,
        related_changes=[],
        answer="",
        notes=notes.strip(),
        resolved_at=None,
    )
    new_doc = OpenQuestionsDocument(questions=[*doc.questions, item])
    write_documents(questions=new_doc, questions_path=questions_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return item


def open_clarification_question(
    parent_id: str,
    clarification: str,
    *,
    area: str | None = None,
    dry_run: bool = False,
    render: bool = True,
    questions_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> dict:
    """Create an OPEN child Question that clarifies a parent.

    Does not alter CURRENT. Safe for agent use (creates human work only).
    """
    parent = get_question(parent_id, questions_path=questions_path)
    text = clarification.strip()
    if not text:
        raise StoreError("Clarification question text cannot be empty.")
    qdoc = load_questions(questions_path)
    for q in qdoc.questions:
        if (
            q.clarifies_question == parent.id
            and q.status == QuestionStatus.OPEN
            and q.question.strip() == text
            and not q.answer.strip()
        ):
            raise StoreError(
                f"Open clarification already exists as {q.id} for {parent.id}"
            )
    area_clean = (area or parent.area).strip() or parent.area
    if dry_run:
        return {
            "dry_run": True,
            "parent_id": parent.id,
            "would_create": {
                "id": qdoc.next_id(),
                "question": text,
                "area": area_clean,
                "clarifies_question": parent.id,
                "status": QuestionStatus.OPEN.value,
            },
        }
    child = OpenQuestion(
        id=qdoc.next_id(),
        question=text,
        area=area_clean,
        status=QuestionStatus.OPEN,
        related_todos=list(parent.related_todos),
        related_changes=[],
        answer="",
        notes=f"Clarifies {parent.id}",
        clarifies_question=parent.id,
        resolved_at=None,
    )
    new_doc = OpenQuestionsDocument(questions=[*qdoc.questions, child])
    write_documents(questions=new_doc, questions_path=questions_path)
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return {
        "dry_run": False,
        "parent_id": parent.id,
        "question_id": child.id,
        "question": child,
        "message": (
            f"Opened clarification {child.id} for {parent.id}. "
            "No CURRENT changes."
        ),
    }


def resolve_question(
    question_id: str,
    answer: str | None = None,
    *,
    related_change: str | None = None,
    verification_note: str | None = None,
    answer_actor=None,
    clock: Clock = default_clock,
    render: bool = True,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    """Promote to FINAL: RESOLVED + non-empty answer + resolved_at; reconciled_at null.

    If ``answer`` is None/blank, uses the existing question answer (draft → resolve).
    ``answer_actor`` defaults from CLI actor context (HUMAN vs BOT).
    BOT cannot supply final human authority for attestation/observation policies.
    """
    from music_rig.actor import AnswerActor, ActorKind, get_actor, require_human
    from music_rig.verification_policy import VerificationPolicy, verification_policy_for

    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")

    cleaned = (answer or "").strip()
    if not cleaned:
        cleaned = current.answer.strip()
    if not cleaned:
        raise StoreError("Resolved questions require a non-empty answer.")

    actor = answer_actor
    if actor is None:
        actor = (
            AnswerActor.BOT
            if get_actor() is ActorKind.BOT
            else AnswerActor.HUMAN
        )
    if isinstance(actor, str):
        actor = AnswerActor(actor)

    # Bots may not finalize as HUMAN authority.
    if actor is AnswerActor.BOT or get_actor() is ActorKind.BOT:
        policy = verification_policy_for(current)
        if policy is not VerificationPolicy.NO_VERIFICATION_REQUIRED:
            raise StoreError(
                "Bots cannot supply the required HUMAN answer.\n"
                "Use a draft/suggestion (rig --am-bot question draft …) or open a "
                "clarification Question; a human must Answer & Resolve."
            )

    changes_doc = None
    change_ids = list(current.related_changes)
    if related_change:
        chg = related_change.strip().upper()
        cdoc = load_changes(changes_path)
        if chg not in cdoc.item_map():
            raise StoreError(f"Change {chg} does not exist.")
        if chg not in change_ids:
            change_ids.append(chg)
        # bidirectional link
        updated_changes: list[ChangeRecord] = []
        for item in cdoc.items:
            if item.id == chg:
                qrefs = list(item.related_questions)
                if key not in qrefs:
                    qrefs.append(key)
                updated_changes.append(
                    ChangeRecord(
                        **{**item.model_dump(), "related_questions": qrefs}
                    )
                )
            else:
                updated_changes.append(item)
        changes_doc = ChangesDocument(items=updated_changes)

    data = current.model_dump()
    data.update(
        {
            "status": QuestionStatus.RESOLVED,
            "related_changes": change_ids,
            "answer": cleaned,
            "answer_actor": actor,
            "resolved_at": clock(),
            "reconciled_at": None,
            "reconciliation_note": "",
        }
    )
    if verification_note is not None:
        data["verification_note"] = verification_note.strip()
    updated = OpenQuestion.model_validate(data)
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(
        questions=new_qdoc,
        changes=changes_doc,
        questions_path=questions_path,
        changes_path=changes_path,
    )
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated


def draft_question(
    question_id: str,
    answer: str,
    *,
    dry_run: bool = False,
    clock: Clock = default_clock,
    render: bool = True,
    questions_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> dict:
    """Save a draft answer: status OPEN, resolved_at/reconciled_at null.

    Does not invent verification_result. Does not reconcile.
    BOT drafts remain answer_actor=BOT and do not clear NEEDS_HUMAN_ANSWER.
    """
    from music_rig.actor import AnswerActor, ActorKind, get_actor

    _ = clock  # reserved for future audit timestamps
    cleaned = answer.strip()
    if not cleaned:
        raise StoreError("Draft answer cannot be empty.")
    current = get_question(question_id, questions_path=questions_path)
    before = question_json_fields(current)
    actor = (
        AnswerActor.BOT if get_actor() is ActorKind.BOT else AnswerActor.HUMAN
    )
    if dry_run:
        return {
            "dry_run": True,
            "question_id": current.id,
            "before": before,
            "after": {
                "id": current.id,
                "question_status": QuestionStatus.OPEN.value,
                "answer_state": AnswerState.DRAFT.value,
                "answer": cleaned,
                "answer_actor": actor.value,
                "resolved_at": None,
                "reconciled_at": None,
            },
            "answer_state": AnswerState.DRAFT.value,
            "question_status": QuestionStatus.OPEN.value,
            "resolved_at": None,
            "reconciled_at": None,
            "suggested_next_command": (
                f"uv run rig question resolve {current.id}"
            ),
            "message": (
                "Draft answer recorded. Question remains OPEN. "
                "Resolve when the answer is final."
            ),
        }
    qdoc = load_questions(questions_path)
    key = current.id
    data = current.model_dump()
    data.update(
        {
            "status": QuestionStatus.OPEN,
            "answer": cleaned,
            "answer_actor": actor,
            "resolved_at": None,
            "reconciled_at": None,
            "reconciliation_note": "",
        }
    )
    updated = OpenQuestion.model_validate(data)
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(questions=new_qdoc, questions_path=questions_path)
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    fields = question_json_fields(updated)
    return {
        "dry_run": False,
        "question_id": updated.id,
        "before": before,
        "after": fields,
        "question": updated,
        "answer_state": fields["answer_state"],
        "question_status": fields["question_status"],
        "resolved_at": None,
        "reconciled_at": None,
        "suggested_next_command": f"uv run rig question resolve {updated.id}",
        "message": (
            "Draft answer recorded. Question remains OPEN. "
            "Resolve when the answer is final."
        ),
    }


def defer_question(
    question_id: str,
    *,
    render: bool = True,
    questions_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")
    updated = OpenQuestion(
        **{
            **current.model_dump(),
            "status": QuestionStatus.DEFERRED,
            "resolved_at": None,
            "reconciled_at": None,
        }
    )
    # DEFERRED may keep a prior answer as evidence; clear resolved_at
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(questions=new_qdoc, questions_path=questions_path)
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated


def reopen_question(
    question_id: str,
    *,
    render: bool = True,
    questions_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")
    notes = current.notes
    if current.answer.strip() and current.status == QuestionStatus.RESOLVED:
        prior = f"Prior answer (reopened): {current.answer.strip()}"
        notes = f"{notes}\n{prior}".strip() if notes.strip() else prior
    updated = OpenQuestion(
        id=current.id,
        question=current.question,
        area=current.area,
        status=QuestionStatus.OPEN,
        related_todos=list(current.related_todos),
        related_changes=list(current.related_changes),
        answer=current.answer,
        notes=notes,
        resolved_at=None,
        reconciled_at=None,
        reconciliation_note="",
        target=current.target,
    )
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(questions=new_qdoc, questions_path=questions_path)
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated


def create_todo_for_question(
    question_id: str,
    task: TodoTask,
    *,
    render: bool = True,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> tuple[OpenQuestion, TodoTask]:
    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")
    todo_doc = load_todo(todo_path)
    # ensure task id is allocated against current todo doc
    if task.id in todo_doc.task_map():
        raise StoreError(f"TODO {task.id} already exists.")
    refs = list(current.related_todos)
    if task.id not in refs:
        refs.append(task.id)
    updated_q = OpenQuestion(**{**current.model_dump(), "related_todos": refs})
    new_todo = TodoDocument(
        next_session=list(todo_doc.next_session),
        tasks=[*todo_doc.tasks, task],
    )
    new_qdoc = OpenQuestionsDocument(
        questions=[updated_q if q.id == key else q for q in qdoc.questions]
    )
    write_documents(
        todo=new_todo,
        questions=new_qdoc,
        todo_path=todo_path,
        questions_path=questions_path,
    )
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated_q, task


def link_todo(
    question_id: str,
    todo_id: str,
    *,
    render: bool = True,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")
    tid = todo_id.strip().upper()
    todo_service.get_task(load_todo(todo_path), tid)
    if tid in current.related_todos:
        raise StoreError(f"{tid} is already linked to {key}.")
    updated = OpenQuestion(
        **{**current.model_dump(), "related_todos": [*current.related_todos, tid]}
    )
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(questions=new_qdoc, questions_path=questions_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated


def link_change(
    question_id: str,
    change_id: str,
    *,
    render: bool = True,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")
    chg = change_id.strip().upper()
    cdoc = load_changes(changes_path)
    record = cdoc.item_map().get(chg)
    if record is None:
        raise StoreError(f"Change {chg} does not exist.")
    if chg in current.related_changes:
        raise StoreError(f"{chg} is already linked to {key}.")
    if key in record.related_questions:
        raise StoreError(f"{key} is already linked on {chg}.")

    updated_q = OpenQuestion(
        **{
            **current.model_dump(),
            "related_changes": [*current.related_changes, chg],
        }
    )
    updated_c = ChangeRecord(
        **{
            **record.model_dump(),
            "related_questions": [*record.related_questions, key],
        }
    )
    new_qdoc = OpenQuestionsDocument(
        questions=[updated_q if q.id == key else q for q in qdoc.questions]
    )
    new_cdoc = ChangesDocument(
        items=[updated_c if c.id == chg else c for c in cdoc.items]
    )
    write_documents(
        questions=new_qdoc,
        changes=new_cdoc,
        questions_path=questions_path,
        changes_path=changes_path,
    )
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated_q


def update_question_fields(
    question_id: str,
    *,
    question: str | None = None,
    area: str | None = None,
    notes: str | None = None,
    answer: str | None = None,
    related_todos: list[str] | None = None,
    related_changes: list[str] | None = None,
    target: dict | None | object = ...,  # type: ignore[assignment]
    clear_target: bool = False,
    render: bool = True,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    """Patch mutable fields on a question. Does not change status/resolved_at alone.

    Pass target=None with clear_target=True to remove typed target.
    Pass a QuestionTarget or dict to set target.
    """
    from music_rig.models import QuestionTarget

    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")

    data = current.model_dump()
    if question is not None:
        cleaned = question.strip()
        if not cleaned:
            raise StoreError("Question text cannot be empty.")
        data["question"] = cleaned
    if area is not None:
        cleaned_area = area.strip()
        if not cleaned_area:
            raise StoreError("Area cannot be empty.")
        data["area"] = cleaned_area
    if notes is not None:
        data["notes"] = notes
    if answer is not None:
        data["answer"] = answer
    if related_todos is not None:
        todo_ids = [t.strip().upper() for t in related_todos if t.strip()]
        known = load_todo(todo_path).task_map()
        for tid in todo_ids:
            if tid not in known:
                raise StoreError(f"Related TODO {tid} does not exist.")
        if len(todo_ids) != len(set(todo_ids)):
            raise StoreError("related_todos must not contain duplicates")
        data["related_todos"] = todo_ids
    if related_changes is not None:
        change_ids = [c.strip().upper() for c in related_changes if c.strip()]
        known_c = load_changes(changes_path).item_map()
        for cid in change_ids:
            if cid not in known_c:
                raise StoreError(f"Related change {cid} does not exist.")
        if len(change_ids) != len(set(change_ids)):
            raise StoreError("related_changes must not contain duplicates")
        data["related_changes"] = change_ids
    if clear_target:
        data["target"] = None
    elif target is not ...:
        if target is None:
            data["target"] = None
        elif isinstance(target, QuestionTarget):
            data["target"] = target.model_dump()
        elif isinstance(target, dict):
            cleaned_t = {k: v for k, v in target.items() if v not in (None, "", [])}
            if "domain" not in cleaned_t or not str(cleaned_t["domain"]).strip():
                raise StoreError("Typed target requires a domain.")
            data["target"] = QuestionTarget.model_validate(cleaned_t).model_dump()
        else:
            raise StoreError("Invalid target value.")

    # Preserve RESOLVED invariants when editing answer
    if data["status"] == QuestionStatus.RESOLVED and not str(data.get("answer") or "").strip():
        raise StoreError(f"{key} RESOLVED requires a non-empty answer.")

    updated = OpenQuestion.model_validate(data)
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(questions=new_qdoc, questions_path=questions_path)
    if render:
        render_docs(
            todo_path=todo_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated


def mark_reconciled(
    question_id: str,
    *,
    note: str = "",
    clock: Clock = default_clock,
    no_current_change: bool = False,
    render: bool = True,
    questions_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> OpenQuestion:
    """Mark a RESOLVED question as reconciled into CURRENT (or explicitly no-change).

    Does not invent answers. resolve_question never sets reconciled_at.
    """
    qdoc = load_questions(questions_path)
    key = question_id.strip().upper()
    current = qdoc.question_map().get(key)
    if current is None:
        raise StoreError(f"Question {key} does not exist.")
    if current.status != QuestionStatus.RESOLVED:
        raise StoreError(f"{key} must be RESOLVED before reconciliation.")
    if not current.answer.strip():
        raise StoreError(f"{key} RESOLVED requires a non-empty answer.")
    note_clean = note.strip()
    if no_current_change and not note_clean:
        raise StoreError(
            f"{key}: --no-current-change requires a non-empty --note."
        )
    if current.reconciled_at is not None:
        raise StoreError(f"{key} is already reconciled.")
    updated = OpenQuestion(
        **{
            **current.model_dump(),
            "reconciled_at": clock(),
            "reconciliation_note": note_clean,
        }
    )
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if q.id == key else q for q in qdoc.questions]
    )
    write_documents(questions=new_qdoc, questions_path=questions_path)
    if render:
        render_docs(
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            questions_path=questions_path,
            docs_questions=docs_questions,
            write=True,
        )
    return updated


def open_question_count(*, questions_path: Path | None = None) -> int:
    return sum(
        1
        for q in load_questions(questions_path).questions
        if q.status == QuestionStatus.OPEN
    )


def _target_dict(q: OpenQuestion) -> dict | None:
    if q.target is None:
        return None
    return {k: v for k, v in q.target.model_dump().items() if v is not None}


def answer_question(
    question_id: str,
    answer: str,
    *,
    dry_run: bool = False,
    related_change: str | None = None,
    verification_note: str | None = None,
    clock: Clock = default_clock,
    render: bool = True,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> dict:
    """FINAL answer: RESOLVED + answer + resolved_at; reconciled_at stays null.

    Does not invent verification_result. Prefer ``draft_question`` for provisional text.
    """
    cleaned = answer.strip()
    if not cleaned:
        raise StoreError("Resolved questions require a non-empty answer.")
    current = get_question(question_id, questions_path=questions_path)
    before = question_json_fields(current)
    after_note = (
        verification_note.strip()
        if verification_note is not None
        else current.verification_note
    )
    suggested = f"uv run rig reconcile plan question {current.id} --json"
    if dry_run:
        return {
            "dry_run": True,
            "question_id": current.id,
            "before": before,
            "after": {
                "id": current.id,
                "question_status": QuestionStatus.RESOLVED.value,
                "answer_state": AnswerState.FINAL.value,
                "answer": cleaned,
                "resolved_at": "(would set)",
                "reconciled_at": None,
                "verification_note": after_note,
            },
            "answer_state": AnswerState.FINAL.value,
            "question_status": QuestionStatus.RESOLVED.value,
            "resolved_at": "(would set)",
            "reconciled_at": None,
            "suggested_next_command": suggested,
            "next_command": suggested,
            "message": "Answer recorded. CURRENT reconciliation still required.",
        }
    updated = resolve_question(
        question_id,
        cleaned,
        related_change=related_change,
        verification_note=verification_note,
        clock=clock,
        render=render,
        questions_path=questions_path,
        changes_path=changes_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )
    fields = question_json_fields(updated)
    return {
        "dry_run": False,
        "question_id": updated.id,
        "before": before,
        "after": fields,
        "question": updated,
        "answer_state": fields["answer_state"],
        "question_status": fields["question_status"],
        "resolved_at": fields["resolved_at"],
        "reconciled_at": None,
        "suggested_next_command": (
            f"uv run rig reconcile plan question {updated.id} --json"
        ),
        "next_command": f"uv run rig reconcile plan question {updated.id} --json",
        "message": "Answer recorded. CURRENT reconciliation still required.",
    }


_TARGET_FIELDS = (
    "domain",
    "bay",
    "pair",
    "path",
    "gear",
    "device",
    "channel",
    "branch",
    "node",
    "context",
)


def show_target(
    question_id: str, *, questions_path: Path | None = None
) -> dict:
    q = get_question(question_id, questions_path=questions_path)
    return {
        "question_id": q.id,
        "target": _target_dict(q),
    }


def validate_target_refs(
    target: dict,
    *,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    inventory_path: Path | None = None,
) -> None:
    """Exact-ref validation via existing services. No fuzzy match."""
    from music_rig import inventory_state, patchbay_state, routing_state
    from music_rig.models import QuestionTarget

    qt = QuestionTarget.model_validate(
        {k: v for k, v in target.items() if v not in (None, "", [])}
    )
    if qt.bay:
        data = patchbay_state.load_raw(patchbays_path)
        bay_id = qt.bay.strip().upper()
        bays = data.get("patchbays") or {}
        if bay_id not in bays:
            raise StoreError(f"Patchbay {bay_id} does not exist.")
        if qt.pair:
            try:
                patchbay_state.resolve_pair(bay_id, qt.pair, data)
            except StoreError as exc:
                raise StoreError(str(exc)) from exc
    if qt.path:
        rdata = routing_state.load_raw(routing_path)
        try:
            routing_state.get_named_path(rdata, qt.path)
        except StoreError as exc:
            raise StoreError(str(exc)) from exc
    if qt.gear:
        inv = inventory_state.load_document(inventory_path)
        if inv.resolve(qt.gear) is None:
            raise StoreError(f"Gear {qt.gear!r} does not exist in inventory.")


def set_target(
    question_id: str,
    *,
    domain: str | None = None,
    bay: str | None = None,
    pair: str | None = None,
    path: str | None = None,
    gear: str | None = None,
    device: str | None = None,
    channel: str | None = None,
    branch: str | None = None,
    node: str | None = None,
    context: str | None = None,
    clear_fields: list[str] | None = None,
    dry_run: bool = False,
    render: bool = True,
    questions_path: Path | None = None,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    inventory_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> dict:
    """Merge typed target fields onto a question. Validates refs exactly."""
    from music_rig.models import QuestionTarget

    q = get_question(question_id, questions_path=questions_path)
    before = _target_dict(q)
    merged: dict = dict(before or {})
    updates = {
        "domain": domain,
        "bay": bay,
        "pair": pair,
        "path": path,
        "gear": gear,
        "device": device,
        "channel": channel,
        "branch": branch,
        "node": node,
        "context": context,
    }
    any_set = False
    for key, value in updates.items():
        if value is not None:
            merged[key] = value.strip() if isinstance(value, str) else value
            any_set = True
    for field in clear_fields or []:
        fname = field.strip().lower()
        if fname not in _TARGET_FIELDS:
            raise StoreError(f"Unknown target field {field!r}")
        merged.pop(fname, None)
        any_set = True
    if not any_set:
        raise StoreError("Provide at least one target field to set or clear.")
    if "domain" not in merged or not str(merged.get("domain") or "").strip():
        raise StoreError("Typed target requires a domain.")
    if merged.get("bay"):
        merged["bay"] = str(merged["bay"]).strip().upper()
    validate_target_refs(
        merged,
        patchbays_path=patchbays_path,
        routing_path=routing_path,
        inventory_path=inventory_path,
    )
    after = {
        k: v
        for k, v in QuestionTarget.model_validate(merged).model_dump().items()
        if v is not None
    }
    if dry_run:
        return {
            "dry_run": True,
            "question_id": q.id,
            "before": before,
            "after": after,
        }
    updated = update_question_fields(
        question_id,
        target=after,
        render=render,
        questions_path=questions_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )
    return {
        "dry_run": False,
        "question_id": updated.id,
        "before": before,
        "after": _target_dict(updated),
    }


def clear_target(
    question_id: str,
    *,
    fields: list[str] | None = None,
    dry_run: bool = False,
    render: bool = True,
    questions_path: Path | None = None,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    inventory_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> dict:
    """Clear entire target, or clear specific fields when `fields` is provided."""
    q = get_question(question_id, questions_path=questions_path)
    before = _target_dict(q)
    if fields:
        return set_target(
            question_id,
            clear_fields=fields,
            dry_run=dry_run,
            render=render,
            questions_path=questions_path,
            patchbays_path=patchbays_path,
            routing_path=routing_path,
            inventory_path=inventory_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            docs_questions=docs_questions,
        )
    if dry_run:
        return {
            "dry_run": True,
            "question_id": q.id,
            "before": before,
            "after": None,
        }
    updated = update_question_fields(
        question_id,
        clear_target=True,
        render=render,
        questions_path=questions_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )
    return {
        "dry_run": False,
        "question_id": updated.id,
        "before": before,
        "after": None,
    }
