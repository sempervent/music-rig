from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from music_rig import change_service, current_service, routing_state
from music_rig.models import ChangeCategory, QuestionStatus
from music_rig.render import check_render_sync, render_docs
from music_rig.routing_projections import (
    render_aux_send_loop_mermaid,
    render_current_routing_section,
    render_pedal_chains_section,
)
from music_rig.store import StoreError, load_changes, load_questions


@pytest.fixture
def routing_file(tmp_path: Path) -> Path:
    path = tmp_path / "routing.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "dirty": {
                        "label": "DIRTY",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "Main",
                                "nodes": [
                                    {"id": "a", "label": "A"},
                                    {"id": "b", "label": "B"},
                                    {"id": "c", "label": "C"},
                                    {"id": "d", "label": "D"},
                                ],
                            }
                        },
                    },
                    "space": {
                        "label": "SPACE",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "Main",
                                "nodes": [
                                    {"id": "send", "label": "Send"},
                                    {"id": "sy-1", "label": "SY-1"},
                                    {"id": "ls-2", "label": "LS-2"},
                                    {"id": "return", "label": "Return"},
                                ],
                            },
                            "sy-loop": {
                                "label": "SY loop",
                                "attach": "sy-1",
                                "position": "before",
                                "nodes": [
                                    {"id": "ph-3", "label": "PH-3"},
                                    {"id": "tr-2", "label": "TR-2"},
                                ],
                            },
                            "ls-a": {
                                "label": "LS A",
                                "attach": "ls-2",
                                "position": "before",
                                "nodes": [
                                    {"id": "sl-2", "label": "SL-2"},
                                    {"id": "dd-8", "label": "DD-8"},
                                ],
                            },
                        },
                    },
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _ids(data: dict, path: str, branch: str = "main") -> list[str]:
    _, named = routing_state.get_named_path(data, path)
    return [node.id for node in named.branches[branch].nodes]


def test_production_routing_loads_and_validates():
    data = routing_state.load_raw()
    doc = routing_state.load_document()
    assert routing_state.validate_routing_doc(data) == []
    assert {"dirty", "space", "aux", "kaoss"} <= set(doc.named_paths)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"before": "b"}, ["a", "d", "b", "c"]),
        ({"after": "b"}, ["a", "b", "d", "c"]),
        ({"first": True}, ["d", "a", "b", "c"]),
        ({"last": True}, ["a", "b", "c", "d"]),
    ],
)
def test_dirty_linear_move_placements(routing_file, kwargs, expected):
    preview, data = routing_state.propose_move("dirty", "d", routing_path=routing_file, **kwargs)
    assert preview.changed == (expected != ["a", "b", "c", "d"])
    assert _ids(data, "dirty") == expected


def test_insert_remove_duplicate_invalid_and_dry_run(routing_file):
    before = routing_file.read_text(encoding="utf-8")
    preview, inserted = routing_state.propose_insert(
        "dirty",
        "new-node",
        label="New Node",
        after="b",
        routing_path=routing_file,
    )
    current_service.commit_routing(
        inserted,
        preview,
        dry_run=True,
        render=False,
        routing_path=routing_file,
    )
    assert routing_file.read_text(encoding="utf-8") == before

    current_service.commit_routing(inserted, preview, render=False, routing_path=routing_file)
    assert _ids(routing_state.load_raw(routing_file), "dirty") == [
        "a",
        "b",
        "new-node",
        "c",
        "d",
    ]
    remove_preview, removed = routing_state.propose_remove(
        "dirty", "new-node", routing_path=routing_file
    )
    current_service.commit_routing(removed, remove_preview, render=False, routing_path=routing_file)
    assert _ids(routing_state.load_raw(routing_file), "dirty") == ["a", "b", "c", "d"]

    with pytest.raises(StoreError, match="already exists"):
        routing_state.propose_insert("dirty", "a", last=True, routing_path=routing_file)
    with pytest.raises(StoreError, match="Invalid node id"):
        routing_state.propose_insert("dirty", "bad id", last=True, routing_path=routing_file)
    with pytest.raises(StoreError, match="exactly one"):
        routing_state.propose_move("dirty", "a", routing_path=routing_file)


def test_space_branch_reorder_leaves_siblings_unchanged(routing_file):
    original = routing_state.load_raw(routing_file)
    preview, data = routing_state.propose_move(
        "space",
        "tr-2",
        branch="sy-loop",
        before="ph-3",
        routing_path=routing_file,
    )
    assert preview.changed
    assert _ids(data, "space", "sy-loop") == ["tr-2", "ph-3"]
    assert _ids(data, "space", "main") == _ids(original, "space", "main")
    assert _ids(data, "space", "ls-a") == _ids(original, "space", "ls-a")
    assert "No other space branches change." in preview.message


def test_routing_projections_are_deterministic(routing_file):
    data = routing_state.load_raw(routing_file)
    first = (
        render_current_routing_section(data),
        render_pedal_chains_section(data),
        render_aux_send_loop_mermaid(data),
    )
    second = (
        render_current_routing_section(data),
        render_pedal_chains_section(data),
        render_aux_send_loop_mermaid(data),
    )
    assert second == first
    assert "Named CURRENT paths" in first[0]
    assert "DIRTY" in first[1]
    assert "SY loop" in first[1]


def test_render_sync_and_second_render_has_no_diff(tmp_path, routing_file):
    files = {
        "todo": tmp_path / "todo.yaml",
        "wish": tmp_path / "wish.yaml",
        "questions": tmp_path / "questions.yaml",
        "patchbays": tmp_path / "patchbays.yaml",
        "channels": tmp_path / "channels.yaml",
        "docs_todo": tmp_path / "todo.md",
        "docs_wish": tmp_path / "wish.md",
        "docs_questions": tmp_path / "questions.md",
        "docs_patchbays": tmp_path / "patchbays.md",
        "docs_tascam": tmp_path / "tascam.md",
        "docs_alesis": tmp_path / "alesis.md",
        "docs_routing": tmp_path / "routing.md",
        "docs_pedals": tmp_path / "pedals.md",
        "diag_pb": tmp_path / "pb.mmd",
        "diag_t": tmp_path / "t.mmd",
        "diag_aux": tmp_path / "aux.mmd",
    }
    files["todo"].write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    files["wish"].write_text("items: []\n", encoding="utf-8")
    files["questions"].write_text("questions: []\n", encoding="utf-8")
    files["patchbays"].write_text("patchbays: {}\n", encoding="utf-8")
    files["channels"].write_text("tascam: {}\nalesis: {}\n", encoding="utf-8")
    markers = [
        ("docs_todo", "todo"),
        ("docs_wish", "wishlist"),
        ("docs_questions", "questions"),
        ("docs_patchbays", "patchbays"),
        ("docs_tascam", "tascam"),
        ("docs_alesis", "alesis"),
        ("docs_routing", "routing"),
        ("docs_pedals", "pedal-chains"),
    ]
    for key, marker in markers:
        files[key].write_text(
            f"x\n<!-- rig:{marker}:start -->\n<!-- rig:{marker}:end -->\n",
            encoding="utf-8",
        )
    kwargs = {
        "todo_path": files["todo"],
        "wishlist_path": files["wish"],
        "questions_path": files["questions"],
        "patchbays_path": files["patchbays"],
        "channel_map_path": files["channels"],
        "routing_path": routing_file,
        "docs_todo": files["docs_todo"],
        "docs_wishlist": files["docs_wish"],
        "docs_questions": files["docs_questions"],
        "docs_patchbays": files["docs_patchbays"],
        "docs_tascam": files["docs_tascam"],
        "docs_alesis": files["docs_alesis"],
        "docs_routing": files["docs_routing"],
        "docs_pedal_chains": files["docs_pedals"],
        "diagram_patchbays": files["diag_pb"],
        "diagram_tascam": files["diag_t"],
        "diagram_aux_loop": files["diag_aux"],
    }
    changed, _ = render_docs(**kwargs, write=True)
    assert changed
    changed_again, names = render_docs(**kwargs, write=True)
    assert not changed_again
    assert names == []
    assert check_render_sync(**kwargs) == []


def test_verify_batch_does_not_write_until_commit(routing_file):
    before = routing_file.read_text(encoding="utf-8")
    preview, data = routing_state.propose_batch(
        "dirty",
        [
            {"op": "move", "node": "d", "first": True},
            {"op": "remove", "node": "b"},
            {"op": "insert", "node": "x", "label": "X", "after": "a"},
        ],
        routing_path=routing_file,
    )
    assert preview.changed
    assert routing_file.read_text(encoding="utf-8") == before
    current_service.commit_routing(data, preview, render=False, routing_path=routing_file)
    assert _ids(routing_state.load_raw(routing_file), "dirty") == ["d", "a", "x", "c"]


def test_evidence_resolution_apply_and_failed_validation_are_atomic(tmp_path, routing_file):
    questions = tmp_path / "questions.yaml"
    changes = tmp_path / "changes.yaml"
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "Is B first?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    changes.write_text("items: []\n", encoding="utf-8")
    change = change_service.create_change(
        "Moved B",
        category=ChangeCategory.PEDAL_CHAIN,
        changes_path=changes,
        link_session=False,
    )
    preview, data = routing_state.propose_move("dirty", "b", first=True, routing_path=routing_file)
    current_service.commit_routing(
        data,
        preview,
        render=False,
        routing_path=routing_file,
        questions_path=questions,
        changes_path=changes,
        question_id="Q-001",
        change_id=change.id,
        resolve_q=True,
        apply_chg=True,
        answer="B is first",
    )
    assert load_questions(questions).question_map()["Q-001"].status == QuestionStatus.RESOLVED
    assert load_changes(changes).item_map()[change.id].status.value == "APPLIED"

    routing_before = routing_file.read_text(encoding="utf-8")
    questions_before = questions.read_text(encoding="utf-8")
    changes_before = changes.read_text(encoding="utf-8")
    invalid = routing_state.load_raw(routing_file)
    invalid["named_paths"]["dirty"]["branches"]["main"]["nodes"][1]["id"] = "b"
    with pytest.raises(StoreError, match="Routing validation failed"):
        current_service.commit_routing(
            invalid,
            preview,
            render=False,
            routing_path=routing_file,
            questions_path=questions,
            changes_path=changes,
            question_id="Q-001",
            change_id=change.id,
            resolve_q=True,
            apply_chg=True,
            answer="must not write",
        )
    assert routing_file.read_text(encoding="utf-8") == routing_before
    assert questions.read_text(encoding="utf-8") == questions_before
    assert changes.read_text(encoding="utf-8") == changes_before


def test_production_semantic_fingerprint_stable_keys():
    fingerprint = routing_state.semantic_fingerprint(routing_state.load_document())
    assert list(fingerprint["dirty"]["branches"]) == ["main"]
    assert set(fingerprint["space"]["branches"]) == {
        "main",
        "sy1-send",
        "ls2-a",
        "ls2-b",
    }
    assert [n["id"] for n in fingerprint["aux"]["branches"]["main"]["nodes"]] == [
        "alesis-aux-send",
        "rc-1",
        "cry-baby",
        "joyo",
        "ch-1",
        "alesis-return-1-2",
    ]
    assert [n["id"] for n in fingerprint["kaoss"]["branches"]["main"]["nodes"]] == [
        "tascam-3-4",
        "kaoss-replay",
        "tascam-15-16",
    ]
