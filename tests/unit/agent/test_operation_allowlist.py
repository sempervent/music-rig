"""Tests migrated to unit/agent/test_operation_allowlist.py."""

from __future__ import annotations

from music_rig.agent import (
    capabilities,
)
from music_rig.reconciliation.operation_registry import allowlisted_kinds, get_spec


def test_capabilities_includes_new_ops():
    caps = capabilities()
    kinds = caps["allowlisted_operations"]
    assert "channels.set_source" in kinds
    assert "channels.clear_source" in kinds
    assert "path.move" in kinds
    assert "path.set_evidence" in kinds
    assert "PLAN_ONLY" in caps["autonomy_levels"]


def test_allowlisted_includes_path_and_channels_clear():
    kinds = allowlisted_kinds(agent_only=True)
    assert "path.insert" in kinds
    assert "path.remove" in kinds
    assert "path.set_mode" in kinds
    assert "channels.clear_source" in kinds
    assert get_spec("channels.clear_source").agent_allowed is True
