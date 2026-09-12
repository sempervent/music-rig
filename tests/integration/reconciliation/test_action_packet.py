"""Tests migrated to integration/reconciliation/test_action_packet.py."""

from __future__ import annotations

from fixtures.repo_fixtures import _clock
from music_rig import (
    question_service,
    verification_service,
)
from music_rig.models import (
    QuestionStatus,
)
from music_rig.reconciliation import service as reconcile_service


def test_action_packet_contents(fx17):
    question_service.answer_question(
        "Q-174", "splitter goes to pedalboard", clock=_clock, render=False
    )
    plan = reconcile_service.plan_question("Q-174")
    packet = (plan.details or {}).get("action_packet")
    assert packet is not None
    assert "human_answer" in packet
    assert "suggested_command_families" in packet
    assert "postcondition" in packet
    assert "related_ids" in packet
    joined = " ".join(packet["suggested_command_families"]).casefold()
    assert "yaml" not in joined or "edit" not in joined


def test_sweep_unlock_and_failed_test_guard(fx17):
    verification_service.record_observation(
        "Q-170",
        "confirmed",
        value="ableton",
        clock=_clock,
        render=False,
    )
    reconcile_service.apply_question("Q-170", dry_run=False, yes=True)
    sweep = reconcile_service.sweep(dry_run=True, yes=True, confirm_dod=True)
    assert "Q-170" in sweep.get("would_finalize", []) or sweep["counts"]["ready_to_finalize"] >= 1

    # FAILED_TEST leaves question OPEN — never finalized as success
    verification_service.record_observation(
        "Q-171",
        "failed_test",
        note="broken",
        clock=_clock,
        render=False,
    )
    assert question_service.get_question("Q-171").status == QuestionStatus.OPEN
    sweep2 = reconcile_service.sweep(dry_run=True, yes=True, confirm_dod=True)
    assert "Q-171" not in sweep2.get("would_finalize", [])
    assert "Q-171" not in sweep2.get("finalized", [])

    # Also guard RESOLVED + FAILED_TEST observation
    question_service.answer_question("Q-171", "map documented", clock=_clock, render=False)
    verification_service.record_observation(
        "Q-171",
        "failed_test",
        value="did not work",
        note="broken",
        clock=_clock,
        render=False,
    )
    sweep3 = reconcile_service.sweep(dry_run=True, yes=True, confirm_dod=True)
    skipped = {s["id"]: s.get("reason", "") for s in sweep3["skipped"]}
    assert "Q-171" in skipped
    assert "FAILED_TEST" in skipped["Q-171"]
    assert "Q-171" not in sweep3.get("would_finalize", [])
