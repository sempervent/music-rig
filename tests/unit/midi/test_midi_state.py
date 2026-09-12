from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from music_rig import current_service, midi_state
from music_rig.midi_projections import (
    render_midi_clock_section,
    render_midi_topology_mermaid,
    render_midi_topology_section,
)
from music_rig.models import MidiEvidenceStatus, QuestionStatus
from music_rig.store import StoreError, load_questions


@pytest.fixture
def midi_files(tmp_path: Path) -> tuple[Path, Path]:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "controller",
                        "name": "Controller",
                        "category": "MIDI",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
                    {
                        "id": "synth",
                        "name": "Synth",
                        "category": "Synth",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
                    {
                        "id": "retired",
                        "name": "Retired",
                        "category": "MIDI",
                        "ownership_status": "RETIRED",
                        "condition": "UNKNOWN",
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    midi = tmp_path / "midi.yaml"
    midi.write_text(
        yaml.safe_dump(
            {
                "endpoints": [{"id": "ableton", "kind": "software", "name": "Ableton Live"}],
                "devices": [
                    {"gear_ref": "controller", "role": "controller"},
                    {"gear_ref": "synth", "role": "synth"},
                ],
                "connections": [],
                "channels": [
                    {
                        "gear_ref": "controller",
                        "channel": 10,
                        "status": "INTENDED",
                    }
                ],
                "clock": {
                    "master": {"endpoint_ref": "ableton", "status": "INTENDED"},
                    "destinations": [
                        {
                            "gear_ref": "synth",
                            "enabled": "unknown",
                            "status": "INTENDED",
                        }
                    ],
                    "transport": {"status": "UNKNOWN"},
                },
                "ableton_ports": [
                    {
                        "id": "controller-in",
                        "direction": "input",
                        "gear_ref": "controller",
                        "track": "unknown",
                        "sync": "unknown",
                        "remote": "unknown",
                        "status": "UNKNOWN",
                    }
                ],
                "routes": [],
                "unknowns": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return midi, inventory


def test_production_midi_is_conservative_and_valid():
    doc = midi_state.load_document()
    assert midi_state.validate_midi_doc(midi_state.load_raw()) == []
    assert len(doc.devices) == 12
    assert len(doc.endpoints) == 2
    assert doc.connections == []
    assert len(doc.channels) == 4
    assert all(item.status == MidiEvidenceStatus.INTENDED for item in doc.channels)
    assert doc.clock.master is not None
    assert doc.clock.master.endpoint_ref == "ableton"
    assert doc.clock.master.status == MidiEvidenceStatus.INTENDED
    assert doc.ableton_ports == []
    questions = load_questions().question_map()
    assert questions["Q-014"].target.domain == "midi.clock_master"
    assert questions["Q-015"].target.domain == "midi.verify"
    assert questions["Q-016"].target.domain == "controls.verify"
    assert questions["Q-016"].target.gear == "behringer-fcb1010"
    assert questions["Q-017"].target.domain == "controls.verify"
    assert questions["Q-017"].target.gear == "novation-remote-zero-sl"


@pytest.mark.parametrize("channel", [0, 17, "ALL", ""])
def test_channel_validation_rejects_invalid_values(midi_files, channel):
    midi, inventory = midi_files
    with pytest.raises((StoreError, ValueError), match="1-16"):
        midi_state.propose_set_channel(
            "controller", channel, midi_path=midi, inventory_path=inventory
        )


def test_channel_and_link_mutations_are_typed_and_idempotent(midi_files):
    midi, inventory = midi_files
    preview, data = midi_state.propose_set_channel(
        "controller", "16", midi_path=midi, inventory_path=inventory
    )
    assert preview.after["channel"] == 16
    assert preview.after["status"] == "VERIFIED"
    link_preview, linked = midi_state.propose_add_link(
        source="controller",
        source_port="MIDI OUT",
        destination="synth",
        destination_port="MIDI IN",
        transport="DIN",
        data=data,
        inventory_path=inventory,
    )
    assert link_preview.target == "midi-link-001"
    duplicate, unchanged = midi_state.propose_add_link(
        source="controller",
        source_port="MIDI OUT",
        destination="synth",
        destination_port="MIDI IN",
        transport="DIN",
        data=linked,
        inventory_path=inventory,
    )
    assert not duplicate.changed
    assert unchanged == linked
    removed, final = midi_state.propose_remove_link(
        "midi-link-001", data=linked, inventory_path=inventory
    )
    assert removed.changed
    assert final["connections"] == []


def test_clock_master_replace_and_destination_state(midi_files):
    midi, inventory = midi_files
    master, data = midi_state.propose_set_clock_master(
        "synth", midi_path=midi, inventory_path=inventory
    )
    assert master.before["endpoint_ref"] == "ableton"
    assert master.after["gear_ref"] == "synth"
    assert "endpoint_ref" not in master.after
    destination, data = midi_state.propose_set_clock_destination(
        "synth", "on", data=data, inventory_path=inventory
    )
    assert destination.after["enabled"] == "on"
    assert destination.after["status"] == "VERIFIED"
    assert len(data["clock"]["destinations"]) == 1


def test_ableton_three_state_and_inactive_refs(midi_files):
    midi, inventory = midi_files
    preview, data = midi_state.propose_ableton_set(
        "controller-in",
        track="on",
        sync="off",
        remote="unknown",
        midi_path=midi,
        inventory_path=inventory,
    )
    assert preview.after["track"] == "on"
    assert preview.after["sync"] == "off"
    assert preview.after["remote"] == "unknown"
    assert preview.after["status"] == "UNKNOWN"
    assert data["ableton_ports"][0]["remote"] == "unknown"
    raw = midi_state.load_raw(midi)
    raw["devices"].append({"gear_ref": "retired", "role": "controller"})
    with pytest.raises(StoreError, match="inactive"):
        midi_state.propose_set_channel("retired", 1, data=raw, inventory_path=inventory)


def test_verify_batch_is_atomic_in_memory(midi_files):
    midi, inventory = midi_files
    before = midi.read_text(encoding="utf-8")
    preview, data = midi_state.propose_batch(
        [
            {"op": "set_channel", "gear_ref": "controller", "channel": 11},
            {"op": "set_clock_master", "ref": "ableton"},
            {
                "op": "set_clock_destination",
                "ref": "synth",
                "enabled": "on",
            },
            {
                "op": "ableton_set",
                "port_id": "controller-in",
                "track": "on",
                "remote": "on",
            },
        ],
        midi_path=midi,
        inventory_path=inventory,
    )
    assert preview.domain == "midi.verify"
    assert preview.changed
    assert midi.read_text(encoding="utf-8") == before
    assert data["channels"][0]["status"] == "VERIFIED"


def test_midi_projections_only_draw_explicit_connections(midi_files):
    midi, inventory = midi_files
    doc = midi_state.load_document(midi, inventory_path=inventory)
    topology = render_midi_topology_section(doc)
    clock = render_midi_clock_section(doc)
    diagram = render_midi_topology_mermaid(doc)
    assert "No verified physical links" in topology
    assert "INTENDED" in clock
    assert "UNKNOWN physical MIDI topology" in diagram
    assert "-->" not in diagram


def test_midi_commit_supports_question_evidence(midi_files, tmp_path):
    midi, inventory = midi_files
    questions = tmp_path / "questions.yaml"
    changes = tmp_path / "changes.yaml"
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "Clock master?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "target": {"domain": "midi.clock_master"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    changes.write_text("items: []\n", encoding="utf-8")
    preview, data = midi_state.propose_set_clock_master(
        "synth", midi_path=midi, inventory_path=inventory
    )
    current_service.commit_midi(
        data,
        preview,
        render=False,
        midi_path=midi,
        inventory_path=inventory,
        questions_path=questions,
        changes_path=changes,
        question_id="Q-001",
        resolve_q=True,
        answer="Synth verified as master",
    )
    assert load_questions(questions).question_map()["Q-001"].status == QuestionStatus.RESOLVED
    assert midi_state.load_document(midi, inventory_path=inventory).clock.master.gear_ref == "synth"
