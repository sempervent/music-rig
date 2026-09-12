"""Shared types for reconciliation workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from music_rig.models import ReconciliationState


class Capability(str, Enum):
    APPLY_AND_VERIFY = "APPLY_AND_VERIFY"
    VERIFY_ONLY = "VERIFY_ONLY"
    MANUAL = "MANUAL"
    UNSUPPORTED = "UNSUPPORTED"


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
    blockers: list[str] = field(default_factory=list)
    suggested_commands: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        data["capability"] = self.capability.value
        return data


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
