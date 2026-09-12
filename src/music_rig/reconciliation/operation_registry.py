"""Typed action registry — allowlisted RigOperation specs + prepare/dispatch.

Maps operation kinds to preparers and executors. Not presentation, not path assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from music_rig.reconciliation.preparers import (
    PreparedOperation,
    materialize_working_docs,
    prepare_channels_clear_source,
    prepare_channels_set_source,
    prepare_finalize_manual,
    prepare_gear_set_location,
    prepare_open_clarification,
    prepare_patchbay_set_connection,
    prepare_patchbay_set_mode,
    prepare_patchbay_set_model,
    prepare_path_insert,
    prepare_path_move,
    prepare_path_remove,
    prepare_path_set_evidence,
    prepare_path_set_mode,
)
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operations import OperationMutability, RigOperation
from music_rig.store import StoreError

Dispatcher = Callable[[RigOperation, ReconciliationContext, bool], dict[str, Any]]
Preparer = Callable[
    [RigOperation, ReconciliationContext, dict[str, Any]], PreparedOperation
]


@dataclass(frozen=True, slots=True)
class OperationSpec:
    kind: str
    namespace: str
    action: str
    mutability: OperationMutability
    required_args: tuple[str, ...]
    optional_args: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    agent_allowed: bool = True
    requires_confirmation: bool = True
    supports_dry_run: bool = True
    supports_preparation: bool = True
    autonomous_safe: bool = False
    requires_human_verification: bool = False
    documents_touched: tuple[str, ...] = ()
    description: str = ""
    dispatcher: Dispatcher | None = field(default=None, hash=False, compare=False)
    preparer: Preparer | None = field(default=None, hash=False, compare=False)

    def capability_row(self) -> dict[str, Any]:
        return {
            "operation": self.kind,
            "domain": list(self.domains) or ["*"],
            "read_write": (
                "read" if self.mutability is OperationMutability.READ_ONLY else "write"
            ),
            "autonomous_safe": self.autonomous_safe,
            "requires_verification": self.requires_human_verification,
            "transaction_support": self.supports_preparation and self.preparer is not None,
            "documents_touched": list(self.documents_touched),
            "agent_allowed": self.agent_allowed,
            "description": self.description,
        }


def _preview_result(op: RigOperation, preview) -> dict[str, Any]:
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


def _dispatch_via_prepare(
    op: RigOperation, ctx: ReconciliationContext, dry_run: bool
) -> dict[str, Any]:
    """Single-op path: prepare + optional transactional commit of one op."""
    from music_rig.agent.transaction import commit_transaction, prepare_transaction

    if dry_run:
        working: dict[str, Any] = {}
        prep = prepare_operation(op, ctx, working)
        return {
            "dry_run": True,
            "kind": op.kind,
            "preview": {
                "before": prep.before,
                "after": prep.after,
                "message": prep.preview_message,
                "touched_documents": prep.touched_documents,
            },
        }
    prepared = prepare_transaction([op], ctx=ctx)
    result = commit_transaction(
        prepared,
        ctx=ctx,
        artifact_id=str(op.args.get("question_id") or "Q-000"),
        require_finalize=op.kind == "question.finalize_manual",
    )
    return {"dry_run": False, "kind": op.kind, **result}


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
    routing_domains = ("routing.verify", "Routing", "Capture", "channels")
    patchbay_domains = ("inventory.patchbay_mapping", "patchbay.mode", "Patchbay")

    _register(
        OperationSpec(
            kind="patchbay.set_model",
            namespace="patchbay",
            action="set_model",
            mutability=OperationMutability.MUTATING,
            required_args=("bay_id", "model"),
            optional_args=("question_id", "yes"),
            domains=patchbay_domains,
            documents_touched=("patchbays",),
            autonomous_safe=True,
            description="Set patchbay hardware_model (model-level, not unit id)",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_patchbay_set_model,
        )
    )
    _register(
        OperationSpec(
            kind="patchbay.set_mode",
            namespace="patchbay",
            action="set_mode",
            mutability=OperationMutability.MUTATING,
            required_args=("bay_id", "jack_spec", "mode"),
            optional_args=("question_id", "yes"),
            domains=patchbay_domains,
            documents_touched=("patchbays",),
            autonomous_safe=True,
            description="Set patchbay pair mode",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_patchbay_set_mode,
        )
    )
    _register(
        OperationSpec(
            kind="patchbay.set_connection",
            namespace="patchbay",
            action="set_connection",
            mutability=OperationMutability.MUTATING,
            required_args=("bay_id", "jack_spec"),
            optional_args=("upper_connection", "lower_connection", "question_id", "yes"),
            domains=patchbay_domains,
            documents_touched=("patchbays",),
            autonomous_safe=True,
            description="Set existing pair connections (no arbitrary pair creation)",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_patchbay_set_connection,
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
            domains=routing_domains,
            documents_touched=("channels",),
            autonomous_safe=True,
            description="Set channel map source label",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_channels_set_source,
        )
    )
    _register(
        OperationSpec(
            kind="channels.clear_source",
            namespace="channels",
            action="clear_source",
            mutability=OperationMutability.MUTATING,
            required_args=("device", "channel"),
            optional_args=("question_id", "yes"),
            domains=routing_domains,
            documents_touched=("channels",),
            autonomous_safe=True,
            description="Clear channel source (status → UNASSIGNED)",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_channels_clear_source,
        )
    )
    for kind, action, required, preparer, desc, auto, verify in [
        (
            "path.move",
            "move",
            ("path_id", "node"),
            prepare_path_move,
            "Move a routing path node",
            True,
            False,
        ),
        (
            "path.insert",
            "insert",
            ("path_id", "node_id"),
            prepare_path_insert,
            "Insert a node on a routing path",
            True,
            False,
        ),
        (
            "path.remove",
            "remove",
            ("path_id", "node"),
            prepare_path_remove,
            "Remove a node from a routing path",
            True,
            False,
        ),
        (
            "path.set_mode",
            "set_mode",
            ("path_id", "node", "mode"),
            prepare_path_set_mode,
            "Set routing node mode",
            True,
            False,
        ),
        (
            "path.set_evidence",
            "set_evidence",
            ("path_id", "evidence"),
            prepare_path_set_evidence,
            "Set path evidence (VERIFIED requires verification_result)",
            False,
            True,
        ),
    ]:
        optional = ("branch", "before", "after", "first", "last", "label", "question_id", "yes")
        _register(
            OperationSpec(
                kind=kind,
                namespace="path",
                action=action,
                mutability=OperationMutability.MUTATING,
                required_args=required,
                optional_args=optional,
                domains=routing_domains,
                documents_touched=("routing",),
                autonomous_safe=auto,
                requires_human_verification=verify,
                description=desc,
                dispatcher=_dispatch_via_prepare,
                preparer=preparer,
            )
        )
    _register(
        OperationSpec(
            kind="gear.set_location",
            namespace="gear",
            action="set_location",
            mutability=OperationMutability.MUTATING,
            required_args=("gear_id", "location"),
            optional_args=("question_id", "yes"),
            domains=("Inventory", "inventory.location", "Patchbay"),
            documents_touched=("inventory",),
            autonomous_safe=True,
            description="Set inventory gear location",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_gear_set_location,
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
            documents_touched=("questions", "todo", "changes"),
            autonomous_safe=False,
            description="Finalize AFTER CURRENT matches (confirm-current-reconciled)",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_finalize_manual,
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
            agent_allowed=False,
            supports_preparation=False,
            description="Promote/resolve question answer (not agent-allowed)",
            dispatcher=None,
            preparer=None,
        )
    )
    _register(
        OperationSpec(
            kind="question.open_clarification",
            namespace="question",
            action="open_clarification",
            mutability=OperationMutability.MUTATING,
            required_args=("parent_question_id", "clarification"),
            optional_args=("area",),
            domains=(),
            documents_touched=("questions",),
            autonomous_safe=True,
            agent_allowed=True,
            description="Open a linked clarification Question (human work; no CURRENT)",
            dispatcher=_dispatch_via_prepare,
            preparer=prepare_open_clarification,
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
            supports_preparation=False,
            description="Read question JSON",
            dispatcher=_dispatch_inspect_question,
            preparer=None,
        )
    )
    _register(
        OperationSpec(
            kind="inspect.patchbay",
            namespace="inspect",
            action="patchbay",
            mutability=OperationMutability.READ_ONLY,
            required_args=("bay_id",),
            domains=patchbay_domains,
            requires_confirmation=False,
            supports_preparation=False,
            description="Read one patchbay bay",
            dispatcher=_dispatch_inspect_patchbay,
            preparer=None,
        )
    )


def reset_registry_for_tests() -> None:
    """Test helper — clear singleton so bootstrap re-runs after code reload."""
    _REGISTRY.clear()


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
    # path.set_evidence uses evidence as required arg — allow that key only there
    for key in op.args:
        fold = key.casefold()
        if fold in forbidden and not (
            op.kind == "path.set_evidence" and fold == "evidence"
        ):
            raise StoreError(f"forbidden argument {key!r} on {op.kind}")
        if fold == "evidence" and op.kind != "path.set_evidence":
            if str(op.args[key]).casefold() == "verified":
                raise StoreError("agent must not set evidence=VERIFIED directly")
        if "verified" == fold and op.kind != "path.set_evidence":
            raise StoreError(f"forbidden argument {key!r} on {op.kind}")


def prepare_operation(
    op: RigOperation,
    ctx: ReconciliationContext,
    working: dict[str, Any],
) -> PreparedOperation:
    validate_operation_shape(op, agent=True)
    spec = get_spec(op.kind)
    if spec.preparer is None:
        raise StoreError(f"no preparer registered for {op.kind}")
    return spec.preparer(op, ctx, working)


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


__all__ = [
    "OperationSpec",
    "allowlisted_kinds",
    "dispatch_operation",
    "get_spec",
    "list_operations",
    "materialize_working_docs",
    "prepare_operation",
    "reset_registry_for_tests",
    "validate_operation_shape",
]
