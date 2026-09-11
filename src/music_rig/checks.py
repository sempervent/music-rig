"""Repository consistency checks for Stage 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from music_rig.render import check_render_sync
from music_rig.store import (
    EXISTING_YAML,
    StoreError,
    load_todo,
    load_wishlist,
    parse_existing_yaml,
)


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def run_checks(
    *,
    root: Path | None = None,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        load_todo(todo_path)
    except StoreError as exc:
        errors.append(str(exc))

    try:
        load_wishlist(wishlist_path)
    except StoreError as exc:
        errors.append(str(exc))

    try:
        stale = check_render_sync(
            todo_path=todo_path,
            wishlist_path=wishlist_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
        )
        for path in stale:
            errors.append(
                f"{path} is out of date with canonical YAML\nRun: uv run rig render"
            )
    except StoreError as exc:
        errors.append(str(exc))

    for path in EXISTING_YAML:
        try:
            parse_existing_yaml(path)
        except StoreError as exc:
            errors.append(str(exc))

    return CheckResult(ok=not errors, errors=errors, warnings=warnings)
