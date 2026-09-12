from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import current_service, gear_usage, inventory_state, routing_state
from music_rig.cli import app
from music_rig.inventory_projections import render_inventory_section
from music_rig.models import GearCondition, OwnershipStatus
from music_rig.store import StoreError, load_inventory, load_todo, load_wishlist


@pytest.fixture
def inventory_fx(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "inventory": tmp_path / "inventory.yaml",
        "routing": tmp_path / "routing.yaml",
        "wishlist": tmp_path / "wishlist.yaml",
        "todo": tmp_path / "todo.yaml",
    }
    paths["inventory"].write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "example-pedal",
                        "name": "Example Pedal",
                        "manufacturer": "Example",
                        "model": "Pedal",
                        "category": "pedals",
                        "quantity": 1,
                        "ownership_status": "OWNED",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    paths["routing"].write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "test": {
                        "label": "Test",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "Main",
                                "nodes": [
                                    {
                                        "id": "pedal",
                                        "label": "Example Pedal",
                                        "gear_ref": "example-pedal",
                                        "kind": "device",
                                    }
                                ],
                            }
                        },
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    paths["wishlist"].write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "item": "Future Box",
                        "category": "pedals",
                        "problem_capability": "A future capability",
                        "priority": "P2",
                        "status": "BUY LATER",
                        "todo_refs": ["RIG-001"],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    paths["todo"].write_text(
        yaml.safe_dump(
            {
                "next_session": [],
                "tasks": [
                    {
                        "id": "RIG-001",
                        "task": "Integrate Future Box",
                        "area": "Routing",
                        "priority": "P2",
                        "status": "WAITING",
                        "definition_of_done": "Integrated",
                        "waiting_on": "Acquisition",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return paths


def test_production_inventory_and_projection():
    doc = load_inventory()
    assert len(doc.items) == 49
    assert doc.resolve("art-p48-1").id == "art-p48"
    rendered = render_inventory_section(doc)
    assert "Interfaces Mixers" in rendered
    assert "boss-rc-1" in rendered


def test_add_and_field_mutations(inventory_fx):
    preview, data = inventory_state.propose_add(
        name="New Device",
        manufacturer="Maker",
        model="Model 1",
        category="utility",
        inventory_path=inventory_fx["inventory"],
    )
    assert preview.target == "maker-model-1"
    current_service.commit_inventory(
        data, preview, render=False, inventory_path=inventory_fx["inventory"]
    )
    condition, data = inventory_state.propose_set_condition(
        preview.target,
        GearCondition.ISSUE,
        inventory_path=inventory_fx["inventory"],
    )
    current_service.commit_inventory(
        data, condition, render=False, inventory_path=inventory_fx["inventory"]
    )
    location, data = inventory_state.propose_set_location(
        preview.target, "verified shelf", inventory_path=inventory_fx["inventory"]
    )
    assert location.after["location"] == "verified shelf"
    with pytest.raises(StoreError, match="non-empty"):
        inventory_state.propose_set_location(
            preview.target, "", inventory_path=inventory_fx["inventory"]
        )


def test_usage_and_routed_retirement_blocked(inventory_fx):
    usage = gear_usage.usage_for(
        "example-pedal",
        inventory_path=inventory_fx["inventory"],
        routing_path=inventory_fx["routing"],
        wishlist_path=inventory_fx["wishlist"],
    )
    assert usage["routing"][0]["path"] == "test"
    assert usage["patchbay"] == []
    with pytest.raises(StoreError, match="CURRENT routing"):
        inventory_state.propose_set_status(
            "example-pedal",
            OwnershipStatus.SOLD,
            inventory_path=inventory_fx["inventory"],
            routing_path=inventory_fx["routing"],
        )


def test_acquisition_payloads_and_transaction(inventory_fx):
    preview, inventory, wishlist, todo = inventory_state.propose_acquire(
        "Future Box",
        manufacturer="Future",
        model="Box",
        inventory_path=inventory_fx["inventory"],
        wishlist_path=inventory_fx["wishlist"],
        todo_path=inventory_fx["todo"],
        make_waiting_ready=True,
    )
    assert preview.domain == "inventory.acquire"
    assert wishlist.find("Future Box").inventory_ref == "future-box"
    assert todo.task_map()["RIG-001"].status.value == "READY"
    current_service.commit_acquisition(
        inventory,
        wishlist,
        todo,
        preview,
        render=False,
        inventory_path=inventory_fx["inventory"],
        wishlist_path=inventory_fx["wishlist"],
        todo_path=inventory_fx["todo"],
    )
    assert load_inventory(inventory_fx["inventory"]).resolve("future-box")
    assert load_wishlist(inventory_fx["wishlist"]).find("Future Box").status.value == "ACQUIRED"
    assert load_todo(inventory_fx["todo"]).task_map()["RIG-001"].status.value == "READY"


def test_routing_gear_ref_validation(inventory_fx):
    data = routing_state.load_raw(inventory_fx["routing"])
    data["named_paths"]["test"]["branches"]["main"]["nodes"][0]["gear_ref"] = "missing"
    errors = routing_state.validate_routing_doc(data, inventory_path=inventory_fx["inventory"])
    assert any("does not resolve" in error for error in errors)


def test_gear_cli_list_show_usage():
    runner = CliRunner()
    listed = runner.invoke(app, ["gear", "list", "--category", "pedals"])
    assert listed.exit_code == 0
    assert "boss-od-1" in listed.stdout
    shown = runner.invoke(app, ["gear", "show", "boss-rc-1"])
    assert shown.exit_code == 0
    assert "BOSS RC-1" in shown.stdout
    usage = runner.invoke(app, ["gear", "usage", "boss-rc-1"])
    assert usage.exit_code == 0
    assert "aux/main" in usage.stdout


def test_production_topology_fingerprint_ignores_identity_metadata():
    raw = routing_state.load_raw()
    before = routing_state.semantic_fingerprint(raw)
    stripped = yaml.safe_load(yaml.safe_dump(raw))
    for path in stripped["named_paths"].values():
        for branch in path["branches"].values():
            for node in branch["nodes"]:
                node.pop("gear_ref", None)
                node.pop("kind", None)
    assert routing_state.semantic_fingerprint(stripped) == before
