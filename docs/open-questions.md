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
| Q-001 | Routing | Where does the non-clean leg of each A/B/Y splitter go (acoustic, bass, electric)? | RIG-003 | — |
| Q-002 | Routing | Does acoustic have an Alesis channel assignment, or only the TASCAM 5 clean path? | RIG-008 | — |
| Q-003 | Routing | What exact jack(s) receive CH-1 stereo back into the Alesis? | RIG-009 | — |
| Q-004 | Routing | Does physical KAOSS monitor/capture match documented Monitor Out → KAOSS → TASCAM 9/10? | RIG-010 | — |
| Q-005 | Routing | Should the PYLE-PRO dual DI live near the Privia, near the JOYO output, or near clean instrument taps? | RIG-024 | — |
| Q-006 | Routing | Should LS-2 also remain a bass split/blend tool outside its CURRENT SPACE role? | RIG-025 | — |
| Q-007 | Patchbay | Which physical unit is PB-A / PB-B / PB-C / PB-D (ART P48 vs Behringer PX3000)? | RIG-004 | — |
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
| — | — | — | — | — |

## Answers and notes

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
