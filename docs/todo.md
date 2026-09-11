# Todo

**TODO = work that has been accepted as worth doing.**

Wishlist ideas are **not** TODOs. See [Wishlist](wishlist.md).

```text
Wishlist item
   ↓
evaluation
   ↓
accepted decision
   ↓
TODO item (this file)
```

Open questions record unresolved **facts**. TODOs record the **actions** that resolve them. See [Open Questions](open-questions.md).

Canonical structured source: `data/todo.yaml`. Edit data via `uv run rig todo ...` or YAML, then `uv run rig render`.
Do not renumber IDs after completion. Prefer clear Definition of Done.
`## Next Session` holds at most three tasks.

## Status legend
Next Session membership is stored separately in `data/todo.yaml` (`next_session`) and is not a TODO status.


| Status | Meaning |
|---|---|
| READY | Unblocked; can start anytime |
| BLOCKED | Cannot proceed until a dependency clears |
| IN PROGRESS | Actively being worked |
| WAITING | External dependency (parts, arrival, someone else) |
| DONE | Completed and verified |
| DEFERRED | Intentionally postponed |
| CANCELLED | Will not do |

<!-- rig:todo:start -->
<!-- GENERATED FROM data/todo.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Next Session

At most three tasks. Prefer resolving physical uncertainty, reproducibility, and documentation drift — not purchases.

| ID | Task | Why this session |
|---|---|---|
| RIG-001 | Physically verify DIRTY chain order and SPACE topology (SY-1 SEND PH-3→TR-2; LS-2 loops; A+B MIX↔BYPASS) | Unlocks confident playing; catches doc drift immediately |
| RIG-002 | Inspect and record normal / half-normal / thru for every populated PB-B pair | Highest-value patchbay unknown; quick rack check |
| RIG-003 | Trace and document non-clean A/B/Y destinations for acoustic, bass, electric | Completes clean-path story without buying anything |

## Waiting / External

| ID | Task | Waiting on |
|---|---|---|
| RIG-020 | Bench-test Big Muff with known-good cables and power | Bench time + known-good PSU/cables available |
| RIG-021 | Isolate RE-2 / Space Echo noise (one-pedal-at-a-time) | Quiet session; optional spare isolated supply for A/B after RIG-047 |
| RIG-022 | Complete FCB1010 MIDI OUT → TASCAM MIDI IN direct test | MIDI cable + MIDI monitor app session |
| RIG-023 | Decide whether MIDI Captain remains WAITING or becomes a buy decision | Outcome of RIG-022 + RIG-035 + RIG-030 |
| RIG-032 | Design and implement RC-600 integration | RC-600 acquisition (wishlist BUY LATER) |

## Active queue

| ID | Task | Area | Priority | Status | Depends On | Definition of Done | Notes |
|---|---|---|---|---|---|---|---|
| RIG-001 | Physically verify DIRTY chain order and SPACE topology (SY-1 SEND PH-3→TR-2; LS-2 loops; A+B MIX↔BYPASS) | Pedals | P0 | READY | — | `docs/pedal-chains.md` matches the physical board; any mismatch updated in pedal docs, diagrams, and inventory active lists | Do not invent fixes; document what is actually wired |
| RIG-002 | Inspect and record normal / half-normal / thru for every populated PB-B pair | Patchbay | P0 | READY | — | Every populated pair in `data/patchbays.yaml` and `docs/patchbays.md` has `mode` set to normal, half-normal, or thru | Upper 9–12 / lower 33–36 included if physically checkable |
| RIG-003 | Trace and document non-clean A/B/Y destinations for acoustic, bass, electric | Routing | P0 | READY | — | Each instrument’s other splitter leg is recorded in `docs/current-routing.md` + `data/routing.yaml`, or explicitly marked UNKNOWN with reason | Resolves open-questions routing fact |
| RIG-004 | Map ART P48 / Behringer PX3000 units to PB-A/B/C/D letters | Patchbay | P1 | READY | — | `data/patchbays.yaml` and `docs/patchbays.md` list hardware_model per bay | Visual/serial inspection at rack |
| RIG-005 | Decide roles for PB-A, PB-C, PB-D (remain open vs assigned roles) | Patchbay | P1 | READY | RIG-004 helpful | Each bay has a documented role or explicit “leave undocumented/open for now” decision in `docs/patchbays.md` | Decision, not speculative wiring |
| RIG-006 | Identify intended sources for PB-B lower 33–36 (or confirm intentionally unused) | Patchbay | P1 | READY | — | Upper 9–12 plan or “intentionally unassigned” recorded in patchbay docs/YAML | Do not invent sources |
| RIG-007 | Verify `assets/pedal-flow.jpeg` against CURRENT topology; update, archive, or remove | Docs | P2 | READY | RIG-001 | Image matches CURRENT or is moved/labeled HISTORICAL/removed with a note in docs | Untracked asset; treat carefully |
| RIG-008 | Determine acoustic instrument Alesis mixer assignment if any | Routing | P1 | READY | RIG-003 helpful | Alesis map + channel-map YAML updated, or documented as TASCAM-only | Open question fact |
| RIG-009 | Verify physical CH-1 stereo return jack(s) into Alesis | Routing | P1 | READY | — | Exact return path recorded in `docs/current-routing.md` and `docs/alesis-mixer-map.md` | Stereo return vs specific line channel |
| RIG-010 | Physically verify KAOSS Replay monitor/capture path vs docs | Routing | P1 | READY | — | Monitor Out → KAOSS → TASCAM 9/10 confirmed or docs corrected | Separate from AUX SEND |
| RIG-011 | Confirm Flamma Mod and PH-2 physical location (disconnected / stored / elsewhere) | Pedals | P2 | READY | RIG-001 | Inventory notes state location; still not listed as CURRENT path unless rewired and documented | Owned ≠ in chain |
| RIG-012 | Label major cables (clean legs, AUX SEND loop, KAOSS, PB-B critical pairs) | Studio ops | P1 | READY | — | Critical paths have readable labels; optional legend added under docs or patchbays | Prefer heat-shrink / tape that survives |
| RIG-013 | Label patchbay front rows for populated PB-B jacks | Patchbay | P1 | READY | RIG-002 helpful | Front labels match `docs/patchbays.md` jack map | — |
| RIG-014 | Write startup / shutdown checklist | Studio ops | P1 | READY | — | Doc covers power-up/down order, Mac/USB, Ableton, interface, mixer, MIDI sanity, audio sanity, emergency shutdown | Link from index |
| RIG-015 | Define and run known-good baseline smoke test | Studio ops | P0 | READY | RIG-001 helpful | Checklist + dated pass/fail proving clean captures, AUX loop, and KAOSS path; distinguishes “broken” from “booted differently” | — |
| RIG-016 | Capture a dated full-rig reference configuration snapshot | Docs | P1 | READY | RIG-001, RIG-002 | Dated note or commit references that routing/YAML/docs match the physical rack that day | Photo optional |
| RIG-017 | Back up controller mappings (Launchpad, Launch Control 3, padKONTROL, FCB, ZeRO SL, Stream Deck+) | Studio ops | P2 | READY | — | Backup location documented; files recoverable | Prefer external/archive path noted in docs, not large binaries in git |
| RIG-018 | Back up Ableton PFL jam template / set | Studio ops | P1 | READY | RIG-038 helpful | Template location + version/date documented; restore tested once | — |
| RIG-019 | Document recovery from a bad live-looping state | Studio ops | P1 | READY | — | Short recovery steps: clear RC-1, wrong clip, runaway feedback, stuck MIDI, KAOSS mistake, wrong scene, mute/solo accidents, pedal noise, emergency stop — prefer without keyboard/mouse | Expanded by RIG-044 |
| RIG-024 | Test PYLE-PRO PDC22 placement options (Privia / JOYO / clean taps) | Routing | P2 | READY | — | Recommendation written in reamp-and-di.md; open question updated | Not a purchase |
| RIG-025 | Decide whether LS-2 has any bass split/blend role outside SPACE | Pedals | P2 | DEFERRED | RIG-001 | Decision recorded: SPACE-only vs additional bass role | Currently CURRENT in SPACE |
| RIG-030 | Write a minimal MIDI mapping plan (Ableton + foot control targets) | MIDI | P2 | READY | — | One-page mapping plan in midi-clock.md or linked doc | Feeds RIG-035 / RIG-036 / RIG-037 |
| RIG-031 | Confirm Ableton as default master clock in practice | MIDI | P2 | READY | — | midi-clock.md states verified CURRENT behavior, not only intent | — |
| RIG-033 | Define PFL Eurorack v1 requirements and integration boundary | Modular | P1 | READY | — | Written brief answers: what Eurorack adds vs Ableton/Reason/pedals; MIDI/CV; audio I/O; rack size; performance vs generative roles; sync; recording path; budget boundary; MVP first case; what NOT to duplicate | Research/design only — not purchase authorization |
| RIG-034 | Map Launch Control 3 for Ableton performance sends (esp. Send D) | Controllers | P1 | READY | RIG-038 helpful | Exact active tracks listed; Send D mapped coherently; remaining encoders/buttons assigned; Custom Mode vs Ableton mode documented; config backed up | Do not invent track names that conflict with ableton-track-map.md — verify live set first |
| RIG-035 | Finalize FCB1010 configuration and Ableton mappings | Controllers | P1 | READY | RIG-022 | MIDI ch16; EXP A=CC111; EXP B=CC112; banks 00 arm/FX, 01 looper, 02 scene launcher documented; all switches assigned; no MIDI conflicts; tested; mapping stored in repo; rebuild procedure written | Exact switch map TBD until confirmed |
| RIG-036 | Finalize and document Novation ReMOTE ZeRO SL performance templates | Controllers | P1 | READY | RIG-030 helpful | Templates verified (PFL SEND C, REVERB FX, DELAY/SEND, MIDI GEN, MASTERING, QUANT, FX, CHAOS); avoid broken encoder #6; MIDI ch15 documented; PAD 8 = HOME; backups saved; no collisions with FCB1010/padKONTROL/Privia | — |
| RIG-037 | Document and verify final physical MIDI topology | MIDI | P0 | READY | RIG-031 helpful | Physical USB + DIN paths; U6MIDI Pro routes/filters; Thru5 WC role; clock master + destinations; channels (Privia 1, padKONTROL 10, ZeRO 15, FCB 16); Ableton Track/Sync/Remote settings; feedback prevention; All Notes Off path; MIDI-monitor tested | Owned CME gear — operate, don’t repurchase |
| RIG-038 | Create/finalize repeatable PFL JAM Ableton template | Ableton | P0 | READY | — | Turn-on-and-play set: active tracks, names, clean/wet/KAOSS paths, returns/sends (incl. Send D role if used), controller mappings, clock, monitoring, Session layout, record-ready, panic/recovery; can record a rough jam immediately | Finished music outranks rig redesign |
| RIG-039 | Normalize padKONTROL footswitch clip-record toggle to single predictable action | Ableton / M4L | P1 | READY | — | Max for Live (or alternate) clip-record start/stop is one intentional action each; double-press stop issue gone or documented workaround; behavior tested | Prior workflow had two-press stop; not documented as solved in repo |
| RIG-040 | Complete PB-A / PB-C / PB-D design for workflow access | Patchbay | P1 | BLOCKED | RIG-001, RIG-002, RIG-003, RIG-004, RIG-005, RIG-006 | Design doc assigns remaining bays for live looping, clean+wet simultaneous record, front-panel access, growth space; preserves documented PB-B; no speculative CURRENT jack fills until wired | — |
| RIG-041 | Cable inventory and labeling pass | Studio ops | P1 | READY | — | Counts by type/length (TS, TRS, XLR, MIDI DIN, USB, expression, patch); shortage list; installed ends labeled; patchbay cables identified; avoid needless cable purchases | Extends RIG-012 |
| RIG-042 | Audit owned OBS / webcam inventory vs needed PFL angles | Video | P2 | READY | — | Owned cameras/angles documented; USB bandwidth constraints noted; wishlist camera row marked REDUNDANT or kept RESEARCH with a concrete gap | — |
| RIG-043 | Establish rig backup / archive procedure | Studio ops | P1 | READY | — | Procedure covers Ableton template, M4L devices, LC3, ZeRO SL, FCB1010 docs, U6MIDI Pro routes, Stream Deck profiles, KAOSS settings, important samples/PFL assets; docs record backup *location* without dumping binaries into git | Extends RIG-017/018 |
| RIG-044 | Write one-performer live-looping recovery playbook | Studio ops | P1 | READY | RIG-019 | Playbook covers bad RC-1 loop, wrong clip, runaway delay/feedback, stuck note, KAOSS mistake, wrong scene, mute/solo accidents, pedal noise, full emergency stop; prefer recovery without keyboard/mouse | — |
| RIG-045 | Finish Stream Deck+ / OBS hands-off performance profiles | Video / ops | P1 | READY | RIG-042 helpful | Profiles (PFL HOME, OBS REC, OBS SCENES, OBS SAFE, ABLETON, FILES, MAC-RIG, SETTINGS) verified or remaining gaps listed; OBS SAFE provides stop-record, mute, camera isolate, replay save where supported, return to known scene; no keyboard/mouse needed for core performance | Do not recreate already-complete pages |
| RIG-046 | Record one complete PFL reference jam through the documented rig | Integration | P0 | READY | RIG-015 helpful | At least one instrument source; AUX SEND wet path; RC-1 used; JOYO branch used; KAOSS available/used; Ableton records expected paths; OBS/camera if practical; recording reviewed; discrepancies logged | Proves the rig makes music |
| RIG-047 | Audit pedal power supplies vs CURRENT pedal load | Pedals / power | P1 | READY | RIG-001 helpful | Per-pedal voltage + current need, supply assignment, isolation, total headroom documented; wishlist power item updated (buy / park / REDUNDANT) | Change one variable at a time if diagnosing noise |
| RIG-048 | Research stereo line-to-pedal / reamp / isolation options against owned ProRMP + PDC22 | Routing | P2 | READY | RIG-024 helpful | Written comparison of capability gap vs owned gear; shortlist or “no buy — workflow change” decision; no product purchase committed | Wishlist RESEARCH companion |

## Done

| ID | Task | Completed | Notes |
|---|---|---|---|
| — | — | — | No TODO items marked done yet |

## ID allocation

Next free ID: **RIG-049**.
<!-- rig:todo:end -->
