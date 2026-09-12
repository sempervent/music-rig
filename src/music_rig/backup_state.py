"""Backup plan status and package creation from data/backups.yaml."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from music_rig import __version__
from music_rig.local_config import has_any_configured_path, load_local_config, resolve_path
from music_rig.models import (
    BACKUP_LOCATOR_KEYS,
    BackupImportance,
    BackupItem,
    BackupKind,
    BackupsDocument,
    LocalConfig,
)
from music_rig.snapshot_service import create_snapshot
from music_rig.store import (
    BACKUPS_PATH,
    DATA_DIR,
    StoreError,
    load_todo,
    parse_existing_yaml,
    write_text_files,
)

Clock = Callable[[], datetime]
BACKUP_ID_PREFIX = "BACKUP-"
MANIFEST_NAME = "manifest.yaml"


def default_clock() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(UTC)


class BackupReadiness(StrEnum):
    READY = "READY"
    MISSING_PATH = "MISSING PATH"
    MANUAL = "MANUAL"
    NOT_CONFIGURED = "NOT CONFIGURED"
    UNKNOWN = "UNKNOWN"


class BackupPackageResult(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass
class BackupItemStatus:
    item: BackupItem
    readiness: BackupReadiness
    detail: str = ""


@dataclass
class BackupItemOutcome:
    item_id: str
    status: str
    detail: str = ""


@dataclass
class BackupPackageReport:
    backup_id: str
    result: BackupPackageResult
    output_dir: Path
    snapshot_id: str | None = None
    outcomes: list[BackupItemOutcome] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_raw(path: Path | None = None) -> dict:
    target = path or BACKUPS_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_document(path: Path | None = None) -> BackupsDocument:
    raw = load_raw(path)
    try:
        return BackupsDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Backups schema validation failed: {exc}") from exc


def validate_backups_doc(
    data: dict,
    *,
    todo_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        doc = BackupsDocument.model_validate(data)
    except Exception as exc:
        return [f"schema: {exc}"]

    known_todos = set()
    try:
        known_todos = set(load_todo(todo_path).task_map())
    except StoreError as exc:
        errors.append(str(exc))

    for item in doc.items:
        if item.locator_key is not None and item.locator_key not in BACKUP_LOCATOR_KEYS:
            errors.append(f"{item.id}: unknown locator_key {item.locator_key!r}")
        for ref in item.related_todos:
            if known_todos and ref not in known_todos:
                errors.append(f"{item.id}: unknown TODO {ref}")
    return errors


def item_readiness(
    item: BackupItem,
    config: LocalConfig | None,
) -> BackupItemStatus:
    if item.kind == BackupKind.REPOSITORY_STATE:
        return BackupItemStatus(item, BackupReadiness.READY, "automatic via rig snapshot")
    if item.kind == BackupKind.MANUAL_EXPORT:
        if item.locator_key:
            path = resolve_path(item.locator_key, config)
            if path is not None:
                if path.exists():
                    return BackupItemStatus(item, BackupReadiness.READY, "export path configured")
                return BackupItemStatus(
                    item, BackupReadiness.MISSING_PATH, "configured path missing"
                )
        return BackupItemStatus(item, BackupReadiness.MANUAL, "manual export required")
    if item.kind in {BackupKind.FILE_COPY, BackupKind.DIRECTORY_COPY}:
        if not item.locator_key:
            return BackupItemStatus(item, BackupReadiness.NOT_CONFIGURED, "no locator_key")
        path = resolve_path(item.locator_key, config)
        if path is None:
            return BackupItemStatus(
                item, BackupReadiness.NOT_CONFIGURED, "locator not set in local config"
            )
        if not path.exists():
            return BackupItemStatus(
                item, BackupReadiness.MISSING_PATH, "configured path does not exist"
            )
        return BackupItemStatus(item, BackupReadiness.READY, "path present")
    return BackupItemStatus(item, BackupReadiness.UNKNOWN, "kind unknown")


def plan_items(path: Path | None = None) -> list[BackupItem]:
    return list(load_document(path).items)


def status_items(
    *,
    backups_path: Path | None = None,
    local_config_path: Path | None = None,
    root: Path | None = None,
) -> list[BackupItemStatus]:
    doc = load_document(backups_path)
    config = load_local_config(local_config_path, root=root)
    return [item_readiness(item, config) for item in doc.items]


def backup_id_for(when: datetime) -> str:
    aware = when if when.tzinfo is not None else when.astimezone()
    return f"{BACKUP_ID_PREFIX}{aware.strftime('%Y%m%d-%H%M%S')}"


def _safe_copy_file(source: Path, dest: Path) -> None:
    if dest.exists():
        raise StoreError(f"Refusing to overwrite existing file: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        # Copy target file content once; do not recurse into link trees.
        target = source.resolve(strict=True)
        if not target.is_file():
            raise StoreError(f"Symlink {source} does not resolve to a regular file")
        shutil.copyfile(target, dest, follow_symlinks=True)
        return
    if not source.is_file():
        raise StoreError(f"Expected a file at {source}")
    shutil.copyfile(source, dest)


def _safe_copy_directory(source: Path, dest: Path) -> None:
    if dest.exists():
        raise StoreError(f"Refusing to overwrite existing directory: {dest}")
    if source.is_symlink():
        raise StoreError(
            f"Refusing to follow directory symlink {source}; "
            "configure a real directory or export manually"
        )
    if not source.is_dir():
        raise StoreError(f"Expected a directory at {source}")

    def _ignore_symlinks(directory: str, names: list[str]) -> set[str]:
        skipped: set[str] = set()
        base = Path(directory)
        for name in names:
            candidate = base / name
            if candidate.is_symlink() and candidate.is_dir():
                skipped.add(name)
        return skipped

    shutil.copytree(source, dest, symlinks=False, ignore=_ignore_symlinks)


def create_backup_package(
    *,
    output: Path | None = None,
    backups_path: Path | None = None,
    local_config_path: Path | None = None,
    root: Path | None = None,
    data_dir: Path | None = None,
    clock: Clock | None = None,
) -> BackupPackageReport:
    tick = clock or default_clock
    config = load_local_config(local_config_path, root=root)
    if output is not None:
        package_root = Path(output)
    else:
        configured = resolve_path("backup_root", config)
        if configured is None:
            raise StoreError(
                "Backup output required: pass --output PATH or set "
                "paths.backup_root in .rig.local.yaml"
            )
        package_root = configured

    when = tick()
    backup_id = backup_id_for(when)
    dest = package_root / backup_id
    if dest.exists():
        raise StoreError(f"Backup destination already exists: {dest}")

    dest.mkdir(parents=True, exist_ok=False)
    outcomes: list[BackupItemOutcome] = []
    errors: list[str] = []
    snapshot_id: str | None = None
    critical_failed = False

    try:
        snap = create_snapshot(
            output_dir=dest / "snapshot",
            root=root,
            data_dir=data_dir or DATA_DIR,
            clock=tick,
        )
        # create_snapshot nests under SNAP-id; re-home to dest/snapshot/SNAP-*
        # Actually create_snapshot creates output_dir/SNAP-id. We passed dest/snapshot
        # so result is dest/snapshot/SNAP-*. That's fine.
        snapshot_id = snap.snapshot_id
        outcomes.append(
            BackupItemOutcome(
                "repository-state",
                "COPIED",
                f"embedded snapshot {snapshot_id}",
            )
        )
    except Exception as exc:
        critical_failed = True
        errors.append(f"repository-state failed: {exc}")
        outcomes.append(BackupItemOutcome("repository-state", "FAILED", str(exc)))

    doc = load_document(backups_path)
    for item in doc.items:
        if item.id == "repository-state":
            continue
        readiness = item_readiness(item, config)
        if item.kind == BackupKind.MANUAL_EXPORT:
            if readiness.readiness == BackupReadiness.READY and item.locator_key:
                path = resolve_path(item.locator_key, config)
                assert path is not None
                try:
                    target = dest / "exports" / item.id
                    if path.is_dir():
                        _safe_copy_directory(path, target)
                    else:
                        _safe_copy_file(path, target / path.name)
                    outcomes.append(BackupItemOutcome(item.id, "COPIED", "export path copied"))
                except Exception as exc:
                    outcomes.append(BackupItemOutcome(item.id, "FAILED", str(exc)))
                    errors.append(f"{item.id}: {exc}")
                    if item.importance == BackupImportance.CRITICAL:
                        critical_failed = True
            else:
                outcomes.append(
                    BackupItemOutcome(
                        item.id,
                        "MANUAL",
                        readiness.detail or "manual export required",
                    )
                )
            continue

        if item.kind in {BackupKind.FILE_COPY, BackupKind.DIRECTORY_COPY}:
            if readiness.readiness != BackupReadiness.READY:
                outcomes.append(
                    BackupItemOutcome(
                        item.id,
                        readiness.readiness.value,
                        readiness.detail,
                    )
                )
                if item.importance == BackupImportance.CRITICAL:
                    # Missing critical copy is not COMPLETE; mark partial unless
                    # repository already failed.
                    if readiness.readiness == BackupReadiness.MISSING_PATH:
                        errors.append(f"{item.id}: {readiness.detail}")
                continue
            path = resolve_path(item.locator_key or "", config)
            assert path is not None
            try:
                target_dir = dest / "copies" / item.id
                if item.kind == BackupKind.DIRECTORY_COPY or path.is_dir():
                    if path.is_symlink() and path.is_dir():
                        raise StoreError(f"Refusing to follow directory symlink for {item.id}")
                    if path.is_dir():
                        _safe_copy_directory(path, target_dir)
                    else:
                        _safe_copy_file(path, target_dir / path.name)
                else:
                    _safe_copy_file(path, target_dir / path.name)
                outcomes.append(BackupItemOutcome(item.id, "COPIED", "copied from local path"))
            except Exception as exc:
                outcomes.append(BackupItemOutcome(item.id, "FAILED", str(exc)))
                errors.append(f"{item.id}: {exc}")
                if item.importance == BackupImportance.CRITICAL:
                    critical_failed = True
            continue

        outcomes.append(BackupItemOutcome(item.id, "UNKNOWN", readiness.detail or "skipped"))

    if critical_failed or snapshot_id is None:
        result = BackupPackageResult.FAILED
    elif any(
        outcome.status
        in {
            BackupReadiness.MANUAL.value,
            BackupReadiness.NOT_CONFIGURED.value,
            BackupReadiness.MISSING_PATH.value,
            BackupReadiness.UNKNOWN.value,
            "FAILED",
            "MANUAL",
        }
        for outcome in outcomes
        if outcome.item_id != "repository-state"
    ):
        result = BackupPackageResult.PARTIAL
    else:
        result = BackupPackageResult.COMPLETE

    manifest = {
        "backup_id": backup_id,
        "created_at": when.isoformat(),
        "result": result.value,
        "snapshot_id": snapshot_id,
        "tool_version": __version__,
        "local_config_present": load_local_config(local_config_path, root=root) is not None,
        "configured_paths_present": has_any_configured_path(config),
        "outcomes": [
            {"item_id": o.item_id, "status": o.status, "detail": o.detail} for o in outcomes
        ],
        "errors": errors,
    }
    write_text_files(
        [
            (
                dest / MANIFEST_NAME,
                yaml.safe_dump(
                    manifest,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                    width=88,
                ),
            )
        ]
    )
    return BackupPackageReport(
        backup_id=backup_id,
        result=result,
        output_dir=dest,
        snapshot_id=snapshot_id,
        outcomes=outcomes,
        errors=errors,
    )
