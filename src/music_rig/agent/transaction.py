"""Transactional multi-operation agent apply.

prepare != commit. All mutating ops stage into working document copies,
conflicts and concurrency are checked, then one write_text_files batch
commits. Projection/postcondition failure rolls canonical files back.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from music_rig.agent.errors import (
    AgentError,
    ConcurrentModificationError,
    PlanConflictError,
)
from music_rig.models import QuestionStatus
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operation_registry import (
    get_spec,
    prepare_operation,
    validate_operation_shape,
)
from music_rig.reconciliation.operations import OperationMutability, RigOperation
from music_rig.reconciliation.preparers import PreparedOperation, materialize_working_docs
from music_rig.store import StoreError, write_text_files


@dataclass
class PreparedTransaction:
    prepared: list[PreparedOperation]
    payloads: list[tuple[Path, str]]  # final canonical texts
    source_hashes: dict[str, str]  # str(path) -> sha256 of original bytes
    originals: dict[str, bytes]  # str(path) -> original bytes
    finalize_plan: dict[str, Any] | None = None
    atomic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "atomic": self.atomic,
            "operations": [
                {
                    "operation_id": p.operation.operation_id,
                    "kind": p.operation.kind,
                    "touched_documents": p.touched_documents,
                    "conflict_claims": p.conflict_claims,
                    "before": p.before,
                    "after": p.after,
                    "preview_message": p.preview_message,
                }
                for p in self.prepared
            ],
            "paths": [str(p) for p, _ in self.payloads],
            "source_hashes": self.source_hashes,
            "finalize_plan": self.finalize_plan,
        }


def _file_hash(path: Path) -> str:
    if not path.exists():
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_bytes(path: Path) -> bytes:
    if not path.exists():
        return b""
    return path.read_bytes()


def prepare_transaction(
    operations: list[RigOperation],
    *,
    ctx: ReconciliationContext,
    finalize_op: RigOperation | None = None,
) -> PreparedTransaction:
    """Stage every operation; detect PLAN_CONFLICT; build commit payloads."""
    working: dict[str, Any] = {}
    claimed: dict[str, tuple[str, Any]] = {}
    prepared: list[PreparedOperation] = []
    touched_paths: set[Path] = set()

    all_ops = list(operations)
    if finalize_op is not None:
        all_ops.append(finalize_op)

    for op in all_ops:
        validate_operation_shape(op, agent=True)
        spec = get_spec(op.kind)
        if spec.mutability is OperationMutability.READ_ONLY:
            raise StoreError(f"read-only operation cannot be applied: {op.kind}")
        if not spec.supports_preparation or spec.preparer is None:
            raise StoreError(f"operation does not support preparation: {op.kind}")

        prep = prepare_operation(op, ctx, working)
        for key, value in prep.conflict_claims.items():
            if key in claimed and claimed[key][1] != value:
                other_id = claimed[key][0]
                raise PlanConflictError(
                    f"conflicting operations on {key}: {other_id} vs {op.operation_id}",
                    operation_ids=(other_id, op.operation_id),
                    conflict_key=key,
                )
            claimed[key] = (op.operation_id, value)
        prepared.append(prep)
        for doc_key in prep.touched_documents:
            path = _doc_path(doc_key, ctx)
            if path is not None:
                touched_paths.add(path)

    payloads, finalize_plan = materialize_working_docs(working, ctx, prepared)

    originals: dict[str, bytes] = {}
    source_hashes: dict[str, str] = {}
    for path, _text in payloads:
        key = str(path)
        originals[key] = _read_bytes(path)
        source_hashes[key] = _file_hash(path)
    # Also hash any path we might have touched even if text unchanged
    for path in touched_paths:
        key = str(path)
        if key not in originals:
            originals[key] = _read_bytes(path)
            source_hashes[key] = _file_hash(path)

    return PreparedTransaction(
        prepared=prepared,
        payloads=payloads,
        source_hashes=source_hashes,
        originals=originals,
        finalize_plan=finalize_plan,
    )


def _doc_path(doc_key: str, ctx: ReconciliationContext) -> Path | None:
    mapping = {
        "channels": ctx.paths.channels,
        "routing": ctx.paths.routing,
        "patchbays": ctx.paths.patchbays,
        "inventory": ctx.paths.inventory,
        "questions": ctx.paths.questions,
        "todo": ctx.paths.todo,
        "changes": ctx.paths.changes,
        "midi": ctx.paths.midi,
        "controllers": ctx.paths.controllers,
    }
    return mapping.get(doc_key)


def check_concurrency(prepared: PreparedTransaction) -> None:
    for path_str, expected in prepared.source_hashes.items():
        current = _file_hash(Path(path_str))
        if current != expected:
            raise ConcurrentModificationError(
                f"source changed underfoot: {path_str}",
            )


def rollback_canonical(prepared: PreparedTransaction) -> None:
    restore = [
        (Path(p), data.decode("utf-8") if data else "") for p, data in prepared.originals.items()
    ]
    # Only restore paths that exist in originals (may include empty new files)
    write_text_files([(path, text) for path, text in restore if path.parent.exists() or True])


def _render_projections(ctx: ReconciliationContext) -> None:
    """Refresh required projections. Planning docs are mandatory; CURRENT optional."""
    from music_rig.render import render_docs

    kwargs: dict[str, Any] = {
        "todo_path": ctx.paths.todo,
        "questions_path": ctx.paths.questions,
        "docs_todo": ctx.paths.docs_todo,
        "docs_wishlist": ctx.paths.docs_wishlist,
        "docs_questions": ctx.paths.docs_questions,
        "write": True,
    }
    if ctx.paths.docs_patchbays.exists():
        kwargs["patchbays_path"] = ctx.paths.patchbays
        kwargs["docs_patchbays"] = ctx.paths.docs_patchbays
    try:
        render_docs(**kwargs)
    except Exception as exc:
        raise StoreError(f"projection render failed: {exc}") from exc


def commit_transaction(
    prepared: PreparedTransaction,
    *,
    ctx: ReconciliationContext,
    artifact_id: str,
    require_finalize: bool = False,
) -> dict[str, Any]:
    """Commit all payloads atomically; roll back on projection/postcondition failure."""
    check_concurrency(prepared)

    try:
        write_text_files(prepared.payloads)
    except Exception as exc:
        # write_text_files already cleans temps; ensure originals intact
        try:
            rollback_canonical(prepared)
        except Exception:
            pass
        raise AgentError(
            f"canonical commit failed: {exc}",
            code="COMMIT_FAILURE",
        ) from exc

    try:
        _render_projections(ctx)
    except Exception as exc:
        rollback_canonical(prepared)
        try:
            _render_projections(ctx)
        except Exception:
            pass
        raise AgentError(
            f"projection failure after commit; rolled back: {exc}",
            code="PROJECTION_FAILURE",
        ) from exc

    post = evaluate_postconditions(
        artifact_id=artifact_id,
        ctx=ctx,
        require_finalize=require_finalize,
        finalize_plan=prepared.finalize_plan,
    )
    if not post["ok"]:
        rollback_canonical(prepared)
        try:
            _render_projections(ctx)
        except Exception:
            pass
        return {
            "ok": False,
            "rolled_back": True,
            "postconditions": post,
            "message": (
                "Postconditions failed; canonical state rolled back. Question was NOT finalized."
            ),
            "code": "POSTCONDITION_FAILURE",
        }

    return {
        "ok": True,
        "rolled_back": False,
        "postconditions": post,
        "paths_written": [str(p) for p, _ in prepared.payloads],
        "finalize_plan": prepared.finalize_plan,
        "message": "Atomic transaction committed; postconditions passed",
    }


def evaluate_postconditions(
    *,
    artifact_id: str,
    ctx: ReconciliationContext,
    require_finalize: bool = False,
    finalize_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from music_rig import question_service

    q = question_service.get_question(artifact_id, questions_path=ctx.paths.questions)
    errors: list[str] = []
    if q.status != QuestionStatus.RESOLVED:
        errors.append(f"{artifact_id} is not RESOLVED")
    if not q.answer.strip():
        errors.append(f"{artifact_id} has empty answer")
    if require_finalize or (finalize_plan and finalize_plan.get("requested")):
        if q.reconciled_at is None:
            errors.append(f"{artifact_id} reconciled_at not set after finalize")
    return {
        "ok": not errors,
        "errors": errors,
        "question_status": q.status.value,
        "reconciled_at": q.reconciled_at.isoformat() if q.reconciled_at else None,
    }
