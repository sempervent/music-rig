# Operational readiness (Stage 24)

Working document for burning down open Questions and establishing a known-good
playable baseline. **No HUMAN answers are invented here.**

Pre-Stage-24 snapshot: `SNAP-20260912-153105` (post Stage 23 merge `c11aac5`).

## Baseline census (post Stage 23)

| Metric | Count |
|---|---:|
| Questions total | 20 |
| FINAL / reconciled | 7 (6 LEGACY + 1 HUMAN Q-014) |
| OPEN | 13 |
| OPEN + `EXPLICIT_OBSERVATION_REQUIRED` | 2 (Q-016, Q-017) |
| TODOs READY | 32 |
| TODOs DONE | 6 |
| TODOs WAITING | 5 |
| TODOs BLOCKED | 1 (RIG-040) |
| Next Session | RIG-001, RIG-002 |

## OPEN Question triage

Priority = effect on sitting down and making sound safely.

| ID | Pri | Class | Area | Next actor | Why | Highest-value consequence |
|---|---|---|---|---|---|---|
| Q-018 | P0 | HUMAN_ANSWER | Performance | HUMAN | Need exact Live-set tracks for turn-on-and-play | Unlocks PFL JAM template / smoke / reference jam |
| Q-011 | P0 | HUMAN_ANSWER | Pedals | HUMAN | Wet path must match documented DIRTY/SPACE | Safe AUX loop / smoke test |
| Q-015 | P0 | HUMAN_ANSWER | MIDI | HUMAN | Clock/control depend on real U6MIDI+Thru5 wiring | Sync + controller delivery |
| Q-008 | P0 | HUMAN_ANSWER | Patchbay | HUMAN | PB-B modes UNKNOWN can silently alter signals | Correct patchbay behavior (Next Session) |
| Q-016 | P1 | EXPLICIT_HUMAN_OBSERVATION | MIDI/Control | HUMAN | Foot control for loop/panic unknown | One-performer control + recovery |
| Q-017 | P1 | EXPLICIT_HUMAN_OBSERVATION | MIDI/Control | HUMAN | ZeRO templates unknown | Desk control surface reliability |
| Q-020 | P1 | HUMAN_ANSWER | Performance | HUMAN | Default loop order is a workflow decision | Reference jam recipe |
| Q-010 | P1 | HUMAN_ANSWER | Patchbay | HUMAN | Lower 33–36 sources undecided | Completes PB-B usability |
| Q-009 | P2 | HUMAN_ANSWER | Patchbay | HUMAN | Rear panels of PB-A/C/D unknown | Docs accuracy; RIG-040 still BLOCKED until design |
| Q-005 | P2 | HUMAN_ANSWER | Routing | HUMAN | PYLE-PRO placement preference | Convenience; not required for baseline jam |
| Q-012 | P2 | HUMAN_ANSWER | Pedals | HUMAN | Locate Flamma Mod / PH-2 | Inventory honesty |
| Q-013 | P2 | HUMAN_ANSWER | Pedals | HUMAN | Pedal power audit | Safety / PSU planning |
| Q-019 | P3 | HUMAN_ANSWER | Video | HUMAN | Webcam angles | Video only; not audio playability |

Class notes:

- **HUMAN_ANSWER** — visual inspection or workflow decision; attestation sufficient.
- **EXPLICIT_HUMAN_OBSERVATION** — policy requires observed device/behavior evidence (Q-016, Q-017).
- None currently classified **OBSOLETE/DUPLICATE** or **REPOSITORY/DOCUMENTARY_RESOLUTION** without HUMAN input.
- **RIG-031** remains READY with HUMAN DoD after Q-014 reconcile — do not bot-complete.

## First HUMAN batch (max 5)

Do these in order. Answer via TUI / non-bot CLI so provenance stays HUMAN
(do **not** use `rig --am-bot question answer`).

UNKNOWN is a valid answer.

### 1. Q-018 — PFL JAM active tracks

**Check:** Open the Ableton Live set you actually use for PFL jam (offline is fine). List every **active** track name (and note muted/disabled tracks if obvious).

**Answer with:** Plain list of track names as they appear in Live (or `UNKNOWN` if you cannot open the set).

**Requires:** Computer + Ableton (rig audio power optional).

**Time:** ~2 minutes.

**Why:** Startup / smoke / reference jam cannot be defined without the real set.

### 2. Q-011 — DIRTY / SPACE vs docs

**Check:** Stand at the pedalboards. Walk `docs/pedal-chains.md` (DIRTY Send A and SPACE Send B) left-to-right against the physical boards.

**Answer with:** `YES` (matches), `NO` + brief mismatch list, or `UNKNOWN`.

**Requires:** Visual inspection of boards (power optional unless labels need light).

**Time:** ~3–5 minutes.

**Why:** AUX wet-loop smoke test is meaningless if the boards do not match CURRENT docs.

### 3. Q-015 — Physical MIDI topology

**Check:** Trace cables from **U6MIDI Pro** and **Thru5 WC** end-to-end. Note what plugs into what (DIN/USB ports and gear names).

**Answer with:** A short topology description in your own words, or `UNKNOWN` for untraced segments.

**Requires:** Visual cable trace (devices may stay off).

**Time:** ~3–5 minutes.

**Why:** Clock and controllers depend on the real MIDI graph (RIG-037).

### 4. Q-020 — Default one-player loop order

**Check:** Decide from how you actually jam (not aspirational gear).

**Answer with:** One sentence, e.g. `RC-1 first, then KAOSS` / `KAOSS first` / `UNKNOWN — still experimenting`.

**Requires:** None (decision).

**Time:** ~30 seconds.

**Why:** Reference jam recipe needs a default capture order.

### 5. Q-016 — FCB1010 banks 00/01/02 (observation)

**PURPOSE:** Record the actual switch map on the FCB1010 for banks 00, 01, and 02.

**PRECONDITIONS:** FCB1010 connected the way you normally use it for PFL jam (or editor dump if that is your verification method).

**SETUP:** Select bank 00 on the FCB. Have a notepad ready (or MIDI monitor / FCB editor dump).

**PHYSICAL ACTION:** For bank 00, note what each switch 1–10 (and expression pedals if assigned) is programmed to do — from the pedal display, editor dump, or one press at a time while watching the intended Ableton/target. Repeat for banks 01 and 02.

**EXPECTED RESULT:** A concrete per-bank map (even if some switches are empty).

**FAILURE RESULT:** Cannot read programming / no response → answer `UNKNOWN` for that bank/switch (do not guess from wishlist).

**ANSWER OPTIONS:** Free text map, or `UNKNOWN`.

**RECOVERY:** Return FCB to bank 00; no need to rewrite programming during this check.

**Requires:** FCB powered; Ableton optional unless you verify by pressing into Live.

**Time:** ~5–10 minutes.

**Why:** Smoke test needs one reliable foot action; recovery should not depend on a mouse.

## First HUMAN batch — received and reconciled

| ID | HUMAN answer (summary) | Reconciliation |
|---|---|---|
| Q-018 | Active tracks: 1 Zoned Kit, 2 miniKORG, 3 KAOSS, 6 MIXER, 7 mix, 8 clean (guitars) | CURRENT ableton template notes/active flags; finalized |
| Q-011 | Current docs are correct | No CURRENT mutation; finalized |
| Q-015 | U6MIDI Pro sends to Thru5 WC on 1; inputs from FCB1010 | CURRENT midi links; finalized |
| Q-020 | Default RC-1 → KAOSS (+ RC-600 variants) | Documented in known-good-ops; finalized |
| Q-016 | Bank 00 arms tracks 1–10 / group control | controllers.yaml notes; finalized (01/02 still open) |

See [Known-good ops](known-good-ops.md) for startup / smoke / reference jam.

## Deferred next HUMAN batch

- **Q-008** — PB-B normalization modes (RIG-002)
- **Q-017** — ZeRO SL loaded templates (observation)
- Physical smoke-test PASS and reference-jam PASS checkboxes in known-good-ops
