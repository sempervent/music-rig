"""Load and save canonical planning YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from music_rig.models import InboxDocument, TodoDocument, WishlistDocument

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
TODO_PATH = DATA_DIR / "todo.yaml"
WISHLIST_PATH = DATA_DIR / "wishlist.yaml"
INBOX_PATH = DATA_DIR / "inbox.yaml"
DOCS_TODO_PATH = ROOT / "docs" / "todo.md"
DOCS_WISHLIST_PATH = ROOT / "docs" / "wishlist.md"

EXISTING_YAML = (
    DATA_DIR / "channel-map.yaml",
    DATA_DIR / "inventory.yaml",
    DATA_DIR / "patchbays.yaml",
    DATA_DIR / "routing.yaml",
)


class StoreError(Exception):
    """User-facing data store error."""


def _dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _load_mapping(path: Path, label: str) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing {label} data file: {path}") from exc
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise StoreError(f"{path} must contain a YAML mapping")
    return raw


def load_todo(path: Path | None = None) -> TodoDocument:
    target = path or TODO_PATH
    raw = _load_mapping(target, "TODO")
    try:
        return TodoDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"TODO schema validation failed: {exc}") from exc


def load_wishlist(path: Path | None = None) -> WishlistDocument:
    target = path or WISHLIST_PATH
    raw = _load_mapping(target, "wishlist")
    try:
        return WishlistDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Wishlist schema validation failed: {exc}") from exc


def load_inbox(path: Path | None = None) -> InboxDocument:
    target = path or INBOX_PATH
    if not target.exists():
        return InboxDocument(items=[])
    raw = _load_mapping(target, "inbox")
    try:
        return InboxDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Inbox schema validation failed: {exc}") from exc


def save_todo(doc: TodoDocument, path: Path | None = None) -> None:
    target = path or TODO_PATH
    TodoDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json")))


def save_wishlist(doc: WishlistDocument, path: Path | None = None) -> None:
    target = path or WISHLIST_PATH
    WishlistDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json")))


def save_inbox(doc: InboxDocument, path: Path | None = None) -> None:
    target = path or INBOX_PATH
    InboxDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json")))


def write_documents(
    *,
    todo: TodoDocument | None = None,
    wishlist: WishlistDocument | None = None,
    inbox: InboxDocument | None = None,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    inbox_path: Path | None = None,
) -> None:
    """Validate all provided docs, then write them. Fail before any write on error."""
    payloads: list[tuple[Path, str]] = []
    if todo is not None:
        TodoDocument.model_validate(todo.model_dump())
        payloads.append(
            (todo_path or TODO_PATH, _dump_yaml(todo.model_dump(mode="json")))
        )
    if wishlist is not None:
        WishlistDocument.model_validate(wishlist.model_dump())
        payloads.append(
            (
                wishlist_path or WISHLIST_PATH,
                _dump_yaml(wishlist.model_dump(mode="json")),
            )
        )
    if inbox is not None:
        InboxDocument.model_validate(inbox.model_dump())
        payloads.append(
            (inbox_path or INBOX_PATH, _dump_yaml(inbox.model_dump(mode="json")))
        )
    for path, text in payloads:
        _atomic_write(path, text)


def parse_existing_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing YAML file: {path}") from exc
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {path}: {exc}") from exc
