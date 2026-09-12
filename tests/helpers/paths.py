"""Path helpers for tests (repo root, etc.)."""

from __future__ import annotations

from pathlib import Path

from music_rig.store import ROOT


def repo_root() -> Path:
    """Return the music-rig repository root (same as ``music_rig.store.ROOT``)."""
    return ROOT
