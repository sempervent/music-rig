# Inventory

Ownership and role. **Owned ≠ currently in the active signal path.** Active topology lives in [Pedal Chains](pedal-chains.md) and [Current Routing](current-routing.md).

## Interfaces and mixers

| Device | Role | Notes |
|---|---|---|
| TASCAM US-16x08 | Main audio interface | Clean, synth, acoustic, bass, electric, KAOSS, SR-18 stems |
| Alesis mixer | Live routing and AUX SEND hub | Feeds main clean capture and wet loop |

## Instruments and sound sources

| Device | Role | Notes |
|---|---|---|
| Casio Privia | Piano | Alesis 5/6 (via PB-B) |
| Korg miniKORG | Synth | TASCAM 3/4 (via PB-B); AUDIO IN 1/2 on PB-B lower 35/36 |
| Alesis SR-18 | Drum machine | TASCAM 11/12 (via PB-B) |
| Acoustic instrument | Instrument | Clean → TASCAM 5 after BOSS acoustic preamp |
| Bass | Instrument | Alesis 1 (prior); clean → TASCAM 6 after BBox preamp |
| Electric guitar | Instrument | Alesis 2 (prior); clean → TASCAM 7 after Flamma preamp |
| Electric kazoo | Instrument/noise source | Alesis 4 |

## Preamps and splitters

| Device | Role | Notes |
|---|---|---|
| BOSS acoustic preamp | Acoustic front end | Before A/B/Y; clean leg → TASCAM 5 |
| BBox preamp | Bass front end | Before A/B/Y; clean leg → TASCAM 6 |
| Flamma preamp | Electric guitar front end | Before A/B/Y; clean leg → TASCAM 7 |
| A/B/Y splitters | Path split after preamps | Clean TASCAM legs confirmed; other legs UNKNOWN |

## Loopers and samplers

| Device | Role | Notes |
|---|---|---|
| BOSS RC-1 | Looper | CURRENT in AUX SEND ahead of wah / JOYO; external STOP/UNDO footswitch works |
| KAOSS Replay | Sampler/effects/performance brain | Fed by Alesis monitor out; captured on TASCAM 9/10 |

## Patchbays

| Item | Role | Notes |
|---|---|---|
| PB-A / PB-B / PB-C / PB-D | Named 48-point TRS patchbays | Only PB-B has documented jack assignments |
| 2× ART Pro Audio P48 | Patchbay hardware | Which units map to which PB letter: UNKNOWN |
| 2× Behringer PX3000 | Patchbay hardware | Which units map to which PB letter: UNKNOWN |

## Splitters, routers, DI, and reamp

| Device | Role | Notes |
|---|---|---|
| JOYO A/B/Bypass router | Switch/route wet chain | CURRENT: A = DIRTY, B = SPACE |
| BOSS LS-2 | Line selector | CURRENT in SPACE after SY-1; A+B MIX ↔ BYPASS |
| Radial ProRMP | Reamp box | AUX SEND signal was too attenuated; not default wet-loop device |
| PYLE-PRO PDC22 dual DI | Dual DI | Can tap two mono channels or stereo L/R into TASCAM/mixer paths |
| MXR TRS split + tap | Utility splitter/tap | Candidate for expression/TAP/control workflows |

## Pedals — CURRENT active path

| Location | Devices |
|---|---|
| AUX front | RC-1, Cry Baby |
| DIRTY (JOYO A) | OD-1, BD-2, JB-2, MT-2w, DS-1 |
| SPACE (JOYO B) | SY-1 (PH-3 → TR-2 in SEND/RETURN), LS-2 with LOOP A: SL-2 → DD-8, LOOP B: TE-2 → RE-2 |
| Post-JOYO | CH-1 |

## Pedals — OWNED / AVAILABLE, not in CURRENT active chain

| Device | Notes |
|---|---|
| Flamma Mod | Previously in older SPACE experiments; not CURRENT |
| PH-2 | Previously in older SPACE experiments; not CURRENT |
| Big Muff | Failed/no audio; bench-test |

## Controllers

| Device | Role | Notes |
|---|---|---|
| Launchpad X | Ableton control | Recording issue appears solved by this |
| Novation Launch Control 3 | Ableton performance macros / sends | OWNED; Send D mapping TODO RIG-034 |
| Korg padKONTROL | Drum pads | MIDI channel 10 drums; footswitch clip-record workflow TODO RIG-039 |
| Behringer FCB1010 | Foot controller | Target ch16; EXP A CC111 / EXP B CC112 (finalize RIG-035); USB Uno recognition unresolved |
| Novation ReMOTE ZeRO SL | MIDI controller | Target ch15; encoder #6 broken; template finalize RIG-036 |
| Elgato Stream Deck+ | OBS / hands-off ops | OWNED; profile finish TODO RIG-045 |
| MOSKY Dual Switch | Momentary dual footswitch | Useful with RC-1 STOP/UNDO; likely better than single switch |
| BOSS EV-30 | Dual expression pedal | Candidate for SL-2 / PH-3 / other expression-capable pedals |

## MIDI interfaces / distribution

| Device | Role | Notes |
|---|---|---|
| CME U6MIDI Pro | USB MIDI interface / router | 3 in / 3 out; routing, merging, filtering/remapping — OWNED |
| CME MIDI Thru5 WC | Hardware MIDI thru | Clock/controller distribution — OWNED |

Do **not** wishlist another generic MIDI thru/splitter while these are owned. Document topology via TODO RIG-037.
