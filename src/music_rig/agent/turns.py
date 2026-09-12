"""Typed agent turn schema (Pydantic) — shared by all providers."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentTurnKind(str, Enum):
    READY = "READY"
    NEEDS_MORE_CONTEXT = "NEEDS_MORE_CONTEXT"
    NEEDS_HUMAN_CLARIFICATION = "NEEDS_HUMAN_CLARIFICATION"
    NO_SAFE_PLAN = "NO_SAFE_PLAN"


class InspectionRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AgentTurn(BaseModel):
    """Exactly one turn outcome from a reconciliation provider."""

    model_config = ConfigDict(extra="forbid")

    kind: AgentTurnKind
    rationale: str = ""
    proposal: dict[str, Any] | None = None
    inspection_requests: list[InspectionRequestModel] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AgentTurn:
        data = dict(raw)
        if "kind" not in data and "status" in data:
            data["kind"] = data["status"]
        if data.get("inspection_requests") is None and data.get("requests"):
            data["inspection_requests"] = data["requests"]
        if data.get("proposal") is None and str(data.get("kind") or "") == "READY":
            if "operations" in data or "artifact_id" in data:
                data["proposal"] = {
                    k: data[k]
                    for k in (
                        "artifact_id",
                        "status",
                        "rationale",
                        "operations",
                        "expected_postconditions",
                        "finalize",
                        "clarification_questions",
                    )
                    if k in data
                }
        return cls.model_validate(data)

    def inspection_as_requests(self):
        from music_rig.agent.inspection import InspectionRequest

        return [
            InspectionRequest(kind=r.kind, id=r.id, filters=dict(r.filters))
            for r in self.inspection_requests
        ]


def agent_turn_json_schema() -> dict[str, Any]:
    """JSON Schema for Ollama structured output / Cursor prompt."""
    return AgentTurn.model_json_schema()
