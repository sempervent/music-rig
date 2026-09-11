"""Load and save canonical planning YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from music_rig.models import (
    ChangesDocument,
    InboxDocument,
    InventoryDocument,
    MidiDocument,
    OpenQuestionsDocument,
    RoutingDocument,
    SessionLog,
    TodoDocument,
    WishlistDocument,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
TODO_PATH = DATA_DIR / "todo.yaml"
WISHLIST_PATH = DATA_DIR / "wishlist.yaml"
INBOX_PATH = DATA_DIR / "inbox.yaml"
CHANGES_PATH = DATA_DIR / "changes.yaml"
QUESTIONS_PATH = DATA_DIR / "open-questions.yaml"
SESSIONS_DIR = DATA_DIR / "sessions"
CHANNEL_MAP_PATH = DATA_DIR / "channel-map.yaml"
PATCHBAYS_PATH = DATA_DIR / "patchbays.yaml"
ROUTING_PATH = DATA_DIR / "routing.yaml"
INVENTORY_PATH = DATA_DIR / "inventory.yaml"
MIDI_PATH = DATA_DIR / "midi.yaml"
DOCS_TODO_PATH = ROOT / "docs" / "todo.md"
DOCS_WISHLIST_PATH = ROOT / "docs" / "wishlist.md"
DOCS_QUESTIONS_PATH = ROOT / "docs" / "open-questions.md"
DOCS_PATCHBAYS_PATH = ROOT / "docs" / "patchbays.md"
DOCS_TASCAM_PATH = ROOT / "docs" / "tascam-channel-map.md"
DOCS_ALESIS_PATH = ROOT / "docs" / "alesis-mixer-map.md"
DOCS_ROUTING_PATH = ROOT / "docs" / "current-routing.md"
DOCS_PEDAL_CHAINS_PATH = ROOT / "docs" / "pedal-chains.md"
DOCS_INVENTORY_PATH = ROOT / "docs" / "inventory.md"
DOCS_MIDI_TOPOLOGY_PATH = ROOT / "docs" / "midi-topology.md"
DOCS_MIDI_CLOCK_PATH = ROOT / "docs" / "midi-clock.md"
DIAGRAM_PATCHBAYS_PATH = ROOT / "diagrams" / "patchbays.mmd"
DIAGRAM_TASCAM_PATH = ROOT / "diagrams" / "tascam-channel-map.mmd"
DIAGRAM_AUX_LOOP_PATH = ROOT / "diagrams" / "aux-send-loop.mmd"
DIAGRAM_MIDI_TOPOLOGY_PATH = ROOT / "diagrams" / "midi-topology.mmd"

EXISTING_YAML = (
    CHANNEL_MAP_PATH,
    INVENTORY_PATH,
    PATCHBAYS_PATH,
    ROUTING_PATH,
    MIDI_PATH,
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


def write_text_files(payloads: list[tuple[Path, str]]) -> None:
    """Stage all temps then replace. Clean up temps on failure."""
    if not payloads:
        return
    staged: list[tuple[Path, Path]] = []
    try:
        for path, text in payloads:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            staged.append((tmp, path))
        for tmp, path in staged:
            tmp.replace(path)
            staged = [(t, p) for t, p in staged if t != tmp]
    except Exception:
        for tmp, _path in staged:
            if tmp.exists():
                tmp.unlink()
        raise


def _atomic_write(path: Path, text: str) -> None:
    write_text_files([(path, text)])


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


def load_changes(path: Path | None = None) -> ChangesDocument:
    target = path or CHANGES_PATH
    if not target.exists():
        return ChangesDocument(items=[])
    raw = _load_mapping(target, "changes")
    try:
        return ChangesDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Changes schema validation failed: {exc}") from exc


def save_changes(doc: ChangesDocument, path: Path | None = None) -> None:
    target = path or CHANGES_PATH
    ChangesDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json")))


def load_questions(path: Path | None = None) -> OpenQuestionsDocument:
    target = path or QUESTIONS_PATH
    raw = _load_mapping(target, "open-questions")
    try:
        return OpenQuestionsDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Open questions schema validation failed: {exc}") from exc


def save_questions(doc: OpenQuestionsDocument, path: Path | None = None) -> None:
    target = path or QUESTIONS_PATH
    OpenQuestionsDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json")))


def load_routing(path: Path | None = None) -> RoutingDocument:
    target = path or ROUTING_PATH
    raw = _load_mapping(target, "routing")
    try:
        return RoutingDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Routing schema validation failed: {exc}") from exc


def load_inventory(path: Path | None = None) -> InventoryDocument:
    target = path or INVENTORY_PATH
    raw = _load_mapping(target, "inventory")
    try:
        return InventoryDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Inventory schema validation failed: {exc}") from exc


def save_inventory(doc: InventoryDocument, path: Path | None = None) -> None:
    target = path or INVENTORY_PATH
    InventoryDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json", exclude_none=True)))


def load_midi(path: Path | None = None) -> MidiDocument:
    target = path or MIDI_PATH
    raw = _load_mapping(target, "MIDI")
    try:
        return MidiDocument.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"MIDI schema validation failed: {exc}") from exc


def save_midi(doc: MidiDocument, path: Path | None = None) -> None:
    target = path or MIDI_PATH
    MidiDocument.model_validate(doc.model_dump())
    _atomic_write(target, _dump_yaml(doc.model_dump(mode="json", exclude_none=True)))


def session_path(session_id: str, sessions_dir: Path | None = None) -> Path:
    return (sessions_dir or SESSIONS_DIR) / f"{session_id}.yaml"


def load_session(session_id: str, sessions_dir: Path | None = None) -> SessionLog:
    path = session_path(session_id, sessions_dir)
    raw = _load_mapping(path, "session")
    try:
        return SessionLog.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Session schema validation failed: {exc}") from exc


def save_session(session: SessionLog, sessions_dir: Path | None = None) -> Path:
    SessionLog.model_validate(session.model_dump())
    path = session_path(session.id, sessions_dir)
    _atomic_write(path, _dump_yaml(session.model_dump(mode="json")))
    return path


def list_session_files(sessions_dir: Path | None = None) -> list[Path]:
    directory = sessions_dir or SESSIONS_DIR
    if not directory.exists():
        return []
    return sorted(directory.glob("SES-*.yaml"), reverse=True)


def load_all_sessions(sessions_dir: Path | None = None) -> list[SessionLog]:
    sessions: list[SessionLog] = []
    for path in list_session_files(sessions_dir):
        try:
            sessions.append(load_session(path.stem, sessions_dir))
        except StoreError:
            raise
    return sessions


def write_documents(
    *,
    todo: TodoDocument | None = None,
    wishlist: WishlistDocument | None = None,
    inbox: InboxDocument | None = None,
    changes: ChangesDocument | None = None,
    questions: OpenQuestionsDocument | None = None,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    inbox_path: Path | None = None,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
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
    if changes is not None:
        ChangesDocument.model_validate(changes.model_dump())
        payloads.append(
            (
                changes_path or CHANGES_PATH,
                _dump_yaml(changes.model_dump(mode="json")),
            )
        )
    if questions is not None:
        OpenQuestionsDocument.model_validate(questions.model_dump())
        payloads.append(
            (
                questions_path or QUESTIONS_PATH,
                _dump_yaml(questions.model_dump(mode="json")),
            )
        )
    write_text_files(payloads)


def parse_existing_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing YAML file: {path}") from exc
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {path}: {exc}") from exc
