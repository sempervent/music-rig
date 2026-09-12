"""Shared TUI fixtures — fixture-only mutations, never production data/."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Fail fast if pytest was launched with Homebrew/system Python instead of uv.
if sys.version_info < (3, 12):
    raise RuntimeError(
        f"music-rig tests require Python >= 3.12 (got {sys.version.split()[0]} "
        f"from {sys.executable}).\n"
        "Use: uv run pytest\n"
        "Not: pytest / python -m pytest from Homebrew."
    )
try:
    import pydantic
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "pydantic is missing in this interpreter.\nUse: uv run pytest"
    ) from exc
if tuple(int(p) for p in pydantic.__version__.split(".")[:2]) < (2, 0):
    raise RuntimeError(
        f"music-rig requires pydantic v2 (got {pydantic.__version__} from "
        f"{pydantic.__file__}).\n"
        "Use: uv run pytest"
    )

from music_rig import store


def _write_docs(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
    ]:
        path = tmp_path / name
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")
        paths[name] = path
    return paths


@pytest.fixture
def tui_fx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated YAML store for mutation tests — never touches production data."""
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    docs = _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": [],
                "tasks": [
                    {
                        "id": "RIG-001",
                        "task": "Fixture task",
                        "area": "Docs",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "done",
                        "notes": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "test-gear",
                        "name": "Test Gear",
                        "category": "utility",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "What mode is PB-B 1/25?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": ["RIG-001"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": "1/25",
                        },
                        "verification": {
                            "kind": "PATCHBAY_MODE",
                            "prompt": "Inspect switch",
                            "answer_type": "ENUM",
                            "choices": ["normal", "half-normal", "thru", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-002",
                        "question": "Unrelated MIDI clock?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        "# test patchbays\n"
        + yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-A": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                    "PB-B": {
                        "hardware_model": "unknown",
                        "status": "partially_documented",
                        "jacks": {
                            1: {
                                "row": "upper",
                                "connection": "miniKORG L",
                                "paired_with": 25,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            25: {
                                "row": "lower",
                                "connection": "TASCAM 3",
                                "paired_with": 1,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            2: {
                                "row": "upper",
                                "connection": "miniKORG R",
                                "paired_with": 26,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            26: {
                                "row": "lower",
                                "connection": "TASCAM 4",
                                "paired_with": 2,
                                "mode": "unknown",
                                "status": "documented",
                            },
                        },
                    },
                    "PB-C": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                    "PB-D": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    from music_rig import (
        change_service,
        current_service,
        inbox_service,
        patchbay_state,
        question_service,
        todo_service,
        wishlist_service,
    )
    from music_rig import render as render_mod

    def _noop_render(**kwargs):
        return False, []

    monkeypatch.setattr(render_mod, "render_docs", _noop_render)
    for mod in (
        question_service,
        current_service,
        todo_service,
        wishlist_service,
        inbox_service,
        change_service,
    ):
        if hasattr(mod, "render_docs"):
            monkeypatch.setattr(mod, "render_docs", _noop_render)

    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(store, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(current_service, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(current_service, "INVENTORY_PATH", inventory, raising=False)

    return {
        "questions": questions,
        "todo": todo,
        "wish": wish,
        "inbox": inbox,
        "changes": changes,
        "patchbays": patchbays,
        "inventory": inventory,
        "tmp_path": tmp_path,
    }


