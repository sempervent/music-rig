# MIDI Clock and Controllers

## Goal

Ableton should be the master clock where practical, sending tempo/sync to:

- miniKORG
- KAOSS Replay
- BOSS SL-2
- other MIDI-capable devices as added

## Current intent

```text
Ableton Live
  -> TASCAM US-16x08 MIDI Out
  -> MIDI splitter/thru
  -> miniKORG / KAOSS Replay / SL-2
```

## Controllers

| Controller | Role | Status |
|---|---|---|
| Launchpad X | Ableton recording/control | Working well enough to solve recording issue |
| padKONTROL | Drums | MIDI channel 10 |
| FCB1010 via USB Uno | Foot control | Not recognized reliably yet |
| Remote Zero SL | Knobs/faders/buttons | Available for mapping |
| MOSKY Dual Switch | Momentary control | Useful on RC-1 STOP/UNDO |
| BOSS EV-30 | Dual expression | Candidate for SL-2 / PH-3 expression workflows |

## Wishlist control and clock implications

Ableton remains the intended master clock.

The MIDI Captain is a command controller, not a reliable continuous clock source.

A dedicated MIDI splitter/router is still required for distributing clock to the miniKORG, KAOSS Replay, SL-2, Microcosm, RC-505mkII, and other future MIDI-capable devices.

The FCB1010 direct-to-TASCAM test remains open and should be completed before replacing it on workflow grounds alone.

## FCB1010 problem statement

The device appears in Ableton indirectly through the USB Uno interface, but presses are not being recognized as expected. Track exact observations here before changing multiple variables.

Checklist:

- Confirm MIDI interface appears in macOS Audio MIDI Setup.
- Confirm Ableton Preferences > Link/Tempo/MIDI has Track and Remote enabled for the correct input.
- Use a MIDI monitor to confirm whether CC/PC messages arrive outside Ableton.
- Confirm FCB1010 programming mode and channel.
- Test a known-good MIDI cable.
- Test FCB1010 MIDI OUT directly into TASCAM MIDI IN if available.
