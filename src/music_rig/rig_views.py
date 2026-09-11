"""Read-only CURRENT rig views derived from canonical YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.tree import Tree

from music_rig.models import NamedPath, PathTreeNode
from music_rig.store import (
    CHANNEL_MAP_PATH,
    PATCHBAYS_PATH,
    StoreError,
    load_routing,
    parse_existing_yaml,
)


def load_channel_map(path: Path | None = None) -> dict[str, Any]:
    target = path or CHANNEL_MAP_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_patchbays(path: Path | None = None) -> dict[str, Any]:
    target = path or PATCHBAYS_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict) or "patchbays" not in raw:
        raise StoreError(f"{target} must contain a patchbays mapping")
    return raw


def _channel_key_sort(key: Any) -> tuple[int, str]:
    text = str(key)
    if text.isdigit():
        return (0, f"{int(text):04d}")
    return (1, text)


def format_channels(
    *,
    device: str | None = None,
    channel_map_path: Path | None = None,
) -> str:
    data = load_channel_map(channel_map_path)
    want = (device or "all").strip().lower()
    lines: list[str] = []

    def _tascam() -> None:
        tascam = data.get("tascam") or {}
        lines.append("TASCAM US-16x08")
        lines.append("")
        # Pair consecutive stereo channels when names suggest L/R and sequential
        keys = sorted(tascam.keys(), key=_channel_key_sort)
        i = 0
        while i < len(keys):
            key = keys[i]
            meta = tascam[key]
            source = meta.get("source")
            name = meta.get("name", "")
            label = source if source not in (None, "") else name or "UNASSIGNED"
            # Try pairing n / n+1 when both numeric and consecutive
            if (
                str(key).isdigit()
                and i + 1 < len(keys)
                and str(keys[i + 1]).isdigit()
                and int(keys[i + 1]) == int(key) + 1
            ):
                meta2 = tascam[keys[i + 1]]
                src2 = meta2.get("source")
                name2 = meta2.get("name", "")
                # Pair if both L/R-ish or same type stereo bus
                pairable = (
                    str(name).endswith("_L")
                    and str(name2).endswith("_R")
                    and name[:-2] == name2[:-2]
                ) or (
                    str(name).endswith("L")
                    and str(name2).endswith("R")
                    and name[:-1] == name2[:-1]
                    and name not in {"UNASSIGNED"}
                )
                if pairable:
                    # Prefer a combined label from L source
                    left = source or name
                    if isinstance(left, str) and left.endswith(" L"):
                        combined = left[:-2]
                    elif isinstance(left, str) and left.endswith("L"):
                        combined = left[:-1].rstrip("_")
                    else:
                        combined = left
                    lines.append(f"{key}/{keys[i + 1]:<4}  {combined}")
                    i += 2
                    continue
            ch = str(key)
            lines.append(f"{ch:<7}  {label if label else 'UNASSIGNED'}")
            i += 1

    def _alesis() -> None:
        alesis = data.get("alesis") or {}
        lines.append("Alesis Mixer")
        lines.append("")
        for key in sorted(alesis.keys(), key=_channel_key_sort):
            meta = alesis[key]
            source = meta.get("source")
            aux = "aux" if meta.get("aux_send") else "no aux"
            label = "UNASSIGNED" if source in (None, "") else source
            lines.append(f"{str(key):<7}  {label}  [{aux}]")

    if want in {"all", "tascam"}:
        _tascam()
    if want == "all":
        lines.append("")
    if want in {"all", "alesis"}:
        _alesis()
    if want not in {"all", "tascam", "alesis"}:
        raise StoreError("device must be tascam, alesis, or omit for both")
    return "\n".join(lines) + "\n"


def format_channels_compat(*, channel_map_path: Path | None = None) -> str:
    """Legacy print_channel_map.py style output."""
    data = load_channel_map(channel_map_path)
    lines = ["TASCAM"]
    for channel, meta in (data.get("tascam") or {}).items():
        status = meta.get("status", "")
        status_suffix = f" ({status})" if status else ""
        source = "—" if meta.get("source") is None else meta.get("source")
        lines.append(
            f"  {channel}: {meta['name']} <- {source} [{meta['type']}]{status_suffix}"
        )
    lines.append("")
    lines.append("Alesis")
    for channel, meta in (data.get("alesis") or {}).items():
        aux = "aux" if meta.get("aux_send") else "no aux"
        status = meta.get("status", "")
        status_suffix = f" ({status})" if status else ""
        source = "—" if meta.get("source") is None else meta.get("source")
        lines.append(f"  {channel}: {source} [{aux}]{status_suffix}")
    return "\n".join(lines) + "\n"


def _jack_label(jack: dict[str, Any] | None, number: int | str) -> str:
    if not jack:
        return f"{number} —"
    conn = jack.get("connection")
    if conn in (None, ""):
        return f"{number} —"
    return f"{number} {conn}"


def format_patchbay_list(*, patchbays_path: Path | None = None) -> str:
    data = load_patchbays(patchbays_path)
    lines: list[str] = []
    for name, bay in (data.get("patchbays") or {}).items():
        model = bay.get("hardware_model", "unknown")
        jacks = bay.get("jacks") or {}
        populated = sum(
            1
            for j in jacks.values()
            if isinstance(j, dict) and j.get("connection") not in (None, "")
        )
        unknown_modes = sum(
            1
            for j in jacks.values()
            if isinstance(j, dict)
            and j.get("connection") not in (None, "")
            and str(j.get("mode", "unknown")).lower() == "unknown"
        )
        parts = [f"{name:<6}", f"model {model}", f"populated {populated}"]
        if unknown_modes:
            parts.append(f"unknown modes {unknown_modes}")
        lines.append("   ".join(parts))
    return "\n".join(lines) + "\n"


def format_patchbay(
    bay_id: str,
    *,
    unknown_only: bool = False,
    show_all_jacks: bool = False,
    patchbays_path: Path | None = None,
) -> str:
    data = load_patchbays(patchbays_path)
    key = bay_id.strip().upper()
    bays = data.get("patchbays") or {}
    if key not in bays:
        raise StoreError(f"Unknown patchbay {bay_id!r}.")
    bay = bays[key]
    jacks: dict[Any, dict] = bay.get("jacks") or {}
    lines = [key, "", f"{'UPPER':<22} {'LOWER':<28} MODE"]

    # Build pairs from upper jacks
    uppers = {
        int(n): j
        for n, j in jacks.items()
        if isinstance(j, dict) and str(j.get("row", "")).lower() == "upper"
    }
    lowers = {
        int(n): j
        for n, j in jacks.items()
        if isinstance(j, dict) and str(j.get("row", "")).lower() == "lower"
    }

    pair_nums = sorted(uppers.keys())
    if show_all_jacks and not pair_nums:
        lines.append("(no jacks documented)")
        return "\n".join(lines) + "\n"

    shown = 0
    for upper_n in pair_nums:
        upper = uppers[upper_n]
        lower_n = upper.get("paired_with")
        lower = lowers.get(int(lower_n)) if lower_n is not None else None
        mode = str(upper.get("mode") or (lower or {}).get("mode") or "unknown").upper()
        has_conn = upper.get("connection") not in (None, "") or (
            lower and lower.get("connection") not in (None, "")
        )
        if unknown_only and mode != "UNKNOWN":
            continue
        if not show_all_jacks and not has_conn and not unknown_only:
            # still show documented empties that have notes? skip empty unassigned for default
            if upper.get("status") == "unassigned" and (
                not lower or lower.get("connection") in (None, "")
            ):
                continue
        upper_label = _jack_label(upper, upper_n)
        lower_label = _jack_label(lower, lower_n if lower_n is not None else "?")
        lines.append(f"{upper_label:<22} {lower_label:<28} {mode}")
        shown += 1

    if shown == 0:
        lines.append("(no matching pairs)")
    return "\n".join(lines) + "\n"


def _add_tree_nodes(tree: Tree, node: PathTreeNode) -> None:
    branch = tree.add(node.label)
    for child in node.children:
        _add_tree_nodes(branch, child)


def list_named_paths(*, routing_path: Path | None = None) -> list[tuple[str, NamedPath]]:
    doc = load_routing(routing_path)
    return sorted(doc.named_paths.items(), key=lambda x: x[0])


def format_path_list(*, routing_path: Path | None = None) -> str:
    lines = ["NAMED PATHS", ""]
    for name, path in list_named_paths(routing_path=routing_path):
        lines.append(f"{name:<14} {path.status:<10} {path.label}")
    if len(lines) == 2:
        lines.append("(none)")
    return "\n".join(lines) + "\n"


def path_tree_for(name: str, *, routing_path: Path | None = None) -> tuple[str, Tree]:
    from music_rig import routing_state

    doc = load_routing(routing_path)
    key = name.strip().lower()
    path = doc.named_paths.get(key)
    if path is None:
        available = ", ".join(sorted(doc.named_paths)) or "(none)"
        raise StoreError(f"Unknown path {name!r}. Available: {available}")
    header = f"{key} — {path.label} [{path.status}]"
    display = routing_state.path_to_display_tree(path)
    tree = Tree(display.label)
    for child in display.children:
        _add_tree_nodes(tree, child)
    return header, tree


def patchbay_unknown_mode_stats(
    *, patchbays_path: Path | None = None
) -> list[tuple[str, int]]:
    data = load_patchbays(patchbays_path)
    stats: list[tuple[str, int]] = []
    for name, bay in (data.get("patchbays") or {}).items():
        jacks = bay.get("jacks") or {}
        count = sum(
            1
            for j in jacks.values()
            if isinstance(j, dict)
            and j.get("connection") not in (None, "")
            and str(j.get("mode", "unknown")).lower() == "unknown"
        )
        if count:
            stats.append((name, count))
    return stats
