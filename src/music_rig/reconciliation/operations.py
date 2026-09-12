"""Structured RigOperation — allowlisted intent, not shell strings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class OperationMutability(str, Enum):
    READ_ONLY = "read_only"
    MUTATING = "mutating"


@dataclass(frozen=True, slots=True)
class RigOperation:
    """Allowlisted rig capability invocation.

    Canonical representation for agent proposals, plans, and action packets.
    CLI strings are rendered separately — never stored as the source of truth.
    """

    namespace: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    operation_id: str = field(default_factory=lambda: f"op-{uuid4().hex[:10]}")
    description: str = ""
    mutability: OperationMutability = OperationMutability.MUTATING
    requires_confirmation: bool = True
    supports_dry_run: bool = True
    domain: str = ""

    @property
    def kind(self) -> str:
        return f"{self.namespace}.{self.action}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind
        data["mutability"] = self.mutability.value
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RigOperation:
        kind = raw.get("kind") or f"{raw.get('namespace')}.{raw.get('action')}"
        if "namespace" in raw and "action" in raw:
            ns, act = str(raw["namespace"]), str(raw["action"])
        else:
            parts = str(kind).split(".", 1)
            if len(parts) != 2:
                raise ValueError(f"invalid operation kind: {kind!r}")
            ns, act = parts
        mut = raw.get("mutability", OperationMutability.MUTATING)
        if isinstance(mut, str):
            mut = OperationMutability(mut)
        return cls(
            namespace=ns,
            action=act,
            args=dict(raw.get("args") or {}),
            operation_id=str(raw.get("operation_id") or f"op-{uuid4().hex[:10]}"),
            description=str(raw.get("description") or ""),
            mutability=mut,
            requires_confirmation=bool(raw.get("requires_confirmation", True)),
            supports_dry_run=bool(raw.get("supports_dry_run", True)),
            domain=str(raw.get("domain") or ""),
        )
