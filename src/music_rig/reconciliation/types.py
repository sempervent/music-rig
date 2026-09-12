"""Shared types for reconciliation workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from music_rig.models import ReconciliationState


class Capability(str, Enum):
    APPLY_AND_VERIFY = "APPLY_AND_VERIFY"
    # Human must observe; after verification_result, adapter may apply evidence/value.
    # Historical name VERIFY_ONLY kept for CLI/compat; behavior is human-verify-then-apply.
    VERIFY_ONLY = "VERIFY_ONLY"
    HUMAN_VERIFY_THEN_APPLY = "HUMAN_VERIFY_THEN_APPLY"
    MANUAL = "MANUAL"
    UNSUPPORTED = "UNSUPPORTED"


class PlanOperationKind(str, Enum):
    SET_CURRENT_VALUE = "SET_CURRENT_VALUE"
    SET_EVIDENCE_VERIFIED = "SET_EVIDENCE_VERIFIED"
    SET_EVIDENCE_UNKNOWN = "SET_EVIDENCE_UNKNOWN"
    RECORD_FAILED_VERIFICATION = "RECORD_FAILED_VERIFICATION"
    NO_CURRENT_CHANGE = "NO_CURRENT_CHANGE"


def op(
    kind: PlanOperationKind | str,
    *,
    target: str = "",
    before: Any = None,
    after: Any = None,
    note: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Typed plan operation dict for reconcile plan JSON."""
    kind_val = kind.value if isinstance(kind, PlanOperationKind) else str(kind)
    payload: dict[str, Any] = {"op": kind_val}
    if target:
        payload["target"] = target
    if before is not None:
        payload["before"] = before
    if after is not None:
        payload["after"] = after
    if note:
        payload["note"] = note
    payload.update(extra)
    return payload


class VerificationStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNVERIFIABLE = "UNVERIFIABLE"
    BLOCKED = "BLOCKED"


@dataclass
class Plan:
    artifact_type: str
    artifact_id: str
    state: ReconciliationState
    capability: Capability
    current: Any = None
    desired: Any = None
    operations: list[dict[str, Any]] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    closable: list[str] = field(default_factory=list)
    # Strings or structured dicts ({code, field, candidates, suggested_commands, message})
    blockers: list[Any] = field(default_factory=list)
    # DEPRECATED presentation field — prefer ``suggestions``; filled from suggestions
    # at construction / ``to_dict`` for agent JSON compatibility.
    suggested_commands: list[str] = field(default_factory=list)
    # Canonical next-step suggestions (structured).
    suggestions: list[Any] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.suggestions and not self.suggested_commands:
            from music_rig.reconciliation.suggestions import render_suggestions

            self.suggested_commands = render_suggestions(self.suggestions)

    def rendered_commands(self, *, actor: str = "HUMAN") -> list[str]:
        """Presentation CLI strings (actor-aware)."""
        if self.suggestions:
            from music_rig.reconciliation.suggestions import render_suggestions

            return render_suggestions(self.suggestions, actor=actor)
        return list(self.suggested_commands)

    def to_dict(self) -> dict[str, Any]:
        from music_rig.reconciliation.suggestions import (
            ActionSuggestion,
            render_suggestions,
            suggestions_asdicts,
        )

        suggestions: list[ActionSuggestion] = []
        for item in self.suggestions:
            if isinstance(item, ActionSuggestion):
                suggestions.append(item)
            elif isinstance(item, dict):
                suggestions.append(ActionSuggestion.from_dict(item))

        # Prefer structured suggestions; fall back to legacy suggested_commands.
        if suggestions:
            cmds = render_suggestions(suggestions)
        else:
            cmds = list(self.suggested_commands)

        return {
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "state": self.state.value,
            "capability": self.capability.value,
            "current": self.current,
            "desired": self.desired,
            "operations": list(self.operations),
            "postconditions": list(self.postconditions),
            "closable": list(self.closable),
            "blockers": list(self.blockers),
            "suggestions": suggestions_asdicts(suggestions),
            # DEPRECATED: presentation list for agent JSON compatibility.
            "suggested_commands": cmds,
            "details": dict(self.details),
        }


@dataclass
class VerifyResult:
    status: VerificationStatus
    current: Any = None
    expected: Any = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "current": self.current,
            "expected": self.expected,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class QueueItem:
    artifact_type: str
    artifact_id: str
    state: ReconciliationState
    summary: str
    capability: Capability | None = None
    area: str = ""
    related: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "state": self.state.value,
            "summary": self.summary,
            "capability": self.capability.value if self.capability else None,
            "area": self.area,
            "related": self.related,
        }


def ok_payload(operation: str, result: Any) -> dict[str, Any]:
    return {"ok": True, "operation": operation, "result": result}


def err_payload(
    code: str, message: str, *, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }
