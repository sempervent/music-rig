from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from music_rig import control_state, current_service
from music_rig.ableton_projections import render_ableton_section
from music_rig.control_projections import render_controller_mappings_section
from music_rig.models import MidiEvidenceStatus
from music_rig.reconcile import format_reconcile_question
from music_rig.store import (
    ABLETON_PATH,
    CONTROLLERS_PATH,
    INVENTORY_PATH,
    MIDI_PATH,
    StoreError,
    load_ableton,
    load_questions,
)


@pytest.fixture
def control_files(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name, source in (
        ("controllers", CONTROLLERS_PATH),
        ("ableton", ABLETON_PATH),
        ("inventory", INVENTORY_PATH),
        ("midi", MIDI_PATH),
    ):
        target = tmp_path / source.name
        shutil.copy(source, target)
        paths[name] = target
    return paths


def _kwargs(paths):
    return {
        "controllers_path": paths["controllers"],
        "ableton_path": paths["ableton"],
        "inventory_path": paths["inventory"],
        "midi_path": paths["midi"],
    }


def _load(paths):
    return control_state.load_document(
        paths["controllers"],
        ableton_path=paths["ableton"],
        inventory_path=paths["inventory"],
        midi_path=paths["midi"],
    )


def test_production_controller_and_ableton_data_load_conservatively():
    doc = control_state.load_document()
    assert len(doc.controllers) == 5
    assert all(item.coverage.value in {"PARTIAL", "UNKNOWN"} for item in doc.controllers)
    assert not any(
        control.evidence == MidiEvidenceStatus.VERIFIED and control.availability.value != "BROKEN"
        for controller in doc.controllers
        for context in controller.contexts
        for control in context.controls
    )
    ableton = load_ableton()
    assert len(ableton.tracks) == 12
    assert len(ableton.sends) == 4
    assert len(ableton.actions) == 4
    assert all(item.evidence == MidiEvidenceStatus.INTENDED for item in ableton.tracks)


def test_message_mutations_resolve_device_channel_without_editing_midi(control_files):
    before = control_files["midi"].read_bytes()
    preview, data = control_state.propose_set_message(
        "behringer-fcb1010",
        "bank-00",
        "exp-a",
        {"type": "CC", "number": 113, "channel": "DEVICE", "value_behavior": "range"},
        **_kwargs(control_files),
    )
    assert preview.domain == "controls.message"
    control = (
        control_state.ControllersDocument.model_validate(data)
        if hasattr(control_state, "ControllersDocument")
        else None
    )
    assert data["controllers"][0]["contexts"][0]["controls"][0]["messages"][0]["number"] == 113
    assert (
        control_state.resolve_message_channel(
            "behringer-fcb1010",
            _load(control_files).controllers[0].contexts[0].controls[0].messages[0],
            midi_path=control_files["midi"],
        )
        == 16
    )
    assert control_files["midi"].read_bytes() == before
    assert control is not None


def test_broken_control_cannot_be_mapped_or_marked_broken_while_mapped(control_files):
    with pytest.raises(StoreError, match="BROKEN"):
        control_state.propose_set_target(
            "novation-remote-zero-sl",
            "pfl-send-c",
            "encoder-06",
            {
                "state": "MAPPED",
                "kind": "ABLETON_ACTION",
                "action": "template-home",
            },
            **_kwargs(control_files),
        )
    with pytest.raises(StoreError, match="clear its target"):
        control_state.propose_set_availability(
            "novation-remote-zero-sl",
            "pfl-send-c",
            "pad-08",
            "BROKEN",
            **_kwargs(control_files),
        )


def test_gaps_and_conflicts_are_reported(control_files):
    doc = _load(control_files)
    gaps = control_state.find_gaps(doc)
    assert any(gap["gear"] == "launchpad-x" and gap["gap"] == "no contexts" for gap in gaps)
    raw = control_state.load_raw(control_files["controllers"])
    controls = raw["controllers"][0]["contexts"][0]["controls"]
    controls[1]["messages"] = copy.deepcopy(controls[0]["messages"])
    conflicts = control_state.find_conflicts(
        control_state.ControllersDocument.model_validate(raw),
        midi_path=control_files["midi"],
    )
    assert conflicts[0]["controls"] == "exp-a, exp-b"


def test_verify_batch_and_commit_are_controller_only(control_files):
    midi_before = hashlib.sha256(control_files["midi"].read_bytes()).hexdigest()
    preview, data = control_state.propose_batch(
        [
            {
                "op": "set_evidence",
                "context_id": "bank-00",
                "control_id": "exp-a",
                "evidence": "VERIFIED",
            }
        ],
        gear_ref="behringer-fcb1010",
        **_kwargs(control_files),
    )
    assert preview.domain == "controls.verify"
    current_service.commit_controllers(data, preview, render=False, **_kwargs(control_files))
    updated = _load(control_files)
    assert updated.controllers[0].contexts[0].controls[0].evidence.value == "VERIFIED"
    assert hashlib.sha256(control_files["midi"].read_bytes()).hexdigest() == midi_before


def test_projections_include_structured_targets_and_preserve_evidence():
    controller_text = render_controller_mappings_section(control_state.load_document())
    ableton_text = render_ableton_section(load_ableton())
    assert "encoder-06" in controller_text
    assert "BROKEN" in controller_text
    assert "ABLETON_ACTION: template-home" in controller_text
    assert "Send D" in ableton_text
    assert "INTENDED" in ableton_text


def test_q016_q017_targets_and_reconcile_commands():
    questions = load_questions().question_map()
    assert questions["Q-016"].target.gear == "behringer-fcb1010"
    assert questions["Q-017"].target.gear == "novation-remote-zero-sl"
    # Q-016 HUMAN bank-00 answer reconciled; banks 01/02 still incomplete in CURRENT.
    assert questions["Q-016"].reconciled_at is not None
    assert "bank 00" in (questions["Q-016"].answer or "").casefold()
    # Q-017 remains OPEN — reconcile text still points at controls verify.
    assert questions["Q-017"].status.value == "OPEN"
    assert "rig current controls verify novation-remote-zero-sl" in format_reconcile_question(
        "Q-017"
    )


def test_midi_topology_clock_channels_and_statuses_remain_unchanged(control_files):
    raw = yaml.safe_load(control_files["midi"].read_text(encoding="utf-8"))
    fingerprint = {key: raw[key] for key in ("connections", "channels", "clock")}
    preview, data = control_state.clear_target(
        "korg-padkontrol", "global", "footswitch", **_kwargs(control_files)
    )
    current_service.commit_controllers(data, preview, render=False, **_kwargs(control_files))
    after = yaml.safe_load(control_files["midi"].read_text(encoding="utf-8"))
    assert {key: after[key] for key in ("connections", "channels", "clock")} == fingerprint
