"""Tests migrated to smoke/test_tui_cli.py."""

from __future__ import annotations

import shutil
from pathlib import Path
import pytest
import yaml
from music_rig import store
from music_rig.patchbay_state import list_pairs, load_raw
from music_rig.store import StoreError, load_questions
from music_rig.tui.app import RigApp
from music_rig.tui.editable_domains import registry
from music_rig.tui.modes import EditorMode, parse_command
from music_rig.tui.save_outcome import SaveOutcome
from music_rig.tui.working import ConcurrentModificationError, WorkingDocument

def test_cli_tui_debug_flag():
    import re

    from typer.testing import CliRunner

    from music_rig.cli import app

    result = CliRunner().invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--debug" in plain

