# Stage 25 — Live validation session

**Pre-validation snapshot:** `SNAP-20260912-161313` (post Stage 24 merge `d741ff6`).

**Goal:** one powered session (~15–30 min) that runs the Stage 24 smoke checklist,
closes the highest-value unknowns (PB-B modes, ZeRO templates, Thru5 fan-out),
optionally satisfies RIG-031 DoD, then runs the reference jam + one recovery check.

Answer via TUI / non-bot CLI where provenance matters. For each physical check use:

`PASS` · `FAIL` · `UNKNOWN` / `NOT TESTED`

Bot will **not** invent results.

Reuse [known-good-ops.md](known-good-ops.md) — do not invent a second checklist.

---

## Session order

### A. Startup (~5 min)

Follow **Startup** in known-good-ops.md exactly (TASCAM → mixer → pedals → KAOSS → Mac → Ableton PFL JAM).

| ACTION | EXPECTED | HUMAN RESULT |
|---|---|---|
| Complete startup steps 1–7 | Dry source audible; Ableton clock; FCB bank 00 awake | PASS / FAIL / UNKNOWN — notes: |

Keyboard/mouse during setup only is OK. Note any step that was wrong/missing.

### B–H. Smoke test (known-good-ops table)

Run steps **A–H** from known-good-ops.md smoke table on this powered rig.

| Step | ACTION (from CURRENT) | EXPECTED | RESULT |
|---|---|---|---|
| A Monitoring | Headphones/monitors low | Hear Ableton/interface safely | |
| B Synth | Play **miniKORG** → Live track **2** | Signal present | |
| C Clean | Play into Live track **8 clean (guitars)** | Signal present | |
| D AUX wet | Small **AUX SEND** → RC-1 / JOYO | Wet return heard | |
| E KAOSS | **TASCAM OUT 3/4 → KAOSS → IN 15/16** | Return on KAOSS track as expected | |
| F Clock | Confirm Ableton is master (no KAOSS/SL-2 leading) | Ableton master only | |
| G Foot | **FCB bank 00** switch arms a track **1–10** | Track arm / group reacts | |
| H Recovery | Stop RC-1 and/or mute wet (safe level) | Bad loop / wet can be stopped | |

Overall smoke: PASS / FAIL / PARTIAL / NOT RUN

### I. Q-008 — PB-B normalization (populated pairs only)

Inspect **ART P48 PB-B** selector for each **populated** pair below (skip empty bay pairs).

Modes: `normal` · `half-normal` · `thru` · `UNKNOWN`

| Pair (upper/lower) | What is patched | CURRENT mode | HUMAN sees |
|---|---|---|---|
| **1 / 25** | miniKORG L → TASCAM IN 3 | unknown | |
| **2 / 26** | miniKORG R → TASCAM IN 4 | unknown | |
| **3 / 27** | SR-18 L → TASCAM IN 11 | unknown | |
| **4 / 28** | SR-18 R → TASCAM IN 12 | unknown | |
| **7 / 31** | Privia L → Alesis CH 5 | unknown | |
| **8 / 32** | Privia R → Alesis CH 6 | unknown | |

Optional (unassigned uppers — only if quick): 9/33, 10/34, 11/35, 12/36.

Record answers in TUI for Q-008 (set `target.pair` per pair if the UI requires it, or one text answer listing all pairs).

### J. MIDI Thru5 fan-out (RIG-037 remainder)

Already VERIFIED — do **not** re-check unless wrong:

- FCB1010 MIDI OUT → U6MIDI Pro MIDI IN 1
- U6MIDI Pro MIDI OUT 1 → Thru5 WC MIDI IN 1

**ACTION:** Trace Thru5 **outputs** that have cables. For each used OUT, name the destination gear.

| Thru5 OUT | Destination (gear / port) or UNUSED |
|---|---|
| OUT 1 | |
| OUT 2 | |
| OUT 3 | |
| OUT 4 | |
| OUT 5 | |

Also note: any other U6MIDI DIN/USB cables you see that matter for clock/controllers (or `UNKNOWN`).

### K. Q-017 — ReMOTE ZeRO SL templates

**Policy:** EXPLICIT_OBSERVATION_REQUIRED.

**ACTION:** On the ZeRO SL, read which templates are **actually loaded** (device display / template list). Do **not** use encoder **#6** (broken).

**EXPECTED:** Template name list, or `UNKNOWN`.

**OPTIONAL behavior spot-check (one control only):** pick one healthy mapped control (not #6); move it once; note whether the intended Ableton target moves. PASS / FAIL / UNKNOWN.

### L. RIG-031 DoD (only after smoke F / clock looks good)

Exact Definition of Done:

> **midi-clock.md states verified CURRENT behavior, not only intent**

Q-014 already set Ableton master **VERIFIED** in CURRENT. Smoke step F tests it in a live session.

**HUMAN:** Does this session satisfy RIG-031’s Definition of Done?  
**YES** / **NO** (no negotiation)

### M. Reference jam (~5–10 min)

Follow **Reference jam recipe** in known-good-ops.md.

Minimum: Ableton + Zoned Kit or clip + miniKORG **or** clean guitar + one AUX/RC-1 moment + FCB bank 00 action + safe stop.

| Field | HUMAN |
|---|---|
| Result | PASS / PASS WITH ISSUE / FAIL / NOT RUN |
| Duration | |
| BPM / meter | |
| Sources used | |
| Loop used | |
| Wet-path event | |
| Hands-free control | |
| Keyboard/mouse **during performance** (after start) | none / list moments |
| Recovery event tested | which + PASS/FAIL |
| Issues | |

### N. Shutdown

Follow **Shutdown** in known-good-ops.md once. Note friction: PASS / FAIL / notes.

---

## How to return results

Reply in chat with the filled tables (or paste TUI-confirmed Question IDs). Prefer:

1. Smoke A–H results  
2. Q-008 pair modes  
3. Thru5 OUT map  
4. Q-017 templates (+ optional spot-check)  
5. RIG-031 YES/NO  
6. Reference jam + recovery  
7. Startup/shutdown friction notes  

Stage 25 continues only after these HUMAN results.
