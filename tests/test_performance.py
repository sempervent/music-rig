from __future__ import annotations

from typer.testing import CliRunner

import pytest

from music_rig import performance_state
from music_rig.cli import app
from music_rig.models import (
    MidiEvidenceStatus,
    PerformanceDocument,
    ReadinessResult,
)
from music_rig.store import StoreError

runner = CliRunner()


def _fixture_doc(*, with_binding: bool) -> PerformanceDocument:
    return PerformanceDocument.model_validate(
        {
            "modes": [
                {
                    "id": "pfl-jam",
                    "label": "PFL JAM",
                    "purpose": "test",
                    "evidence": "VERIFIED",
                    "required_actions": ["stop"],
                }
            ],
            "actions": [
                {
                    "id": "stop",
                    "label": "Stop",
                    "category": "RECOVERY",
                    "criticality": "EMERGENCY",
                    "evidence": "VERIFIED",
                    "effects": [
                        {
                            "kind": "OBS_ACTION",
                            "effect_id": "obs-stop",
                            "evidence": "VERIFIED",
                        }
                    ],
                }
            ],
            "bindings": (
                [
                    {
                        "id": "stop-binding",
                        "action_ref": "stop",
                        "surface_ref": "elgato-stream-deck-plus",
                        "context_ref": "obs-safe",
                        "control_ref": "stop-recording",
                        "evidence": "VERIFIED",
                    }
                ]
                if with_binding
                else []
            ),
            "recovery": [
                {
                    "id": "emergency",
                    "label": "Emergency",
                    "severity": "EMERGENCY",
                    "symptom": "test",
                    "action_refs": ["stop"],
                    "manual_steps": [],
                    "keyboard_mouse_required": False,
                    "evidence": "VERIFIED",
                }
            ],
            "requirements": [],
        }
    )


def test_production_loads_partial_without_verified_upgrades():
    doc = performance_state.load_document()
    readiness = performance_state.evaluate_readiness(doc)
    assert readiness.result == ReadinessResult.PARTIAL
    assert all(action.evidence != MidiEvidenceStatus.VERIFIED for action in doc.actions)
    assert all(binding.evidence != MidiEvidenceStatus.VERIFIED for binding in doc.bindings)
    assert all(item.evidence != MidiEvidenceStatus.VERIFIED for item in doc.recovery)


def test_ready_and_not_ready_fixtures():
    assert (
        performance_state.evaluate_readiness(_fixture_doc(with_binding=True)).result
        == ReadinessResult.READY
    )
    assert (
        performance_state.evaluate_readiness(_fixture_doc(with_binding=False)).result
        == ReadinessResult.NOT_READY
    )


def test_bind_and_unbind_round_trip_in_memory():
    preview, data = performance_state.propose_bind(
        "next-scene",
        "obs-safe",
        "known-scene",
        surface_ref="elgato-stream-deck-plus",
        binding_id="test-next-scene",
    )
    assert preview.changed
    assert any(item["id"] == "test-next-scene" for item in data["bindings"])
    preview, data = performance_state.propose_unbind(
        "test-next-scene", data=data
    )
    assert preview.changed
    assert not any(item["id"] == "test-next-scene" for item in data["bindings"])


def test_broken_control_binding_rejected():
    with pytest.raises(StoreError, match="BROKEN"):
        performance_state.propose_bind(
            "next-scene",
            "pfl-send-c",
            "encoder-06",
            controller_ref="novation-remote-zero-sl",
        )


def test_verify_batch_is_transactional_in_memory():
    preview, data = performance_state.propose_batch(
        [
            {
                "op": "set_evidence",
                "binding_id": "streamdeck-obs-safe-stop-rec",
                "evidence": "VERIFIED",
            },
            {
                "op": "set_recovery_evidence",
                "recovery_id": "wrong-scene",
                "evidence": "VERIFIED",
            },
        ]
    )
    assert preview.changed
    assert next(
        item for item in data["bindings"] if item["id"] == "streamdeck-obs-safe-stop-rec"
    )["evidence"] == "VERIFIED"
    assert next(item for item in data["recovery"] if item["id"] == "wrong-scene")[
        "evidence"
    ] == "VERIFIED"


def test_now_play_remains_available_with_partial_readiness():
    result = runner.invoke(app, ["now", "--play"])
    assert result.exit_code == 0
    assert "PLAY" in result.stdout
    assert "PFL JAM" in result.stdout
    assert "rig performance mode pfl-jam" in result.stdout
