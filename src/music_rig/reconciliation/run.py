"""Unified `rig reconcile run` — dispatch-first, provider only when eligible."""

from __future__ import annotations

from typing import Any

from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile
from music_rig.agent.provider import detect_providers, provider_status
from music_rig.models import ReconciliationState
from music_rig.reconciliation import service as recon
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.dispatch import (
    DispatchMode,
    classify_reconciliation_dispatch,
)


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
    interactive_verify: bool | None = None,
    on_progress=None,
) -> dict[str, Any]:
    """End-to-end reconciliation entrypoint (preview by default).

    Provider is invoked only when ``classify_reconciliation_dispatch`` returns
    AGENT. Human observation / answer / clarification never call a provider.
    ``--yes`` confirms writes; it does NOT fabricate human observation.
    """
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
    dispatch = classify_reconciliation_dispatch(plan)
    state = plan.state
    capability = plan.capability
    base = {
        "artifact_id": qid,
        "state": state.value,
        "capability": capability.value,
        "dispatch": dispatch.to_dict(),
        "provider_invoked": False,
        "value_match": dispatch.value_match,
        "plan": plan.to_dict(),
    }

    if dispatch.mode is DispatchMode.DONE:
        return {
            **base,
            "ok": True,
            "mode": "already_reconciled",
            "message": f"{qid} is already reconciled.",
        }

    if dispatch.mode is DispatchMode.HUMAN_ANSWER:
        return {
            **base,
            "ok": False,
            "mode": "needs_human",
            "message": (
                f"{qid} needs a final human answer before reconciliation.\n"
                f'  uv run rig question answer {qid} --answer "…"'
            ),
        }

    if dispatch.mode is DispatchMode.HUMAN_OBSERVATION:
        return _human_observation_path(
            qid,
            plan=plan,
            dispatch=dispatch,
            apply=apply,
            yes=yes,
            paths=paths,
            interactive_verify=interactive_verify,
            base=base,
        )

    if dispatch.mode is DispatchMode.HUMAN_CLARIFICATION:
        return {
            **base,
            "ok": False,
            "mode": "needs_clarification",
            "message": (
                f"{qid}: human clarification required — an agent cannot invent "
                f"the missing fact.\n"
                f'  uv run rig question answer {qid} --answer "…"'
            ),
            "blockers": list(plan.blockers or []),
        }

    if dispatch.mode is DispatchMode.DETERMINISTIC:
        return {
            **base,
            **_deterministic_path(
                qid,
                plan=plan,
                apply=apply,
                yes=yes,
                paths=paths,
                finalize=False,
            ),
        }

    if dispatch.mode is DispatchMode.FINALIZE:
        return {
            **base,
            **_deterministic_path(
                qid,
                plan=plan,
                apply=apply,
                yes=yes,
                paths=paths,
                finalize=True,
            ),
        }

    if dispatch.mode is DispatchMode.AGENT:
        status = provider_status(root=root)
        if not status.get("configured") and not provider:
            detected = detect_providers(root=root)
            return {
                **base,
                "ok": False,
                "mode": "needs_provider",
                "provider_configured": False,
                "detected": detected,
                "message": _missing_provider_message(detected),
                "setup_hint": "uv run rig agent provider setup",
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
            on_progress=on_progress,
        )
        result["mode"] = "agent"
        result["provider_invoked"] = True
        result["state"] = state.value
        result["capability"] = capability.value
        result["dispatch"] = dispatch.to_dict()
        result["value_match"] = dispatch.value_match
        return result

    return {
        **base,
        "ok": False,
        "mode": "blocked",
        "message": (
            f"No automated path for {qid}: {dispatch.reason}."
        ),
        "blockers": list(plan.blockers or []),
    }


def _human_observation_path(
    qid: str,
    *,
    plan,
    dispatch,
    apply: bool,
    yes: bool,
    paths: dict[str, Any],
    interactive_verify: bool | None,
    base: dict[str, Any],
) -> dict[str, Any]:
    """Human verification required — never invoke a provider."""
    current = plan.current
    desired = plan.desired
    match_line = (
        "MATCH"
        if dispatch.value_match is True
        else ("MISMATCH" if dispatch.value_match is False else "UNKNOWN")
    )
    message = _format_observation_message(
        qid,
        current=current,
        desired=desired,
        match_line=match_line,
    )

    out: dict[str, Any] = {
        **base,
        "ok": False,
        "mode": "needs_verification",
        "message": message,
        "blockers": list(plan.blockers or []),
        "suggested_commands": [
            f"uv run rig verify record {qid} --outcome confirmed --value … --yes --json",
            f"uv run rig tui verify",
            f"uv run rig verify question {qid}",
        ],
    }

    # Interactive TTY --apply may offer observation confirmation.
    # --yes alone NEVER fabricates observation.
    if apply and interactive_verify and not yes:
        confirmed = interactive_verify  # callable or bool handled by CLI
        if callable(interactive_verify):
            confirmed = interactive_verify(
                {
                    "question_id": qid,
                    "current": current,
                    "desired": desired,
                    "value_match": dispatch.value_match,
                }
            )
        if confirmed:
            # Record verification then re-enter deterministic path via caller.
            out["interactive_observation_offered"] = True
            out["interactive_observation_confirmed"] = True
            out["message"] = (
                message
                + "\n\nInteractive verification confirmed — "
                "record via verify machinery before apply."
            )
            out["next_step"] = "record_verification_result"
            return out

    if apply and yes:
        out["message"] = (
            message
            + "\n\n--yes does not imply human observation. "
            "Record verification first:\n"
            f"  uv run rig verify record {qid} --outcome confirmed "
            f"--value … --yes --json"
        )
        out["ok"] = False
        return out

    return out


def _format_observation_message(
    qid: str,
    *,
    current: Any,
    desired: Any,
    match_line: str,
) -> str:
    current_lines = _format_current(current)
    return "\n".join(
        [
            f"RECONCILE {qid}",
            "",
            "Answer:",
            f"  {desired}",
            "",
            "CURRENT:",
            *current_lines,
            "",
            "Value comparison:",
            f"  {match_line}",
            "",
            "Remaining requirement:",
            "  Human verification required before this can become VERIFIED.",
            "",
            "No agent was invoked because an agent cannot perform this observation.",
            "",
            "Next:",
            "  Verify the fact on the actual rig, then record the observation with:",
            f"    uv run rig verify record {qid} --outcome confirmed --value … --yes --json",
            "",
            "  Or use:",
            "    uv run rig tui verify",
        ]
    )


def _format_current(current: Any) -> list[str]:
    if isinstance(current, dict):
        lines = []
        master = current.get("master") or current.get("endpoint_ref")
        status = current.get("status") or current.get("evidence")
        if master is not None:
            lines.append(f"  Clock master: {master}")
        if status is not None:
            lines.append(f"  Evidence: {status}")
        for k, v in current.items():
            if k in {"master", "endpoint_ref", "status", "evidence"}:
                continue
            lines.append(f"  {k}: {v}")
        return lines or [f"  {current!r}"]
    if current is None:
        return ["  (none)"]
    return [f"  {current}"]


def _deterministic_path(
    qid: str,
    *,
    plan,
    apply: bool,
    yes: bool,
    paths: dict[str, Any],
    finalize: bool,
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

    if finalize or state in {
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
