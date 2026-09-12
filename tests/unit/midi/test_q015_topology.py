"""Regression: Q-015 HUMAN MIDI topology links stay in CURRENT."""

from __future__ import annotations

from music_rig import midi_state
from music_rig.models import MidiEvidenceStatus


def test_q015_fcb_u6midi_thru5_links_present():
    doc = midi_state.load_document()
    links = {(c.source, c.destination, c.source_port, c.destination_port) for c in doc.connections}
    assert (
        "behringer-fcb1010",
        "cme-u6midi-pro",
        "MIDI OUT",
        "MIDI IN 1",
    ) in links
    assert (
        "cme-u6midi-pro",
        "cme-midi-thru5-wc",
        "MIDI OUT 1",
        "MIDI IN 1",
    ) in links
    assert all(c.status is MidiEvidenceStatus.VERIFIED for c in doc.connections)
