"""KAOSS Replay route must stay TASCAM OUT 3/4 → KAOSS → TASCAM IN 15/16."""

from __future__ import annotations

import yaml

from music_rig import store
from music_rig.ableton_projections import render_ableton_section
from music_rig.models import AbletonDocument
from music_rig.render import apply_routing_render
from music_rig.routing_state import load_raw


def test_kaoss_channel_map_returns_on_15_16_not_9_10():
    raw = yaml.safe_load(store.CHANNEL_MAP_PATH.read_text(encoding="utf-8"))
    tascam = raw["tascam"]
    assert tascam[15]["source"].casefold().startswith("kaoss")
    assert tascam[16]["source"].casefold().startswith("kaoss")
    for ch in (9, 10):
        src = str(tascam[ch].get("source") or "")
        assert "kaoss" not in src.casefold()


def test_kaoss_routing_uses_out_3_4_and_in_15_16():
    raw = yaml.safe_load(store.ROUTING_PATH.read_text(encoding="utf-8"))
    route = raw["routes"]["kaoss_capture"]
    assert route["from"] == "TASCAM OUT 3/4"
    assert route["to"] == "TASCAM IN 15/16"
    assert "KAOSS" in route["through"].upper()
    nodes = raw["named_paths"]["kaoss"]["branches"]["main"]["nodes"]
    labels = [n["label"] for n in nodes]
    assert labels[0] == "TASCAM OUT 3/4"
    assert labels[1] == "KAOSS Replay"
    assert labels[2] == "TASCAM IN 15/16"


def test_ableton_kaoss_notes_not_stale_9_10():
    raw = yaml.safe_load(store.ABLETON_PATH.read_text(encoding="utf-8"))
    kaoss = next(t for t in raw["tracks"] if t["id"] == "kaoss")
    notes = kaoss.get("notes") or ""
    assert "OUT 3/4" in notes
    assert "IN 15/16" in notes
    assert "9/10" not in notes


def test_rendered_ableton_and_routing_docs_reflect_kaoss_correction():
    ableton = AbletonDocument.model_validate(
        yaml.safe_load(store.ABLETON_PATH.read_text(encoding="utf-8"))
    )
    generated = render_ableton_section(ableton)
    assert "OUT 3/4" in generated
    assert "IN 15/16" in generated
    assert "9/10" not in generated

    stub = "# Routing\n\n<!-- rig:routing:start -->\n<!-- rig:routing:end -->\n"
    paths_md = apply_routing_render(stub, load_raw())
    assert "TASCAM OUT 3/4" in paths_md
    assert "TASCAM IN 15/16" in paths_md
    assert "KAOSS Replay" in paths_md
