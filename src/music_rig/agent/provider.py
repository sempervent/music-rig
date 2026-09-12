"""Vendor-neutral stdio command provider for agent turns."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from music_rig.agent.errors import (
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from music_rig.agent.inspection import InspectionRequest
from music_rig.local_config import load_local_config
from music_rig.models import AgentLocalConfig
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import ROOT, StoreError


class AgentTurnKind(str, Enum):
    READY = "READY"
    NEEDS_MORE_CONTEXT = "NEEDS_MORE_CONTEXT"
    NEEDS_HUMAN_CLARIFICATION = "NEEDS_HUMAN_CLARIFICATION"
    NO_SAFE_PLAN = "NO_SAFE_PLAN"


@dataclass
class AgentTurn:
    kind: AgentTurnKind
    rationale: str = ""
    proposal: dict[str, Any] | None = None
    inspection_requests: list[InspectionRequest] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "rationale": self.rationale,
            "proposal": self.proposal,
            "inspection_requests": [r.to_dict() for r in self.inspection_requests],
            "clarification_questions": list(self.clarification_questions),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AgentTurn:
        kind = AgentTurnKind(str(raw.get("kind") or raw.get("status") or ""))
        reqs = [
            InspectionRequest.from_dict(r)
            for r in (raw.get("inspection_requests") or raw.get("requests") or [])
        ]
        proposal = raw.get("proposal")
        if proposal is None and kind is AgentTurnKind.READY:
            # Allow top-level proposal fields
            if "operations" in raw or "artifact_id" in raw:
                proposal = {
                    k: raw[k]
                    for k in (
                        "artifact_id",
                        "status",
                        "rationale",
                        "operations",
                        "expected_postconditions",
                        "finalize",
                        "clarification_questions",
                    )
                    if k in raw
                }
        return cls(
            kind=kind,
            rationale=str(raw.get("rationale") or ""),
            proposal=proposal,
            inspection_requests=reqs,
            clarification_questions=list(raw.get("clarification_questions") or []),
            reason=raw.get("reason"),
        )


def load_agent_local_config(*, root: Path | None = None) -> AgentLocalConfig:
    cfg = load_local_config(root=root)
    if cfg is None:
        return AgentLocalConfig()
    return cfg.agent


def provider_status(*, root: Path | None = None) -> dict[str, Any]:
    agent = load_agent_local_config(root=root)
    configured = (
        agent.provider == "command"
        and bool(agent.argv)
        and Path(agent.argv[0]).exists()
        if agent.argv
        else False
    )
    return {
        "configured": configured,
        "provider_type": agent.provider,
        "executable": agent.argv[0] if agent.argv else None,
        "argv": list(agent.argv),
        "timeout_seconds": agent.timeout_seconds,
        "forwarded_environment_variable_names": list(agent.env_forward),
        "max_context_rounds": agent.max_context_rounds,
        "max_stdout_bytes": agent.max_stdout_bytes,
    }


@dataclass
class CommandProvider:
    argv: list[str]
    timeout_seconds: int = 120
    env_forward: list[str] = field(default_factory=list)
    max_stdout_bytes: int = 1_000_000
    max_stderr_bytes: int = 100_000

    @classmethod
    def from_local_config(cls, *, root: Path | None = None) -> CommandProvider:
        agent = load_agent_local_config(root=root)
        if agent.provider != "command" or not agent.argv:
            raise ProviderNotConfiguredError("No command provider configured in .rig.local.yaml")
        return cls(
            argv=list(agent.argv),
            timeout_seconds=int(agent.timeout_seconds),
            env_forward=list(agent.env_forward),
            max_stdout_bytes=int(agent.max_stdout_bytes),
        )

    def _env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        path = os.environ.get("PATH")
        if path:
            env["PATH"] = path
        for name in self.env_forward:
            if name in os.environ:
                env[name] = os.environ[name]
        return env

    def run_turn(
        self,
        *,
        packet: dict[str, Any],
        context: list[dict[str, Any]] | None = None,
    ) -> tuple[AgentTurn, dict[str, Any]]:
        envelope = {
            "protocol_version": 1,
            "packet": packet,
            "context": list(context or []),
        }
        stdin_blob = json.dumps(envelope, default=str).encode("utf-8")
        diagnostics: dict[str, Any] = {
            "argv": list(self.argv),
            "timeout_seconds": self.timeout_seconds,
            "cwd_isolated": True,
            "forwarded_env_names": list(self.env_forward),
        }
        with tempfile.TemporaryDirectory(prefix="rig-agent-") as tmp:
            try:
                completed = subprocess.run(  # noqa: S603 — argv only, never shell
                    self.argv,
                    input=stdin_blob,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    cwd=tmp,
                    env=self._env(),
                    shell=False,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                diagnostics["stderr_preview"] = _preview(exc.stderr, self.max_stderr_bytes)
                raise ProviderTimeoutError(
                    f"provider timed out after {self.timeout_seconds}s"
                ) from exc

        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        diagnostics["exit_code"] = completed.returncode
        diagnostics["stdout_bytes"] = len(stdout)
        diagnostics["stderr_bytes"] = len(stderr)
        diagnostics["stderr_preview"] = _preview(stderr, self.max_stderr_bytes)

        if len(stdout) > self.max_stdout_bytes:
            raise ProviderInvalidResponseError(
                f"provider stdout exceeded {self.max_stdout_bytes} bytes"
            )
        if completed.returncode != 0:
            raise ProviderInvalidResponseError(
                f"provider exited {completed.returncode}"
            )
        try:
            text = stdout.decode("utf-8")
            raw = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(
                f"provider returned non-JSON stdout: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ProviderInvalidResponseError("provider JSON must be an object")
        try:
            turn = AgentTurn.from_dict(raw)
        except Exception as exc:
            raise ProviderInvalidResponseError(
                f"provider turn schema invalid: {exc}"
            ) from exc
        return turn, diagnostics


def _preview(data: bytes | None, limit: int) -> str:
    if not data:
        return ""
    text = data.decode("utf-8", errors="replace")
    return text[:limit]


def provider_test(*, root: Path | None = None) -> dict[str, Any]:
    """Handshake with a minimal fixture packet — no repository mutations."""
    provider = CommandProvider.from_local_config(root=root)
    packet = {
        "schema": "music_rig.agent_packet.v1",
        "artifact": {"type": "question", "id": "Q-000"},
        "final_human_answer": "provider test handshake",
        "allowed_operation_kinds": [],
        "handshake": True,
    }
    turn, diag = provider.run_turn(packet=packet, context=[])
    return {"ok": True, "turn": turn.to_dict(), "diagnostics": diag}
