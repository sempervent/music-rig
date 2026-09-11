from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig.cli import app
from music_rig.models import TodoDocument, TodoPriority, TodoStatus, WishlistDocument
from music_rig.render import (
    WISH_END,
    WISH_START,
    TODO_END,
    TODO_START,
    apply_todo_render,
    apply_wishlist_render,
    check_render_sync,
    render_todo_section,
    render_wishlist_section,
)
from music_rig.store import load_todo, load_wishlist, save_todo


runner = CliRunner()


def _minimal_todo(**overrides) -> dict:
    base = {
        "next_session": ["RIG-001"],
        "tasks": [
            {
                "id": "RIG-001",
                "task": "One",
                "area": "Docs",
                "priority": "P0",
                "status": "NEXT",
                "depends_on": [],
                "definition_of_done": "Done when one.",
                "notes": "",
            },
            {
                "id": "RIG-002",
                "task": "Two",
                "area": "Docs",
                "priority": "P1",
                "status": "READY",
                "depends_on": [],
                "definition_of_done": "Done when two.",
                "notes": "",
            },
        ],
    }
    base.update(overrides)
    return base


def test_load_repo_todo_yaml():
    doc = load_todo()
    assert len(doc.tasks) == 44
    assert doc.next_session == ["RIG-001", "RIG-002", "RIG-003"]
    assert doc.next_id() == "RIG-049"
    ids = {t.id for t in doc.tasks}
    assert "RIG-032" in ids
    assert "RIG-048" in ids
    assert "RIG-026" not in ids  # historical gap


def test_load_repo_wishlist_yaml():
    doc = load_wishlist()
    assert len(doc.items) == 16
    rc600 = doc.find("boss rc-600")
    assert rc600 is not None
    assert rc600.status.value == "BUY LATER"
    midi = doc.find("Generic MIDI thru / splitter / router")
    assert midi is not None
    assert midi.status.value == "REDUNDANT"
    assert midi.priority is None


def test_duplicate_todo_id_rejected():
    data = _minimal_todo()
    data["tasks"].append(dict(data["tasks"][0]))
    with pytest.raises(Exception):
        TodoDocument.model_validate(data)


def test_bad_dependency_rejected():
    data = _minimal_todo()
    data["tasks"][1]["depends_on"] = ["RIG-999"]
    with pytest.raises(Exception):
        TodoDocument.model_validate(data)


def test_self_dependency_rejected():
    data = _minimal_todo()
    data["tasks"][0]["depends_on"] = ["RIG-001"]
    with pytest.raises(Exception):
        TodoDocument.model_validate(data)


def test_invalid_status_rejected():
    data = _minimal_todo()
    data["tasks"][0]["status"] = "SOON"
    with pytest.raises(Exception):
        TodoDocument.model_validate(data)


def test_next_session_over_three_rejected():
    data = _minimal_todo()
    data["tasks"].append(
        {
            "id": "RIG-003",
            "task": "Three",
            "area": "Docs",
            "priority": "P2",
            "status": "READY",
            "depends_on": [],
            "definition_of_done": "x",
            "notes": "",
        }
    )
    data["tasks"].append(
        {
            "id": "RIG-004",
            "task": "Four",
            "area": "Docs",
            "priority": "P2",
            "status": "READY",
            "depends_on": [],
            "definition_of_done": "x",
            "notes": "",
        }
    )
    data["next_session"] = ["RIG-001", "RIG-002", "RIG-003", "RIG-004"]
    with pytest.raises(Exception):
        TodoDocument.model_validate(data)


def test_done_not_in_next_session():
    data = _minimal_todo()
    data["tasks"][0]["status"] = "DONE"
    with pytest.raises(Exception):
        TodoDocument.model_validate(data)


def test_deterministic_render(tmp_path: Path):
    doc = TodoDocument.model_validate(_minimal_todo())
    a = render_todo_section(doc)
    b = render_todo_section(doc)
    assert a == b
    assert "GENERATED FROM data/todo.yaml" in a


def test_render_check_success_on_repo():
    assert check_render_sync() == []


def test_render_check_failure_on_stale(tmp_path: Path):
    todo_yaml = tmp_path / "todo.yaml"
    wish_yaml = tmp_path / "wishlist.yaml"
    docs_todo = tmp_path / "todo.md"
    docs_wish = tmp_path / "wishlist.md"

    todo = TodoDocument.model_validate(_minimal_todo())
    wish = WishlistDocument.model_validate(
        {
            "items": [
                {
                    "item": "Widget",
                    "category": "Test",
                    "problem_capability": "Testing",
                    "priority": "P3",
                    "status": "IDEA",
                }
            ]
        }
    )
    todo_yaml.write_text(
        yaml.safe_dump(todo.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    wish_yaml.write_text(
        yaml.safe_dump(wish.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )

    docs_todo.write_text(
        f"Intro\n{TODO_START}\nstale\n{TODO_END}\nOutro\n", encoding="utf-8"
    )
    docs_wish.write_text(
        f"Intro\n{WISH_START}\n{render_wishlist_section(wish)}{WISH_END}\n",
        encoding="utf-8",
    )

    stale = check_render_sync(
        todo_path=todo_yaml,
        wishlist_path=wish_yaml,
        docs_todo=docs_todo,
        docs_wishlist=docs_wish,
    )
    assert stale == ["docs/todo.md"]


def test_next_id_allocation():
    doc = load_todo()
    assert doc.next_id() == "RIG-049"


def test_cli_todo_list():
    result = runner.invoke(app, ["todo", "list", "--priority", "P0"])
    assert result.exit_code == 0
    assert "RIG-001" in result.stdout


def test_cli_unknown_todo():
    result = runner.invoke(app, ["todo", "show", "RIG-999"])
    assert result.exit_code != 0
    assert "does not exist" in result.stdout or "does not exist" in result.stderr


def test_save_todo_roundtrip(tmp_path: Path):
    src = load_todo()
    out = tmp_path / "todo.yaml"
    save_todo(src, out)
    again = load_todo(out)
    assert again.model_dump() == src.model_dump()


def test_apply_preserves_outside_markers():
    doc = TodoDocument.model_validate(_minimal_todo())
    original = f"KEEP-BEFORE\n{TODO_START}\nold\n{TODO_END}\nKEEP-AFTER\n"
    updated = apply_todo_render(original, doc)
    assert updated.startswith("KEEP-BEFORE\n")
    assert updated.endswith("KEEP-AFTER\n")
    assert "RIG-001" in updated
