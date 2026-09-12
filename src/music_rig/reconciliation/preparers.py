"""Prepare mutations without commit (prepare != commit).

Stages document working sets and conflict claims for agent transactions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dataclasses import dataclass, field

from music_rig.models import (
    ChangeStatus,
    OpenQuestion,
    OpenQuestionsDocument,
    QuestionStatus,
    TodoDocument,
    TodoStatus,
)
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, load_changes, load_questions, load_todo


@dataclass
class PreparedOperation:
    operation: RigOperation
    touched_documents: list[str]
    conflict_claims: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]
    preview_message: str
    postconditions: list[str] = field(default_factory=list)


def _ensure(working: dict[str, Any], key: str, loader) -> Any:
    if key not in working:
        working[key] = loader()
    return working[key]


def _preview_dict(preview) -> tuple[dict, dict, str]:
    return dict(preview.before or {}), dict(preview.after or {}), str(preview.message)


def prepare_patchbay_set_model(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import patchbay_state

    def load():
        return patchbay_state.load_raw(ctx.paths.patchbays)

    doc = _ensure(working, "patchbays", load)
    preview, new_doc = patchbay_state.propose_set_model(
        str(op.args["bay_id"]),
        str(op.args["model"]),
        data=doc,
        path=ctx.paths.patchbays,
    )
    working["patchbays"] = new_doc
    bay = str(op.args["bay_id"]).upper()
    before, after, msg = _preview_dict(preview)
    return PreparedOperation(
        operation=op,
        touched_documents=["patchbays"],
        conflict_claims={f"patchbay:{bay}:hardware_model": after.get("hardware_model")},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_patchbay_set_mode(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import patchbay_state

    def load():
        return patchbay_state.load_raw(ctx.paths.patchbays)

    doc = _ensure(working, "patchbays", load)
    preview, new_doc = patchbay_state.propose_set_mode(
        str(op.args["bay_id"]),
        str(op.args["jack_spec"]),
        str(op.args["mode"]),
        data=doc,
        path=ctx.paths.patchbays,
    )
    working["patchbays"] = new_doc
    bay = str(op.args["bay_id"]).upper()
    jack = str(op.args["jack_spec"])
    before, after, msg = _preview_dict(preview)
    return PreparedOperation(
        operation=op,
        touched_documents=["patchbays"],
        conflict_claims={f"patchbay:{bay}:{jack}:mode": after.get("mode")},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_patchbay_set_connection(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import patchbay_state

    def load():
        return patchbay_state.load_raw(ctx.paths.patchbays)

    doc = _ensure(working, "patchbays", load)
    preview, new_doc = patchbay_state.propose_set_connection(
        str(op.args["bay_id"]),
        str(op.args["jack_spec"]),
        upper_connection=op.args.get("upper_connection"),
        lower_connection=op.args.get("lower_connection"),
        data=doc,
        path=ctx.paths.patchbays,
    )
    working["patchbays"] = new_doc
    bay = str(op.args["bay_id"]).upper()
    jack = str(op.args["jack_spec"])
    before, after, msg = _preview_dict(preview)
    claim = {
        f"patchbay:{bay}:{jack}:connection": (
            after.get("upper_connection"),
            after.get("lower_connection"),
        )
    }
    return PreparedOperation(
        operation=op,
        touched_documents=["patchbays"],
        conflict_claims=claim,
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_channels_set_source(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import channel_state

    def load():
        return channel_state.load_raw(ctx.paths.channels)

    doc = _ensure(working, "channels", load)
    source = op.args.get("source")
    preview, new_doc = channel_state.propose_set_source(
        str(op.args["device"]),
        op.args["channel"],
        None if source is None else str(source),
        data=doc,
        path=ctx.paths.channels,
    )
    working["channels"] = new_doc
    before, after, msg = _preview_dict(preview)
    key = f"channel:{after.get('device')}:{after.get('channel')}:source"
    return PreparedOperation(
        operation=op,
        touched_documents=["channels"],
        conflict_claims={key: after.get("source")},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_channels_clear_source(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    args = dict(op.args)
    args["source"] = None
    cleared = RigOperation(
        namespace=op.namespace,
        action="set_source",
        args=args,
        operation_id=op.operation_id,
        description=op.description or "clear channel source",
        domain=op.domain,
    )
    return prepare_channels_set_source(cleared, ctx, working)


def _path_kwargs(op: RigOperation) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for key in ("branch", "before", "after", "label", "node", "node_token", "node_id"):
        if key in op.args and op.args[key] is not None:
            kwargs[key if key != "node_token" else "node_token"] = op.args[key]
    if op.args.get("first"):
        kwargs["first"] = True
    if op.args.get("last"):
        kwargs["last"] = True
    return kwargs


def prepare_path_move(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import routing_state

    def load():
        return routing_state.load_raw(ctx.paths.routing)

    doc = _ensure(working, "routing", load)
    kwargs = _path_kwargs(op)
    node = str(op.args.get("node") or op.args.get("node_token") or "")
    preview, new_doc = routing_state.propose_move(
        str(op.args["path_id"]),
        node,
        branch=kwargs.get("branch"),
        before=kwargs.get("before"),
        after=kwargs.get("after"),
        first=bool(kwargs.get("first")),
        last=bool(kwargs.get("last")),
        data=doc,
        routing_path=ctx.paths.routing,
    )
    working["routing"] = new_doc
    before, after, msg = _preview_dict(preview)
    pid = str(op.args["path_id"])
    claim_key = f"routing:{pid}:{after.get('branch', kwargs.get('branch', 'main'))}:order"
    return PreparedOperation(
        operation=op,
        touched_documents=["routing"],
        conflict_claims={claim_key: after.get("chain")},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_path_insert(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import routing_state

    def load():
        return routing_state.load_raw(ctx.paths.routing)

    doc = _ensure(working, "routing", load)
    kwargs = _path_kwargs(op)
    preview, new_doc = routing_state.propose_insert(
        str(op.args["path_id"]),
        str(op.args["node_id"]),
        label=op.args.get("label"),
        branch=kwargs.get("branch"),
        before=kwargs.get("before"),
        after=kwargs.get("after"),
        first=bool(kwargs.get("first")),
        last=bool(kwargs.get("last")),
        data=doc,
        routing_path=ctx.paths.routing,
    )
    working["routing"] = new_doc
    before, after, msg = _preview_dict(preview)
    pid = str(op.args["path_id"])
    nid = str(op.args["node_id"])
    return PreparedOperation(
        operation=op,
        touched_documents=["routing"],
        conflict_claims={f"routing:{pid}:node:{nid}": "present"},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_path_remove(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import routing_state

    def load():
        return routing_state.load_raw(ctx.paths.routing)

    doc = _ensure(working, "routing", load)
    node = str(op.args.get("node") or op.args.get("node_token") or "")
    preview, new_doc = routing_state.propose_remove(
        str(op.args["path_id"]),
        node,
        branch=op.args.get("branch"),
        data=doc,
        routing_path=ctx.paths.routing,
    )
    working["routing"] = new_doc
    before, after, msg = _preview_dict(preview)
    pid = str(op.args["path_id"])
    return PreparedOperation(
        operation=op,
        touched_documents=["routing"],
        conflict_claims={f"routing:{pid}:node:{node}": "absent"},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_path_set_mode(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import routing_state

    def load():
        return routing_state.load_raw(ctx.paths.routing)

    doc = _ensure(working, "routing", load)
    node = str(op.args.get("node") or op.args.get("node_token") or "")
    preview, new_doc = routing_state.propose_set_mode(
        str(op.args["path_id"]),
        node,
        str(op.args["mode"]),
        branch=op.args.get("branch"),
        data=doc,
        routing_path=ctx.paths.routing,
    )
    working["routing"] = new_doc
    before, after, msg = _preview_dict(preview)
    pid = str(op.args["path_id"])
    return PreparedOperation(
        operation=op,
        touched_documents=["routing"],
        conflict_claims={f"routing:{pid}:{node}:mode": after.get("mode")},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_path_set_evidence(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import question_service, routing_state
    from music_rig.models import MidiEvidenceStatus

    evidence = str(op.args["evidence"]).strip().upper()
    if evidence == MidiEvidenceStatus.VERIFIED.value:
        qid = op.args.get("question_id")
        if not qid:
            raise StoreError(
                "path.set_evidence VERIFIED requires question_id with verification_result"
            )
        q = question_service.get_question(str(qid), questions_path=ctx.paths.questions)
        if q.verification_result is None:
            raise StoreError(
                "path.set_evidence VERIFIED forbidden without verification_result"
            )
        outcome = q.verification_result.outcome.value
        if outcome in {"FAILED_TEST", "INCONCLUSIVE", "SKIPPED"}:
            raise StoreError(
                f"path.set_evidence VERIFIED forbidden when verification_result={outcome}"
            )

    def load():
        return routing_state.load_raw(ctx.paths.routing)

    doc = _ensure(working, "routing", load)
    preview, new_doc = routing_state.propose_set_path_evidence(
        str(op.args["path_id"]),
        evidence,
        data=doc,
        routing_path=ctx.paths.routing,
    )
    working["routing"] = new_doc
    before, after, msg = _preview_dict(preview)
    pid = str(op.args["path_id"])
    return PreparedOperation(
        operation=op,
        touched_documents=["routing"],
        conflict_claims={f"routing:{pid}:evidence": after.get("evidence")},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_gear_set_location(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    from music_rig import inventory_state

    def load():
        return inventory_state.load_raw(ctx.paths.inventory)

    doc = _ensure(working, "inventory", load)
    preview, new_doc = inventory_state.propose_set_location(
        str(op.args["gear_id"]),
        str(op.args["location"]),
        data=doc,
        inventory_path=ctx.paths.inventory,
    )
    working["inventory"] = new_doc
    before, after, msg = _preview_dict(preview)
    gid = str(op.args["gear_id"])
    return PreparedOperation(
        operation=op,
        touched_documents=["inventory"],
        conflict_claims={f"inventory:{gid}:location": after.get("location") or after},
        before=before,
        after=after,
        preview_message=msg,
    )


def prepare_finalize_manual(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    """Stage question/todo/changes finalize without writing."""
    qid = str(op.args["question_id"]).upper()
    note = str(op.args.get("note") or "agent-assisted reconciliation").strip()
    if not note:
        raise StoreError("finalize requires non-empty note")

    def load_q():
        return load_questions(ctx.paths.questions)

    def load_t():
        return load_todo(ctx.paths.todo)

    def load_c():
        return load_changes(ctx.paths.changes)

    qdoc = _ensure(working, "questions", load_q)
    if not isinstance(qdoc, OpenQuestionsDocument):
        raise StoreError("working questions must be OpenQuestionsDocument")
    q = qdoc.question_map().get(qid)
    if q is None:
        raise StoreError(f"unknown question {qid}")
    if q.status != QuestionStatus.RESOLVED or not q.answer.strip():
        raise StoreError(f"{qid} must be RESOLVED with a non-empty answer")
    if q.reconciled_at is not None:
        raise StoreError(f"{qid} is already reconciled")

    recon_note = note
    if "agent-interpreted" not in recon_note.casefold():
        recon_note = f"[agent-interpreted / manually reconciled] {recon_note}".strip()

    now = datetime.now(timezone.utc)
    updated_q = OpenQuestion(
        **{**q.model_dump(), "reconciled_at": now, "reconciliation_note": recon_note}
    )
    working["questions"] = OpenQuestionsDocument(
        questions=[updated_q if x.id == q.id else x for x in qdoc.questions]
    )

    completed: list[str] = []
    if bool(op.args.get("complete_linked_todos", True)):
        tdoc = _ensure(working, "todo", load_t)
        confirm_dod = bool(op.args.get("confirm_dod", True))
        from music_rig.reconciliation import service as recon

        new_tdoc = tdoc
        for tid in q.related_todos:
            task = new_tdoc.task_map().get(tid)
            if task and task.status not in {
                TodoStatus.DONE,
                TodoStatus.CANCELLED,
                TodoStatus.DEFERRED,
            }:
                new_tdoc = recon._complete_todo_in_doc(  # noqa: SLF001
                    new_tdoc, tid, confirm_dod=confirm_dod
                )
                completed.append(tid)
        for tid in q.related_todos:
            if tid in new_tdoc.next_session:
                task = new_tdoc.task_map().get(tid)
                if task and task.status == TodoStatus.DONE:
                    new_tdoc = TodoDocument(
                        next_session=[t for t in new_tdoc.next_session if t != tid],
                        tasks=list(new_tdoc.tasks),
                    )
        working["todo"] = new_tdoc

    applied: list[str] = []
    if bool(op.args.get("apply_linked_changes", True)):
        cdoc = _ensure(working, "changes", load_c)
        from music_rig.reconciliation import service as recon

        new_cdoc = cdoc
        for cid in q.related_changes:
            chg = new_cdoc.item_map().get(cid)
            if chg and chg.status == ChangeStatus.OPEN:
                new_cdoc = recon._apply_change_in_doc(new_cdoc, cid)  # noqa: SLF001
                applied.append(cid)
        working["changes"] = new_cdoc

    touched = ["questions"]
    if "todo" in working:
        touched.append("todo")
    if "changes" in working:
        touched.append("changes")

    return PreparedOperation(
        operation=op,
        touched_documents=touched,
        conflict_claims={f"question:{qid}:reconciled_at": "set"},
        before={"reconciled_at": None},
        after={"reconciled_at": "set", "completed_todos": completed, "applied_changes": applied},
        preview_message=f"Finalize {qid} with note; todos={completed}; changes={applied}",
        postconditions=[f"{qid} reconciled_at set"],
    )


def prepare_open_clarification(
    op: RigOperation, ctx: ReconciliationContext, working: dict[str, Any]
) -> PreparedOperation:
    """Stage a new OPEN clarification Question linked to a parent."""
    parent_id = str(op.args["parent_question_id"]).upper()
    text = str(op.args.get("clarification") or "").strip()
    if not text:
        raise StoreError("clarification text required")

    def load_q():
        return load_questions(ctx.paths.questions)

    qdoc = _ensure(working, "questions", load_q)
    assert isinstance(qdoc, OpenQuestionsDocument)
    parent = qdoc.question_map().get(parent_id)
    if parent is None:
        raise StoreError(f"unknown parent question {parent_id}")
    for q in qdoc.questions:
        if (
            q.clarifies_question == parent_id
            and q.status == QuestionStatus.OPEN
            and q.question.strip() == text
            and not q.answer.strip()
        ):
            raise StoreError(
                f"Open clarification already exists as {q.id} for {parent_id}"
            )
    area = str(op.args.get("area") or parent.area).strip() or parent.area
    new_id = qdoc.next_id()
    child = OpenQuestion(
        id=new_id,
        question=text,
        area=area,
        status=QuestionStatus.OPEN,
        related_todos=list(parent.related_todos),
        related_changes=[],
        answer="",
        notes=f"Clarifies {parent_id}",
        clarifies_question=parent_id,
        resolved_at=None,
    )
    working["questions"] = OpenQuestionsDocument(
        questions=[*qdoc.questions, child]
    )
    return PreparedOperation(
        operation=op,
        touched_documents=["questions"],
        conflict_claims={f"question:{new_id}": "create"},
        before={"parent": parent_id},
        after={"question_id": new_id, "clarifies_question": parent_id},
        preview_message=f"Open clarification {new_id} for {parent_id}",
        postconditions=[f"{new_id} exists and clarifies {parent_id}"],
    )


def materialize_working_docs(
    working: dict[str, Any],
    ctx: ReconciliationContext,
    prepared: list[PreparedOperation],
) -> tuple[list[tuple[Any, str]], dict[str, Any] | None]:
    """Serialize staged documents to (path, text) payloads."""
    from music_rig import (
        channel_state,
        inventory_state,
        patchbay_state,
        routing_state,
    )
    from music_rig.store import _dump_yaml  # noqa: SLF001

    payloads: list[tuple[Any, str]] = []
    finalize_plan: dict[str, Any] | None = None

    if "patchbays" in working:
        existing = (
            ctx.paths.patchbays.read_text(encoding="utf-8")
            if ctx.paths.patchbays.exists()
            else None
        )
        text = patchbay_state.dump_with_header(
            working["patchbays"], existing_text=existing
        )
        errors = patchbay_state.validate_patchbays_doc(working["patchbays"])
        if errors:
            raise StoreError("Patchbay validation failed: " + "; ".join(errors))
        payloads.append((ctx.paths.patchbays, text))

    if "channels" in working:
        existing = (
            ctx.paths.channels.read_text(encoding="utf-8")
            if ctx.paths.channels.exists()
            else None
        )
        errors = channel_state.validate_channel_map(working["channels"])
        if errors:
            raise StoreError("Channel map validation failed: " + "; ".join(errors))
        text = channel_state.dump_with_header(
            working["channels"], existing_text=existing
        )
        payloads.append((ctx.paths.channels, text))

    if "routing" in working:
        existing = (
            ctx.paths.routing.read_text(encoding="utf-8")
            if ctx.paths.routing.exists()
            else None
        )
        errors = routing_state.validate_routing_doc(working["routing"])
        if errors:
            raise StoreError("Routing validation failed: " + "; ".join(errors))
        text = routing_state.dump_with_header(
            working["routing"], existing_text=existing
        )
        payloads.append((ctx.paths.routing, text))

    if "inventory" in working:
        existing = (
            ctx.paths.inventory.read_text(encoding="utf-8")
            if ctx.paths.inventory.exists()
            else None
        )
        errors = inventory_state.validate_inventory_doc(working["inventory"])
        if errors:
            raise StoreError("Inventory validation failed: " + "; ".join(errors))
        text = inventory_state.dump_with_header(
            working["inventory"], existing_text=existing
        )
        payloads.append((ctx.paths.inventory, text))

    if "questions" in working:
        qdoc = working["questions"]
        assert isinstance(qdoc, OpenQuestionsDocument)
        payload = qdoc.model_dump(mode="json")
        for item in payload.get("questions", []):
            if item.get("target") is None:
                item.pop("target", None)
        payloads.append((ctx.paths.questions, _dump_yaml(payload)))
        for prep in prepared:
            if prep.operation.kind == "question.finalize_manual":
                finalize_plan = {
                    "requested": True,
                    "question_id": prep.operation.args.get("question_id"),
                    "after": prep.after,
                }

    if "todo" in working:
        tdoc = working["todo"]
        assert isinstance(tdoc, TodoDocument)
        payloads.append(
            (ctx.paths.todo, _dump_yaml(tdoc.model_dump(mode="json")))
        )

    if "changes" in working:
        from music_rig.models import ChangesDocument

        cdoc = working["changes"]
        assert isinstance(cdoc, ChangesDocument)
        payloads.append(
            (ctx.paths.changes, _dump_yaml(cdoc.model_dump(mode="json")))
        )

    return payloads, finalize_plan
