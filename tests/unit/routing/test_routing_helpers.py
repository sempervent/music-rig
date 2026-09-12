"""Routing state helper / batch / validation edges."""

from __future__ import annotations

import pytest
import yaml

from music_rig import routing_state
from music_rig.store import StoreError


def test_validate_routing_doc_basic_errors():
    assert "mapping" in routing_state.validate_routing_doc("x")[0]
    errs = routing_state.validate_routing_doc({"named_paths": []})
    assert any("named_paths must be a mapping" in e for e in errs)
    errs = routing_state.validate_routing_doc({"named_paths": {"Dirty": {}, "dirty": {}}})
    assert any("unique" in e for e in errs)


def test_propose_batch_and_empty(tmp_path):
    path = tmp_path / "routing.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "dirty": {
                        "label": "DIRTY",
                        "status": "CURRENT",
                        "evidence": "UNKNOWN",
                        "branches": {
                            "main": {
                                "label": "Main",
                                "nodes": [
                                    {"id": "a", "label": "A"},
                                    {"id": "b", "label": "B"},
                                ],
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    preview, data = routing_state.propose_batch(
        "dirty",
        [
            {"op": "move", "node": "b", "first": True},
            {"op": "insert", "node": "z", "label": "Z", "last": True},
            {"op": "remove", "node": "z"},
        ],
        routing_path=path,
    )
    assert preview.domain == "routing.verify"
    ids = [
        n["id"] if isinstance(n, dict) else n.id
        for n in data["named_paths"]["dirty"]["branches"]["main"]["nodes"]
    ]
    # after move first + insert last + remove z → b, a
    assert ids[0] == "b"

    with pytest.raises(StoreError, match="Unknown batch op"):
        routing_state.propose_batch("dirty", [{"op": "explode"}], routing_path=path)

    preview_empty, _ = routing_state.propose_batch("dirty", [], routing_path=path)
    assert preview_empty.changed is False


def test_load_raw_rejects_non_mapping(tmp_path):
    path = tmp_path / "routing.yaml"
    path.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(StoreError):
        routing_state.load_raw(path)
