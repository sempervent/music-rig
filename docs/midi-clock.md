# MIDI Clock and Controllers

Clock intent, channel assignment, physical cabling, and Ableton Track / Sync /
Remote settings are separate facts. `INTENDED` is never equivalent to `VERIFIED`.
See [MIDI Topology](midi-topology.md) for physical-link evidence.

<!-- rig:midi-clock:start -->
<!-- GENERATED FROM data/midi.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Clock state

Master: **ableton** — INTENDED

Desired default. Not VERIFIED CURRENT — see Q-014 and TODO RIG-031. Do not treat this as confirmed practice yet.

| Destination | Enabled | Evidence | Notes |
|---|---|---|---|
| korg-minikorg | UNKNOWN | INTENDED | Listed as intended clock consumer in docs/midi-clock.md |
| kaoss-replay | UNKNOWN | INTENDED | Listed as intended clock consumer; may sometimes lead (Q-014) |
| boss-sl-2 | UNKNOWN | INTENDED | Listed as intended clock consumer; may sometimes lead (Q-014) |

Transport start/stop evidence: **UNKNOWN**

## Channel assignments

| Device | Channel | Evidence | Notes |
|---|---:|---|---|
| casio-privia | 1 | INTENDED | Planning isolation; confirm in RIG-037 / Q-015 |
| korg-padkontrol | 10 | INTENDED | Drums; confirm in RIG-037 |
| novation-remote-zero-sl | 15 | INTENDED | Confirm in RIG-037; encoder #6 broken (inventory) |
| behringer-fcb1010 | 16 | INTENDED | Target channel; EXP A/B CC map is controller-mapping Stage 9+ (RIG-035) |

## Ableton MIDI ports

| Port | Direction | Reference | Track | Sync | Remote | Evidence |
|---|---|---|---|---|---|---|
| — | — | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
<!-- rig:midi-clock:end -->

## Owned MIDI hardware (not wishlist purchases)

| Device | Capability | Notes |
|---|---|---|
| CME U6MIDI Pro | 3 in / 3 out; route / merge / filter / remap | OWNED |
| CME MIDI Thru5 WC | Hardware thru distribution | OWNED |

A generic “buy MIDI thru/splitter” wishlist item is **REDUNDANT** while these are owned.

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
