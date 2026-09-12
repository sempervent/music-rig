"""Channel map validation and resolution helpers."""

from __future__ import annotations

import pytest

from music_rig.channel_state import (
    dump_with_header,
    resolve_channel_key,
    validate_channel_map,
)
from music_rig.store import StoreError


def test_validate_channel_map_type_and_contradictions():
    assert validate_channel_map({}) == []
    errs = validate_channel_map({"alesis": "bad"})
    assert any("mapping" in e for e in errs)
    errs = validate_channel_map({"alesis": {"1": "x"}})
    assert any("must be a mapping" in e for e in errs)
    errs = validate_channel_map(
        {
            "tascam": {1: {"status": "UNASSIGNED", "source": "leak"}},
            "alesis": {"5_6": {"status": "CURRENT", "source": None}},
        }
    )
    assert any("source/status" in e for e in errs)
    assert any("missing type" in e for e in errs)
    errs = validate_channel_map({"alesis": {"1": {"source": None}}})
    assert any("missing status" in e for e in errs)


def test_resolve_channel_key_variants():
    section = {"1": {}, "5_6": {}, 3: {}}
    assert resolve_channel_key("alesis", "1", section) == "1"
    assert resolve_channel_key("alesis", "5/6", section) == "5_6"
    assert resolve_channel_key("alesis", 3, section) == 3
    with pytest.raises(StoreError, match="Alesis channel"):
        resolve_channel_key("alesis", "99", section)
    with pytest.raises(StoreError, match="TASCAM channel"):
        resolve_channel_key("tascam", "9", {"1": {}})


def test_dump_with_header_preserves_existing_comments():
    existing = "# custom header\n# line2\nalesis: {}\n"
    text = dump_with_header({"alesis": {}}, existing_text=existing)
    assert text.startswith("# custom header")
    assert "alesis:" in text
