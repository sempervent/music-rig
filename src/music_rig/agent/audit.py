"""Local audit records for agent provider runs (.rig/agent-runs/)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from music_rig.store import ROOT

AGENT_RUNS_DIRNAME = "agent-runs"


def agent_runs_dir(*, root: Path | None = None) -> Path:
    return (root or ROOT) / ".rig" / AGENT_RUNS_DIRNAME


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def write_agent_run(
    record: dict[str, Any],
    *,
    root: Path | None = None,
    run_id: str | None = None,
) -> Path:
    """Write a redacted agent-run JSON under .rig/agent-runs/ (gitignored)."""
    rid = run_id or new_run_id()
    directory = agent_runs_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{rid}.json"
    safe = dict(record)
    safe["run_id"] = rid
    safe.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    # Never persist env values
    if "env" in safe:
        safe.pop("env", None)
    if "diagnostics" in safe and isinstance(safe["diagnostics"], dict):
        diag = dict(safe["diagnostics"])
        diag.pop("env", None)
        # Keep names only
        if "forwarded_env_names" not in diag and "env_forward" in diag:
            diag["forwarded_env_names"] = diag.pop("env_forward")
        safe["diagnostics"] = diag
    path.write_text(json.dumps(safe, indent=2, default=str) + "\n", encoding="utf-8")
    return path
