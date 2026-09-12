"""Shared helpers for provider process / HTTP isolation."""

from __future__ import annotations

import os
from typing import Any


def minimal_env(*, env_forward: list[str] | None = None) -> dict[str, str]:
    env: dict[str, str] = {}
    path = os.environ.get("PATH")
    if path:
        env["PATH"] = path
    # Cursor / home tooling often needs HOME for auth store
    for key in ("HOME", "USER", "LANG", "LC_ALL"):
        if key in os.environ:
            env[key] = os.environ[key]
    for name in env_forward or []:
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def preview_bytes(data: bytes | None, limit: int) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")[:limit]


def diagnostics_base(**extra: Any) -> dict[str, Any]:
    out = {"cwd_isolated": True}
    out.update(extra)
    return out
