#!/usr/bin/env python3
"""Print the studio channel map from data/channel-map.yaml."""

from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    sys.exit("Missing PyYAML. Install with: uv pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "channel-map.yaml"

with DATA.open("r", encoding="utf-8") as f:
    channel_map = yaml.safe_load(f)

print("TASCAM")
for channel, meta in channel_map["tascam"].items():
    print(f"  {channel}: {meta['name']} <- {meta['source']} [{meta['type']}]")

print("\nAlesis")
for channel, meta in channel_map["alesis"].items():
    aux = "aux" if meta["aux_send"] else "no aux"
    print(f"  {channel}: {meta['source']} [{aux}]")
