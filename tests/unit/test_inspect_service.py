"""Inspect service helpers beyond CLI smoke."""

from __future__ import annotations

import pytest

from music_rig import inspect_service
from music_rig.store import StoreError


def test_list_domains_and_supports_reconcile():
    rows = inspect_service.list_domains()
    assert any(r["id"] == "question" for r in rows)
    assert inspect_service._supports_reconcile("question") is True
    assert isinstance(inspect_service._supports_reconcile("doctor"), bool)


def test_schema_for_patchbay_and_unknown():
    schema = inspect_service.schema_for("patchbay")
    assert schema["domain"] == "patchbay"
    assert schema["fields"]
    with pytest.raises(StoreError, match="Unknown domain"):
        inspect_service.schema_for("not-a-domain-xyz")


def test_list_show_and_find_refs(iso):
    rows = inspect_service.list_records("todo")
    assert isinstance(rows, list)
    with pytest.raises(StoreError):
        inspect_service.list_records("not-listable-xyz")
    with pytest.raises(StoreError):
        inspect_service.show_record("not-a-domain-xyz", "x")

    refs = inspect_service.find_refs("iso-gear")
    assert refs["id"] == "iso-gear"
    assert "refs" in refs


def test_dumps_formats():
    domains = inspect_service.list_domains()
    text = inspect_service.dumps(domains, as_json=False, kind="domains")
    assert "question" in text.casefold() or "Question" in text
    js = inspect_service.dumps({"a": 1}, as_json=True)
    assert '"a"' in js
    rows = [{"id": "X", "label": "Y"}]
    table = inspect_service.dumps(rows, as_json=False)
    assert "X" in table
    assert inspect_service.dumps(["plain"], as_json=False) == "plain"
    assert inspect_service.dumps(123, as_json=False) == "123"
