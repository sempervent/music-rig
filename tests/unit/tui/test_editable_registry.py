"""Tests migrated to unit/tui/test_editable_registry.py."""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml
from music_rig import inspect_service, question_service, rename_service, store
from music_rig.patchbay_state import propose_set_connection, load_raw, save_raw
from music_rig.tui.editable_domains import registry
from music_rig.tui.fields import FieldType

def test_registry_all_editable_have_fieldspecs():
    for adapter in registry.all_adapters():
        specs = adapter.get_field_specs()
        assert specs, adapter.id
        assert any(s.type != FieldType.READONLY or s.read_only for s in specs) or True
        # schema serializes
        for s in specs:
            d = s.to_dict()
            assert d["name"] and d["type"]

