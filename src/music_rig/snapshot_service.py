"""Canonical YAML repository snapshots (local, gitignored under `.rig/`)."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from music_rig import __version__
from music_rig.store import DATA_DIR, ROOT, StoreError, write_text_files

Clock = Callable[[], datetime]
SNAP_ID_PREFIX = "SNAP-"
MANIFEST_NAME = "manifest.yaml"


def default_clock() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(UTC)


@dataclass(frozen=True)
class CanonicalFileRecord:
    path: str
    sha256: str


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    created_at: str
    git_commit: str | None
    git_branch: str | None
    working_tree_clean: bool | None
    canonical_files: list[CanonicalFileRecord]
    generated_docs_synchronized: bool | None
    tool_version: str

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "working_tree_clean": self.working_tree_clean,
            "canonical_files": [
                {"path": item.path, "sha256": item.sha256} for item in self.canonical_files
            ],
            "generated_docs_synchronized": self.generated_docs_synchronized,
            "tool_version": self.tool_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SnapshotManifest:
        files = [
            CanonicalFileRecord(path=str(item["path"]), sha256=str(item["sha256"]))
            for item in data.get("canonical_files") or []
        ]
        return cls(
            snapshot_id=str(data["snapshot_id"]),
            created_at=str(data["created_at"]),
            git_commit=data.get("git_commit"),
            git_branch=data.get("git_branch"),
            working_tree_clean=data.get("working_tree_clean"),
            canonical_files=files,
            generated_docs_synchronized=data.get("generated_docs_synchronized"),
            tool_version=str(data.get("tool_version") or ""),
        )


def _git_meta(root: Path | None = None) -> tuple[str | None, str | None, bool | None]:
    from music_rig.status import git_branch, git_commit_sha, git_working_tree_clean

    return (
        git_commit_sha(root=root),
        git_branch(root=root),
        git_working_tree_clean(root=root),
    )


def default_snapshots_dir(root: Path | None = None) -> Path:
    return (root or ROOT) / ".rig" / "snapshots"


def snapshot_id_for(when: datetime) -> str:
    aware = when if when.tzinfo is not None else when.astimezone()
    return f"{SNAP_ID_PREFIX}{aware.strftime('%Y%m%d-%H%M%S')}"


def discover_canonical_yaml(data_dir: Path | None = None) -> list[Path]:
    directory = data_dir or DATA_DIR
    if not directory.is_dir():
        raise StoreError(f"Missing data directory: {directory}")
    return sorted(path for path in directory.glob("*.yaml") if path.is_file())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file_streaming(source: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source.open("rb") as src, dest.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def _docs_synchronized() -> bool | None:
    try:
        from music_rig.render import check_render_sync

        stale = check_render_sync()
        return not stale
    except Exception:
        return None


def create_snapshot(
    *,
    output_dir: Path | None = None,
    root: Path | None = None,
    data_dir: Path | None = None,
    clock: Clock | None = None,
) -> SnapshotManifest:
    tick = clock or default_clock
    base = output_dir or default_snapshots_dir(root)
    when = tick()
    snap_id = snapshot_id_for(when)
    dest = base / snap_id
    if dest.exists():
        raise StoreError(f"Snapshot destination already exists: {dest}")

    files = discover_canonical_yaml(data_dir)
    if not files:
        raise StoreError("No canonical data/*.yaml files found to snapshot")

    dest.mkdir(parents=True, exist_ok=False)
    data_dest = dest / "data"
    data_dest.mkdir(parents=True, exist_ok=True)

    records: list[CanonicalFileRecord] = []
    try:
        for path in files:
            rel = f"data/{path.name}"
            digest = _copy_file_streaming(path, data_dest / path.name)
            records.append(CanonicalFileRecord(path=rel, sha256=digest))

        created_at = when.isoformat()
        commit, branch, clean = _git_meta(root)
        manifest = SnapshotManifest(
            snapshot_id=snap_id,
            created_at=created_at,
            git_commit=commit,
            git_branch=branch,
            working_tree_clean=clean,
            canonical_files=records,
            generated_docs_synchronized=_docs_synchronized(),
            tool_version=__version__,
        )
        write_text_files(
            [
                (
                    dest / MANIFEST_NAME,
                    yaml.safe_dump(
                        manifest.to_dict(),
                        sort_keys=False,
                        allow_unicode=True,
                        default_flow_style=False,
                        width=88,
                    ),
                )
            ]
        )
        return manifest
    except Exception:
        if dest.exists():
            shutil.rmtree(dest)
        raise


def list_snapshots(snapshots_dir: Path | None = None) -> list[SnapshotManifest]:
    base = snapshots_dir or default_snapshots_dir()
    if not base.exists():
        return []
    manifests: list[SnapshotManifest] = []
    for path in sorted(base.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        manifest_path = path / MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        try:
            manifests.append(load_manifest(path))
        except StoreError:
            continue
    return manifests


def resolve_snapshot_dir(
    snapshot_id: str,
    snapshots_dir: Path | None = None,
) -> Path:
    base = snapshots_dir or default_snapshots_dir()
    target = base / snapshot_id
    if not target.is_dir():
        raise StoreError(f"Unknown snapshot {snapshot_id!r}")
    return target


def load_manifest(snapshot_dir: Path) -> SnapshotManifest:
    path = snapshot_dir / MANIFEST_NAME
    if not path.is_file():
        raise StoreError(f"Missing snapshot manifest: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid snapshot manifest YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise StoreError("Snapshot manifest must be a YAML mapping")
    return SnapshotManifest.from_dict(raw)


def show_snapshot(
    snapshot_id: str,
    snapshots_dir: Path | None = None,
) -> SnapshotManifest:
    return load_manifest(resolve_snapshot_dir(snapshot_id, snapshots_dir))


def verify_snapshot(
    snapshot_id: str,
    snapshots_dir: Path | None = None,
) -> tuple[bool, list[str]]:
    directory = resolve_snapshot_dir(snapshot_id, snapshots_dir)
    manifest = load_manifest(directory)
    problems: list[str] = []
    seen: set[str] = set()
    for record in manifest.canonical_files:
        seen.add(record.path)
        file_path = directory / record.path
        if not file_path.is_file():
            problems.append(f"missing file {record.path}")
            continue
        digest = sha256_file(file_path)
        if digest != record.sha256:
            problems.append(f"hash mismatch {record.path}")
    data_dir = directory / "data"
    if data_dir.is_dir():
        for path in sorted(data_dir.glob("*.yaml")):
            rel = f"data/{path.name}"
            if rel not in seen:
                problems.append(f"unexpected file {rel}")
    return not problems, problems


def _current_file_hashes(data_dir: Path | None = None) -> dict[str, str]:
    return {f"data/{path.name}": sha256_file(path) for path in discover_canonical_yaml(data_dir)}


def _manifest_hashes(manifest: SnapshotManifest) -> dict[str, str]:
    return {item.path: item.sha256 for item in manifest.canonical_files}


def diff_snapshots(
    left_id: str,
    right_id: str,
    *,
    snapshots_dir: Path | None = None,
    data_dir: Path | None = None,
) -> dict[str, list[str]]:
    """Diff two snapshots, or snapshot vs live `current` tree."""
    left = load_manifest(resolve_snapshot_dir(left_id, snapshots_dir))
    left_map = _manifest_hashes(left)
    if right_id == "current":
        right_map = _current_file_hashes(data_dir)
        right_label = "current"
    else:
        right = load_manifest(resolve_snapshot_dir(right_id, snapshots_dir))
        right_map = _manifest_hashes(right)
        right_label = right.snapshot_id

    only_left = sorted(set(left_map) - set(right_map))
    only_right = sorted(set(right_map) - set(left_map))
    changed = sorted(
        path for path in set(left_map) & set(right_map) if left_map[path] != right_map[path]
    )
    return {
        "left": left.snapshot_id,
        "right": right_label,
        "only_left": only_left,
        "only_right": only_right,
        "changed": changed,
    }
