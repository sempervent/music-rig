# Human authority handoff

Pending HUMAN authority requests live in `data/human-actions.yaml`.

These are **proposals**, not factual truth. Accepting them records HUMAN
authority through the same services as direct CLI/TUI.

## Commands

```bash
# BOT prepares (safe)
uv run rig --am-bot human prepare QUESTION_ANSWER Q-008 \
  --value "…" --prompt "…" --why "…"

# HUMAN reviews one inbox
uv run rig human review
uv run rig human pending
uv run rig human accept HAR-001
uv run rig human reject HAR-001

# TUI
uv run rig tui human
```

`uv run rig --am-bot human accept …` is rejected.

## Action types

| Type | Accepts into |
|---|---|
| QUESTION_ANSWER | `question_service.answer_question` (`answer_actor=HUMAN`) |
| VERIFICATION_RESULT | `verification_service.record_observation` |
| TODO_DOD_CONFIRMATION | `todo_service.set_todo_status(…, DONE)` after showing DoD |
| HUMAN_CLARIFICATION | Question answer, or Thru5 OUT map notes (no invented links) |

Stale proposals (target already HUMAN-final / DONE) become `SUPERSEDED`.
