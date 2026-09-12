"""Isolated fixture repositories for split stage-era tests."""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from music_rig import patchbay_state, store
from music_rig import store as store_mod
from music_rig.agent.provider import CommandProvider
from music_rig.reconciliation.context import ReconciliationContext

FIXTURE_PROVIDER = Path(__file__).resolve().parent / "fake_agent_provider.py"


def _clock():
    return datetime(2026, 9, 11, 21, 0, 0, tzinfo=UTC)


def _write_docs(tmp: Path) -> dict[str, Path]:
    paths = {}
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
        ("inventory.md", "<!-- rig:inventory:start -->", "<!-- rig:inventory:end -->"),
    ]:
        path = tmp / name
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")
        paths[name] = path
    return paths


def _write_docs_void(tmp: Path) -> None:
    """Side-effect-only docs markers (stage 20/21 style)."""
    _write_docs(tmp)


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inv = tmp_path / "inventory.yaml"
    pb = tmp_path / "patchbays.yaml"
    changes = tmp_path / "changes.yaml"
    inbox = tmp_path / "inbox.yaml"
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-100",
                        "question": "Iso?",
                        "area": "Test",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "n",
                        "resolved_at": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    todo.write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    wish.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    inv.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "iso-gear",
                        "name": "Iso",
                        "category": "utility",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    pb.write_text(
        yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-Z": {
                        "hardware_model": "unknown",
                        "status": "partially_documented",
                        "jacks": {
                            1: {
                                "row": "upper",
                                "connection": "A",
                                "paired_with": 25,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            25: {
                                "row": "lower",
                                "connection": "B",
                                "paired_with": 1,
                                "mode": "unknown",
                                "status": "documented",
                            },
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INVENTORY_PATH", inv)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", pb)
    return {"questions": questions, "inventory": inv, "patchbays": pb, "tmp": tmp_path}


@pytest.fixture
def fx15(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fixture with Q-080 (bay, no pair) — does not claim prod pair."""
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    inventory = tmp_path / "inventory.yaml"
    docs = _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-080"],
                "tasks": [
                    {
                        "id": "RIG-080",
                        "task": "Record fixture PB mode",
                        "area": "Patchbay",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "mode recorded",
                        "notes": "",
                    },
                    {
                        "id": "RIG-081",
                        "task": "Done task",
                        "area": "Docs",
                        "priority": "P3",
                        "status": "DONE",
                        "depends_on": [],
                        "definition_of_done": "x",
                        "notes": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "CHG-080",
                        "created_at": "2026-09-01T00:00:00+00:00",
                        "category": "PATCHBAY",
                        "summary": "fixture mode",
                        "details": "",
                        "status": "OPEN",
                        "session_id": None,
                        "affected_areas": ["patchbay"],
                        "related_questions": ["Q-080"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "test-gear",
                        "name": "Test",
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
                        "id": "Q-080",
                        "question": "What mode is fixture PB-B pair?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": ["RIG-080"],
                        "related_changes": ["CHG-080"],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            # pair intentionally null — fixture e2e completes it
                        },
                    },
                    {
                        "id": "Q-081",
                        "question": "Clock master in practice?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "midi.clock_master"},
                    },
                    {
                        "id": "Q-082",
                        "question": "Which unit is PB-A?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "inventory.patchbay_mapping"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
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
                                "connection": "A",
                                "paired_with": 25,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            25: {
                                "row": "lower",
                                "connection": "B",
                                "paired_with": 1,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            2: {
                                "row": "upper",
                                "connection": "C",
                                "paired_with": 26,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            26: {
                                "row": "lower",
                                "connection": "D",
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
    routing.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "space": {
                        "label": "SPACE",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "main",
                                "nodes": [{"id": "a", "label": "A"}],
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    midi.write_text(
        yaml.safe_dump(
            {
                "devices": [],
                "links": [],
                "channels": [],
                "clock": {
                    "master": {
                        "endpoint_ref": "ableton",
                        "status": "INTENDED",
                        "notes": "",
                    },
                    "destinations": [],
                    "transport": {"status": "UNKNOWN", "notes": ""},
                },
                "ableton_ports": [],
            }
        ),
        encoding="utf-8",
    )
    controllers.write_text(yaml.safe_dump({"controllers": []}), encoding="utf-8")
    ableton.write_text(
        yaml.safe_dump({"tracks": [], "sends": [], "actions": [], "templates": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "ROUTING_PATH", routing)
    monkeypatch.setattr(store, "MIDI_PATH", midi)
    monkeypatch.setattr(store, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(store, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(store, "DOCS_INVENTORY_PATH", docs["inventory.md"])
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)
    # render.py / midi_state import path constants by value — keep fixtures consistent
    from music_rig import midi_state
    from music_rig import render as render_mod

    monkeypatch.setattr(midi_state, "MIDI_PATH", midi)
    monkeypatch.setattr(render_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(render_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(render_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(render_mod, "TODO_PATH", todo)
    monkeypatch.setattr(render_mod, "WISHLIST_PATH", wish)
    monkeypatch.setattr(render_mod, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(render_mod, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(render_mod, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(render_mod, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(render_mod, "DOCS_INVENTORY_PATH", docs["inventory.md"])

    return {
        "questions": questions,
        "todo": todo,
        "changes": changes,
        "patchbays": patchbays,
        "routing": routing,
        "midi": midi,
        "inventory": inventory,
        "tmp": tmp_path,
    }


@pytest.fixture
def fx17(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    inventory = tmp_path / "inventory.yaml"
    docs = _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": [],
                "tasks": [
                    {
                        "id": "RIG-170",
                        "task": "Stage 17 clock",
                        "area": "MIDI",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "clock verified",
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
                        "id": "ableton",
                        "name": "Ableton",
                        "category": "software",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                        "quantity": 1,
                        "units": [{"id": "ableton-1"}],
                    },
                    {
                        "id": "behringer-fcb1010",
                        "name": "FCB1010",
                        "category": "controller",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                        "quantity": 1,
                        "units": [{"id": "behringer-fcb1010-1"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(yaml.safe_dump({"schema_notes": {}, "patchbays": {}}), encoding="utf-8")
    routing.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "kaoss": {
                        "label": "KAOSS",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "main",
                                "nodes": [{"id": "a", "label": "A"}],
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    midi.write_text(
        yaml.safe_dump(
            {
                "devices": [],
                "connections": [],
                "channels": [],
                "clock": {
                    "master": {
                        "endpoint_ref": "ableton",
                        "status": "INTENDED",
                        "notes": "",
                    },
                    "destinations": [],
                    "transport": {"status": "UNKNOWN", "notes": ""},
                },
                "ableton_ports": [],
                "endpoints": [
                    {"id": "ableton", "kind": "software", "name": "Ableton"},
                    {"id": "kaoss", "kind": "host", "name": "KAOSS"},
                ],
            }
        ),
        encoding="utf-8",
    )
    controllers.write_text(
        yaml.safe_dump(
            {
                "controllers": [
                    {
                        "gear_ref": "behringer-fcb1010",
                        "coverage": "PARTIAL",
                        "related_todos": [],
                        "notes": "",
                        "contexts": [
                            {
                                "id": "bank-00",
                                "label": "Bank 00",
                                "kind": "BANK",
                                "evidence": "INTENDED",
                                "notes": "",
                                "controls": [
                                    {
                                        "id": "sw1",
                                        "label": "Switch 1",
                                        "physical_type": "FOOTSWITCH",
                                        "availability": "AVAILABLE",
                                        "evidence": "INTENDED",
                                        "messages": [],
                                        "target": {"state": "UNASSIGNED"},
                                    }
                                ],
                            },
                            {
                                "id": "bank-01",
                                "label": "Bank 01",
                                "kind": "BANK",
                                "evidence": "INTENDED",
                                "notes": "",
                                "controls": [],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ableton.write_text(
        yaml.safe_dump(
            {
                "tracks": [],
                "sends": [],
                "actions": [],
                "templates": [
                    {
                        "id": "pfl-jam",
                        "label": "PFL Jam",
                        "evidence": "INTENDED",
                        "related_todos": [],
                        "notes": "",
                        "tracks": [],
                        "sends": [],
                        "requirements": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-170",
                        "question": "Is Ableton the MIDI clock master in practice?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": ["RIG-170"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "midi.clock_master"},
                        "verification": {
                            "kind": "MIDI_CLOCK",
                            "prompt": "Check who leads clock",
                            "answer_type": "ENUM",
                            "choices": ["ableton", "kaoss", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                        "verification_result": None,
                    },
                    {
                        "id": "Q-171",
                        "question": "Does FCB bank-00 work?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {
                            "domain": "controls.verify",
                            "gear": "behringer-fcb1010",
                            "context": "bank-00",
                        },
                        "verification": {
                            "kind": "CONTROLLER_MAPPING",
                            "prompt": "Test switch",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-172",
                        "question": "PFL jam template tracks?",
                        "area": "Ableton",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "ableton.template", "path": "pfl-jam"},
                        "verification": {
                            "kind": "ABLETON_SETTING",
                            "prompt": "Open Live set",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-173",
                        "question": "Does kaoss path match?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "routing.verify", "path": "kaoss"},
                        "verification": {
                            "kind": "ROUTING_COMPARE",
                            "prompt": "Trace path",
                            "answer_type": "BOOL",
                            "choices": ["YES", "NO", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-174",
                        "question": "Freeform topology?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "Describe",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "ROUTING_PATH", routing)
    monkeypatch.setattr(store, "MIDI_PATH", midi)
    monkeypatch.setattr(store, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(store, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(store, "DOCS_INVENTORY_PATH", docs["inventory.md"])

    from music_rig import (
        ableton_state as ableton_mod,
    )
    from music_rig import (
        control_state as control_mod,
    )
    from music_rig import (
        current_service as current_mod,
    )
    from music_rig import (
        midi_state as midi_mod,
    )
    from music_rig import render as render_mod
    from music_rig import (
        routing_state as routing_mod,
    )

    monkeypatch.setattr(midi_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(control_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(control_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(control_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(ableton_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(routing_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(current_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(current_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(current_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(current_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(current_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(current_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(current_mod, "CHANGES_PATH", changes)
    for attr, path in [
        ("MIDI_PATH", midi),
        ("CONTROLLERS_PATH", controllers),
        ("ABLETON_PATH", ableton),
        ("INVENTORY_PATH", inventory),
        ("ROUTING_PATH", routing),
        ("QUESTIONS_PATH", questions),
    ]:
        if hasattr(render_mod, attr):
            monkeypatch.setattr(render_mod, attr, path)

    # Avoid performance validation pulling production files
    perf = tmp_path / "performance.yaml"
    perf.write_text(
        yaml.safe_dump(
            {
                "modes": [],
                "actions": [],
                "bindings": [],
                "recovery": [],
                "requirements": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "PERFORMANCE_PATH", perf)
    if hasattr(control_mod, "PERFORMANCE_PATH"):
        monkeypatch.setattr(control_mod, "PERFORMANCE_PATH", perf)

    return {
        "questions": questions,
        "midi": midi,
        "ableton": ableton,
        "controllers": controllers,
        "routing": routing,
        "changes": changes,
    }


@pytest.fixture
def fx19(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    channels = tmp_path / "channel-map.yaml"
    routing = tmp_path / "routing.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-190"],
                "tasks": [
                    {
                        "id": "RIG-190",
                        "task": "Document A/B/Y destinations",
                        "area": "Routing",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "CURRENT matches answer",
                        "notes": "",
                    },
                    {
                        "id": "RIG-191",
                        "task": "Terminal leftover",
                        "area": "Docs",
                        "priority": "P3",
                        "status": "DONE",
                        "depends_on": [],
                        "definition_of_done": "x",
                        "notes": "",
                    },
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
                        "id": "fx-gear",
                        "name": "FX Gear",
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
                        "id": "Q-190",
                        "question": "Where do A/B/Y non-clean sends go?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": ["RIG-190"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "target": {"domain": "routing.path", "path": "aby-other"},
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "Observe A/B/Y destinations",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-191",
                        "question": "Simple open unanswered",
                        "area": "Docs",
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
    channels.write_text(
        yaml.safe_dump(
            {
                "tascam": {
                    1: {"type": "line", "status": "UNASSIGNED", "source": None},
                    2: {"type": "line", "status": "UNASSIGNED", "source": None},
                },
                "alesis": {
                    1: {"status": "UNASSIGNED", "source": None},
                    2: {"status": "UNASSIGNED", "source": None},
                    3: {"status": "UNASSIGNED", "source": None},
                },
            }
        ),
        encoding="utf-8",
    )
    routing.write_text(
        yaml.safe_dump(
            {
                "named_paths": {
                    "aby-other": {
                        "summary": "A/B/Y other",
                        "status": "CURRENT",
                        "branches": {
                            "a": {"nodes": [{"id": "n1", "label": "A", "gear_ref": "fx-gear"}]}
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text("patchbays: {}\n", encoding="utf-8")

    monkeypatch.setattr("music_rig.store.QUESTIONS_PATH", questions)
    monkeypatch.setattr("music_rig.store.TODO_PATH", todo)
    monkeypatch.setattr("music_rig.store.WISHLIST_PATH", wish)
    monkeypatch.setattr("music_rig.store.INBOX_PATH", inbox)
    monkeypatch.setattr("music_rig.store.CHANGES_PATH", changes)
    monkeypatch.setattr("music_rig.store.CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr("music_rig.store.ROUTING_PATH", routing)
    monkeypatch.setattr("music_rig.store.PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr("music_rig.store.INVENTORY_PATH", inventory)
    monkeypatch.setattr("music_rig.channel_state.CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr("music_rig.routing_state.ROUTING_PATH", routing)

    # Never write production docs from fixture mutations
    from music_rig import question_service as qs_mod
    from music_rig import render as render_mod
    from music_rig import todo_service as ts_mod

    def _noop_render(**kwargs):
        return False, []

    monkeypatch.setattr(render_mod, "render_docs", _noop_render)
    monkeypatch.setattr(qs_mod, "render_docs", _noop_render)
    monkeypatch.setattr(ts_mod, "render_docs", _noop_render)
    monkeypatch.setattr(
        "music_rig.reconciliation.service._render_planning_and_patchbay",
        lambda *a, **k: None,
    )

    return {
        "questions": questions,
        "todo": todo,
        "channels": channels,
        "routing": routing,
        "tmp": tmp_path,
    }


@pytest.fixture
def fx20(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    channels = tmp_path / "channel-map.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-200"],
                "tasks": [
                    {
                        "id": "RIG-200",
                        "task": "Map patchbay models",
                        "area": "Patchbay",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "models recorded",
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
                        "id": "art-p48-1",
                        "name": "ART P48 #1",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
                    {
                        "id": "behringer-px3000-1",
                        "name": "Behringer PX3000 #1",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
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
                        "id": "Q-200",
                        "question": "PB models?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": "PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "inventory.patchbay_mapping"},
                        "verification": {
                            "kind": "PATCHBAY_UNIT",
                            "prompt": "read faceplates",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-201",
                        "question": "Broken target?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "normal",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": None,
                        },
                        "verification": {
                            "kind": "PATCHBAY_MODE",
                            "prompt": "mode",
                            "answer_type": "ENUM",
                            "choices": ["normal", "thru"],
                        },
                    },
                    {
                        "id": "Q-202",
                        "question": "Ambiguous destinations",
                        "area": "Routing",
                        "status": "RESOLVED",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "maybe Alesis 2 or maybe Alesis 3 for acoustic",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "routing.verify"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        "# test\n"
        + yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-A": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-B": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-C": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-D": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                },
            }
        ),
        encoding="utf-8",
    )
    channels.write_text("devices: {}\n", encoding="utf-8")
    routing.write_text("paths: []\n", encoding="utf-8")
    midi.write_text("{}\n", encoding="utf-8")
    controllers.write_text("{}\n", encoding="utf-8")
    ableton.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store_mod, "TODO_PATH", todo)
    monkeypatch.setattr(store_mod, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store_mod, "INBOX_PATH", inbox)
    monkeypatch.setattr(store_mod, "CHANGES_PATH", changes)
    monkeypatch.setattr(store_mod, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store_mod, "CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr(store_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(store_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(store_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store_mod, "DOCS_TODO_PATH", tmp_path / "todo.md")
    monkeypatch.setattr(store_mod, "DOCS_WISHLIST_PATH", tmp_path / "wishlist.md")
    monkeypatch.setattr(store_mod, "DOCS_QUESTIONS_PATH", tmp_path / "open-questions.md")
    monkeypatch.setattr(store_mod, "DOCS_PATCHBAYS_PATH", tmp_path / "patchbays.md")
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)

    ctx = ReconciliationContext.for_root(tmp_path)
    return {"tmp": tmp_path, "ctx": ctx, "questions": questions, "patchbays": patchbays}


def _minimal_routing() -> dict:
    return {
        "routes": {},
        "named_paths": {
            "dirty": {
                "label": "DIRTY",
                "status": "CURRENT",
                "evidence": "UNKNOWN",
                "branches": {
                    "main": {
                        "label": "Main",
                        "nodes": [
                            {"id": "a", "label": "A"},
                            {"id": "b", "label": "B"},
                            {"id": "c", "label": "C"},
                        ],
                    }
                },
            }
        },
    }


def _install_fake_provider(tmp: Path) -> Path:
    dest = tmp / "fake_agent_provider.py"
    shutil.copy(FIXTURE_PROVIDER, dest)
    dest.chmod(0o755)
    return dest


def _provider(
    script: Path,
    *,
    mode: str,
    state: Path | None = None,
    probe: Path | None = None,
    timeout_seconds: int = 2,
    max_stdout_bytes: int = 1_000_000,
) -> CommandProvider:
    forward = ["FAKE_PROVIDER_MODE"]
    if state is not None:
        forward.append("FAKE_PROVIDER_STATE")
    if probe is not None:
        forward.append("CWD_PROBE_PATH")
    return CommandProvider(
        argv=[sys.executable, str(script)],
        timeout_seconds=timeout_seconds,
        env_forward=forward,
        max_stdout_bytes=max_stdout_bytes,
    )


@pytest.fixture
def fx21(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    channels = tmp_path / "channel-map.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-200"],
                "tasks": [
                    {
                        "id": "RIG-200",
                        "task": "Map patchbay models",
                        "area": "Patchbay",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "models recorded",
                        "notes": "",
                    },
                    {
                        "id": "RIG-001",
                        "task": "Map Alesis returns",
                        "area": "Routing",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "channels recorded",
                        "notes": "",
                    },
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
                        "id": "art-p48-1",
                        "name": "ART P48 #1",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
                    {
                        "id": "behringer-px3000-1",
                        "name": "Behringer PX3000 #1",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
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
                        "id": "Q-200",
                        "question": "PB models?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": ("PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000"),
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "inventory.patchbay_mapping"},
                        "verification": {
                            "kind": "PATCHBAY_UNIT",
                            "prompt": "read faceplates",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-001",
                        "question": "Where do A/B/Y non-clean legs go?",
                        "area": "Routing",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-001"],
                        "related_changes": [],
                        "answer": "Acoustic: Alesis 2, bass: Alesis 1, electric: Alesis 3",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "routing.verify"},
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "trace cables",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-007",
                        "question": "Which unit is each bay?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": ("PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000"),
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "inventory.patchbay_mapping"},
                        "verification": {
                            "kind": "PATCHBAY_UNIT",
                            "prompt": "read faceplates",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-210",
                        "question": "Multi-domain fixture",
                        "area": "Routing",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": ("Alesis 2=Acoustic; PB-A is ART P48 for the return path"),
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "inventory.patchbay_mapping"},
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "observe",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        "# test\n"
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
                        "status": "undocumented",
                        "jacks": {},
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
    channels.write_text(
        yaml.safe_dump(
            {
                "alesis": {
                    "1": {"source": None, "status": "UNASSIGNED"},
                    "2": {"source": None, "status": "UNASSIGNED"},
                    "3": {"source": None, "status": "UNASSIGNED"},
                }
            }
        ),
        encoding="utf-8",
    )
    routing.write_text(yaml.safe_dump(_minimal_routing()), encoding="utf-8")
    midi.write_text(
        yaml.safe_dump({"clock": {"transport": {"status": "UNKNOWN"}}}),
        encoding="utf-8",
    )
    controllers.write_text("controllers: []\n", encoding="utf-8")
    ableton.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store_mod, "TODO_PATH", todo)
    monkeypatch.setattr(store_mod, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store_mod, "INBOX_PATH", inbox)
    monkeypatch.setattr(store_mod, "CHANGES_PATH", changes)
    monkeypatch.setattr(store_mod, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store_mod, "CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr(store_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(store_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(store_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store_mod, "DOCS_TODO_PATH", tmp_path / "todo.md")
    monkeypatch.setattr(store_mod, "DOCS_WISHLIST_PATH", tmp_path / "wishlist.md")
    monkeypatch.setattr(store_mod, "DOCS_QUESTIONS_PATH", tmp_path / "open-questions.md")
    monkeypatch.setattr(store_mod, "DOCS_PATCHBAYS_PATH", tmp_path / "patchbays.md")
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)

    script = _install_fake_provider(tmp_path)
    ctx = ReconciliationContext.for_root(tmp_path)
    return {
        "tmp": tmp_path,
        "ctx": ctx,
        "questions": questions,
        "patchbays": patchbays,
        "channels": channels,
        "routing": routing,
        "script": script,
    }
