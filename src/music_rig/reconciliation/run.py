"""Unified `rig reconcile run` — deterministic first, agent planner when needed."""

from __future__ import annotations

from typing import Any

from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile
from music_rig.agent.provider import detect_providers, provider_status
from music_rig.models import ReconciliationState
from music_rig.reconciliation import service as recon
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.types import Capability


def reconcile_run(
    question_id: str,
    *,
    ctx: ReconciliationContext | None = None,
    apply: bool = False,
    yes: bool = False,
    dry_run: bool = True,
    provider: str | None = None,
    ollama_model: str | None = None,
    root=None,
) -> dict[str, Any]:
    """End-to-end reconciliation entrypoint (preview by default)."""
    ctx = ctx or ReconciliationContext.default()
    qid = question_id.upper()
    paths = ctx.path_dict()

    plan = recon.plan_question(
        qid,
        questions_path=paths.get("questions"),
        changes_path=paths.get("changes"),
        todo_path=paths.get("todo"),
        patchbays_path=paths.get("patchbays"),
        routing_path=paths.get("routing"),
        midi_path=paths.get("midi"),
        controllers_path=paths.get("controllers"),
        ableton_path=paths.get("ableton"),
        docs_todo=paths.get("docs_todo"),
        docs_wishlist=paths.get("docs_wishlist"),
        docs_questions=paths.get("docs_questions"),
    )
    state = plan.state
    capability = plan.capability

    if state in {ReconciliationState.NEEDS_ANSWER, ReconciliationState.DRAFT_ANSWER}:
        return {
            "ok": False,
            "mode": "needs_human",
            "artifact_id": qid,
            "state": state.value,
            "capability": capability.value,
            "message": (
                f"{qid} needs a final human answer before reconciliation.\n"
                f"  uv run rig question answer {qid} --answer \"…\""
            ),
            "provider_invoked": False,
        }

    if state in {
        ReconciliationState.READY_TO_APPLY,
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
    }:
        return _deterministic_path(
            qid,
            plan=plan,
            apply=apply,
            yes=yes,
            paths=paths,
        )

    agentish = state == ReconciliationState.NEEDS_AGENT_ACTION or capability in {
        Capability.MANUAL,
        Capability.UNSUPPORTED,
    }
    if agentish or (
        state == ReconciliationState.BLOCKED and capability == Capability.MANUAL
    ):
        status = provider_status(root=root)
        if not status.get("configured") and not provider:
            detected = detect_providers(root=root)
            return {
                "ok": False,
                "mode": "needs_provider",
                "artifact_id": qid,
                "state": state.value,
                "capability": capability.value,
                "provider_configured": False,
                "detected": detected,
                "message": _missing_provider_message(detected),
                "setup_hint": "uv run rig agent provider setup",
                "provider_invoked": False,
            }

        autonomy = AutonomyLevel.PLAN_ONLY
        if apply and yes:
            autonomy = AutonomyLevel.APPLY_SAFE
        result = autonomous_reconcile(
            qid,
            ctx=ctx,
            autonomy=autonomy,
            apply=apply and yes,
            yes=yes,
            dry_run=not (apply and yes),
            provider_name=provider,
            ollama_model=ollama_model,
            root=root,
        )
        result["mode"] = "agent"
        result["provider_invoked"] = True
        result["state"] = state.value
        result["capability"] = capability.value
        return result

    if capability in {
        Capability.VERIFY_ONLY,
        Capability.HUMAN_VERIFY_THEN_APPLY,
    }:
        return {
            "ok": False,
            "mode": "needs_verification",
            "artifact_id": qid,
            "state": state.value,
            "capability": capability.value,
            "message": (
                f"{qid} needs guided verification.\n"
                f"  uv run rig verify question {qid}"
            ),
            "provider_invoked": False,
        }

    if state == ReconciliationState.RECONCILED:
        return {
            "ok": True,
            "mode": "already_reconciled",
            "artifact_id": qid,
            "state": state.value,
            "message": f"{qid} is already reconciled.",
            "provider_invoked": False,
        }

    return {
        "ok": False,
        "mode": "unsupported",
        "artifact_id": qid,
        "state": state.value,
        "capability": capability.value,
        "message": f"No automated path for {qid} in state {state.value}.",
        "blockers": list(plan.blockers or []),
        "provider_invoked": False,
    }


def _deterministic_path(
    qid: str,
    *,
    plan,
    apply: bool,
    yes: bool,
    paths: dict[str, Any],
) -> dict[str, Any]:
    state = plan.state
    out: dict[str, Any] = {
        "ok": True,
        "mode": "deterministic",
        "artifact_id": qid,
        "state": state.value,
        "capability": plan.capability.value,
        "provider_invoked": False,
        "plan": plan.to_dict(),
        "suggested_commands": list(plan.suggested_commands or []),
        "dry_run": True,
        "applied": False,
        "message": f"Deterministic plan for {qid}: {state.value}",
    }

    if state in {
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
    }:
        fin = recon.finalize_question(
            qid,
            dry_run=not (apply and yes),
            yes=bool(apply and yes),
            confirm_current_reconciled=True,
            note="deterministic reconcile run",
            complete_linked_todos=True,
            confirm_dod=True,
            questions_path=paths.get("questions"),
            changes_path=paths.get("changes"),
            todo_path=paths.get("todo"),
            patchbays_path=paths.get("patchbays"),
            routing_path=paths.get("routing"),
            midi_path=paths.get("midi"),
            controllers_path=paths.get("controllers"),
            ableton_path=paths.get("ableton"),
            docs_todo=paths.get("docs_todo"),
            docs_wishlist=paths.get("docs_wishlist"),
            docs_questions=paths.get("docs_questions"),
        )
        out["finalize"] = fin
        out["dry_run"] = fin.get("dry_run", True)
        out["applied"] = not fin.get("dry_run", True)
        out["message"] = (
            f"Finalize plan for {qid} (deterministic)."
            if fin.get("dry_run")
            else f"Finalized {qid}."
        )
        return out

    if apply and yes:
        applied = recon.apply_question(
            qid,
            dry_run=False,
            yes=True,
            questions_path=paths.get("questions"),
            changes_path=paths.get("changes"),
            patchbays_path=paths.get("patchbays"),
            routing_path=paths.get("routing"),
            midi_path=paths.get("midi"),
            controllers_path=paths.get("controllers"),
            ableton_path=paths.get("ableton"),
            docs_todo=paths.get("docs_todo"),
            docs_wishlist=paths.get("docs_wishlist"),
            docs_questions=paths.get("docs_questions"),
        )
        out["apply_result"] = applied
        out["dry_run"] = False
        out["applied"] = True
        out["message"] = f"Applied deterministic reconciliation for {qid}."
    else:
        out["message"] = (
            f"Deterministic apply available for {qid}.\n"
            f"Review plan, then: uv run rig reconcile run {qid} --apply --yes"
        )
    return out


def _missing_provider_message(detected: dict[str, Any]) -> str:
    cursor = detected.get("cursor") or {}
    ollama = detected.get("ollama") or {}
    return "\n".join(
        [
            "Agent reconciliation is required.",
            "",
            "Available:",
            f"  Cursor {'✓' if cursor.get('available') else '✗'}",
            f"  Ollama {'✓' if ollama.get('available') else '✗'}",
            "",
            "Configure Provider:",
            "  uv run rig agent provider setup",
            "",
            "Or:",
            "  uv run rig agent provider use cursor",
            "  uv run rig agent provider use ollama --model <model>",
        ]
    )
