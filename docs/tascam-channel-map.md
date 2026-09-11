# TASCAM Channel Map

Canonical CURRENT assignments: `data/channel-map.yaml`.

Edit with `uv run rig current channels set-source …` (or clear-source).

<!-- rig:tascam:start -->
<!-- GENERATED FROM data/channel-map.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

| Input | Track Name | Source | Type | Status |
|---:|---|---|---|---|
| 1 | MIXER_L | Alesis main out L | clean_stereo_bus | CURRENT |
| 2 | MIXER_R | Alesis main out R | clean_stereo_bus | CURRENT |
| 3 | miniKORG_L | miniKORG L | synth | CURRENT |
| 4 | miniKORG_R | miniKORG R | synth | CURRENT |
| 5 | ACOUSTIC_CLEAN | Acoustic after BOSS acoustic preamp | clean_mono | CURRENT |
| 6 | BASS_CLEAN | Bass after BBox preamp | clean_mono | CURRENT |
| 7 | GUITAR_CLEAN | Electric after Flamma preamp | clean_mono | CURRENT |
| 8 | UNASSIGNED | — | unassigned | UNASSIGNED |
| 9 | KAOSS_L | KAOSS Replay L | wet_stereo | CURRENT |
| 10 | KAOSS_R | KAOSS Replay R | wet_stereo | CURRENT |
| 11 | SR18_L | Alesis SR-18 MAIN L | rhythm | CURRENT |
| 12 | SR18_R | Alesis SR-18 MAIN R | rhythm | CURRENT |
| 13 | UNASSIGNED | — | unassigned | UNASSIGNED |
| 14 | UNASSIGNED | — | unassigned | UNASSIGNED |
| 15 | UNASSIGNED | — | unassigned | UNASSIGNED |
| 16 | UNASSIGNED | — | unassigned | UNASSIGNED |
<!-- rig:tascam:end -->

## Notes

- Clean instrument legs (5/6/7) use preamp → A/B/Y; non-clean A/B/Y destinations remain OPEN questions.
- miniKORG and SR-18 also appear on PB-B pairs into TASCAM 3/4 and 11/12.
- UNASSIGNED channels have `source: null` in YAML.
