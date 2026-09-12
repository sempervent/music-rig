"""Reconciliation orchestration — queue / plan / apply / verify / finalize / sweep.

Adapters call existing CURRENT services (propose_* + commit_*). This module does
not duplicate editors. Audit trail: OpenQuestion.reconciled_at + Change/TODO status
(no separate reconciliation-log.yaml).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from music_rig import change_service, question_service, snapshot_service, todo_service
from music_rig.inbox_service import default_clock
from music_rig.models import (
    ChangeRecord,
    ChangeStatus,
    ChangesDocument,
    OpenQuestion,
    OpenQuestionsDocument,
    QuestionStatus,
    ReconciliationState,
    TodoDocument,
    TodoStatus,
    TodoTask,
)
from music_rig.reconcile import (
    build_reconcile_summary,
    format_reconcile_change,
    format_reconcile_question,
)
from music_rig.reconciliation.adapters import get_adapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    QueueItem,
    VerificationStatus,
    VerifyResult,
)
from music_rig.store import (
    StoreError,
    load_changes,
    load_questions,
    load_todo,
    write_documents,
)
from music_rig import store as store_mod

Clock = Callable[[], datetime]


def _render_planning_and_patchbay(paths: dict[str, Any]) -> None:
    """Update questions/todo/wishlist/patchbay projections without loading MIDI/controls.

    Full `render_docs` couples inventory+midi; fixture monkeypatches often break that.
    """
    from music_rig.render import (
        apply_patchbays_render,
        apply_questions_render,
        apply_todo_render,
        apply_wishlist_render,
    )
    from music_rig.store import load_wishlist

    qdoc = load_questions(paths.get("questions"))
    tdoc = load_todo(paths.get("todo"))
    wdoc = load_wishlist(None)

    q_md = paths.get("docs_questions") or store_mod.DOCS_QUESTIONS_PATH
    t_md = paths.get("docs_todo") or store_mod.DOCS_TODO_PATH
    w_md = paths.get("docs_wishlist") or store_mod.DOCS_WISHLIST_PATH
    pb_md = paths.get("docs_patchbays") or store_mod.DOCS_PATCHBAYS_PATH
    pb_path = paths.get("patchbays") or store_mod.PATCHBAYS_PATH

    if q_md.exists():
        q_md.write_text(
            apply_questions_render(q_md.read_text(encoding="utf-8"), qdoc),
            encoding="utf-8",
        )
    if t_md.exists():
        t_md.write_text(
            apply_todo_render(t_md.read_text(encoding="utf-8"), tdoc),
            encoding="utf-8",
        )
    if w_md.exists():
        w_md.write_text(
            apply_wishlist_render(w_md.read_text(encoding="utf-8"), wdoc),
            encoding="utf-8",
        )
    if pb_md.exists() and pb_path.exists():
        from music_rig import patchbay_state

        data = patchbay_state.load_raw(pb_path)
        text = pb_md.read_text(encoding="utf-8")
        if "rig:patchbays:start" in text:
            pb_md.write_text(apply_patchbays_render(text, data), encoding="utf-8")


def _default_paths(**overrides: Path | None) -> dict[str, Any]:
    """Resolve paths at call time so monkeypatched store.*_PATH is honored."""
    base = {
        "questions": store_mod.QUESTIONS_PATH,
        "changes": store_mod.CHANGES_PATH,
        "todo": store_mod.TODO_PATH,
        "patchbays": store_mod.PATCHBAYS_PATH,
        "routing": store_mod.ROUTING_PATH,
        "midi": store_mod.MIDI_PATH,
        "controllers": store_mod.CONTROLLERS_PATH,
        "ableton": store_mod.ABLETON_PATH,
        "inventory": store_mod.INVENTORY_PATH,
        "docs_todo": store_mod.DOCS_TODO_PATH,
        "docs_wishlist": store_mod.DOCS_WISHLIST_PATH,
        "docs_questions": store_mod.DOCS_QUESTIONS_PATH,
        "docs_patchbays": store_mod.DOCS_PATCHBAYS_PATH,
    }
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base


def _paths(**overrides: Path | None) -> dict[str, Any]:
    return _default_paths(**overrides)


def _adapter_for(question: OpenQuestion):
    domain = question.target.domain if question.target else None
    return get_adapter(domain)


def question_state(
    question: OpenQuestion,
    *,
    paths: dict[str, Any] | None = None,
) -> ReconciliationState:
    if question.reconciled_at is not None:
        return ReconciliationState.RECONCILED
    adapter = _adapter_for(question)
    plan = adapter.plan(question, paths=paths or {})
    return plan.state


def build_queue(
    *,
    artifact_type: str | None = None,
    state: str | None = None,
    ready: bool = False,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    todo_path: Path | None = None,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    midi_path: Path | None = None,
    controllers_path: Path | None = None,
    ableton_path: Path | None = None,
) -> list[QueueItem]:
    """Default queue: OPEN unanswered, RESOLVED unreconciled, reconcilable OPEN changes,
    TODOs linked to ready reconciliations. Excludes RECONCILED/DONE/APPLIED.
    """
    paths = _paths(
        questions=questions_path,
        changes=changes_path,
        todo=todo_path,
        patchbays=patchbays_path,
        routing=routing_path,
        midi=midi_path,
        controllers=controllers_path,
        ableton=ableton_path,
    )
    qdoc = load_questions(questions_path)
    cdoc = load_changes(changes_path)
    tdoc = load_todo(todo_path)
    items: list[QueueItem] = []
    ready_states = {
        ReconciliationState.READY_TO_APPLY,
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
    }
    state_filter = ReconciliationState(state) if state else None
    type_filter = artifact_type.strip().lower() if artifact_type else None

    for q in qdoc.questions:
        if q.reconciled_at is not None:
            continue
        if q.status == QuestionStatus.DEFERRED:
            continue
        st = question_state(q, paths=paths)
        if st == ReconciliationState.RECONCILED:
            continue
        # Include OPEN unanswered and RESOLVED unreconciled (any derived state)
        if q.status == QuestionStatus.OPEN or q.status == QuestionStatus.RESOLVED:
            if ready and st not in ready_states:
                continue
            if state_filter and st != state_filter:
                continue
            item = QueueItem(
                artifact_type="question",
                artifact_id=q.id,
                state=st,
                summary=q.question,
                capability=_adapter_for(q).capability,
                area=q.area,
                related={
                    "todos": list(q.related_todos),
                    "changes": list(q.related_changes),
                },
            )
            if type_filter in (None, "question", "questions"):
                items.append(item)

    for chg in cdoc.items:
        if chg.status != ChangeStatus.OPEN:
            continue
        # Reconcilable OPEN changes linked to questions or with likely CURRENT impact
        st = ReconciliationState.NEEDS_AGENT_ACTION
        related_q = list(chg.related_questions)
        for qid in related_q:
            q = qdoc.question_map().get(qid)
            if q and q.status == QuestionStatus.RESOLVED and q.reconciled_at is None:
                qst = question_state(q, paths=paths)
                if qst in ready_states:
                    st = ReconciliationState.READY_TO_FINALIZE
                    break
                st = qst
        if ready and st not in ready_states:
            continue
        if state_filter and st != state_filter:
            continue
        item = QueueItem(
            artifact_type="change",
            artifact_id=chg.id,
            state=st,
            summary=chg.summary,
            capability=Capability.MANUAL,
            area=chg.category.value,
            related={"questions": related_q},
        )
        if type_filter in (None, "change", "changes"):
            items.append(item)

    # TODOs linked to ready question reconciliations
    for task in tdoc.tasks:
        if task.status in {TodoStatus.DONE, TodoStatus.CANCELLED, TodoStatus.DEFERRED}:
            continue
        linked_ready = False
        linked_q: list[str] = []
        for q in qdoc.questions:
            if task.id not in q.related_todos:
                continue
            linked_q.append(q.id)
            if q.reconciled_at is not None:
                continue
            st = question_state(q, paths=paths)
            if st in ready_states | {ReconciliationState.CURRENT_MATCHES}:
                linked_ready = True
        if not linked_ready:
            continue
        st = ReconciliationState.READY_TO_FINALIZE
        if ready and st not in ready_states:
            continue
        if state_filter and st != state_filter:
            continue
        item = QueueItem(
            artifact_type="todo",
            artifact_id=task.id,
            state=st,
            summary=task.task,
            capability=Capability.MANUAL,
            area=task.area,
            related={"questions": linked_q},
        )
        if type_filter in (None, "todo", "todos"):
            items.append(item)

    return items


def show_question(
    question_id: str,
    *,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    todo_path: Path | None = None,
    **path_overrides: Path | None,
) -> dict[str, Any]:
    paths = _paths(
        questions=questions_path,
        changes=changes_path,
        todo=todo_path,
        **path_overrides,
    )
    q = question_service.get_question(question_id, questions_path=questions_path)
    adapter = _adapter_for(q)
    plan = adapter.plan(q, paths=paths)
    current = adapter.read_current(q, paths=paths)
    tdoc = load_todo(todo_path)
    cdoc = load_changes(changes_path)
    related_todos = []
    for tid in q.related_todos:
        task = tdoc.task_map().get(tid)
        related_todos.append(
            {
                "id": tid,
                "status": task.status.value if task else None,
                "in_next_session": tid in tdoc.next_session,
                "definition_of_done": task.definition_of_done if task else None,
            }
        )
    related_changes = []
    for cid in q.related_changes:
        chg = cdoc.item_map().get(cid)
        related_changes.append(
            {
                "id": cid,
                "status": chg.status.value if chg else None,
                "summary": chg.summary if chg else None,
            }
        )
    return {
        "artifact_type": "question",
        "question": q.model_dump(mode="json"),
        "state": plan.state.value,
        "capability": adapter.capability.value,
        "current": current,
        "plan": plan.to_dict(),
        "related_todos": related_todos,
        "related_changes": related_changes,
        "suggested_commands": plan.suggested_commands,
        "advisory": format_reconcile_question(
            q.id, questions_path=questions_path
        ).rstrip(),
    }


def show_change(
    change_id: str,
    *,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> dict[str, Any]:
    chg = change_service.get_change(change_id, changes_path=changes_path)
    return {
        "artifact_type": "change",
        "change": chg.model_dump(mode="json"),
        "advisory": format_reconcile_change(
            chg.id,
            changes_path=changes_path,
            questions_path=questions_path,
            todo_path=todo_path,
        ).rstrip(),
    }


def show_artifact(
    artifact_type: str,
    artifact_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    kind = artifact_type.strip().lower()
    if kind in {"question", "questions", "q"}:
        return show_question(artifact_id, **kwargs)
    if kind in {"change", "changes", "chg"}:
        return show_change(artifact_id, **kwargs)
    raise StoreError(f"Unknown artifact type {artifact_type!r}")


def plan_question(question_id: str, **kwargs: Any) -> Plan:
    paths = _paths(**{k: v for k, v in kwargs.items() if k.endswith("_path") or k in {
        "questions", "changes", "todo", "patchbays", "routing", "midi",
        "controllers", "ableton", "docs_todo", "docs_wishlist", "docs_questions",
    }})
    # Normalize kwargs into paths dict
    path_map = {
        "questions_path": "questions",
        "changes_path": "changes",
        "todo_path": "todo",
        "patchbays_path": "patchbays",
        "routing_path": "routing",
        "midi_path": "midi",
        "controllers_path": "controllers",
        "ableton_path": "ableton",
        "docs_todo": "docs_todo",
        "docs_wishlist": "docs_wishlist",
        "docs_questions": "docs_questions",
    }
    for src, dest in path_map.items():
        if src in kwargs and kwargs[src] is not None:
            paths[dest] = kwargs[src]
    q = question_service.get_question(
        question_id, questions_path=kwargs.get("questions_path")
    )
    return _adapter_for(q).plan(q, paths=paths)


def apply_question(
    question_id: str,
    *,
    dry_run: bool = False,
    yes: bool = False,
    snapshot_before: bool = False,
    clock: Clock = default_clock,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    midi_path: Path | None = None,
    controllers_path: Path | None = None,
    ableton_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    q = question_service.get_question(question_id, questions_path=questions_path)
    if q.status != QuestionStatus.RESOLVED or not q.answer.strip():
        raise StoreError(f"{q.id} must be RESOLVED with a non-empty answer to apply")
    paths = _paths(
        questions=questions_path,
        changes=changes_path,
        patchbays=patchbays_path,
        routing=routing_path,
        midi=midi_path,
        controllers=controllers_path,
        ableton=ableton_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
    )
    adapter = _adapter_for(q)
    if adapter.capability == Capability.APPLY_AND_VERIFY:
        pass
    elif adapter.capability in {
        Capability.VERIFY_ONLY,
        Capability.HUMAN_VERIFY_THEN_APPLY,
    }:
        from music_rig.reconciliation.action_packet import has_positive_observation

        if not has_positive_observation(q):
            raise StoreError(
                f"{q.id} capability is {adapter.capability.value}; "
                "apply requires verification_result CONFIRMED or CORRECTED"
            )
    else:
        raise StoreError(
            f"{q.id} capability is {adapter.capability.value}; apply not supported"
        )
    snap_info = None
    if snapshot_before and not dry_run:
        snap = snapshot_service.create_snapshot(
            clock=clock,
            root=snapshot_root,
        )
        snap_info = {"id": snap.snapshot_id}
    result = adapter.apply(q, paths=paths, dry_run=dry_run, yes=yes or dry_run)
    # After apply that changed CURRENT, state may be ready to verify
    q2 = question_service.get_question(question_id, questions_path=questions_path)
    plan = adapter.plan(q2, paths=paths)
    return {
        "question_id": q.id,
        "dry_run": dry_run,
        "snapshot": snap_info,
        "apply": result,
        "state": plan.state.value,
        "plan": plan.to_dict(),
    }


def verify_question(
    question_id: str,
    *,
    questions_path: Path | None = None,
    **path_overrides: Path | None,
) -> dict[str, Any]:
    path_map = {
        "patchbays_path": "patchbays",
        "routing_path": "routing",
        "midi_path": "midi",
        "controllers_path": "controllers",
        "ableton_path": "ableton",
        "changes_path": "changes",
    }
    paths = _paths(questions=questions_path)
    for src, dest in path_map.items():
        if src in path_overrides and path_overrides[src] is not None:
            paths[dest] = path_overrides[src]
    # also accept already-normalized keys
    for key in ("patchbays", "routing", "midi", "controllers", "ableton"):
        if key in path_overrides and path_overrides[key] is not None:
            paths[key] = path_overrides[key]
    q = question_service.get_question(question_id, questions_path=questions_path)
    adapter = _adapter_for(q)
    result = adapter.verify(q, paths=paths)
    state = question_state(q, paths=paths)
    if (
        result.status == VerificationStatus.MATCH
        and q.reconciled_at is None
        and q.status == QuestionStatus.RESOLVED
    ):
        state = ReconciliationState.READY_TO_FINALIZE
    return {
        "question_id": q.id,
        "verification": result.status.value,
        "verify": result.to_dict(),
        "state": state.value,
    }


def _complete_todo_in_doc(
    doc: TodoDocument,
    todo_id: str,
    *,
    confirm_dod: bool,
) -> TodoDocument:
    task = todo_service.get_task(doc, todo_id)
    if task.status == TodoStatus.DONE:
        # still ensure removed from next_session
        if task.id in doc.next_session:
            return TodoDocument(
                next_session=[t for t in doc.next_session if t != task.id],
                tasks=list(doc.tasks),
            )
        return doc
    if task.definition_of_done.strip() and not confirm_dod:
        raise StoreError(
            f"{todo_id} has a non-empty definition_of_done; pass --confirm-dod "
            "to complete during finalize/sweep"
        )
    updated = TodoTask.model_validate(
        {**task.model_dump(), "status": TodoStatus.DONE.value}
    )
    tasks = [updated if t.id == todo_id else t for t in doc.tasks]
    next_session = [t for t in doc.next_session if t != todo_id]
    return TodoDocument(next_session=next_session, tasks=tasks)


def _apply_change_in_doc(doc: ChangesDocument, change_id: str) -> ChangesDocument:
    items: list[ChangeRecord] = []
    found = False
    for item in doc.items:
        if item.id != change_id:
            items.append(item)
            continue
        found = True
        if item.status == ChangeStatus.APPLIED:
            items.append(item)
        else:
            items.append(
                ChangeRecord(**{**item.model_dump(), "status": ChangeStatus.APPLIED})
            )
    if not found:
        raise StoreError(f"Change {change_id} does not exist.")
    return ChangesDocument(items=items)


def finalize_question(
    question_id: str,
    *,
    dry_run: bool = False,
    yes: bool = False,
    complete_linked_todos: bool = False,
    apply_linked_changes: bool = False,
    confirm_dod: bool = False,
    no_current_change: bool = False,
    note: str = "",
    snapshot_before: bool = False,
    clock: Clock = default_clock,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    todo_path: Path | None = None,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    midi_path: Path | None = None,
    controllers_path: Path | None = None,
    ableton_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    if not yes and not dry_run:
        raise StoreError("finalize requires --yes (or --dry-run)")
    paths = _paths(
        questions=questions_path,
        changes=changes_path,
        todo=todo_path,
        patchbays=patchbays_path,
        routing=routing_path,
        midi=midi_path,
        controllers=controllers_path,
        ableton=ableton_path,
    )
    q = question_service.get_question(question_id, questions_path=questions_path)
    if q.status != QuestionStatus.RESOLVED or not q.answer.strip():
        raise StoreError(f"{q.id} must be RESOLVED with a non-empty answer")
    if q.reconciled_at is not None:
        raise StoreError(f"{q.id} is already reconciled")

    adapter = _adapter_for(q)
    verify = adapter.verify(q, paths=paths)
    note_clean = note.strip()
    if no_current_change:
        if not note_clean:
            raise StoreError("--no-current-change requires a non-empty --note")
    elif verify.status != VerificationStatus.MATCH:
        # CURRENT_MATCHES from plan also OK when verify MATCH not available but
        # plan says CURRENT_MATCHES for APPLY domains that already match
        plan = adapter.plan(q, paths=paths)
        if plan.state != ReconciliationState.CURRENT_MATCHES:
            raise StoreError(
                f"{q.id} finalize requires verify MATCH or "
                f"--no-current-change with --note (got {verify.status.value})"
            )

    snap_info = None
    if snapshot_before and not dry_run:
        snap = snapshot_service.create_snapshot(
            clock=clock,
            root=snapshot_root,
        )
        snap_info = {"id": snap.snapshot_id}

    qdoc = load_questions(questions_path)
    cdoc = load_changes(changes_path)
    tdoc = load_todo(todo_path)

    updated_q = OpenQuestion(
        **{
            **q.model_dump(),
            "reconciled_at": clock(),
            "reconciliation_note": note_clean,
        }
    )
    new_qdoc = OpenQuestionsDocument(
        questions=[updated_q if x.id == q.id else x for x in qdoc.questions]
    )
    new_cdoc = cdoc
    new_tdoc = tdoc
    completed_todos: list[str] = []
    applied_changes: list[str] = []

    if apply_linked_changes:
        for cid in q.related_changes:
            chg = cdoc.item_map().get(cid)
            if chg and chg.status == ChangeStatus.OPEN:
                new_cdoc = _apply_change_in_doc(new_cdoc, cid)
                applied_changes.append(cid)

    if complete_linked_todos:
        for tid in q.related_todos:
            task = tdoc.task_map().get(tid)
            if task and task.status not in {
                TodoStatus.DONE,
                TodoStatus.CANCELLED,
                TodoStatus.DEFERRED,
            }:
                new_tdoc = _complete_todo_in_doc(
                    new_tdoc, tid, confirm_dod=confirm_dod
                )
                completed_todos.append(tid)
        # Also strip DONE tasks still lingering in next_session for linked ids
        for tid in q.related_todos:
            if tid in new_tdoc.next_session:
                task = new_tdoc.task_map().get(tid)
                if task and task.status == TodoStatus.DONE:
                    new_tdoc = TodoDocument(
                        next_session=[t for t in new_tdoc.next_session if t != tid],
                        tasks=list(new_tdoc.tasks),
                    )

    result = {
        "question_id": q.id,
        "dry_run": dry_run,
        "reconciled_at": updated_q.reconciled_at.isoformat()
        if updated_q.reconciled_at
        else None,
        "reconciliation_note": note_clean,
        "no_current_change": no_current_change,
        "verification": verify.status.value,
        "completed_todos": completed_todos,
        "applied_changes": applied_changes,
        "snapshot": snap_info,
        "removed_from_next_session": [
            tid
            for tid in q.related_todos
            if tid in tdoc.next_session and tid not in new_tdoc.next_session
        ],
    }

    if dry_run:
        return result

    write_documents(
        questions=new_qdoc,
        changes=new_cdoc if apply_linked_changes else None,
        todo=new_tdoc if complete_linked_todos else None,
        questions_path=questions_path,
        changes_path=changes_path,
        todo_path=todo_path,
    )
    try:
        _render_planning_and_patchbay(
            _default_paths(
                questions=questions_path,
                todo=todo_path,
                patchbays=patchbays_path,
                docs_todo=docs_todo,
                docs_wishlist=docs_wishlist,
                docs_questions=docs_questions,
            )
        )
    except StoreError:
        pass
    return result


def sweep(
    *,
    dry_run: bool = True,
    yes: bool = False,
    confirm_dod: bool = False,
    clock: Clock = default_clock,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    todo_path: Path | None = None,
    patchbays_path: Path | None = None,
    routing_path: Path | None = None,
    midi_path: Path | None = None,
    controllers_path: Path | None = None,
    ableton_path: Path | None = None,
    docs_todo=None,
    docs_wishlist=None,
    docs_questions=None,
) -> dict[str, Any]:
    """Finalize CURRENT_MATCHES / READY_TO_FINALIZE only. Never answers OPEN."""
    if not dry_run and not yes:
        raise StoreError("sweep write requires --yes (default is dry-run)")
    paths = _paths(
        questions=questions_path,
        changes=changes_path,
        todo=todo_path,
        patchbays=patchbays_path,
        routing=routing_path,
        midi=midi_path,
        controllers=controllers_path,
        ableton=ableton_path,
    )
    qdoc = load_questions(questions_path)
    eligible: list[str] = []
    skipped: list[dict[str, str]] = []
    counts = {
        "ready_to_finalize": 0,
        "needs_answer": 0,
        "needs_target_metadata": 0,
        "needs_agent_action": 0,
        "blocked_by_dod": 0,
        "already_reconciled": 0,
    }
    for q in qdoc.questions:
        if q.reconciled_at is not None:
            counts["already_reconciled"] += 1
            continue
        if q.status == QuestionStatus.OPEN:
            skipped.append({"id": q.id, "reason": "OPEN — sweep never answers"})
            counts["needs_answer"] += 1
            continue
        if q.status != QuestionStatus.RESOLVED:
            continue
        from music_rig.reconciliation.action_packet import observation_blocks_success

        if observation_blocks_success(q):
            skipped.append(
                {
                    "id": q.id,
                    "reason": "FAILED_TEST — sweep must not finalize as success",
                }
            )
            counts["needs_agent_action"] += 1
            continue
        st = question_state(q, paths=paths)
        adapter = _adapter_for(q)
        verify = adapter.verify(q, paths=paths)
        plan = adapter.plan(q, paths=paths)
        if st == ReconciliationState.NEEDS_ANSWER:
            counts["needs_answer"] += 1
            skipped.append({"id": q.id, "reason": f"state {st.value}"})
            continue
        if st == ReconciliationState.NEEDS_AGENT_ACTION:
            missing_target = False
            for b in plan.blockers:
                if isinstance(b, dict) and b.get("code") == "missing_target_field":
                    missing_target = True
                    break
                if isinstance(b, str) and "target." in b and "missing" in b.lower():
                    missing_target = True
                    break
            if missing_target:
                counts["needs_target_metadata"] += 1
            else:
                counts["needs_agent_action"] += 1
            skipped.append({"id": q.id, "reason": f"state {st.value}"})
            continue
        if st in {
            ReconciliationState.CURRENT_MATCHES,
            ReconciliationState.READY_TO_FINALIZE,
        } or (
            verify.status == VerificationStatus.MATCH
            and st
            in {
                ReconciliationState.READY_TO_FINALIZE,
                ReconciliationState.CURRENT_MATCHES,
                ReconciliationState.READY_TO_APPLY,
            }
        ):
            if st == ReconciliationState.READY_TO_APPLY and verify.status != VerificationStatus.MATCH:
                skipped.append({"id": q.id, "reason": f"state {st.value}"})
                continue
            if st not in {
                ReconciliationState.CURRENT_MATCHES,
                ReconciliationState.READY_TO_FINALIZE,
            } and verify.status != VerificationStatus.MATCH:
                skipped.append({"id": q.id, "reason": f"state {st.value}"})
                continue
            if st == ReconciliationState.CURRENT_MATCHES or verify.status == VerificationStatus.MATCH:
                counts["ready_to_finalize"] += 1
                eligible.append(q.id)
            else:
                skipped.append({"id": q.id, "reason": f"state {st.value}"})
        else:
            skipped.append({"id": q.id, "reason": f"state {st.value}"})

    results = []
    for qid in eligible:
        try:
            results.append(
                finalize_question(
                    qid,
                    dry_run=dry_run,
                    yes=yes or dry_run,
                    complete_linked_todos=True,
                    apply_linked_changes=True,
                    confirm_dod=confirm_dod,
                    no_current_change=True,
                    note="sweep: CURRENT already matches / verified",
                    clock=clock,
                    questions_path=questions_path,
                    changes_path=changes_path,
                    todo_path=todo_path,
                    patchbays_path=patchbays_path,
                    routing_path=routing_path,
                    midi_path=midi_path,
                    controllers_path=controllers_path,
                    ableton_path=ableton_path,
                    docs_todo=docs_todo,
                    docs_wishlist=docs_wishlist,
                    docs_questions=docs_questions,
                )
            )
        except StoreError as exc:
            skipped.append({"id": qid, "reason": str(exc)})
            if "confirm-dod" in str(exc).lower() or "definition of done" in str(exc).lower():
                counts["blocked_by_dod"] += 1
                counts["ready_to_finalize"] = max(0, counts["ready_to_finalize"] - 1)

    suggested_next: list[str] = []
    if counts["needs_answer"]:
        suggested_next.append("uv run rig question list --open")
        suggested_next.append(
            "uv run rig question answer Q-xxx --answer \"...\" --json"
        )
    if counts["needs_target_metadata"]:
        suggested_next.append(
            "uv run rig question target set Q-xxx --pair <pair> --yes --json"
        )
        suggested_next.append("uv run rig reconcile plan question Q-xxx --json")
    if counts["ready_to_finalize"]:
        suggested_next.append(
            "uv run rig reconcile sweep --write --yes --confirm-dod --json"
        )
    if counts["needs_agent_action"]:
        suggested_next.append("uv run rig reconcile queue --state NEEDS_AGENT_ACTION --json")

    return {
        "dry_run": dry_run,
        "eligible": eligible,
        "finalized": [r["question_id"] for r in results if not dry_run],
        "would_finalize": [r["question_id"] for r in results] if dry_run else [],
        "results": results,
        "skipped": skipped,
        "counts": counts,
        "suggested_next_commands": suggested_next,
    }


def status_summary() -> str:
    return build_reconcile_summary()


def cleanup_reconciliation_issues(
    *,
    questions_path: Path | None = None,
    changes_path: Path | None = None,
    todo_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Inspect cleanup extras for reconciliation hygiene."""
    issues: list[dict[str, Any]] = []
    qdoc = load_questions(questions_path)
    cdoc = load_changes(changes_path)
    tdoc = load_todo(todo_path)
    paths = _paths(questions=questions_path, changes=changes_path, todo=todo_path)
    for q in qdoc.questions:
        if q.status == QuestionStatus.RESOLVED and q.reconciled_at is None:
            issues.append(
                {
                    "severity": "warning",
                    "code": "resolved_not_reconciled",
                    "id": q.id,
                    "detail": "RESOLVED but reconciled_at is null",
                    "suggested_commands": [
                        f"uv run rig reconcile plan question {q.id} --json",
                        f"uv run rig reconcile finalize question {q.id} --yes --json",
                    ],
                }
            )
            try:
                plan = _adapter_for(q).plan(q, paths=paths)
                if plan.state == ReconciliationState.CURRENT_MATCHES:
                    issues.append(
                        {
                            "severity": "info",
                            "code": "current_matches",
                            "id": q.id,
                            "detail": "CURRENT already matches answer — ready to finalize",
                            "suggested_commands": [
                                f"uv run rig reconcile finalize question {q.id} "
                                f"--yes --no-current-change --note \"matches\" --json"
                            ],
                        }
                    )
                for b in plan.blockers:
                    if isinstance(b, dict) and b.get("code") == "missing_target_field":
                        issues.append(
                            {
                                "severity": "warning",
                                "code": "missing_target_field",
                                "id": q.id,
                                "field": b.get("field"),
                                "detail": b.get("message") or "missing target field",
                                "candidates": b.get("candidates") or [],
                                "suggested_commands": b.get("suggested_commands") or [],
                            }
                        )
            except Exception:
                pass
        if q.reconciled_at is not None:
            for cid in q.related_changes:
                chg = cdoc.item_map().get(cid)
                if chg and chg.status == ChangeStatus.OPEN:
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "reconciled_open_change",
                            "id": q.id,
                            "detail": f"reconciled but linked change {cid} still OPEN",
                            "suggested_commands": [
                                f"uv run rig changes apply {cid} --yes"
                            ],
                        }
                    )
            for tid in q.related_todos:
                task = tdoc.task_map().get(tid)
                if task and task.status not in {
                    TodoStatus.DONE,
                    TodoStatus.CANCELLED,
                    TodoStatus.DEFERRED,
                }:
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "reconciled_unfinished_todo",
                            "id": q.id,
                            "detail": f"reconciled but linked TODO {tid} is {task.status.value}",
                            "suggested_commands": [f"uv run rig todo done {tid}"],
                        }
                    )
        # Incomplete targets on OPEN questions (RESOLVED covered via plan blockers above)
        if q.status == QuestionStatus.OPEN and q.reconciled_at is None:
            if q.target and q.target.domain == "patchbay.mode" and q.target.bay and not q.target.pair:
                from music_rig import patchbay_state

                try:
                    pairs = patchbay_state.list_pairs(q.target.bay, paths.get("patchbays"))
                    candidates = [
                        (
                            f"{p['upper_n']}/{p['lower_n']}"
                            if p["lower_n"] is not None
                            else str(p["upper_n"])
                        )
                        for p in pairs
                    ]
                except Exception:
                    candidates = []
                issues.append(
                    {
                        "severity": "warning",
                        "code": "missing_target_field",
                        "id": q.id,
                        "field": "pair",
                        "detail": "patchbay.mode target missing pair",
                        "candidates": candidates,
                        "suggested_commands": [
                            f"uv run rig question target set {q.id} --pair {c} --yes"
                            for c in candidates[:5]
                        ],
                    }
                )
    for tid in tdoc.next_session:
        task = tdoc.task_map().get(tid)
        if task and task.status == TodoStatus.DONE:
            issues.append(
                {
                    "severity": "error",
                    "code": "done_in_next_session",
                    "id": tid,
                    "detail": "DONE TODO still listed in next_session",
                    "suggested_commands": [
                        f"uv run rig todo next remove {tid}"
                    ],
                }
            )
    return issues
