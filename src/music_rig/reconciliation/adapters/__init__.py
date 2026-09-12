"""Adapter registry by question target domain."""

from __future__ import annotations

from music_rig.reconciliation.adapters.ableton_template import AbletonTemplateAdapter
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.adapters.controls_verify import ControlsVerifyAdapter
from music_rig.reconciliation.adapters.inventory_mapping import InventoryMappingAdapter
from music_rig.reconciliation.adapters.midi_clock import MidiClockAdapter
from music_rig.reconciliation.adapters.midi_verify import MidiVerifyAdapter
from music_rig.reconciliation.adapters.patchbay_mode import PatchbayModeAdapter
from music_rig.reconciliation.adapters.routing_verify import RoutingVerifyAdapter
from music_rig.reconciliation.adapters.unsupported import UnsupportedAdapter

_REGISTRY: dict[str, ReconciliationAdapter] = {
    "patchbay.mode": PatchbayModeAdapter(),
    "inventory.patchbay_mapping": InventoryMappingAdapter(),
    "routing.verify": RoutingVerifyAdapter(),
    "midi.clock_master": MidiClockAdapter(),
    "midi.verify": MidiVerifyAdapter(),
    "controls.verify": ControlsVerifyAdapter(),
    "ableton.template": AbletonTemplateAdapter(),
}


def get_adapter(domain: str | None) -> ReconciliationAdapter:
    if not domain:
        return UnsupportedAdapter("(none)")
    return _REGISTRY.get(domain, UnsupportedAdapter(domain))


def registered_domains() -> list[str]:
    return sorted(_REGISTRY.keys())
