"""Render RigOperation to human/CLI forms — never the reverse."""

from __future__ import annotations

import shlex
from typing import Any

from music_rig.reconciliation.operations import RigOperation


def render_cli(
    operation: RigOperation,
    *,
    prefix: str = "uv run rig",
) -> str:
    """Render a shell-safe CLI suggestion for humans/docs."""
    argv = render_argv(operation, prefix=prefix)
    return " ".join(shlex.quote(part) for part in argv)


def render_argv(operation: RigOperation, *, prefix: str = "uv run rig") -> list[str]:
    """Build argv for display; not used for subprocess execution."""
    parts = [p for p in prefix.split() if p]
    kind = operation.kind
    args = operation.args
    if kind == "patchbay.set_model":
        parts += [
            "current",
            "patchbay",
            "set-model",
            str(args["bay_id"]),
            str(args["model"]),
        ]
        if args.get("question_id"):
            parts += ["--question", str(args["question_id"])]
        if args.get("yes"):
            parts.append("--yes")
    elif kind == "channels.set_source":
        parts += [
            "current",
            "channels",
            "set-source",
            str(args["device"]),
            str(args["channel"]),
            str(args["source"]),
        ]
        if args.get("question_id"):
            parts += ["--question", str(args["question_id"])]
        if args.get("yes"):
            parts.append("--yes")
    elif kind == "question.finalize_manual":
        parts += [
            "reconcile",
            "finalize",
            "question",
            str(args["question_id"]),
            "--confirm-current-reconciled",
            "--note",
            str(args.get("note") or "agent-assisted reconciliation"),
            "--complete-linked-todos",
            "--confirm-dod",
            "--yes",
            "--json",
        ]
    elif kind == "question.resolve":
        parts += ["question", "resolve", str(args["question_id"])]
    elif kind == "inspect.question":
        parts += ["question", "show", str(args["question_id"]), "--json"]
    elif kind == "inspect.patchbay":
        parts += ["patchbay", "show", str(args["bay_id"])]
    else:
        parts += [operation.namespace, operation.action]
        for key, value in sorted(args.items()):
            if isinstance(value, bool):
                if value:
                    parts.append(f"--{key.replace('_', '-')}")
            else:
                parts += [f"--{key.replace('_', '-')}", str(value)]
    return parts


def render_human(operation: RigOperation) -> str:
    desc = operation.description or operation.kind
    return f"{operation.kind}: {desc}"


def operation_json_view(
    operation: RigOperation, *, prefix: str = "uv run rig"
) -> dict[str, Any]:
    return {
        "operation": operation.to_dict(),
        "rendered_cli": render_cli(operation, prefix=prefix),
    }
