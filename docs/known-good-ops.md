# Known-good operations

Practical procedures for sitting down and playing. Facts below are grounded in
reconciled HUMAN answers and CURRENT state as of Stage 24. Items still marked
INTENDED or UNKNOWN are called out explicitly.

Related Questions: Q-011, Q-014, Q-015, Q-016, Q-018, Q-020.

## Startup (everything off → ready to make sound)

Target: ~5 minutes. Baseline session only (not every owned device).

1. Power **TASCAM US-16x08**, then **Alesis mixer**, then pedalboard PSU(s), then
   **KAOSS Replay**, then computer.
2. Connect headphones / monitors at a low level. Confirm TASCAM is the Mac
   audio device.
3. Launch **Ableton Live** and open the **PFL JAM** set.
4. Confirm active Live tracks match the HUMAN list (Q-018):
   **1 Zoned Kit, 2 miniKORG, 3 KAOSS, 6 MIXER, 7 mix, 8 clean (guitars)**.
5. Confirm MIDI clock master is Ableton (Q-014 — VERIFIED in CURRENT).
6. Confirm FCB1010 is awake on bank **00** (Q-016: arms tracks 1–10 / group
   control). Banks 01/02 still unobserved.
7. Play a known source (miniKORG or a clean guitar) and confirm it returns in
   Ableton / monitors.
8. Optional wet check: send a little AUX SEND → RC-1 path (boards match docs
   per Q-011).
9. Optional KAOSS check: feed from **TASCAM OUT 3/4**, return on **IN 15/16**.

You are ready when you hear a dry source and the transport is under Ableton
clock.

## Shutdown

1. Stop recording / clips; clear or stop **RC-1** if looping.
2. Mute or lower monitor / headphone level before powering speakers down.
3. Save the Ableton set if you changed anything you want to keep.
4. Power down: KAOSS → pedal PSU → mixer → TASCAM → computer (or leave Mac on).
5. Do not invent manufacturer-critical power order beyond “level down before
   cutting speaker amps.”

## Smoke test (~3–5 minutes) — HUMAN observation

Bot documents the procedure; **PASS is HUMAN-only**.

| Step | Domain | Action | Pass if |
|---|---|---|---|
| A | Monitoring | Headphones/monitors on, low level | You hear Ableton / interface safely |
| B | Synth | Play miniKORG into Ableton track 2 | Signal present |
| C | Clean instrument | Play into clean path (track 8) | Signal present |
| D | AUX wet | Small AUX SEND into RC-1 / JOYO path | Wet return heard (boards OK per Q-011) |
| E | KAOSS | OUT 3/4 → KAOSS → IN 15/16 | KAOSS returns on tracks as expected |
| F | Clock | Ableton is master | No competing master (Q-014) |
| G | Foot control | FCB bank 00 switch arms a track 1–10 | Track arm / group reacts (Q-016) |
| H | Recovery | Stop RC-1 / mute wet / panic path if mapped | Bad loop or wet runaway can be stopped |

Result log (fill when performed):

- Date: 2026-09-12
- Result: PASS (HUMAN Stage 25 live validation — “All passes”)
- Notes: Physical smoke A–H reported PASS by HUMAN in session.

## Reference jam recipe (~5–10 minutes)

**BPM / meter:** choose a comfortable session tempo in the PFL JAM set (not
mandated here — set and note it when you run the jam).

**Startup scene:** PFL JAM Live set with Q-018 tracks active.

**Active sources (minimum):**

- Zoned Kit (track 1) or a simple rhythm clip
- miniKORG (track 2) **or** clean guitar (track 8)
- MIXER bus (track 6) as needed

**Loop workflow (Q-020 HUMAN):** default **RC-1 → KAOSS**. When RC-600 is in
play, path is RC-1 → KAOSS | RC-600, or instrument → RC-600 via Alesis mixer.

**Wet-path moment:** one AUX SEND phrase through RC-1 / JOYO (DIRTY or SPACE).

**Control action:** FCB bank 00 arm/select among tracks 1–10.

**Stop / recovery:** RC-1 stop/undo; mute wet send; Ableton stop; see
[Live Recovery](live-recovery.md) (still mostly INTENDED mappings).

Result log:

- Date: 2026-09-12
- Result: PASS (HUMAN Stage 25 — “All passes”)
- BPM / meter used: (not specified)
- Notes: Reference jam reported PASS by HUMAN in the same validation session.

## Still open (blocks “fully known” but not necessarily “can play”)

- Q-008 PB-B normalization modes
- Q-017 ZeRO templates loaded
- Thru5 downstream fan-out (RIG-037 remainder)
- RIG-031 HUMAN DoD for clock docs wording
- Physical smoke / reference jam PASS checkboxes above
