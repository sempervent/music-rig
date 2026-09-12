# Music Rig

This is the living map for the studio: instruments, mixer, interface, pedals, loopers, patchbays, MIDI, Ableton tracks, and known failure modes.

The design goal is not purity. It is controllable chaos: clean captures available at all times, wet loops available on demand, KAOSS sampling fed from the mixer monitor path, patchbay connectivity documented where known, and enough documentation that future changes do not turn the room into a copper snake nest.

## Core principles

1. **Always preserve clean signals where possible.**
   The TASCAM gets clean mixer, miniKORG, acoustic, bass, electric guitar, KAOSS, and SR-18 channels separately where assigned.

2. **Treat the AUX SEND as the creative wet loop.**
   Instruments can be sent into the RC-1 (then wah / JOYO pedal chains) and stereo return without destroying the clean path.

3. **Keep KAOSS Replay as its own captured instrument.**
   KAOSS output lands on TASCAM 9/10.

4. **Keep patchbay facts separate from high-level routing.**
   See [Patchbays](patchbays.md). Owned gear is not automatically in the current chain.

5. **Document every weird failure.**
   The rig is complicated enough that solved problems need a tombstone.

## Planning layers

| Doc | Use for |
|---|---|
| [Current routing](current-routing.md) | What is physically wired now |
| [Todo](todo.md) | Accepted work to do next |
| [Wishlist](wishlist.md) | Speculative purchases and ideas (not commitments) |
| [Open questions](open-questions.md) | Unresolved facts |
| [Reconciliation](reconciliation.md) | Question ↔ CURRENT engine architecture |
| [Testing](testing.md) | Suite layout, markers, coverage gate |
| [Inventory](inventory.md) | What is owned |
