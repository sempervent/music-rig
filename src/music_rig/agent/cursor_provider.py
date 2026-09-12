"""Cursor Agent CLI provider — read-only planner via --mode=ask."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from music_rig.agent.errors import (
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from music_rig.agent.prompt import build_handshake_prompt, build_planner_prompt
from music_rig.agent.providers_util import diagnostics_base, minimal_env, preview_bytes
from music_rig.agent.turns import AgentTurn


def find_cursor_executable(preferred: str | None = None) -> str | None:
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(["agent", "cursor-agent"])
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def cursor_version(executable: str) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603
            [executable, "--version"],
            capture_output=True,
            timeout=10,
            shell=False,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or completed.stderr or "").strip() or None


@dataclass
class CursorProvider:
    executable: str = "agent"
    model: str | None = None
    timeout_seconds: int = 120
    env_forward: list[str] = field(default_factory=list)
    max_stdout_bytes: int = 1_000_000
    max_stderr_bytes: int = 100_000

    @property
    def provider_type(self) -> str:
        return "cursor"

    def build_argv(self, prompt: str) -> list[str]:
        argv = [
            self.executable,
            "-p",
            "--mode=ask",
            "--trust",
            "--output-format",
            "json",
        ]
        if self.model:
            argv.extend(["--model", self.model])
        argv.append(prompt)
        return argv

    def run_turn(
        self,
        *,
        packet: dict[str, Any],
        context: list[dict[str, Any]] | None = None,
    ) -> tuple[AgentTurn, dict[str, Any]]:
        # Cursor has no structured format= — keep schema in the prompt.
        prompt = build_planner_prompt(
            packet=packet,
            context=context,
            include_schema=True,
            compact_packet=True,
        )
        return self._invoke(prompt)

    def handshake(self) -> tuple[AgentTurn, dict[str, Any]]:
        return self._invoke(build_handshake_prompt(include_schema=True))

    def _invoke(self, prompt: str) -> tuple[AgentTurn, dict[str, Any]]:
        argv = self.build_argv(prompt)
        # Never pass repository --workspace; cwd is a neutral temp dir.
        diagnostics = diagnostics_base(
            provider="cursor",
            argv=[*argv[:-1], "<prompt>"],
            executable=self.executable,
            model=self.model,
            mode="ask",
            timeout_seconds=self.timeout_seconds,
            forwarded_env_names=list(self.env_forward),
            workspace_flag=False,
        )
        with tempfile.TemporaryDirectory(prefix="rig-cursor-") as tmp:
            try:
                completed = subprocess.run(  # noqa: S603
                    argv,
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
                    f"Cursor provider timed out after {self.timeout_seconds}s"
                ) from exc

        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        diagnostics["exit_code"] = completed.returncode
        diagnostics["stdout_bytes"] = len(stdout)
        diagnostics["stderr_bytes"] = len(stderr)
        diagnostics["stderr_preview"] = preview_bytes(stderr, self.max_stderr_bytes)
        diagnostics["version"] = cursor_version(self.executable)

        if len(stdout) > self.max_stdout_bytes:
            raise ProviderInvalidResponseError(
                f"Cursor stdout exceeded {self.max_stdout_bytes} bytes"
            )
        if completed.returncode != 0:
            raise ProviderInvalidResponseError(f"Cursor exited {completed.returncode}")
        try:
            envelope = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(f"Cursor returned non-JSON stdout: {exc}") from exc
        turn = parse_cursor_envelope(envelope)
        return turn, diagnostics


def parse_cursor_envelope(envelope: dict[str, Any]) -> AgentTurn:
    """Parse Cursor --output-format json envelope into AgentTurn."""
    if not isinstance(envelope, dict):
        raise ProviderInvalidResponseError("Cursor envelope must be an object")
    if envelope.get("is_error") is True:
        raise ProviderInvalidResponseError(
            f"Cursor reported error: {envelope.get('result') or envelope}"
        )
    # Envelope: {"type":"result","result":"<json-string or object>", ...}
    if envelope.get("type") == "result" or "result" in envelope:
        payload = envelope.get("result")
        if isinstance(payload, str):
            try:
                raw = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ProviderInvalidResponseError(
                    f"Cursor result is not JSON AgentTurn: {exc}"
                ) from exc
        elif isinstance(payload, dict):
            raw = payload
        else:
            raise ProviderInvalidResponseError("Cursor result must be a JSON object or JSON string")
        try:
            return AgentTurn.from_dict(raw)
        except Exception as exc:
            raise ProviderInvalidResponseError(f"Cursor AgentTurn invalid: {exc}") from exc

    # Already a bare AgentTurn
    if "kind" in envelope:
        try:
            return AgentTurn.from_dict(envelope)
        except Exception as exc:
            raise ProviderInvalidResponseError(f"Cursor AgentTurn invalid: {exc}") from exc

    raise ProviderInvalidResponseError("Unrecognized Cursor JSON envelope")


def cursor_provider_from_config(agent_cfg, *, root: Path | None = None) -> CursorProvider:
    exe = find_cursor_executable(
        getattr(getattr(agent_cfg, "cursor", None), "executable", None) or "agent"
    )
    if not exe:
        raise ProviderNotConfiguredError(
            "Cursor selected, but `agent` is not installed.\nRun: uv run rig agent provider setup"
        )
    cursor_cfg = getattr(agent_cfg, "cursor", None)
    return CursorProvider(
        executable=exe,
        model=getattr(cursor_cfg, "model", None),
        timeout_seconds=int(agent_cfg.timeout_seconds),
        env_forward=list(agent_cfg.env_forward),
        max_stdout_bytes=int(agent_cfg.max_stdout_bytes),
    )
