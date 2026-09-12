# Open Questions

Unresolved **facts** about the rig. These are not tasks.

```text
Question = an unresolved factual uncertainty.
```

Actions that resolve them live in [Todo](todo.md). Speculative purchases live in [Wishlist](wishlist.md).

Canonical data: `data/open-questions.yaml`. Edit via `uv run rig question …` or the YAML file, then `uv run rig render`.

Resolving a question records an answer. It does **not** automatically rewrite CURRENT routing docs.

<!-- rig:questions:start -->
<!-- GENERATED FROM data/open-questions.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Open

| ID | Area | Question | Related TODOs | Related Changes |
|---|---|---|---|---|
| Q-005 | Routing | Should the PYLE-PRO dual DI live near the Privia, near the JOYO output, or near clean instrument taps? | RIG-024 | — |
| Q-008 | Patchbay | What normalization mode (normal / half-normal / thru) is each populated PB-B pair set to? | RIG-002 | — |
| Q-009 | Patchbay | What are the rear-panel assignments for PB-A, PB-C, and PB-D? | RIG-005, RIG-040 | — |
| Q-010 | Patchbay | What (if anything) should feed PB-B upper 9–12 into lower 33–36? | RIG-006 | — |
| Q-011 | Pedals / power | Do the physical DIRTY and SPACE boards match docs/pedal-chains.md? | RIG-001 | — |
| Q-012 | Pedals / power | Where are Flamma Mod and PH-2 right now (disconnected, stored, elsewhere)? | RIG-011 | — |
| Q-013 | Pedals / power | What is each CURRENT pedal’s voltage, current draw, and power-supply assignment? | RIG-047 | — |
| Q-014 | MIDI | Is Ableton definitely the master clock in practice, or do KAOSS/SL-2 sometimes lead? | RIG-031 | — |
| Q-015 | MIDI | What is the verified physical MIDI topology using U6MIDI Pro + Thru5 WC? | RIG-037 | — |
| Q-016 | MIDI | What exact FCB1010 switch map is assigned in banks 00/01/02? | RIG-035 | — |
| Q-017 | MIDI | Which ReMOTE ZeRO SL templates are actually loaded on the device? | RIG-036 | — |
| Q-018 | Performance / video | What are the exact active tracks in the current PFL jam Ableton set? | RIG-034, RIG-038 | — |
| Q-019 | Performance / video | What OBS camera angles are already covered by owned webcams? | RIG-042 | — |
| Q-020 | Performance / video | What is the default one-player loop-building order (RC-1 vs KAOSS vs future RC-600)? | RIG-038 | — |

## Deferred

| ID | Area | Question | Related TODOs | Related Changes |
|---|---|---|---|---|
| — | — | — | — | — |

## Resolved

| ID | Area | Question | Related TODOs | Related Changes |
|---|---|---|---|---|
| Q-001 | Routing | Where does the non-clean leg of each A/B/Y splitter go (acoustic, bass, electric)? | RIG-003 | — |
| Q-002 | Routing | Does acoustic have an Alesis channel assignment, or only the TASCAM 5 clean path? | RIG-008 | — |
| Q-003 | Routing | What exact jack(s) receive CH-1 stereo back into the Alesis? | RIG-009 | — |
| Q-004 | Routing | Does physical KAOSS monitor/capture match documented Monitor Out → KAOSS → TASCAM 9/10? | RIG-010 | — |
| Q-006 | Routing | Should LS-2 also remain a bass split/blend tool outside its CURRENT SPACE role? | RIG-025 | — |
| Q-007 | Patchbay | Which physical unit is PB-A / PB-B / PB-C / PB-D (ART P48 vs Behringer PX3000)? | RIG-004 | — |

## Answers and notes

### Q-001 — RESOLVED

Where does the non-clean leg of each A/B/Y splitter go (acoustic, bass, electric)?

**Answer:** Acoustic: Alesis 2, bass: Alesis 1, electric: Alesis 3

**Resolved at:** 2026-09-11T23:39:04.262510-04:00

**Reconciled at:** 2026-09-11T23:39:32.754470-04:00

**Reconciliation note:** Agent applied answer via CURRENT CLI: path aby-other → Alesis 2/1/3 (acoustic/bass/electric); alesis channels 2→Acoustic, 3→Electric (1 already Bass). No verification_result invented.

### Q-002 — RESOLVED

Does acoustic have an Alesis channel assignment, or only the TASCAM 5 clean path?

**Answer:** Alesis 2

**Resolved at:** 2026-09-11T23:48:43.027898-04:00

**Reconciled at:** 2026-09-11T23:49:40.822430-04:00

**Reconciliation note:** Answer Alesis 2 already CURRENT from Q-001 (acoustic aby-other + alesis ch2). No verification_result invented.

### Q-003 — RESOLVED

What exact jack(s) receive CH-1 stereo back into the Alesis?

**Answer:** Alesis Return 1 and 2

**Resolved at:** 2026-09-11T23:48:43.924532-04:00

**Reconciled at:** 2026-09-11T23:49:41.313290-04:00

**Reconciliation note:** Updated aux path return endpoint to Alesis Return 1 and 2 via current path CLI.

### Q-004 — RESOLVED

Does physical KAOSS monitor/capture match documented Monitor Out → KAOSS → TASCAM 9/10?

**Answer:** TASCAM 3/4 -> KAOSS -> TASCAM 15/16

**Resolved at:** 2026-09-11T23:48:44.805664-04:00

**Reconciled at:** 2026-09-11T23:49:41.804328-04:00

**Reconciliation note:** Corrected KAOSS path to TASCAM 3/4 -> KAOSS -> TASCAM 15/16; channels 9/10 cleared, 15/16 KAOSS. Evidence not VERIFIED (no verification_result). miniKORG still on TASCAM 3/4 inputs — dual-use noted.

### Q-006 — RESOLVED

Should LS-2 also remain a bass split/blend tool outside its CURRENT SPACE role?

**Answer:** no, it is only in SPACE

**Resolved at:** 2026-09-11T23:48:45.715212-04:00

**Reconciled at:** 2026-09-11T23:49:42.282222-04:00

**Reconciliation note:** Descriptive decision: LS-2 SPACE-only; no CURRENT topology change.

### Q-007 — RESOLVED

Which physical unit is PB-A / PB-B / PB-C / PB-D (ART P48 vs Behringer PX3000)?

**Answer:** PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000

**Resolved at:** 2026-09-12T09:34:18.085029-04:00

### Q-009 — OPEN

What are the rear-panel assignments for PB-A, PB-C, and PB-D?

**Notes:** Assignments remain UNKNOWN until inspected.

### Q-020 — OPEN

What is the default one-player loop-building order (RC-1 vs KAOSS vs future RC-600)?

**Notes:** Also related to Wishlist playbook IDEA; jam template work tracked under RIG-038.

## ID allocation

Next free ID: **Q-021**.
<!-- rig:questions:end -->

## Hardware candidates

Purchase candidates are on the [Wishlist](wishlist.md). Generic MIDI thru/splitter is **REDUNDANT** (owned CME gear). Isolated power and line-to-pedal isolation remain RESEARCH pending audits (RIG-047, RIG-048).
