# Capture now

Recording is optional. Playing without recording is still a successful session.

## Don't care about recording?

Play. See [Jam now](jam-now.md).

## Want the idea? — Scratch (Level 1)

**Path:** Stream Deck+ → **OBS REC** → start recording  
(INTENDED binding: `streamdeck-obs-rec-start` / `record-start` in performance CURRENT)

| Step | Action |
|---|---|
| Start | One Stream Deck press on OBS REC **start-recording** |
| Stop | OBS SAFE **stop-recording** (or OBS REC stop) |
| After | Find the OBS recording on disk; optional one-line note via `rig session note "…"` |

Does **not** change Ableton monitoring or pedal routing. If OBS fails, the jam continues.

**Not in CURRENT inventory:** a handheld room recorder is also fine for Scratch if you already own one — do not buy gear for this. Do not invent device rows until you add them as owned inventory.

## Want the tracks? — Multitrack (Level 2)

**Meaning:** capture live audio into Ableton for later production.

Live 11 distinction (manual):

- **Arrangement Record** — records armed track inputs (and can log Session launches into Arrangement). Prefer this for “record the whole jam.”
- **Session Record** — records new clips into Session slots on armed tracks. Good for looping takes; not the default “whole jam” path.
- **Clip-record** (padKONTROL footswitch / M4L) — Session clip toggle; stop behavior imperfect (RIG-039). Do **not** rely on it for whole-jam capture.

### Before play (prepare once)

1. Open **PFL JAM**.
2. Confirm useful tracks exist: **1 Zoned Kit · 2 miniKORG · 3 KAOSS · 6 MIXER · 7 mix · 8 clean**.
3. Arm only tracks you need later (typical: **clean**, **KAOSS**, plus any live MIDI→audio you care about). Do **not** arm everything “just in case.”
4. Leave monitoring as in the known-good set — do not flip monitor modes mid-jam (feedback risk).
5. FCB bank **00** remains track arm/select 1–10 (working). Do not steal it for transport.

### Physical start/stop (target)

| Control | Role |
|---|---|
| **Launchpad X** | Preferred greenfield map for Arrangement Record (repo has no custom map yet; historically “solves recording control”) |
| **Stream Deck+ Ableton profile** | Empty today — safe place to add Arrangement Record without touching OBS pages |
| padKONTROL footswitch | Keep for clip-record experiments only (RIG-039) |
| FCB bank 00 | Keep for arm/select — do not remap for Record |

Until Arrangement Record is on a button you trust: press Arrangement Record once before you start playing (acceptable prep). Prefer not to need mouse **during** the performance.

### During / after

| Step | Action |
|---|---|
| Start | Arrangement Record on (physical button when mapped) |
| Stop | Arrangement Record off, or transport Stop |
| Save | After play ends — save the Live set (keyboard OK **after** the jam) |

## Finished?

1. Stop capture (Scratch or Multitrack).
2. Optional: `uv run rig session note "one line about what mattered"`.
3. Promote to CURRENT only if you want to **keep** a wiring/sound change — otherwise leave it as session history.

## Experiment vs CURRENT

| Layer | Use for |
|---|---|
| `rig session note` / `discovery` | Cheap history — may be incomplete |
| `rig capture` / inbox | Zero-friction observation |
| `rig change` | “Reality may have changed” — does **not** edit CURRENT |
| `rig current …` | Intentional promotion to canonical state |

PLAY first → note if useful → promote only if worth keeping.
