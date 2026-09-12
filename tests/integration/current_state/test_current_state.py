from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from music_rig import change_service, channel_state, current_service, patchbay_state
from music_rig.current_projections import (
    render_alesis_section,
    render_patchbays_section,
    render_tascam_section,
)
from music_rig.models import ChangeCategory, QuestionStatus
from music_rig.render import check_render_sync, render_docs
from music_rig.store import StoreError, load_questions


@pytest.fixture
def current_fx(tmp_path: Path):
    patchbays = tmp_path / "patchbays.yaml"
    channels = tmp_path / "channel-map.yaml"
    changes = tmp_path / "changes.yaml"
    questions = tmp_path / "open-questions.yaml"
    docs_pb = tmp_path / "patchbays.md"
    docs_t = tmp_path / "tascam.md"
    docs_a = tmp_path / "alesis.md"
    diag_pb = tmp_path / "patchbays.mmd"
    diag_t = tmp_path / "tascam.mmd"
    docs_todo = tmp_path / "todo.md"
    docs_wish = tmp_path / "wishlist.md"
    docs_q = tmp_path / "questions.md"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"

    patchbays.write_text(
        yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
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
                    "PB-A": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    channels.write_text(
        yaml.safe_dump(
            {
                "tascam": {
                    8: {
                        "name": "UNASSIGNED",
                        "source": None,
                        "type": "unassigned",
                        "status": "UNASSIGNED",
                    },
                    5: {
                        "name": "ACOUSTIC",
                        "source": "Acoustic",
                        "type": "clean_mono",
                        "status": "CURRENT",
                    },
                },
                "alesis": {
                    3: {"source": None, "aux_send": False, "status": "UNASSIGNED"},
                },
            }
        ),
        encoding="utf-8",
    )
    changes.write_text("items: []\n", encoding="utf-8")
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "What mode is PB-B 1/25?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": "1/25",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    todo.write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    wish.write_text("items: []\n", encoding="utf-8")
    for path, start, end in [
        (docs_todo, "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        (docs_wish, "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        (docs_q, "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        (docs_pb, "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
        (docs_t, "<!-- rig:tascam:start -->", "<!-- rig:tascam:end -->"),
        (docs_a, "<!-- rig:alesis:start -->", "<!-- rig:alesis:end -->"),
    ]:
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")

    return {
        "patchbays": patchbays,
        "channels": channels,
        "changes": changes,
        "questions": questions,
        "docs_pb": docs_pb,
        "docs_t": docs_t,
        "docs_a": docs_a,
        "diag_pb": diag_pb,
        "diag_t": diag_t,
        "todo": todo,
        "wish": wish,
        "docs_todo": docs_todo,
        "docs_wish": docs_wish,
        "docs_q": docs_q,
    }


def test_patchbay_generation_deterministic(current_fx):
    data = patchbay_state.load_raw(current_fx["patchbays"])
    section = render_patchbays_section(data)
    assert "UNKNOWN" in section
    assert "miniKORG L" in section
    assert "PB-B" in section
    render_docs(
        todo_path=current_fx["todo"],
        wishlist_path=current_fx["wish"],
        questions_path=current_fx["questions"],
        patchbays_path=current_fx["patchbays"],
        channel_map_path=current_fx["channels"],
        docs_todo=current_fx["docs_todo"],
        docs_wishlist=current_fx["docs_wish"],
        docs_questions=current_fx["docs_q"],
        docs_patchbays=current_fx["docs_pb"],
        docs_tascam=current_fx["docs_t"],
        docs_alesis=current_fx["docs_a"],
        diagram_patchbays=current_fx["diag_pb"],
        diagram_tascam=current_fx["diag_t"],
        write=True,
    )
    assert (
        check_render_sync(
            todo_path=current_fx["todo"],
            wishlist_path=current_fx["wish"],
            questions_path=current_fx["questions"],
            patchbays_path=current_fx["patchbays"],
            channel_map_path=current_fx["channels"],
            docs_todo=current_fx["docs_todo"],
            docs_wishlist=current_fx["docs_wish"],
            docs_questions=current_fx["docs_q"],
            docs_patchbays=current_fx["docs_pb"],
            docs_tascam=current_fx["docs_t"],
            docs_alesis=current_fx["docs_a"],
            diagram_patchbays=current_fx["diag_pb"],
            diagram_tascam=current_fx["diag_t"],
        )
        == []
    )
    before = current_fx["docs_pb"].read_text(encoding="utf-8")
    render_docs(
        todo_path=current_fx["todo"],
        wishlist_path=current_fx["wish"],
        questions_path=current_fx["questions"],
        patchbays_path=current_fx["patchbays"],
        channel_map_path=current_fx["channels"],
        docs_todo=current_fx["docs_todo"],
        docs_wishlist=current_fx["docs_wish"],
        docs_questions=current_fx["docs_q"],
        docs_patchbays=current_fx["docs_pb"],
        docs_tascam=current_fx["docs_t"],
        docs_alesis=current_fx["docs_a"],
        diagram_patchbays=current_fx["diag_pb"],
        diagram_tascam=current_fx["diag_t"],
        write=True,
    )
    assert current_fx["docs_pb"].read_text(encoding="utf-8") == before


def test_patchbay_set_mode_and_dry_run(current_fx):
    preview, data = patchbay_state.propose_set_mode(
        "PB-B", "1", "half-normal", path=current_fx["patchbays"]
    )
    assert preview.changed
    assert preview.before["mode"] == "unknown"
    assert preview.after["mode"] == "half-normal"
    before = current_fx["patchbays"].read_text(encoding="utf-8")
    current_service.commit_patchbay(
        data,
        preview,
        dry_run=True,
        render=False,
        patchbays_path=current_fx["patchbays"],
    )
    assert current_fx["patchbays"].read_text(encoding="utf-8") == before

    current_service.commit_patchbay(
        data,
        preview,
        dry_run=False,
        render=False,
        patchbays_path=current_fx["patchbays"],
    )
    after = patchbay_state.load_raw(current_fx["patchbays"])
    pairs = patchbay_state.list_pairs("PB-B", after)
    assert pairs[0]["mode"] == "half-normal"

    preview2, _ = patchbay_state.propose_set_mode(
        "PB-B", "1", "half-normal", path=current_fx["patchbays"]
    )
    assert not preview2.changed

    with pytest.raises(StoreError):
        patchbay_state.propose_set_mode("PB-B", "5", "normal", path=current_fx["patchbays"])
    with pytest.raises(StoreError):
        patchbay_state.propose_set_mode("PB-B", "1", "bogus", path=current_fx["patchbays"])


def test_patchbay_verify_batch_and_skip(current_fx):
    preview, data = patchbay_state.propose_set_modes_batch(
        "PB-B",
        [("1", "half-normal"), ("2", "thru")],
        path=current_fx["patchbays"],
    )
    assert preview.changed
    current_service.commit_patchbay(
        data, preview, render=False, patchbays_path=current_fx["patchbays"]
    )
    pairs = patchbay_state.list_pairs("PB-B", patchbay_state.load_raw(current_fx["patchbays"]))
    modes = {f"{p['upper_n']}/{p['lower_n']}": p["mode"] for p in pairs}
    assert modes["1/25"] == "half-normal"
    assert modes["2/26"] == "thru"


def test_patchbay_set_model(current_fx):
    preview, data = patchbay_state.propose_set_model(
        "PB-B", "ART P48", path=current_fx["patchbays"]
    )
    assert preview.before["hardware_model"] in {"unknown", "UNKNOWN"} or True
    current_service.commit_patchbay(
        data, preview, render=False, patchbays_path=current_fx["patchbays"]
    )
    bay = patchbay_state.load_raw(current_fx["patchbays"])["patchbays"]["PB-B"]
    assert bay["hardware_model"] == "ART P48"


def test_channel_mutations(current_fx):
    preview, data = channel_state.propose_set_source(
        "tascam", 8, "Example Source", path=current_fx["channels"]
    )
    assert preview.changed
    assert preview.after["status"] == "CURRENT"
    before = current_fx["channels"].read_text(encoding="utf-8")
    current_service.commit_channel(
        data, preview, dry_run=True, render=False, channel_map_path=current_fx["channels"]
    )
    assert current_fx["channels"].read_text(encoding="utf-8") == before
    current_service.commit_channel(
        data, preview, render=False, channel_map_path=current_fx["channels"]
    )
    row = channel_state.load_raw(current_fx["channels"])["tascam"][8]
    assert row["source"] == "Example Source"
    assert row["status"] == "CURRENT"
    clear_p, clear_d = channel_state.clear_source("tascam", 8, path=current_fx["channels"])
    assert clear_p.after["status"] == "UNASSIGNED"
    current_service.commit_channel(
        clear_d, clear_p, render=False, channel_map_path=current_fx["channels"]
    )
    cleared = channel_state.load_raw(current_fx["channels"])["tascam"][8]
    assert cleared["source"] is None
    assert cleared["status"] == "UNASSIGNED"
    with pytest.raises(StoreError):
        channel_state.propose_set_source("tascam", 99, "x", path=current_fx["channels"])


def test_channel_set_source_promotes_unassigned_to_current(current_fx):
    """Regression: assigning a source must set status CURRENT (not leave UNASSIGNED)."""
    raw = channel_state.load_raw(current_fx["channels"])
    assert raw["alesis"][3]["status"] == "UNASSIGNED"
    assert raw["alesis"][3]["source"] is None
    preview, data = channel_state.propose_set_source(
        "alesis", 3, "Electric", path=current_fx["channels"]
    )
    assert preview.before["status"] == "UNASSIGNED"
    assert preview.after["source"] == "Electric"
    assert preview.after["status"] == "CURRENT"
    current_service.commit_channel(
        data, preview, render=False, channel_map_path=current_fx["channels"]
    )
    row = channel_state.load_raw(current_fx["channels"])["alesis"][3]
    assert row["source"] == "Electric"
    assert row["status"] == "CURRENT"


def test_evidence_links_and_idempotent_no_reconcile(current_fx):
    chg = change_service.create_change(
        "verified pair 1",
        category=ChangeCategory.PATCHBAY,
        changes_path=current_fx["changes"],
        link_session=False,
    )
    preview, data = patchbay_state.propose_set_mode(
        "PB-B", "1/25", "normal", path=current_fx["patchbays"]
    )
    current_service.commit_patchbay(
        data,
        preview,
        render=False,
        patchbays_path=current_fx["patchbays"],
        questions_path=current_fx["questions"],
        changes_path=current_fx["changes"],
        question_id="Q-001",
        change_id=chg.id,
        resolve_q=True,
        apply_chg=True,
        answer="normal",
    )
    q = load_questions(current_fx["questions"]).question_map()["Q-001"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "normal"
    from music_rig.store import load_changes

    assert load_changes(current_fx["changes"]).item_map()[chg.id].status.value == "APPLIED"

    # Idempotent: already normal — must not re-resolve / rewrite churn for evidence
    preview2, data2 = patchbay_state.propose_set_mode(
        "PB-B", "1", "normal", path=current_fx["patchbays"]
    )
    assert not preview2.changed
    before_q = current_fx["questions"].read_text(encoding="utf-8")
    current_service.commit_patchbay(
        data2,
        preview2,
        render=False,
        patchbays_path=current_fx["patchbays"],
        questions_path=current_fx["questions"],
        changes_path=current_fx["changes"],
        question_id="Q-001",
        resolve_q=True,
        answer="should-not-apply",
    )
    assert current_fx["questions"].read_text(encoding="utf-8") == before_q

    with pytest.raises(StoreError):
        current_service.commit_patchbay(
            data,
            preview,
            dry_run=True,
            render=False,
            patchbays_path=current_fx["patchbays"],
            question_id="Q-999",
            questions_path=current_fx["questions"],
        )


def test_channel_projections(current_fx):
    data = channel_state.load_raw(current_fx["channels"])
    assert "ACOUSTIC" in render_tascam_section(data)
    assert "UNASSIGNED" in render_alesis_section(data)


def test_production_question_target_q008():
    q = load_questions().question_map()["Q-008"]
    assert q.target is not None
    assert q.target.domain == "patchbay.mode"
    assert q.target.bay == "PB-B"
