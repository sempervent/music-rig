# Pedal Chains

Exact **CURRENT** active pedal topology. Owned pedals that are not in this path remain listed under inventory, not here.

Canonical structured source: `data/routing.yaml` (`named_paths`). Use `uv run rig path show …` / `uv run rig current path …` for inspection and supported mutations.

Purpose of RC-1 ahead of wah / JOYO: a captured phrase can subsequently be manipulated by the downstream pedals.

<!-- rig:pedal-chains:start -->
<!-- GENERATED FROM data/routing.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## AUX SEND front end (CURRENT)

```text
Alesis AUX SEND
-> BOSS RC-1
-> Cry Baby
-> JOYO A/B/Bypass
  A = DIRTY (see: rig path show dirty)
  B = SPACE (see: rig path show space)
```

## JOYO DIRTY — Send A (CURRENT)

```text
JOYO SEND A
-> BOSS OD-1
-> BOSS BD-2
-> BOSS JB-2
-> BOSS MT-2w
-> BOSS DS-1
-> JOYO RETURN A
```

Intent: gain, drive, dirt, classic stompbox abuse.

**Note:** TR-2 is **not** in this branch. It lives in the SPACE / SY-1 SEND loop. Do not infer that TR-2 left the rig.

## JOYO SPACE — Send B (CURRENT)

```text
JOYO SEND B
-> SY-1
  SY-1 SEND loop
    -> PH-3
    -> TR-2
    -> SY-1 RETURN
  -> LS-2 [A+B MIX ↔ BYPASS]
    LS-2 Loop A
      -> SL-2
      -> DD-8
    LS-2 Loop B
      -> TE-2
      -> RE-2
    -> JOYO RETURN B
```

LS-2 mode in use: **A+B MIX ↔ BYPASS**.

Intent: synth voice (SY-1), phase + tremolo in the SY-1 loop, then parallel texture loops via LS-2.

## Post-JOYO stereo spread (CURRENT)

```text
JOYO OUT
-> BOSS CH-1 stereo out
```

Path is mono through JOYO; CH-1 is the stereo stage.
<!-- rig:pedal-chains:end -->

## Owned but not in CURRENT active chain

These remain inventory unless reintroduced and documented:

| Device | Notes |
|---|---|
| Flamma Mod | OWNED; not in CURRENT SPACE topology |
| PH-2 | OWNED; not in CURRENT SPACE topology |
| TR-2 | OWNED and CURRENT, but in SY-1 SEND after PH-3 — not in DIRTY |

## Known pedal issues

| Device | Symptom | Status |
|---|---|---|
| Space Echo / RE-2 area | Noise noted | Needs gain/noise isolation pass |
| Big Muff | Failed/no audio | Remove or bench-test |
| Radial ProRMP on AUX SEND | Signal too low; sends needed to be maxed | Do not place here unless gain staging is solved |
