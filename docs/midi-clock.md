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
  -> CME U6MIDI Pro and/or TASCAM US-16x08 MIDI paths
  -> CME MIDI Thru5 WC (distribution)
  -> miniKORG / KAOSS Replay / SL-2 / future MIDI devices
```

Exact physical topology is not fully verified. Treat the above as intent until TODO RIG-037 is complete.

## Owned MIDI hardware (not wishlist purchases)

| Device | Capability | Notes |
|---|---|---|
| CME U6MIDI Pro | 3 in / 3 out; route / merge / filter / remap | OWNED |
| CME MIDI Thru5 WC | Hardware thru distribution | OWNED |

A generic “buy MIDI thru/splitter” wishlist item is **REDUNDANT** while these are owned.

## Channel isolation direction (planning — verify)

| Device | MIDI channel | Notes |
|---|---:|---|
| Casio Privia | 1 | Confirm in RIG-037 |
| padKONTROL | 10 | Drums |
| Novation ReMOTE ZeRO SL | 15 | Encoder #6 broken |
| Behringer FCB1010 | 16 | EXP A=CC111, EXP B=CC112 (RIG-035) |

## Controllers

| Controller | Role | Status |
|---|---|---|
| Launchpad X | Ableton recording/control | Working well enough to solve recording issue |
| Launch Control 3 | Performance sends/macros (esp. Send D) | OWNED; mapping TODO RIG-034 |
| padKONTROL | Drums / footswitch clip-record | MIDI channel 10; M4L toggle TODO RIG-039 |
| FCB1010 | Foot control | Finalize RIG-035; USB Uno recognition unresolved (RIG-022) |
| ReMOTE ZeRO SL | Knobs/faders/buttons | Templates TODO RIG-036 |
| Stream Deck+ | OBS / hands-off ops | Profiles TODO RIG-045 |
| MOSKY Dual Switch | Momentary control | Useful on RC-1 STOP/UNDO |
| BOSS EV-30 | Dual expression | Candidate for SL-2 / PH-3 expression workflows |

## Wishlist control and clock implications

Ableton remains the intended master clock. Purchase candidates (RC-600, Microcosm, MIDI Captain, Eurorack) live on [Wishlist](wishlist.md) until explicitly accepted into [Todo](todo.md).

The MIDI Captain is a command controller, not a reliable continuous clock source. Finish FCB1010 before buying it.

RC-600 integration (when acquired) must define clock/Ableton relationship without inventing CURRENT wiring (RIG-032).

## FCB1010 problem statement

The device appears in Ableton indirectly through the USB Uno interface, but presses are not being recognized as expected. Track exact observations here before changing multiple variables.

Checklist:

- Confirm MIDI interface appears in macOS Audio MIDI Setup.
- Confirm Ableton Preferences > Link/Tempo/MIDI has Track and Remote enabled for the correct input.
- Use a MIDI monitor to confirm whether CC/PC messages arrive outside Ableton.
- Confirm FCB1010 programming mode and channel (target 16).
- Test a known-good MIDI cable.
- Test FCB1010 MIDI OUT directly into TASCAM MIDI IN if available (RIG-022).
- Prefer routing via owned U6MIDI Pro once direct test clarifies the failure domain.
