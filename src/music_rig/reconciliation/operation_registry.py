"""Allowlisted RigOperation registry + service dispatchers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operations import OperationMutability, RigOperation
from music_rig.store import StoreError

Dispatcher = Callable[[RigOperation, ReconciliationContext, bool], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class OperationSpec:
    kind: str
    namespace: str
    action: str
    mutability: OperationMutability
    required_args: tuple[str, ...]
    optional_args: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()  # empty = any agent-allowed domain relation
    agent_allowed: bool = True
    requires_confirmation: bool = True
    supports_dry_run: bool = True
    description: str = ""
    dispatcher: Dispatcher | None = field(default=None, hash=False, compare=False)


def _dispatch_patchbay_set_model(
    op: RigOperation, ctx: ReconciliationContext, dry_run: bool
) -> dict[str, Any]:
    from music_rig import current_service, patchbay_state

    bay_id = str(op.args["bay_id"])
    model = str(op.args["model"])
    question_id = op.args.get("question_id")
    preview, doc = patchbay_state.propose_set_model(
        bay_id, model, path=ctx.paths.patchbays
    )
    if dry_run:
        return {
            "dry_run": True,
            "kind": op.kind,
            "preview": {
                "domain": preview.domain,
                "target": preview.target,
                "before": preview.before,
                "after": preview.after,
                "changed": preview.changed,
                "message": preview.message,
            },
        }
    result = current_service.commit_patchbay(
        doc,
        preview,
        dry_run=False,
        question_id=str(question_id) if question_id else None,
        patchbays_path=ctx.paths.patchbays,
        questions_path=ctx.paths.questions,
        docs_questions=ctx.paths.docs_questions,
        docs_todo=ctx.paths.docs_todo,
        docs_wishlist=ctx.paths.docs_wishlist,
        render=True,
    )
    return {
        "dry_run": False,
        "kind": op.kind,
        "message": result.message,
        "changed": result.changed,
    }


def _dispatch_finalize_manual(
    op: RigOperation, ctx: ReconciliationContext, dry_run: bool
) -> dict[str, Any]:
    from music_rig.reconciliation import service as recon

    qid = str(op.args["question_id"])
    note = str(op.args.get("note") or "agent-assisted reconciliation")
    return recon.finalize_question(
        qid,
        dry_run=dry_run,
        yes=not dry_run,
        confirm_current_reconciled=True,
        complete_linked_todos=bool(op.args.get("complete_linked_todos", True)),
        apply_linked_changes=bool(op.args.get("apply_linked_changes", True)),
        confirm_dod=bool(op.args.get("confirm_dod", True)),
        note=note,
        questions_path=ctx.paths.questions,
        changes_path=ctx.paths.changes,
        todo_path=ctx.paths.todo,
        patchbays_path=ctx.paths.patchbays,
        routing_path=ctx.paths.routing,
        midi_path=ctx.paths.midi,
        controllers_path=ctx.paths.controllers,
        ableton_path=ctx.paths.ableton,
        docs_todo=ctx.paths.docs_todo,
        docs_wishlist=ctx.paths.docs_wishlist,
        docs_questions=ctx.paths.docs_questions,
    )


def _dispatch_channels_set_source(
    op: RigOperation, ctx: ReconciliationContext, dry_run: bool
) -> dict[str, Any]:
    from music_rig import channel_state, current_service

    device = str(op.args["device"])
    channel = op.args["channel"]
    source = str(op.args["source"])
    question_id = op.args.get("question_id")
    preview, doc = channel_state.propose_set_source(
        device, channel, source, path=ctx.paths.channels
    )
    if dry_run:
        return {
            "dry_run": True,
            "kind": op.kind,
            "preview": {
                "domain": preview.domain,
                "target": preview.target,
                "before": preview.before,
                "after": preview.after,
                "changed": preview.changed,
                "message": preview.message,
            },
        }
    result = current_service.commit_channel(
        doc,
        preview,
        dry_run=False,
        question_id=str(question_id) if question_id else None,
        channel_map_path=ctx.paths.channels,
        questions_path=ctx.paths.questions,
        docs_questions=ctx.paths.docs_questions,
        docs_todo=ctx.paths.docs_todo,
        docs_wishlist=ctx.paths.docs_wishlist,
        render=True,
    )
    return {
        "dry_run": False,
        "kind": op.kind,
        "message": result.message,
        "changed": result.changed,
    }


def _dispatch_inspect_question(
    op: RigOperation, ctx: ReconciliationContext, dry_run: bool
) -> dict[str, Any]:
    from music_rig import question_service

    q = question_service.get_question(
        str(op.args["question_id"]), questions_path=ctx.paths.questions
    )
    return {
        "dry_run": True,
        "kind": op.kind,
        "question": question_service.question_json_fields(q),
    }


def _dispatch_inspect_patchbay(
    op: RigOperation, ctx: ReconciliationContext, dry_run: bool
) -> dict[str, Any]:
    from music_rig import patchbay_state

    data = patchbay_state.load_raw(ctx.paths.patchbays)
    bay = str(op.args["bay_id"])
    body = (data.get("patchbays") or {}).get(bay)
    return {"dry_run": True, "kind": op.kind, "bay_id": bay, "current": body}


_REGISTRY: dict[str, OperationSpec] = {}


def _register(spec: OperationSpec) -> None:
    _REGISTRY[spec.kind] = spec


def _bootstrap() -> None:
    if _REGISTRY:
        return
    _register(
        OperationSpec(
            kind="patchbay.set_model",
            namespace="patchbay",
            action="set_model",
            mutability=OperationMutability.MUTATING,
            required_args=("bay_id", "model"),
            optional_args=("question_id", "yes"),
            domains=("inventory.patchbay_mapping", "patchbay.mode", "Patchbay"),
            description="Set patchbay hardware_model (model-level, not unit id)",
            dispatcher=_dispatch_patchbay_set_model,
        )
    )
    _register(
        OperationSpec(
            kind="channels.set_source",
            namespace="channels",
            action="set_source",
            mutability=OperationMutability.MUTATING,
            required_args=("device", "channel", "source"),
            optional_args=("question_id", "yes"),
            domains=("routing.verify", "channels", "Routing", "Capture"),
            description="Set channel map source label",
            dispatcher=_dispatch_channels_set_source,
        )
    )
    _register(
        OperationSpec(
            kind="question.finalize_manual",
            namespace="question",
            action="finalize_manual",
            mutability=OperationMutability.MUTATING,
            required_args=("question_id",),
            optional_args=(
                "note",
                "complete_linked_todos",
                "apply_linked_changes",
                "confirm_dod",
            ),
            domains=(),
            description="Finalize AFTER CURRENT matches (confirm-current-reconciled)",
            dispatcher=_dispatch_finalize_manual,
        )
    )
    _register(
        OperationSpec(
            kind="question.resolve",
            namespace="question",
            action="resolve",
            mutability=OperationMutability.MUTATING,
            required_args=("question_id",),
            optional_args=("answer",),
            agent_allowed=False,  # humans answer; agents must not invent answers
            description="Promote/resolve question answer (not agent-allowed)",
            dispatcher=None,
        )
    )
    _register(
        OperationSpec(
            kind="inspect.question",
            namespace="inspect",
            action="question",
            mutability=OperationMutability.READ_ONLY,
            required_args=("question_id",),
            domains=(),
            requires_confirmation=False,
            supports_dry_run=True,
            description="Read question JSON",
            dispatcher=_dispatch_inspect_question,
        )
    )
    _register(
        OperationSpec(
            kind="inspect.patchbay",
            namespace="inspect",
            action="patchbay",
            mutability=OperationMutability.READ_ONLY,
            required_args=("bay_id",),
            domains=("inventory.patchbay_mapping", "patchbay.mode", "Patchbay"),
            requires_confirmation=False,
            description="Read one patchbay bay",
            dispatcher=_dispatch_inspect_patchbay,
        )
    )


def list_operations(*, agent_only: bool = False) -> list[OperationSpec]:
    _bootstrap()
    specs = list(_REGISTRY.values())
    if agent_only:
        specs = [s for s in specs if s.agent_allowed]
    return sorted(specs, key=lambda s: s.kind)


def get_spec(kind: str) -> OperationSpec:
    _bootstrap()
    if kind not in _REGISTRY:
        raise StoreError(f"unregistered RigOperation: {kind}")
    return _REGISTRY[kind]


def validate_operation_shape(op: RigOperation, *, agent: bool = True) -> None:
    spec = get_spec(op.kind)
    if agent and not spec.agent_allowed:
        raise StoreError(f"operation not agent-allowed: {op.kind}")
    missing = [a for a in spec.required_args if a not in op.args]
    if missing:
        raise StoreError(f"{op.kind} missing required args: {missing}")
    forbidden = {
        "shell",
        "python",
        "sql",
        "yaml_patch",
        "file_write",
        "command",
        "evidence",
        "verified",
    }
    for key in op.args:
        if key.casefold() in forbidden:
            raise StoreError(f"forbidden argument {key!r} on {op.kind}")
        if "evidence" in key.casefold() and str(op.args[key]).casefold() == "verified":
            raise StoreError("agent must not set evidence=VERIFIED directly")


def dispatch_operation(
    op: RigOperation,
    ctx: ReconciliationContext,
    *,
    dry_run: bool = True,
    agent: bool = True,
) -> dict[str, Any]:
    validate_operation_shape(op, agent=agent)
    spec = get_spec(op.kind)
    if spec.dispatcher is None:
        raise StoreError(f"no dispatcher registered for {op.kind}")
    return spec.dispatcher(op, ctx, dry_run)


def allowlisted_kinds(*, agent_only: bool = True) -> list[str]:
    return [s.kind for s in list_operations(agent_only=agent_only)]
