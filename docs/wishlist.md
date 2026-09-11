# Studio Wishlist

**Wishlist = things that might be desirable. Not a commitment to buy or implement.**

```text
Wishlist item
   ↓
evaluation
   ↓
accepted decision
   ↓
TODO item  (see docs/todo.md)
```

Do not treat rows below as approved work. Accepted work lives only in [Todo](todo.md).
Unresolved **facts** live in [Open Questions](open-questions.md).

Evaluation order: quality → reproducibility → creative novelty → PFL usefulness → cost → learning value → speed.
Prefer finished music and playability over gear accumulation.

Prices: use documented snapshots where present; otherwise **UNKNOWN** (do not invent).

## Status legend

| Status | Meaning |
|---|---|
| IDEA | Speculative; not evaluated deeply |
| RESEARCH | Worth comparing / reading / designing against owned gear |
| BORROW FIRST | Try before buying if possible |
| BUY LATER | Attractive after prerequisites or budget gate |
| BUY NOW | Explicitly approved to purchase soon — use sparingly |
| REDUNDANT | Capability already covered well enough by owned gear |
| REJECTED | Evaluated and declined |
| WAITING | Blocked on another decision, test, or arrival |
| DEFERRED | Intentionally parked behind a preferred direction |

## Priority legend

| Priority | Meaning |
|---|---|
| P0 | Directly blocks useful music-making |
| P1 | High-value near-term |
| P2 | Useful but not urgent |
| P3 | Curiosity / future |

## Master table

| Item | Category | Problem / Capability | Priority | Status | Duplication | Cost | Friction | Likely Music Impact | Notes |
|---|---|---|---|---|---|---|---|---|---|
| BOSS RC-600 | Live looping | Foot-operated multi-track looping; overdub/transition control beyond RC-1; Ableton-friendly solo performance | P1 | BUY LATER | Partial: RC-1, KAOSS, Ableton clips; overlaps RC-505mkII concept | UNKNOWN | High learning + integration | High for one-person live structure | Established future direction. RC-1 stays useful for simple phrase capture. See TODO RIG-032 (WAITING on acquisition). |
| PFL Eurorack v1 | Modular | Generative sound, playable modulation, strange rhythm, controlled randomness, drones, CV interactions, visual interest for PFL | P1 | RESEARCH | Partial: Ableton/Reason, SY-1, SL-2, delays; preferred over MicroFreak as next synth direction | UNKNOWN | High learning + case/power design | High if it unlocks unplayable-elsewhere textures | Design requirements first (TODO RIG-033). Not a shopping list yet. |
| Hologram Microcosm | Pedal / texture | Playable granular / resampling / micro-loop texture not ergonomically covered by current delays alone | P1 | RESEARCH | TE-2, RE-2, DD-8, SL-2, KAOSS, Ableton, Reason, future Eurorack | ~$413 (Jul 2026 snapshot) | Moderate; stereo post-CH-1 candidate | High for texture if unique vs owned tools | Justify by playable capability, not “another ambient pedal.” |
| BOSS RC-505mkII | Live looping | Hands-on multi-track looper with faders | P2 | RESEARCH | Strong overlap with preferred RC-600 + KAOSS + Ableton | ~$640–660 (Jul 2026) | High; less foot-first than RC-600 | Medium unless a separate desk-oriented use case appears | Do not substitute for RC-600. Demoted vs foot-operated priorities. |
| Expanded isolated pedal power | Studio infrastructure | Adequate isolated power for CURRENT pedal population; reduce hum/noise; avoid current-capacity problems | P1 | RESEARCH | Existing supplies (inventory incomplete) | UNKNOWN | Mounting / recabling | Medium–high if noise or brownouts limit takes | Audit load first (TODO RIG-047). Do not buy until audit implicates supply. |
| Stereo line-to-pedal / reamp / isolation solution | Audio isolation | Reliable line-level → pedal-level path without crushing AUX SEND (ProRMP was too quiet) | P2 | RESEARCH | Radial ProRMP, PYLE PDC22, mixer AUX, patchbays | UNKNOWN | Gain-staging design | Medium for wet-loop flexibility | Capability gap, not a product pick yet. |
| Additional reliable 1080p OBS webcam angle | Recording / video | Extra simultaneous OBS view (hands / pedals / room / direct-address) without needing 4K everywhere | P2 | RESEARCH | Unknown until camera inventory audited | UNKNOWN | USB bandwidth on MacBook Air two-port topology | Medium for PFL video | Buy only if owned cameras cannot cover needed angles. |
| Arturia MicroFreak | Instruments | Compact digital/hybrid synth exploration | P3 | DEFERRED | Behind Eurorack exploration preference | UNKNOWN | Moderate | Medium | Interesting but not the preferred next synthesis direction. |
| PaintAudio MIDI Captain | Controllers | Compact foot PC/CC/note control | P2 | WAITING | Overlaps FCB1010 (owned) | ~$180 (Jul 2026) | Mapping work | Medium after MIDI plan | Finish FCB1010 first (RIG-022, RIG-035). |
| Pioneer DJ DDJ-FLX4 | Controllers / performance | DJ + hybrid live workflow | P3 | IDEA | New workflow | ~$329 (Jul 2026) | New discipline | Low unless DJ sets are a real goal | Buy only when hybrid set defined. |
| Line 6 DL4 MkII | Pedals / consolidation | Delay + looper consolidation; mic-input looping | P3 | RESEARCH | Heavy: DD-8, TE-2, RE-2, RC-1, KAOSS, Microcosm, RC-600 | ~$250 (Jul 2026) | High if stacked without removals | Low–medium unless it replaces several pedals | EXPERIMENT only until consolidation criteria met. |
| Nord Stage 4 88 | Instruments | Weighted stage piano/organ/synth replacement for Privia | P3 | BUY LATER | Would replace Privia | ~$5,999 (Jul 2026) | High cost | High if keys become central | Elevate only if Privia limits the project. |
| Generic MIDI thru / splitter / router | MIDI utilities | Distribute / route MIDI clock and controllers | — | REDUNDANT | **Owned:** CME U6MIDI Pro (3×3 route/merge/filter) + CME MIDI Thru5 WC | — | — | — | Do not buy topology twice. Document owned topology (TODO RIG-037). |
| Additional stereo DI / line isolator (generic) | Audio isolation / DI | Extra DI/isolation | P3 | IDEA | Overlaps PYLE-PRO PDC22 + line-to-pedal research item | UNKNOWN | Placement | Low–medium | Prefer solving ProRMP/AUX gain gap (above) and PDC22 placement (RIG-024). |
| Expression mapping (EV-30 → SL-2 / PH-3) | Controllers / workflow | Hands-free params with **owned** EV-30 | P2 | IDEA | N/A (owned) | Time | Patching | Medium | Not a purchase. |
| Default loop-building order playbook | Workflow | RC-1 vs KAOSS vs future RC-600 order | P2 | IDEA | N/A | Time | Process | High | Promote into jam-template / recovery TODOs as decisions land. |

No items are marked **BUY NOW** or **REJECTED**.

## Relationship to TODO

| Wishlist outcome | What happens |
|---|---|
| Stay IDEA / RESEARCH / BUY LATER / DEFERRED | Remains here only |
| Decision: buy or implement | Create a TODO with Definition of Done |
| Capability already owned | Mark REDUNDANT; document/operate owned gear via TODO |

Example:

```text
Wishlist: BOSS RC-600 — BUY LATER
   ↓ (after acquisition)
TODO: RIG-032 — Design and implement RC-600 integration (was WAITING)
```

## Detail notes

### BOSS RC-600 (established direction)

Desired role: multi-track foot looping, sophisticated overdub/transition control, Ableton integration without replacing Ableton, solo-performance operation. RC-1 remains for simple pre-effects phrase capture.

Do **not** invent CURRENT wiring. Integration design is TODO RIG-032 (WAITING on acquisition).

### PFL Eurorack v1

Purpose: make Positive Feedback Loop more interesting via generative/modulation/CV/ergonomics and visual patching — not modular-for-its-own-sake. Prefer exploring Eurorack over treating MicroFreak as the obvious next synth.

Requirements/boundary design: TODO RIG-033. No module shopping list until that exists.

### Hologram Microcosm

Keep as a legitimate candidate. Evaluate against TE-2, RE-2, DD-8, SL-2, KAOSS, Ableton, Reason, and future Eurorack. Status RESEARCH (not BUY NOW / BUY LATER until uniqueness is proven).

### BOSS RC-505mkII

Previously listed as top looper buy. Reclassified: RESEARCH / lower priority vs foot-first RC-600 direction. Separate desk-oriented use case would need explicit justification.

### MIDI topology (owned — not a purchase)

Owned:

- CME U6MIDI Pro — 3 in / 3 out, routing, merging, filtering/remapping
- CME MIDI Thru5 WC — hardware thru distribution

Generic “buy MIDI thru/splitter” is **REDUNDANT**. Finish documentation and verification instead (RIG-037).

### Isolated pedal power

Active RESEARCH pending power audit (RIG-047). Problem statement: power the CURRENT pedal population with adequate isolation/headroom while reducing hum/noise.

### Stereo line-to-pedal / isolation

Historical ProRMP on AUX SEND required maxed sends and was too quiet. Capability gap remains RESEARCH (RIG-048), not a product SKU.

### Additional OBS camera

Only if audit shows missing angles. Account for USB bandwidth and MacBook Air two-port limits.

### MicroFreak

Interesting; **DEFERRED** behind Eurorack exploration.

## Priority change conditions

- RC-600 acquired → promote RIG-032 from WAITING; demote RC-505 further or REJECT if redundant.
- Eurorack MVP defined and budgeted → may become BUY LATER for case/power only after RIG-033.
- FCB1010 reliable → demote MIDI Captain.
- Power audit clears supply → keep isolated-power wishlist parked or REDUNDANT.
- Camera audit shows three solid OBS angles → camera wishlist REDUNDANT.
- Keyboard focus → elevate Nord.
- DL4 replaces multiple delays → elevate; else leave low due to redundancy.
