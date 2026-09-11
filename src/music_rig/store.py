"""Load and save canonical planning YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from music_rig.models import TodoDocument, WishlistDocument

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
TODO_PATH = DATA_DIR / "todo.yaml"
WISHLIST_PATH = DATA_DIR / "wishlist.yaml"
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


def load_todo(path: Path | None = None) -> TodoDocument:
    target = path or TODO_PATH
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing TODO data file: {target}") from exc
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {target}: {exc}") from exc
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    try:
        return TodoDocument.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise StoreError(f"TODO schema validation failed: {exc}") from exc


def load_wishlist(path: Path | None = None) -> WishlistDocument:
    target = path or WISHLIST_PATH
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing wishlist data file: {target}") from exc
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {target}: {exc}") from exc
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    try:
        return WishlistDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Wishlist schema validation failed: {exc}") from exc


def save_todo(doc: TodoDocument, path: Path | None = None) -> None:
    target = path or TODO_PATH
    # Re-validate before write
    TodoDocument.model_validate(doc.model_dump())
    payload = doc.model_dump(mode="json")
    _atomic_write(target, _dump_yaml(payload))


def save_wishlist(doc: WishlistDocument, path: Path | None = None) -> None:
    target = path or WISHLIST_PATH
    WishlistDocument.model_validate(doc.model_dump())
    payload = doc.model_dump(mode="json")
    _atomic_write(target, _dump_yaml(payload))


def parse_existing_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing YAML file: {path}") from exc
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {path}: {exc}") from exc
