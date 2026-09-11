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


def fmt_source(source):
    return "—" if source is None else source


print("TASCAM")
for channel, meta in channel_map["tascam"].items():
    status = meta.get("status", "")
    status_suffix = f" ({status})" if status else ""
    print(
        f"  {channel}: {meta['name']} <- {fmt_source(meta['source'])} "
        f"[{meta['type']}]{status_suffix}"
    )

print("\nAlesis")
for channel, meta in channel_map["alesis"].items():
    aux = "aux" if meta["aux_send"] else "no aux"
    status = meta.get("status", "")
    status_suffix = f" ({status})" if status else ""
    print(f"  {channel}: {fmt_source(meta['source'])} [{aux}]{status_suffix}")
