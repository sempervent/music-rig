# Reconciliation architecture

Question ↔ CURRENT reconciliation lives under `src/music_rig/reconciliation/`.

## Module ownership

| Module | Owns |
|---|---|
| `service.py` | **Public façade** — stable API for CLI/TUI (queue/plan/apply/finalize/sweep) |
| `dispatch.py` | **Decision/routing only** — who acts next (HUMAN / DETERMINISTIC / AGENT) |
| `run.py` | **End-to-end orchestration** — `rig reconcile run` |
| `context.py` | **State access / context construction** — paths + request-scoped cache |
| `operations.py` / `operation_registry.py` | Typed allowlisted actions + registry |
| `preparers.py` | Prepare mutations without commit |
| `action_packet.py` | Agent handoff packets (structured ops first) |
| `suggestions.py` | Canonical `ActionSuggestion` model |
| `operation_renderer.py` | **CLI syntax presentation** (`uv run rig` / `--am-bot`) |
| `adapters/` | Domain-specific plan/apply/verify |
| `checks/` | Sweep inspect findings |

## Authority flow

```text
HUMAN answer / observation
        │
        ▼
   dispatch.py  ── classifies next actor
        │
        ├── HUMAN_*     → stop; return structured suggestions
        ├── DETERMINISTIC / FINALIZE → service apply/finalize
        └── AGENT       → provider + typed RigOperation transaction
                │
                ▼
         preparers → transaction commit
```

Bots never invent HUMAN answers or observations. Prefer `question draft` for
suggestions; humans Answer & Resolve / verify.

## Suggestions vs shell strings

- **Canonical:** `Plan.suggestions: list[ActionSuggestion]`
- **Deprecated compat:** `Plan.suggested_commands: list[str]` — rendered at
  `Plan.to_dict()` / `__post_init__` via `operation_renderer` /
  `suggestions.render_suggestion` (actor-aware: BOT → `uv run rig --am-bot …`)
- Action packets expose `candidate_operations` / `finalize_operation` as
  structured; `finalize_command_template` and `suggested_current_commands` are
  **presentation-only**

CLI syntax is rendered in `operation_renderer.py` / `suggestions.py` — not in
adapters as the source of truth.

## Context entrypoints

Prefer:

```python
ctx = ReconciliationContext.default()       # production
ctx = ReconciliationContext.for_root(tmp)   # fixtures
ctx = ReconciliationContext.from_overrides({...})  # legacy *_path kwargs
```

Service façades accept `ctx=` and normalize legacy `*_path` kwargs at the
boundary only. `path_dict()` remains a temporary adapter dict; new code should
prefer typed `ctx.paths.*`.

## Performance notes

`scripts/bench_reconciliation.py` measures plan + sweep dry-run on synthetic
repos (10 / 100 / 500 questions). A single `plan_question` loads questions
**once** (todo/changes unused on that path) — no request-scoped document cache
is required for plan. Sweep cost grows with question count because checks
inspect every item; that is separate from per-plan load duplication.

## Related docs

- [Testing](testing.md) — suite layout and markers
- [Open questions](open-questions.md) — human-facing Q view
- [AGENTS.md](../AGENTS.md) — bot must use `--am-bot`
