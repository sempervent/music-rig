"""Provider factory + advanced command provider.

First-class providers: cursor, ollama.
Advanced: command (stdio argv).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from music_rig.agent.cursor_provider import (
    CursorProvider,
    cursor_provider_from_config,
    cursor_version,
    find_cursor_executable,
)
from music_rig.agent.errors import (
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from music_rig.agent.ollama_provider import (
    OllamaProvider,
    ollama_provider_from_config,
    ollama_reachable,
    ollama_tags,
)
from music_rig.agent.providers_util import diagnostics_base, minimal_env, preview_bytes
from music_rig.agent.turns import AgentTurn, AgentTurnKind
from music_rig.local_config import load_local_config
from music_rig.models import AgentLocalConfig

# Back-compat re-exports
__all__ = [
    "AgentTurn",
    "AgentTurnKind",
    "CommandProvider",
    "CursorProvider",
    "OllamaProvider",
    "detect_providers",
    "load_agent_local_config",
    "provider_status",
    "provider_test",
    "resolve_provider",
]


class TurnProvider(Protocol):
    provider_type: str

    def run_turn(
        self,
        *,
        packet: dict[str, Any],
        context: list[dict[str, Any]] | None = None,
    ) -> tuple[AgentTurn, dict[str, Any]]: ...


def load_agent_local_config(*, root: Path | None = None) -> AgentLocalConfig:
    cfg = load_local_config(root=root)
    if cfg is None:
        return AgentLocalConfig()
    return cfg.agent


@dataclass
class CommandProvider:
    """Advanced stdio command provider (expert integrations)."""

    argv: list[str]
    timeout_seconds: int = 120
    env_forward: list[str] = field(default_factory=list)
    max_stdout_bytes: int = 1_000_000
    max_stderr_bytes: int = 100_000

    @property
    def provider_type(self) -> str:
        return "command"

    @classmethod
    def from_local_config(cls, *, root: Path | None = None) -> CommandProvider:
        agent = load_agent_local_config(root=root)
        if agent.provider != "command" or not agent.argv:
            raise ProviderNotConfiguredError(
                "Command provider selected, but argv is empty.\n"
                "Prefer: uv run rig agent provider use cursor|ollama"
            )
        return cls(
            argv=list(agent.argv),
            timeout_seconds=int(agent.timeout_seconds),
            env_forward=list(agent.env_forward),
            max_stdout_bytes=int(agent.max_stdout_bytes),
        )

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
        diagnostics = diagnostics_base(
            provider="command",
            argv=list(self.argv),
            timeout_seconds=self.timeout_seconds,
            forwarded_env_names=list(self.env_forward),
        )
        with tempfile.TemporaryDirectory(prefix="rig-agent-") as tmp:
            try:
                completed = subprocess.run(  # noqa: S603
                    self.argv,
                    input=stdin_blob,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    cwd=tmp,
                    env=minimal_env(env_forward=self.env_forward),
                    shell=False,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                diagnostics["stderr_preview"] = preview_bytes(exc.stderr, self.max_stderr_bytes)
                raise ProviderTimeoutError(
                    f"provider timed out after {self.timeout_seconds}s"
                ) from exc

        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        diagnostics["exit_code"] = completed.returncode
        diagnostics["stdout_bytes"] = len(stdout)
        diagnostics["stderr_bytes"] = len(stderr)
        diagnostics["stderr_preview"] = preview_bytes(stderr, self.max_stderr_bytes)

        if len(stdout) > self.max_stdout_bytes:
            raise ProviderInvalidResponseError(
                f"provider stdout exceeded {self.max_stdout_bytes} bytes"
            )
        if completed.returncode != 0:
            raise ProviderInvalidResponseError(f"provider exited {completed.returncode}")
        try:
            raw = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(f"provider returned non-JSON stdout: {exc}") from exc
        if not isinstance(raw, dict):
            raise ProviderInvalidResponseError("provider JSON must be an object")
        try:
            turn = AgentTurn.from_dict(raw)
        except Exception as exc:
            raise ProviderInvalidResponseError(f"provider turn schema invalid: {exc}") from exc
        return turn, diagnostics

    def handshake(self) -> tuple[AgentTurn, dict[str, Any]]:
        packet = {
            "schema": "music_rig.agent_packet.v1",
            "artifact": {"type": "question", "id": "Q-000"},
            "final_human_answer": "provider test handshake",
            "allowed_operation_kinds": [],
            "handshake": True,
        }
        return self.run_turn(packet=packet, context=[])


def resolve_provider(
    *,
    root: Path | None = None,
    provider: str | None = None,
    ollama_model: str | None = None,
    allow_fallback: bool = True,
    on_progress=None,
) -> TurnProvider:
    """Resolve configured (or overridden) provider instance."""
    agent = load_agent_local_config(root=root)
    name = (provider or agent.provider or "").strip().lower() or None
    if not name:
        raise ProviderNotConfiguredError(
            "No reconciliation provider configured.\nRun: uv run rig agent provider setup"
        )

    def _build(which: str) -> TurnProvider:
        if which == "cursor":
            return cursor_provider_from_config(agent, root=root)
        if which == "ollama":
            cfg = agent
            if ollama_model:
                cfg = agent.model_copy(deep=True)
                cfg.ollama.model = ollama_model
            return ollama_provider_from_config(cfg, on_progress=on_progress)
        if which == "command":
            return CommandProvider.from_local_config(root=root)
        raise ProviderNotConfiguredError(
            f"Unknown provider {which!r}. Use cursor, ollama, or command."
        )

    try:
        return _build(name)
    except Exception as primary_exc:
        if not allow_fallback or provider is not None:
            raise
        fb = (agent.fallback or "").strip().lower() or None
        if not fb or fb == name:
            raise
        try:
            return _build(fb)
        except Exception:
            raise primary_exc from None


def detect_providers(*, root: Path | None = None) -> dict[str, Any]:
    agent = load_agent_local_config(root=root)
    base = agent.ollama.base_url or "http://127.0.0.1:11434"
    exe = find_cursor_executable(agent.cursor.executable)
    ver = cursor_version(exe) if exe else None
    reachable = ollama_reachable(base)
    models = ollama_tags(base) if reachable else []
    return {
        "cursor": {
            "available": bool(exe),
            "executable": exe,
            "version": ver,
        },
        "ollama": {
            "available": reachable,
            "base_url": base,
            "models": models,
            "model_count": len(models),
        },
        "command": {
            "available": bool(agent.argv),
            "argv": list(agent.argv),
            "note": "advanced / optional",
        },
        "configured_provider": agent.provider,
        "fallback": agent.fallback,
    }


def provider_status(*, root: Path | None = None) -> dict[str, Any]:
    agent = load_agent_local_config(root=root)
    detected = detect_providers(root=root)
    name = agent.provider
    ready = False
    detail: dict[str, Any] = {}
    message = "No provider configured. Run: uv run rig agent provider setup"

    if name == "cursor":
        ready = bool(detected["cursor"]["available"])
        detail = {
            "executable": detected["cursor"]["executable"],
            "version": detected["cursor"]["version"],
            "model": agent.cursor.model or "Cursor default",
        }
        message = (
            "ready"
            if ready
            else "Cursor selected, but `agent` is not installed.\nRun: uv run rig agent provider setup"
        )
    elif name == "ollama":
        models = detected["ollama"]["models"]
        model = agent.ollama.model
        reachable = detected["ollama"]["available"]
        model_ok = bool(model) and (model in models if models else bool(model))
        ready = reachable and bool(model)
        detail = {
            "server": agent.ollama.base_url,
            "model": model,
            "model_available": model_ok if reachable else False,
            "models": models,
        }
        if not reachable:
            message = f"Ollama selected, but {agent.ollama.base_url} is not reachable."
        elif not model:
            message = "Ollama selected, but no model configured."
        else:
            message = "ready" if ready else "Ollama model not available"
    elif name == "command":
        ready = bool(agent.argv) and Path(agent.argv[0]).exists()
        detail = {"argv": list(agent.argv)}
        message = "ready" if ready else "Command provider argv missing or not found"
    elif name:
        message = f"Unknown provider {name!r}"

    return {
        "configured": bool(name) and ready,
        "provider_type": name,
        "status": "ready" if ready else "not_ready",
        "message": message,
        "detail": detail,
        "timeout_seconds": agent.timeout_seconds,
        "forwarded_environment_variable_names": list(agent.env_forward),
        "max_context_rounds": agent.max_context_rounds,
        "max_stdout_bytes": agent.max_stdout_bytes,
        "fallback": agent.fallback,
        "detected": detected,
        # legacy fields
        "executable": detail.get("executable") or (agent.argv[0] if agent.argv else None),
        "argv": list(agent.argv),
    }


def provider_test(
    *,
    root: Path | None = None,
    provider: str | None = None,
    ollama_model: str | None = None,
) -> dict[str, Any]:
    """Handshake with configured/override provider — no repository mutations."""
    prov = resolve_provider(
        root=root, provider=provider, ollama_model=ollama_model, allow_fallback=False
    )
    if hasattr(prov, "handshake"):
        turn, diag = prov.handshake()  # type: ignore[attr-defined]
    else:
        packet = {
            "schema": "music_rig.agent_packet.v1",
            "artifact": {"type": "question", "id": "Q-000"},
            "final_human_answer": "provider test handshake",
            "allowed_operation_kinds": [],
            "handshake": True,
        }
        turn, diag = prov.run_turn(packet=packet, context=[])
    return {
        "ok": True,
        "provider": getattr(prov, "provider_type", provider),
        "turn": turn.to_dict(),
        "diagnostics": diag,
    }
