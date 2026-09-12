"""Rename service analysis edges (fixture inventory)."""

from __future__ import annotations

from music_rig import rename_service
from music_rig.models import WishlistDocument, WishlistItem, WishStatus


def test_rename_unknown_and_deferred_and_validation(iso):
    deferred = rename_service.analyze_rename("todo", "RIG-1", "RIG-2")
    assert not deferred.ok
    assert "deferred" in deferred.errors[0].casefold()

    unknown = rename_service.analyze_rename("spaceship", "a", "b")
    assert "Unknown rename domain" in unknown.errors[0]

    spaces = rename_service.analyze_rename("gear", "iso-gear", "bad id")
    assert any("slug" in e.casefold() or "space" in e.casefold() for e in spaces.errors)

    identical = rename_service.analyze_rename("gear", "iso-gear", "iso-gear")
    assert any("identical" in e.casefold() for e in identical.errors)


def test_rename_unknown_gear_and_dry_run(iso):
    missing = rename_service.analyze_rename("gear", "no-such-gear", "renamed-gear")
    assert not missing.ok

    preview = rename_service.analyze_rename("gear", "iso-gear", "iso-gear-x")
    assert preview.ok
    dry = rename_service.apply_rename("gear", "iso-gear", "iso-gear-x", dry_run=True)
    assert dry.ok
    # dry-run must not mutate
    from music_rig.store import load_inventory

    assert load_inventory().resolve("iso-gear") is not None


def test_replace_gear_refs_nested():
    obj = {
        "gear_ref": "old",
        "nested": [{"inventory_ref": "old"}, {"gear": "keep"}],
        "other": "old",
    }
    out = rename_service._replace_gear_refs(obj, "old", "new")
    assert out["gear_ref"] == "new"
    assert out["nested"][0]["inventory_ref"] == "new"
    assert out["nested"][1]["gear"] == "keep"
    assert out["other"] == "old"


def test_rename_updates_wishlist_ref(iso, monkeypatch):
    from music_rig import store as store_mod

    wish = WishlistDocument(
        items=[
            WishlistItem(
                item="extra bay",
                category="patchbay",
                problem_capability="more returns",
                status=WishStatus.IDEA,
                inventory_ref="iso-gear",
            )
        ]
    )
    store_mod.save_wishlist(wish)
    preview = rename_service.analyze_rename("gear", "iso-gear", "iso-gear-renamed")
    assert any("wishlist" in r for r in preview.replacements)
    applied = rename_service.apply_rename("gear", "iso-gear", "iso-gear-renamed")
    assert applied.ok
    assert store_mod.load_wishlist().items[0].inventory_ref == "iso-gear-renamed"
