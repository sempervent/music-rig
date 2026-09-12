"""Ollama local HTTP provider — structured AgentTurn via /api/chat."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from music_rig.agent.errors import (
    AgentError,
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from music_rig.agent.prompt import build_handshake_prompt, build_planner_prompt
from music_rig.agent.providers_util import diagnostics_base
from music_rig.agent.turns import AgentTurn, agent_turn_json_schema


class OllamaUnavailableError(AgentError):
    code = "OLLAMA_UNAVAILABLE"


@dataclass
class OllamaProvider:
    base_url: str = "http://127.0.0.1:11434"
    model: str = ""
    timeout_seconds: int = 120
    max_stdout_bytes: int = 1_000_000
    temperature: float = 0.0

    @property
    def provider_type(self) -> str:
        return "ollama"

    def _url(self, path: str) -> str:
        base = self.base_url.rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    def run_turn(
        self,
        *,
        packet: dict[str, Any],
        context: list[dict[str, Any]] | None = None,
    ) -> tuple[AgentTurn, dict[str, Any]]:
        prompt = build_planner_prompt(packet=packet, context=context)
        return self._chat(prompt)

    def handshake(self) -> tuple[AgentTurn, dict[str, Any]]:
        return self._chat(build_handshake_prompt())

    def _chat(self, prompt: str) -> tuple[AgentTurn, dict[str, Any]]:
        if not self.model:
            raise ProviderNotConfiguredError(
                "Ollama selected, but no model configured.\n"
                "Run: uv run rig agent provider use ollama --model <model>"
            )
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a music-rig reconciliation planner. "
                        "Return only JSON matching the provided schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": agent_turn_json_schema(),
            "options": {"temperature": self.temperature},
        }
        diagnostics = diagnostics_base(
            provider="ollama",
            base_url=self.base_url,
            model=self.model,
            endpoint="/api/chat",
            stream=False,
            timeout_seconds=self.timeout_seconds,
            format_schema="AgentTurn.model_json_schema()",
        )
        raw = self._post_json("/api/chat", body, diagnostics=diagnostics)
        message = (raw.get("message") or {}) if isinstance(raw, dict) else {}
        content = message.get("content")
        if content is None and isinstance(raw.get("response"), str):
            content = raw["response"]
        if isinstance(content, dict):
            turn_raw = content
        elif isinstance(content, str):
            try:
                turn_raw = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ProviderInvalidResponseError(
                    f"Ollama content is not JSON: {exc}"
                ) from exc
        else:
            raise ProviderInvalidResponseError("Ollama response missing message.content")
        try:
            turn = AgentTurn.from_dict(turn_raw)
        except Exception as exc:
            raise ProviderInvalidResponseError(
                f"Ollama AgentTurn invalid: {exc}"
            ) from exc
        return turn, diagnostics

    def _post_json(
        self, path: str, body: dict[str, Any], *, diagnostics: dict[str, Any]
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._url(path),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                blob = resp.read()
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Ollama timed out after {self.timeout_seconds}s"
            ) from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            diagnostics["http_status"] = exc.code
            diagnostics["http_error"] = detail
            if exc.code == 404:
                raise ProviderInvalidResponseError(
                    f"Ollama model unavailable or endpoint missing: {detail}"
                ) from exc
            raise ProviderInvalidResponseError(
                f"Ollama HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise OllamaUnavailableError(
                f"Ollama not reachable at {self.base_url}: {exc.reason}"
            ) from exc

        diagnostics["stdout_bytes"] = len(blob)
        if len(blob) > self.max_stdout_bytes:
            raise ProviderInvalidResponseError(
                f"Ollama response exceeded {self.max_stdout_bytes} bytes"
            )
        try:
            parsed = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(
                f"Ollama returned non-JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderInvalidResponseError("Ollama JSON must be an object")
        return parsed


def ollama_tags(base_url: str = "http://127.0.0.1:11434", *, timeout: float = 3.0) -> list[str]:
    url = urljoin(base_url.rstrip("/") + "/", "api/tags")
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    models = data.get("models") or []
    names: list[str] = []
    for item in models:
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return sorted(names)


def ollama_reachable(base_url: str = "http://127.0.0.1:11434", *, timeout: float = 2.0) -> bool:
    url = urljoin(base_url.rstrip("/") + "/", "api/tags")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def ollama_provider_from_config(agent_cfg) -> OllamaProvider:
    ollama_cfg = getattr(agent_cfg, "ollama", None)
    base = getattr(ollama_cfg, "base_url", None) or "http://127.0.0.1:11434"
    model = getattr(ollama_cfg, "model", None) or ""
    if not model:
        raise ProviderNotConfiguredError(
            "Ollama selected, but no model configured.\n"
            "Run: uv run rig agent provider use ollama --model <model>"
        )
    if not ollama_reachable(base):
        raise OllamaUnavailableError(
            f"Ollama selected, but {base} is not reachable.\n"
            "Start Ollama, then re-run provider setup."
        )
    return OllamaProvider(
        base_url=base,
        model=model,
        timeout_seconds=int(agent_cfg.timeout_seconds),
        max_stdout_bytes=int(agent_cfg.max_stdout_bytes),
    )
