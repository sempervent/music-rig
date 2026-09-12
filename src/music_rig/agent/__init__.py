"""Agent-assisted reconciliation — packet / proposal / validate / apply.

The agent reasons. The rig validates and dispatches allowlisted RigOperations.
No shell execution, no YAML edits, no evidence VERIFIED promotion by agents.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from music_rig import patchbay_state, question_service
from music_rig.models import OpenQuestion, QuestionStatus
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operation_registry import (
    allowlisted_kinds,
    get_spec,
    validate_operation_shape,
)
from music_rig.reconciliation.operation_renderer import operation_json_view, render_cli
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, load_todo


class ProposalStatus(str, Enum):
    READY = "READY"
    NEEDS_MORE_CONTEXT = "NEEDS_MORE_CONTEXT"
    NEEDS_HUMAN_CLARIFICATION = "NEEDS_HUMAN_CLARIFICATION"
    NO_SAFE_PLAN = "NO_SAFE_PLAN"
    INVALID = "INVALID"


@dataclass
class AgentReconciliationProposal:
    artifact_id: str
    status: ProposalStatus
    rationale: str = ""
    operations: list[RigOperation] = field(default_factory=list)
    expected_postconditions: list[dict[str, Any]] = field(default_factory=list)
    finalize: bool = False
    clarification_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "rationale": self.rationale,
            "operations": [o.to_dict() for o in self.operations],
            "expected_postconditions": self.expected_postconditions,
            "finalize": self.finalize,
            "clarification_questions": self.clarification_questions,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AgentReconciliationProposal:
        status = ProposalStatus(str(raw.get("status") or ProposalStatus.READY.value))
        ops = [RigOperation.from_dict(o) for o in (raw.get("operations") or [])]
        return cls(
            artifact_id=str(raw.get("artifact_id") or "").upper(),
            status=status,
            rationale=str(raw.get("rationale") or ""),
            operations=ops,
            expected_postconditions=list(raw.get("expected_postconditions") or []),
            finalize=bool(raw.get("finalize", False)),
            clarification_questions=list(raw.get("clarification_questions") or []),
        )


class AgentProvider(Protocol):
    def propose(self, packet: dict[str, Any]) -> AgentReconciliationProposal:
        ...


TRUTH_BOUNDARIES = [
    "Do not invent human observations.",
    "Do not set VERIFIED evidence without an explicit supporting verification_result.",
    "Do not edit canonical YAML directly.",
    "Use only allowlisted RigOperations from this packet.",
    "If the answer is ambiguous, return NEEDS_HUMAN_CLARIFICATION — do not guess.",
    "Model-level facts must not invent unit-level inventory IDs.",
]


def _stable_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _strip_volatile(obj: Any) -> Any:
    """Drop operation_id / other volatile fields before hashing."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in {"operation_id", "packet_hash"}
        }
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


def resolve_context(question: OpenQuestion, ctx: ReconciliationContext) -> dict[str, Any]:
    """Bounded CURRENT context from typed target + area — no full-repo dump."""
    domain = question.target.domain if question.target else None
    area = question.area
    out: dict[str, Any] = {
        "domain": domain,
        "area": area,
        "stable_ids": {
            "question_id": question.id,
            "related_todos": list(question.related_todos),
            "related_changes": list(question.related_changes),
        },
    }
    if domain in {"inventory.patchbay_mapping", "patchbay.mode"} or area == "Patchbay":
        data = patchbay_state.load_raw(ctx.paths.patchbays)
        bays = data.get("patchbays") or {}
        out["patchbays"] = {
            bid: {
                "hardware_model": (body or {}).get("hardware_model"),
                "status": (body or {}).get("status"),
            }
            for bid, body in sorted(bays.items())
            if isinstance(body, dict)
        }
        # Inventory model candidates (ids + names) — not unit assignment
        try:
            from music_rig.store import load_inventory

            inv = load_inventory(ctx.paths.inventory)
            out["inventory_model_candidates"] = [
                {"id": g.id, "name": g.name, "category": getattr(g, "category", None)}
                for g in inv.items
                if "p48" in g.id.casefold()
                or "px3000" in g.id.casefold()
                or "patchbay" in (g.name or "").casefold()
                or "art" in g.id.casefold()
                or "behringer" in g.id.casefold()
            ]
        except Exception:
            out["inventory_model_candidates"] = []
        out["unit_identity_note"] = (
            "hardware_model is model-level. Do not invent art-p48-1 vs art-p48-2 "
            "unless the human answer or inventory evidence uniquely identifies units."
        )
    if (domain and domain.startswith("routing")) or area in {"Routing", "Capture"}:
        try:
            from music_rig import channel_state
            from music_rig.store import load_routing

            routing = load_routing(ctx.paths.routing)
            out["routing_path_ids"] = sorted(p.id for p in routing.paths)
            ch = channel_state.load_raw(ctx.paths.channels)
            out["channel_devices"] = sorted(
                k for k in ch.keys() if isinstance(ch.get(k), dict)
            )
        except Exception:
            pass
    # Linked TODO summaries (bounded)
    try:
        tdoc = load_todo(ctx.paths.todo)
        out["related_todo_summaries"] = []
        for tid in question.related_todos:
            t = tdoc.task_map().get(tid)
            if t:
                out["related_todo_summaries"].append(
                    {"id": t.id, "task": t.task, "status": t.status.value}
                )
    except Exception:
        out["related_todo_summaries"] = []
    return out


def build_agent_packet(
    question_id: str,
    *,
    ctx: ReconciliationContext | None = None,
) -> dict[str, Any]:
    """Build a self-contained agent work packet — no LLM required."""
    ctx = ctx or ReconciliationContext.default()
    q = question_service.get_question(question_id, questions_path=ctx.paths.questions)
    from music_rig.reconciliation.service import question_state
    from music_rig.reconciliation.adapters import get_adapter
    from music_rig.verification_policy import evidence_basis_for, verification_policy_for

    paths = ctx.path_dict()
    adapter = get_adapter(q.target.domain if q.target else None)
    state = question_state(q, paths=paths)
    plan = adapter.plan(q, paths=paths)
    context = resolve_context(q, ctx)
    allowed = allowlisted_kinds(agent_only=True)
    candidate_ops: list[dict[str, Any]] = []
    # Domain-specific candidates for patchbay model mapping
    if (q.target and q.target.domain == "inventory.patchbay_mapping") or q.area == "Patchbay":
        for bay in ("PB-A", "PB-B", "PB-C", "PB-D"):
            candidate_ops.append(
                RigOperation(
                    namespace="patchbay",
                    action="set_model",
                    args={"bay_id": bay, "model": "<from human answer>", "question_id": q.id},
                    description=f"Set {bay} hardware_model from final answer",
                    domain="inventory.patchbay_mapping",
                ).to_dict()
            )
        candidate_ops.append(
            RigOperation(
                namespace="question",
                action="finalize_manual",
                args={
                    "question_id": q.id,
                    "note": "CURRENT patchbay models match final human answer",
                    "complete_linked_todos": True,
                    "confirm_dod": True,
                },
                description="Finalize after model updates",
            ).to_dict()
        )
    packet = {
        "schema": "music_rig.agent_packet.v1",
        "artifact": {"type": "question", "id": q.id},
        "question": q.question,
        "final_human_answer": q.answer,
        "answer_actor": (
            q.answer_actor.value if q.answer_actor is not None else (
                "LEGACY_UNKNOWN" if q.answer.strip() else None
            )
        ),
        "answer_state": question_service.derive_answer_state(q).value,
        "question_status": q.status.value,
        "verification_policy": verification_policy_for(q).value,
        "evidence_basis": evidence_basis_for(q).value,
        "verification_result": (
            {
                "outcome": q.verification_result.outcome.value,
                "observed_value": q.verification_result.observed_value,
                "note": q.verification_result.note,
            }
            if q.verification_result
            else None
        ),
        "typed_target": (
            {k: v for k, v in q.target.model_dump().items() if v is not None}
            if q.target
            else None
        ),
        "reconciliation_state": state.value,
        "capability": plan.capability.value,
        "related_todos": list(q.related_todos),
        "related_changes": list(q.related_changes),
        "clarifies_question": q.clarifies_question,
        "relevant_current_context": context,
        "allowed_operation_kinds": allowed,
        "candidate_operations": candidate_ops,
        "required_postconditions": [
            "canonical CURRENT reflects the final human answer at the stated granularity",
            "question remains RESOLVED",
            "reconciled_at set only after postconditions pass",
        ],
        "forbidden_claims": [
            "Do not invent unique inventory unit IDs from model-only answers.",
            "Do not invent verification_result.",
            "Do not set evidence VERIFIED without Stage 17 observation OR HUMAN answer attestation when policy allows.",
        ],
        "truth_boundaries": TRUTH_BOUNDARIES,
        "plan_blockers": plan.blockers,
    }
    # Semantic hash excludes nothing volatile (no timestamp)
    packet["packet_hash"] = _stable_hash(_strip_volatile(packet))
    return packet


def load_proposal(path: Path | str) -> AgentReconciliationProposal:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AgentReconciliationProposal.from_dict(data)


def validate_proposal(
    proposal: AgentReconciliationProposal,
    *,
    ctx: ReconciliationContext | None = None,
    packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate proposal structure, allowlist, IDs, domain relevance, evidence guards."""
    ctx = ctx or ReconciliationContext.default()
    errors: list[str] = []
    warnings: list[str] = []

    if proposal.status is ProposalStatus.NEEDS_HUMAN_CLARIFICATION:
        return {
            "ok": True,
            "status": proposal.status.value,
            "errors": [],
            "warnings": ["proposal requests human clarification — no apply"],
            "clarification_questions": proposal.clarification_questions,
        }
    if proposal.status is ProposalStatus.NEEDS_MORE_CONTEXT:
        return {
            "ok": True,
            "status": proposal.status.value,
            "errors": [],
            "warnings": ["proposal needs more context — no apply"],
        }
    if proposal.status in {ProposalStatus.NO_SAFE_PLAN, ProposalStatus.INVALID}:
        return {
            "ok": False,
            "status": proposal.status.value,
            "errors": [f"proposal status {proposal.status.value}"],
            "warnings": warnings,
        }

    if not proposal.artifact_id:
        errors.append("artifact_id required")
    else:
        try:
            q = question_service.get_question(
                proposal.artifact_id, questions_path=ctx.paths.questions
            )
        except StoreError as exc:
            errors.append(str(exc))
            q = None
            return {"ok": False, "status": "INVALID", "errors": errors, "warnings": warnings}

    if q is not None and q.status != QuestionStatus.RESOLVED:
        errors.append(f"{q.id} must be RESOLVED before agent apply")
    if q is not None and not q.answer.strip():
        errors.append(f"{q.id} has empty answer")

    domain = q.target.domain if q and q.target else None
    area = q.area if q else ""
    # Expand only from the question's own target/area (no global allow-all).
    _DOMAIN_EXPAND = {
        "inventory.patchbay_mapping": {"Patchbay", "inventory.patchbay_mapping"},
        "patchbay.mode": {"Patchbay", "patchbay.mode"},
        "routing.verify": {"Routing", "Capture", "channels", "routing.verify"},
        "Routing": {"Routing", "Capture", "channels", "routing.verify"},
        "Capture": {"Routing", "Capture", "channels", "routing.verify"},
        "Patchbay": {"Patchbay", "inventory.patchbay_mapping", "patchbay.mode"},
        "Inventory": {"Inventory", "inventory.location"},
        "inventory.location": {"Inventory", "inventory.location"},
        "channels": {"Routing", "Capture", "channels", "routing.verify"},
    }
    seed: set[str] = set()
    if domain:
        seed.add(domain)
    if area:
        seed.add(area)
    allowed_domains: set[str] = set()
    for d in seed:
        allowed_domains.add(d)
        allowed_domains.update(_DOMAIN_EXPAND.get(d, ()))

    for op in proposal.operations:
        try:
            validate_operation_shape(op, agent=True)
            spec = get_spec(op.kind)
            if spec.domains and allowed_domains:
                if not (set(spec.domains) & allowed_domains):
                    errors.append(
                        f"{op.kind} not relevant to target domain {domain!r} / area {area!r}"
                    )
            # ID existence checks
            if "question_id" in op.args:
                question_service.get_question(
                    str(op.args["question_id"]), questions_path=ctx.paths.questions
                )
            if "bay_id" in op.args:
                data = patchbay_state.load_raw(ctx.paths.patchbays)
                bay = str(op.args["bay_id"]).upper()
                if bay not in (data.get("patchbays") or {}):
                    errors.append(f"unknown bay_id {bay}")
            # Unit-ID invention guard for set_model
            if op.kind == "patchbay.set_model":
                model = str(op.args.get("model") or "")
                if model.casefold().startswith("art-p48-") or model.casefold().startswith(
                    "behringer-px3000-"
                ):
                    # Allow only if human answer contains that exact token
                    answer = (q.answer if q else "").casefold()
                    if model.casefold() not in answer:
                        errors.append(
                            f"refusing unit-id-like model {model!r} not present in human answer"
                        )
        except StoreError as exc:
            errors.append(str(exc))

    # Evidence escalation: any op claiming VERIFIED
    blob = json.dumps(proposal.to_dict(), default=str).casefold()
    if "evidence" in blob and "verified" in blob and "verification_result" not in (
        packet or {}
    ):
        if q is None or q.verification_result is None:
            errors.append("evidence VERIFIED escalation forbidden without verification_result")

    if packet and packet.get("artifact", {}).get("id") not in {
        None,
        proposal.artifact_id,
    }:
        if str(packet.get("artifact", {}).get("id")).upper() != proposal.artifact_id:
            warnings.append("proposal artifact_id differs from packet")

    ok = not errors and proposal.status is ProposalStatus.READY
    return {
        "ok": ok,
        "status": proposal.status.value if ok else ProposalStatus.INVALID.value,
        "errors": errors,
        "warnings": warnings,
        "operations": [operation_json_view(o) for o in proposal.operations],
    }


def apply_proposal(
    proposal: AgentReconciliationProposal,
    *,
    ctx: ReconciliationContext | None = None,
    dry_run: bool = True,
    yes: bool = False,
    snapshot_before: bool = False,
) -> dict[str, Any]:
    """Validate then apply via one atomic AgentTransaction (prepare != commit)."""
    from music_rig.agent.errors import AgentError, PlanConflictError
    from music_rig.agent.transaction import commit_transaction, prepare_transaction

    ctx = ctx or ReconciliationContext.default()
    if not dry_run and not yes:
        raise StoreError("agent apply write requires --yes (default is dry-run)")

    validation = validate_proposal(proposal, ctx=ctx)
    if not validation["ok"]:
        return {
            "ok": False,
            "dry_run": dry_run,
            "validation": validation,
            "applied": [],
        }

    if proposal.status is ProposalStatus.NEEDS_HUMAN_CLARIFICATION:
        return {
            "ok": True,
            "dry_run": dry_run,
            "validation": validation,
            "applied": [],
            "message": "clarification required — no mutations",
        }

    if proposal.status is ProposalStatus.NEEDS_MORE_CONTEXT:
        return {
            "ok": True,
            "dry_run": dry_run,
            "validation": validation,
            "applied": [],
            "message": "needs more context — no mutations",
        }

    if snapshot_before and not dry_run:
        from music_rig import snapshot_service

        snapshot_service.create_snapshot(
            note=f"agent apply {proposal.artifact_id}",
        )

    ops = [o for o in proposal.operations if o.kind != "question.finalize_manual"]
    finalize_op = None
    if proposal.finalize or any(
        o.kind == "question.finalize_manual" for o in proposal.operations
    ):
        existing = next(
            (o for o in proposal.operations if o.kind == "question.finalize_manual"),
            None,
        )
        finalize_op = existing or RigOperation(
            namespace="question",
            action="finalize_manual",
            args={
                "question_id": proposal.artifact_id,
                "note": proposal.rationale or "agent-assisted reconciliation",
                "complete_linked_todos": True,
                "apply_linked_changes": True,
                "confirm_dod": True,
            },
        )

    try:
        prepared = prepare_transaction(ops, ctx=ctx, finalize_op=finalize_op)
    except PlanConflictError as exc:
        return {
            "ok": False,
            "dry_run": dry_run,
            "validation": validation,
            "code": exc.code,
            "error": str(exc),
            "operation_ids": list(exc.operation_ids),
            "conflict_key": exc.conflict_key,
            "applied": [],
        }
    except StoreError as exc:
        return {
            "ok": False,
            "dry_run": dry_run,
            "validation": validation,
            "error": str(exc),
            "applied": [],
        }

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "validation": validation,
            "plan": [operation_json_view(o) for o in proposal.operations],
            "prepared_transaction": prepared.to_dict(),
            "atomic": True,
            "message": "No changes applied. Re-run with --yes to commit.",
        }

    try:
        commit = commit_transaction(
            prepared,
            ctx=ctx,
            artifact_id=proposal.artifact_id,
            require_finalize=bool(prepared.finalize_plan),
        )
    except AgentError as exc:
        return {
            "ok": False,
            "dry_run": False,
            "validation": validation,
            "code": exc.code,
            "error": str(exc),
            "applied": [],
        }

    return {
        "ok": commit.get("ok", False),
        "dry_run": False,
        "validation": validation,
        "prepared_transaction": prepared.to_dict(),
        "transaction_result": commit,
        "postconditions_passed": commit.get("postconditions", {}).get("ok"),
        "atomic": True,
        "message": commit.get("message"),
    }


def capabilities() -> dict[str, Any]:
    from music_rig.agent.provider import provider_status
    from music_rig.reconciliation.operation_registry import list_operations

    status = provider_status()
    ops = [s.capability_row() for s in list_operations(agent_only=True)]
    return {
        "provider": status if status.get("configured") else None,
        "provider_configured": bool(status.get("configured")),
        "provider_status": status,
        "allowlisted_operations": allowlisted_kinds(agent_only=True),
        "operations": ops,
        "autonomy_levels": ["PLAN_ONLY", "APPLY_SAFE", "APPLY_AND_FINALIZE"],
        "workflow": [
            "uv run rig agent provider setup",
            "uv run rig reconcile run Q-xxx",
            "uv run rig reconcile run Q-xxx --apply --yes",
        ],
        "advanced_workflow": [
            "uv run rig agent packet Q-xxx --json",
            "uv run rig agent validate proposal.json",
            "uv run rig agent apply proposal.json --dry-run",
            "uv run rig agent apply proposal.json --yes",
        ],
        "truth_boundaries": TRUTH_BOUNDARIES,
    }
