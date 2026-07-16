# Studio Wishlist and Upgrade Priorities

These priorities represent the recommended purchase order for this specific rig and workflow, not absolute product quality rankings.

Prices and availability must be verified before purchase. Approximate price snapshots below are dated July 15, 2026.

## Priority Overview

| Priority | Device | Primary role | Fit with current rig | Main benefit | Existing equipment overlap | Recommended integration point | Purchase condition or decision gate | Approximate price snapshot | Status |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | BOSS RC-505mkII Loop Station | Central multi-track live looper | Very high | Adds structured multi-track loop architecture without removing the current AUX SEND pedal loop | Some overlap with BOSS RC-1 and KAOSS Replay, but fills a larger arrangement role | Alesis Monitor Out -> RC-505mkII -> KAOSS Replay -> TASCAM 9/10 | Buy first if one-person live-loop structure is the main bottleneck | Approximately $640 to $660 | Proposed |
| 2 | Hologram Electronics Microcosm | Creative stereo texture processor | Very high | Adds granular, micro-looping, pitch, glitch, drone, and preset-based stereo processing not covered cleanly by the current rig | Partial overlap with KAOSS Replay and existing delay/modulation pedals, but not an adequate duplication | After BOSS CH-1 stereo output, before Alesis stereo return or stereo line input | Buy after the loop architecture is stabilized, or first among pure sound-design upgrades | Approximately $413 | Proposed |
| 3 | PaintAudio MIDI Captain 10-switch foot controller | Compact foot-command controller | High after a MIDI plan exists | Simplifies hands-free control for Ableton and future MIDI devices | Partial overlap with Behringer FCB1010, but cleaner USB-MIDI and smaller footprint | USB-MIDI or DIN-MIDI control layer for Ableton, RC-505mkII, Microcosm, DL4 MkII, and KAOSS Replay where supported | Buy after writing a MIDI mapping plan and after finishing the direct FCB1010-to-TASCAM test | Approximately $180 | Proposed |
| 4 | Pioneer DJ DDJ-FLX4 | DJ and hybrid performance controller | Medium | Enables a different performance discipline rather than fixing the existing one | Limited overlap with current rig because this is a new workflow | DDJ-FLX4 RCA master output -> dual RCA-to-1/4-inch cable -> Alesis mixer channel 7/8 | Buy only when a DJ/live-hybrid set or recurring DJ practice workflow is defined | Approximately $329 | Proposed |
| 5 | Line 6 DL4 MkII | Delay and looper consolidation option | Conditional | Useful only if it replaces several existing pedals or becomes a portable-core device | Heavy overlap with DD-8, TE-2, RE-2, RC-1, KAOSS Replay, proposed Microcosm, and proposed RC-505mkII | Run a temporary DL4 consolidation experiment rather than adopt a permanent default placement | Buy only if it replaces or rotates with existing delays, anchors a specific loop workflow, becomes a portable core, or its mic input is needed | Approximately $250 | Proposed |
| 6 | Nord Stage 4 88 | Replacement stage keyboard | Aspirational but high-impact if piano/organ become central | Strong long-term instrument upgrade, but lower immediate routing urgency than loop/control tools | Would primarily replace the Casio Privia rather than duplicate it | Nord Stage 4 main outputs -> Alesis mixer channels 5/6 | Buy sooner only if the Privia becomes the limiting factor or a self-contained stage keyboard is required | Approximately $5,999 | Proposed |

## BOSS RC-505mkII

This is the highest-priority workflow upgrade.

It provides five simultaneous stereo phrase tracks, dedicated track controls and faders, substantial loop memory, MIDI control, multiple inputs and outputs, rhythms, input effects, and track effects.

It should complement rather than automatically replace the BOSS RC-1. The RC-1 can remain in the AUX SEND pedal chain for quick pre-effects looping.

Proposed initial routing:

```text
Alesis Monitor Out
  -> BOSS RC-505mkII
  -> KAOSS Replay
  -> TASCAM US-16x08 inputs 9/10
```

This preserves the current AUX SEND pedal loop while allowing the RC-505mkII to build structured multi-track arrangements before the KAOSS Replay performs sampling and destructive effects.

Feedback and monitor-bus contents must be checked before making this routing permanent.

## Hologram Electronics Microcosm

This is the highest-priority creative effects addition.

It adds granular sampling, micro-looping, pitch manipulation, glitch processing, drones, stereo processing, expression control, presets, and MIDI clock synchronization that are not adequately duplicated by the existing DD-8, TE-2, RE-2, PH-3, SL-2, or KAOSS Replay.

Recommended initial placement:

```text
JOYO output
  -> BOSS CH-1 stereo output
  -> Hologram Microcosm stereo input
  -> Alesis stereo return or stereo line channel
```

Placing it after the CH-1 preserves the current stereo spread and uses the Microcosm's stereo and line-level capabilities.

A dedicated TASCAM capture path is a valid alternative experiment if the Microcosm becomes important enough to warrant isolated recording.

Ableton should remain the master clock.

## PaintAudio MIDI Captain 10-switch foot controller

The MIDI Captain can send PC, CC, note, and other configurable commands from ten footswitches, and its Time Engine can replay sequences of switch actions.

The Time Engine is not a substitute for MIDI clock or MTC generation. Ableton remains the intended clock master.

Comparison with the existing Behringer FCB1010:

- The FCB1010 remains a potentially usable controller.
- Its current problem may be the USB Uno interface or configuration rather than the controller itself.
- The existing direct test from FCB1010 MIDI OUT to TASCAM MIDI IN should be completed before retiring it.
- The MIDI Captain offers a smaller form factor, native USB-MIDI, simpler configuration, and a cleaner future control surface.
- Its value increases after adding the RC-505mkII or Microcosm.

Possible control targets:

- Ableton scene launch and transport
- RC-505mkII track operations and memory changes
- Microcosm presets, effect parameters, bypass, and looper functions
- Future DL4 MkII presets and looper controls
- KAOSS Replay commands where supported

## Pioneer DJ DDJ-FLX4

This is a new workflow rather than a repair or upgrade to the current workflow.

Possible uses:

- Hybrid DJ and live-looping performances
- Transitioning between completed tracks and live improvisation
- Playing interludes and reference tracks
- Feeding external tracks into the RC-505mkII or KAOSS Replay
- Preparing conventional two-deck DJ sets

Recommended simple analog integration:

```text
DDJ-FLX4 RCA master output
  -> dual RCA-to-1/4-inch cable
  -> Alesis mixer channel 7/8
```

The TASCAM US-16x08 should remain the main studio audio interface unless a deliberate aggregate-device design is tested and documented.

Decision gate: buy only when a DJ/live-hybrid set or recurring DJ practice workflow has been defined.

## Line 6 DL4 MkII

This is a conditional consolidation purchase.

Benefits:

- Thirty delay models
- Four-switch performance interface
- Stereo operation
- MIDI input and output/thru
- Expression and external footswitch support
- One-switch and four-switch looping modes
- MicroSD-expanded loop storage
- XLR dynamic microphone input

It overlaps heavily with the existing:

- BOSS DD-8
- BOSS TE-2
- BOSS RE-2
- BOSS RC-1
- KAOSS Replay
- Proposed Microcosm
- Proposed RC-505mkII

It should not be permanently added in series after every existing delay.

Valid purchase conditions:

- It replaces or rotates with the DD-8, TE-2, and RE-2.
- Its four-switch looping interface becomes part of a specific performance workflow.
- It becomes the core of a smaller portable pedalboard.
- Its microphone-input looping is specifically needed.

Proposed DL4 consolidation experiment:

```text
Alesis AUX SEND
  -> Cry Baby
  -> BOSS RC-1
  -> JOYO A/B/Bypass input
     -> existing Chain B delay/modulation segment removed or bypassed for the test
  -> JOYO output
  -> Line 6 DL4 MkII stereo input/output in place of selected delay pedals for comparison
  -> Alesis stereo return or stereo line input
```

This is an experiment only, not a permanent routing recommendation.

## Nord Stage 4 88

This is an aspirational replacement instrument.

It offers a weighted triple-sensor 88-key action with aftertouch, piano, organ, and synthesizer engines, per-layer effects, drawbars, MIDI, USB-MIDI, and four assignable outputs.

It would primarily replace the Casio Privia rather than merely sit beside it.

Recommended initial replacement routing:

```text
Nord Stage 4 main outputs
  -> Alesis mixer channels 5/6
```

Optional future testing should include the Nord's assignable outputs into spare TASCAM inputs for isolated piano, organ, or synth capture where the Nord's routing capabilities permit it.

This moves from priority six to priority two if any of the following become true:

- The Privia keybed or sounds materially limit performance.
- Piano and organ become central to the project.
- A self-contained live stage keyboard is required.
- The Privia is being retired rather than retained.

## Conditions That Change the Priority

- If keyboard performance becomes the central focus, move the Nord Stage 4 to priority two.
- If a DJ/live-hybrid set is actively being developed, move the DDJ-FLX4 to priority three.
- If the FCB1010 works reliably through the TASCAM MIDI input, move the MIDI Captain below the DDJ-FLX4.
- If the DL4 MkII will replace multiple existing delay pedals, move it above the DDJ-FLX4.
- If no existing equipment will be removed, leave the DL4 MkII near the bottom because of redundancy.

## Recommended Acquisition Phases

1. Performance architecture: RC-505mkII
2. New sound design: Microcosm
3. Hands-free control: MIDI Captain after a MIDI mapping plan is written
4. New performance discipline: DDJ-FLX4
5. Keyboard replacement: Nord Stage 4 88
6. Optional delay consolidation: DL4 MkII

A dependable MIDI splitter/router and isolated pedal power may have greater infrastructure value than some wishlist devices and should remain tracked separately.
