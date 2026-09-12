"""Patchbay validation / jack helper edges."""

from __future__ import annotations

import pytest

from music_rig.patchbay_state import (
    _bay,
    _get_jack,
    _norm_jack_num,
    dump_with_header,
    parse_mode,
    validate_patchbays_doc,
)
from music_rig.store import StoreError


def test_parse_mode_and_norm_jack():
    assert parse_mode("normal") == "normal"
    assert parse_mode("HALF-NORMAL") == "half-normal"
    with pytest.raises(StoreError):
        parse_mode("weird")
    assert _norm_jack_num(1) == 1
    assert _norm_jack_num("25") == 25
    assert _norm_jack_num(True) is None
    assert _norm_jack_num("x") is None


def test_validate_patchbays_doc_errors():
    assert validate_patchbays_doc({"patchbays": "x"}) == ["patchbays must be a mapping"]
    errs = validate_patchbays_doc(
        {
            "patchbays": {
                "PB-A": "bad",
                "PB-B": {"jacks": "nope"},
                "PB-C": {
                    "jacks": {
                        "x": {"mode": "nope"},
                        1: {"mode": "normal", "paired_with": 2},
                        "1": {"mode": "normal"},
                    }
                },
            }
        }
    )
    assert any("must be a mapping" in e for e in errs)
    assert any("jacks must be a mapping" in e for e in errs)
    assert any("invalid jack key" in e or "duplicate" in e or "invalid mode" in e for e in errs)


def test_bay_and_get_jack_helpers():
    data = {
        "patchbays": {
            "PB-A": {
                "jacks": {
                    1: {"row": "upper"},
                    "2": {"row": "lower"},
                }
            }
        }
    }
    bay = _bay(data, "pb-a")
    assert _get_jack(bay["jacks"], 1) is not None
    assert _get_jack(bay["jacks"], 2) is not None
    assert _get_jack(bay["jacks"], 99) is None
    with pytest.raises(StoreError, match="Unknown patchbay"):
        _bay(data, "PB-Z")


def test_dump_with_header_custom():
    text = dump_with_header(
        {"schema_notes": {}, "patchbays": {}},
        existing_text="# keep me\n",
    )
    assert text.startswith("# keep me")
