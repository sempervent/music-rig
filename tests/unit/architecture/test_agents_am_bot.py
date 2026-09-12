"""Agent docs: workflow `uv run rig` examples should include `--am-bot`."""

from __future__ import annotations

import re
from pathlib import Path

from music_rig.store import ROOT


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:bash|shell|sh)\n(.*?)```", text, flags=re.DOTALL)


def _rig_lines(block: str) -> list[str]:
    lines = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "uv run rig" in line or line.startswith("rig "):
            lines.append(line)
    return lines


def test_agents_md_workflow_rig_commands_include_am_bot():
    """AGENTS.md command blocks that invoke rig should use --am-bot.

    Skips Incorrect contrast examples and HUMAN-only surfaces (TUI).
    """
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    # Drop Incorrect contrast sections so bad examples don't fail the guard.
    cleaned = re.sub(
        r"(?is)Incorrect:.*?```.*?```",
        "",
        text,
    )
    offenders: list[str] = []
    for block in _bash_blocks(cleaned):
        for line in _rig_lines(block):
            if "without --am-bot" in line or "Incorrect" in line:
                continue
            # TUI is HUMAN-only — bots must not use --am-bot tui.
            if re.search(r"\brig tui\b", line):
                continue
            if "uv run rig" in line and "--am-bot" not in line:
                offenders.append(line)
            if re.match(r"^rig (?!--am-bot)", line):
                offenders.append(line)
    assert not offenders, "AGENTS.md rig examples missing --am-bot:\n" + "\n".join(
        offenders
    )


def test_skills_md_agent_workflow_mentions_am_bot():
    text = (ROOT / "SKILLS.md").read_text(encoding="utf-8")
    assert "--am-bot" in text
    # At least one correct agent invocation pattern.
    assert "uv run rig --am-bot" in text or "rig --am-bot" in text
