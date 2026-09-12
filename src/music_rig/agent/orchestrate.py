"""Autonomous agent reconcile orchestration (plan-first)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from music_rig.agent import audit
from music_rig.agent.errors import (
    AgentError,
    PlanConflictError,
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from music_rig.agent.inspection import InspectionRequest, execute_inspection
from music_rig.agent.provider import (
    AgentTurnKind,
    TurnProvider,
    load_agent_local_config,
    resolve_provider,
)
from music_rig.agent.transaction import (
    commit_transaction,
    prepare_transaction,
)
from music_rig.local_config import load_local_config
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operation_registry import get_spec
from music_rig.reconciliation.operation_renderer import operation_json_view, render_human
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError


class AutonomyLevel(str, Enum):
    PLAN_ONLY = "PLAN_ONLY"
    APPLY_SAFE = "APPLY_SAFE"
    APPLY_AND_FINALIZE = "APPLY_AND_FINALIZE"


def _proposal_from_turn(turn_proposal: dict[str, Any], artifact_id: str):
    from music_rig.agent import AgentReconciliationProposal, ProposalStatus

    raw = dict(turn_proposal)
    raw.setdefault("artifact_id", artifact_id)
    raw.setdefault("status", ProposalStatus.READY.value)
    return AgentReconciliationProposal.from_dict(raw)


def run_provider_loop(
    packet: dict[str, Any],
    *,
    ctx: ReconciliationContext,
    provider: TurnProvider,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    """Iterate provider turns until READY / clarification / no-safe-plan / limit."""
    agent_cfg = load_agent_local_config()
    limit = max_rounds or agent_cfg.max_context_rounds
    context: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    seen_requests: set[str] = set()

    for round_idx in range(limit + 1):
        if round_idx >= limit:
            return {
                "ok": False,
                "status": AgentTurnKind.NO_SAFE_PLAN.value,
                "reason": "context_round_limit",
                "turns": turns,
                "context": context,
                "proposal": None,
            }
        turn, diag = provider.run_turn(packet=packet, context=context)
        turns.append({"turn": turn.to_dict(), "diagnostics": diag})

        if turn.kind is AgentTurnKind.NEEDS_MORE_CONTEXT:
            inspection_reqs = (
                turn.inspection_as_requests()
                if hasattr(turn, "inspection_as_requests")
                else []
            )
            if not inspection_reqs:
                # dataclass-era fallback
                from music_rig.agent.inspection import InspectionRequest

                inspection_reqs = [
                    InspectionRequest.from_dict(r.to_dict() if hasattr(r, "to_dict") else r)
                    if not isinstance(r, InspectionRequest)
                    else r
                    for r in getattr(turn, "inspection_requests", []) or []
                ]
            if not inspection_reqs:
                return {
                    "ok": False,
                    "status": AgentTurnKind.NO_SAFE_PLAN.value,
                    "reason": "empty_context_request",
                    "turns": turns,
                    "context": context,
                    "proposal": None,
                }
            fingerprints = [r.fingerprint() for r in inspection_reqs]
            if all(fp in seen_requests for fp in fingerprints):
                return {
                    "ok": False,
                    "status": AgentTurnKind.NO_SAFE_PLAN.value,
                    "reason": "duplicate_context_request",
                    "turns": turns,
                    "context": context,
                    "proposal": None,
                }
            for req in inspection_reqs:
                fp = req.fingerprint()
                seen_requests.add(fp)
                result = execute_inspection(req, ctx=ctx)
                context.append({"request": req.to_dict(), "result": result})
            continue

        if turn.kind is AgentTurnKind.NEEDS_HUMAN_CLARIFICATION:
            return {
                "ok": True,
                "status": turn.kind.value,
                "clarification_questions": turn.clarification_questions,
                "rationale": turn.rationale,
                "turns": turns,
                "context": context,
                "proposal": None,
                "writes": False,
            }

        if turn.kind is AgentTurnKind.NO_SAFE_PLAN:
            return {
                "ok": False,
                "status": turn.kind.value,
                "reason": turn.reason or turn.rationale,
                "turns": turns,
                "context": context,
                "proposal": None,
            }

        if turn.kind is AgentTurnKind.READY:
            if not turn.proposal:
                return {
                    "ok": False,
                    "status": AgentTurnKind.NO_SAFE_PLAN.value,
                    "reason": "ready_without_proposal",
                    "turns": turns,
                    "context": context,
                    "proposal": None,
                }
            artifact_id = str(packet.get("artifact", {}).get("id") or "")
            proposal = _proposal_from_turn(turn.proposal, artifact_id)
            return {
                "ok": True,
                "status": AgentTurnKind.READY.value,
                "turns": turns,
                "context": context,
                "proposal": proposal,
                "rationale": turn.rationale,
            }

        return {
            "ok": False,
            "status": AgentTurnKind.NO_SAFE_PLAN.value,
            "reason": f"unknown_turn_kind:{turn.kind}",
            "turns": turns,
            "context": context,
            "proposal": None,
        }

    return {
        "ok": False,
        "status": AgentTurnKind.NO_SAFE_PLAN.value,
        "reason": "context_round_limit",
        "turns": turns,
        "context": context,
        "proposal": None,
    }


def format_plan_review(
    *,
    question_id: str,
    human_answer: str,
    rationale: str,
    operations: list[RigOperation],
    postconditions: list[Any],
    finalize: bool,
    atomic: bool = True,
    provider_label: str | None = None,
) -> str:
    lines = [
        "RECONCILIATION PLAN",
        "",
        f"Question: {question_id}",
    ]
    if provider_label:
        lines.append(f"Planner: {provider_label}")
    lines.extend(
        [
            "",
            "Human answer:",
            human_answer or "(empty)",
            "",
            "Interpretation:",
            rationale or "(none)",
            "",
            "Proposed updates:",
        ]
    )
    if not operations:
        lines.append("(none)")
    for i, op in enumerate(operations, 1):
        lines.append(f"{i}. {_human_op_line(op)}")
    lines.append("")
    lines.append("Postconditions:")
    if postconditions:
        for p in postconditions:
            lines.append(f"- {p}")
    else:
        lines.append("- question remains RESOLVED; answer non-empty")
    lines.append("")
    lines.append("After successful apply:")
    lines.append(
        f"{question_id} → RECONCILED"
        if finalize
        else f"{question_id} → (finalize not requested)"
    )
    lines.append("")
    lines.append(f"Atomic transaction: {'YES' if atomic else 'NO'}")
    lines.append("")
    lines.append("No changes have been written.")
    lines.append("")
    lines.append("Details (operation kinds):")
    for op in operations:
        lines.append(f"- {op.kind} ({op.operation_id})")
    return "\n".join(lines)


def _human_op_line(op: RigOperation) -> str:
    args = op.args
    if op.kind == "patchbay.set_model":
        return f"Update {args.get('bay_id')} model → {args.get('model')}"
    if op.kind == "patchbay.set_mode":
        return f"Set {args.get('bay_id')} {args.get('jack_spec')} mode → {args.get('mode')}"
    if op.kind == "channels.set_source":
        return (
            f"Set {args.get('device')} channel {args.get('channel')} "
            f"source → {args.get('source')}"
        )
    if op.kind == "channels.clear_source":
        return f"Clear {args.get('device')} channel {args.get('channel')} source"
    if op.kind == "path.move":
        return f"Move node {args.get('node')} on path {args.get('path_id')}"
    if op.kind == "path.insert":
        return f"Insert node {args.get('node_id')} on path {args.get('path_id')}"
    if op.kind == "path.remove":
        return f"Remove node {args.get('node')} from path {args.get('path_id')}"
    if op.kind == "path.set_mode":
        return f"Set path {args.get('path_id')} node {args.get('node')} mode → {args.get('mode')}"
    if op.kind == "gear.set_location":
        return f"Set gear {args.get('gear_id')} location → {args.get('location')}"
    if op.kind == "question.finalize_manual":
        return f"Finalize {args.get('question_id')}"
    return render_human(op)


def autonomous_reconcile(
    question_id: str,
    *,
    ctx: ReconciliationContext | None = None,
    autonomy: AutonomyLevel = AutonomyLevel.PLAN_ONLY,
    apply: bool = False,
    yes: bool = False,
    dry_run: bool = True,
    provider: TurnProvider | None = None,
    provider_name: str | None = None,
    ollama_model: str | None = None,
    root=None,
) -> dict[str, Any]:
    """Provider loop → validate → prepare transaction → optional apply."""
    from music_rig.agent import (
        build_agent_packet,
        validate_proposal,
    )

    ctx = ctx or ReconciliationContext.default()
    qid = question_id.upper()
    packet = build_agent_packet(qid, ctx=ctx)
    run_id = audit.new_run_id()

    try:
        prov = provider or resolve_provider(
            root=root,
            provider=provider_name,
            ollama_model=ollama_model,
            allow_fallback=provider_name is None,
        )
    except ProviderNotConfiguredError as exc:
        return {
            "ok": False,
            "provider_configured": False,
            "artifact_id": qid,
            "packet_hash": packet.get("packet_hash"),
            "message": str(exc),
            "setup_hint": "uv run rig agent provider setup",
            "error": str(exc),
            "code": exc.code,
        }

    provider_label = getattr(prov, "provider_type", provider_name or "provider")
    if provider_label == "ollama" and hasattr(prov, "model"):
        provider_label = f"ollama / {prov.model}"
    elif provider_label == "cursor":
        provider_label = "Cursor"

    try:
        loop = run_provider_loop(packet, ctx=ctx, provider=prov)
    except (ProviderTimeoutError, ProviderInvalidResponseError, AgentError) as exc:
        record = {
            "artifact": qid,
            "packet_hash": packet.get("packet_hash"),
            "provider_type": getattr(prov, "provider_type", "unknown"),
            "provider_version": None,
            "model": getattr(prov, "model", None),
            "error": str(exc),
            "code": getattr(exc, "code", "PROVIDER_ERROR"),
            "dry_run": dry_run,
            "apply": False,
        }
        audit.write_agent_run(record, root=root, run_id=run_id)
        return {
            "ok": False,
            "artifact_id": qid,
            "packet_hash": packet.get("packet_hash"),
            "provider": getattr(prov, "provider_type", None),
            "code": getattr(exc, "code", "PROVIDER_ERROR"),
            "error": str(exc),
            "run_id": run_id,
        }

    if loop.get("status") == AgentTurnKind.NEEDS_HUMAN_CLARIFICATION.value:
        audit.write_agent_run(
            {
                "artifact": qid,
                "packet_hash": packet.get("packet_hash"),
                "provider_type": getattr(prov, "provider_type", "unknown"),
                "turns": loop.get("turns"),
                "status": loop["status"],
                "clarification_questions": loop.get("clarification_questions"),
                "dry_run": True,
                "apply": False,
            },
            root=root,
            run_id=run_id,
        )
        return {
            "ok": True,
            "artifact_id": qid,
            "packet_hash": packet.get("packet_hash"),
            "status": loop["status"],
            "clarification_questions": loop.get("clarification_questions"),
            "rationale": loop.get("rationale"),
            "turns": loop.get("turns"),
            "writes": False,
            "run_id": run_id,
            "message": "Human clarification required — no writes",
        }

    if not loop.get("ok") or loop.get("proposal") is None:
        audit.write_agent_run(
            {
                "artifact": qid,
                "packet_hash": packet.get("packet_hash"),
                "provider_type": getattr(prov, "provider_type", "unknown"),
                "turns": loop.get("turns"),
                "status": loop.get("status"),
                "reason": loop.get("reason"),
                "dry_run": True,
                "apply": False,
            },
            root=root,
            run_id=run_id,
        )
        return {
            "ok": False,
            "artifact_id": qid,
            "packet_hash": packet.get("packet_hash"),
            "status": loop.get("status"),
            "reason": loop.get("reason"),
            "turns": loop.get("turns"),
            "run_id": run_id,
        }

    proposal = loop["proposal"]
    validation = validate_proposal(proposal, ctx=ctx, packet=packet)
    if not validation.get("ok"):
        audit.write_agent_run(
            {
                "artifact": qid,
                "packet_hash": packet.get("packet_hash"),
                "provider_type": getattr(prov, "provider_type", "unknown"),
                "turns": loop.get("turns"),
                "proposal": proposal.to_dict(),
                "validation": validation,
                "dry_run": True,
                "apply": False,
            },
            root=root,
            run_id=run_id,
        )
        return {
            "ok": False,
            "artifact_id": qid,
            "packet_hash": packet.get("packet_hash"),
            "validation": validation,
            "proposal": proposal.to_dict(),
            "turns": loop.get("turns"),
            "run_id": run_id,
        }

    # Autonomy filter for apply
    ops = list(proposal.operations)
    finalize_requested = bool(proposal.finalize) or any(
        o.kind == "question.finalize_manual" for o in ops
    )
    if apply and autonomy is AutonomyLevel.APPLY_SAFE:
        unsafe = [
            o.kind
            for o in ops
            if o.kind != "question.finalize_manual" and not get_spec(o.kind).autonomous_safe
        ]
        if unsafe:
            return {
                "ok": False,
                "artifact_id": qid,
                "code": "AUTONOMY_POLICY",
                "message": f"APPLY_SAFE forbids: {unsafe}",
                "proposal": proposal.to_dict(),
            }
        # Strip finalize unless APPLY_AND_FINALIZE
        ops = [o for o in ops if o.kind != "question.finalize_manual"]
        finalize_requested = False
        proposal.finalize = False

    if apply and autonomy is AutonomyLevel.APPLY_AND_FINALIZE:
        pass  # allow finalize in transaction

    try:
        finalize_op = None
        current_ops = [o for o in ops if o.kind != "question.finalize_manual"]
        if finalize_requested and autonomy is AutonomyLevel.APPLY_AND_FINALIZE:
            existing = next((o for o in ops if o.kind == "question.finalize_manual"), None)
            finalize_op = existing or RigOperation(
                namespace="question",
                action="finalize_manual",
                args={
                    "question_id": qid,
                    "note": proposal.rationale or "agent-assisted reconciliation",
                    "complete_linked_todos": True,
                    "apply_linked_changes": True,
                    "confirm_dod": True,
                },
            )
        prepared = prepare_transaction(current_ops, ctx=ctx, finalize_op=finalize_op)
    except PlanConflictError as exc:
        return {
            "ok": False,
            "artifact_id": qid,
            "code": exc.code,
            "error": str(exc),
            "operation_ids": list(exc.operation_ids),
            "conflict_key": exc.conflict_key,
            "run_id": run_id,
        }
    except StoreError as exc:
        return {
            "ok": False,
            "artifact_id": qid,
            "code": "PREPARE_FAILED",
            "error": str(exc),
            "run_id": run_id,
        }

    review = format_plan_review(
        question_id=qid,
        human_answer=str(packet.get("final_human_answer") or ""),
        rationale=proposal.rationale,
        operations=list(prepared.prepared[i].operation for i in range(len(prepared.prepared))),
        postconditions=proposal.expected_postconditions,
        finalize=bool(prepared.finalize_plan),
        atomic=True,
        provider_label=provider_label,
    )

    result: dict[str, Any] = {
        "ok": True,
        "artifact_id": qid,
        "provider": getattr(prov, "provider_type", None),
        "provider_label": provider_label,
        "model": getattr(prov, "model", None),
        "packet_hash": packet.get("packet_hash"),
        "provider_turns": loop.get("turns"),
        "context": loop.get("context"),
        "proposal": proposal.to_dict(),
        "validation": validation,
        "prepared_transaction": prepared.to_dict(),
        "finalization_plan": prepared.finalize_plan,
        "autonomy": autonomy.value,
        "plan_review": review,
        "dry_run": True,
        "applied": False,
        "run_id": run_id,
        "message": "Plan prepared. No changes have been written.",
    }

    # Default PLAN_ONLY / dry-run: stop before commit
    do_apply = apply and yes and not dry_run and autonomy in {
        AutonomyLevel.APPLY_SAFE,
        AutonomyLevel.APPLY_AND_FINALIZE,
    }
    if not do_apply:
        audit.write_agent_run(
            {
                "artifact": qid,
                "packet_hash": packet.get("packet_hash"),
                "provider_type": getattr(prov, "provider_type", "unknown"),
                "turns": loop.get("turns"),
                "proposal": proposal.to_dict(),
                "validation": validation,
                "prepared_transaction": prepared.to_dict(),
                "dry_run": True,
                "apply": False,
            },
            root=root,
            run_id=run_id,
        )
        return result

    commit = commit_transaction(
        prepared,
        ctx=ctx,
        artifact_id=qid,
        require_finalize=bool(prepared.finalize_plan),
    )
    result.update(
        {
            "dry_run": False,
            "applied": commit.get("ok", False),
            "transaction_result": commit,
            "postconditions": commit.get("postconditions"),
            "ok": commit.get("ok", False),
            "message": commit.get("message"),
        }
    )
    audit.write_agent_run(
        {
            "artifact": qid,
            "packet_hash": packet.get("packet_hash"),
            "provider_type": getattr(prov, "provider_type", "unknown"),
            "turns": loop.get("turns"),
            "proposal": proposal.to_dict(),
            "validation": validation,
            "prepared_transaction": prepared.to_dict(),
            "dry_run": False,
            "apply": True,
            "transaction_result": commit,
            "postcondition_result": commit.get("postconditions"),
        },
        root=root,
        run_id=run_id,
    )
    return result
