#!/usr/bin/env python3
"""Print the studio channel map from data/channel-map.yaml.

Thin wrapper around music_rig.rig_views for CI compatibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from music_rig.rig_views import format_channels_compat  # noqa: E402

print(format_channels_compat().rstrip())
