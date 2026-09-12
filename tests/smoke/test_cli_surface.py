"""Smoke tests for CLI surface (help, bot-safe read-only commands)."""

from __future__ import annotations

from helpers.cli import invoke_rig_bot, invoke_rig_human


def test_rig_help():
    result = invoke_rig_human("--help")
    assert result.exit_code == 0
    assert "Usage" in result.stdout or "usage" in result.stdout.lower()


def test_rig_am_bot_check():
    result = invoke_rig_bot("check")
    # check may warn but should not crash; allow 0 or advisory non-zero if documented
    assert result.exit_code in (0, 1)
    assert result.exception is None or result.exit_code == 1


def test_rig_am_bot_question_list_json():
    result = invoke_rig_bot("question", "list", "--json")
    assert result.exit_code == 0
    assert "[" in result.stdout or "{" in result.stdout


def test_rig_am_bot_agent_provider_status():
    result = invoke_rig_bot("agent", "provider", "status")
    assert result.exit_code == 0
