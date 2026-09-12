"""Generate human-facing CURRENT projections from patchbay/channel YAML."""

from __future__ import annotations

from typing import Any

from music_rig import channel_state, patchbay_state


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    return text or "—"


def _mode_display(mode: str) -> str:
    return str(mode).strip().upper() if mode else "UNKNOWN"


def _conn_display(conn: Any, status: str = "") -> str:
    if conn is None or conn == "":
        st = str(status).lower()
        if st == "unassigned":
            return "UNASSIGNED"
        if st == "undocumented":
            return "UNDOCUMENTED"
        return "—"
    return str(conn)


def render_patchbays_section(data: dict[str, Any] | None = None) -> str:
    doc = data if data is not None else patchbay_state.load_raw()
    bays = doc.get("patchbays") or {}
    lines = [
        "<!-- GENERATED FROM data/patchbays.yaml BY `uv run rig render`. "
        "DO NOT EDIT THIS SECTION DIRECTLY. -->",
        "",
        "## Hardware",
        "",
        "| Named bay | Hardware model | Status |",
        "|---|---|---|",
    ]
    for name, bay in bays.items():
        model = bay.get("hardware_model", "unknown")
        model_s = "UNKNOWN" if str(model).lower() == "unknown" else str(model)
        status = str(bay.get("status", "")).replace("_", " ").upper() or "—"
        lines.append(f"| {name} | {model_s} | {_cell(status)} |")
    lines.append("")
    lines.append("## Represented jack pairs")
    lines.append("")
    lines.append(
        "Only pairs present in `data/patchbays.yaml` are listed. "
        "UNKNOWN modes are shown explicitly."
    )
    lines.append("")
    for name in bays:
        pairs = patchbay_state.list_pairs(name, doc)
        lines.append(f"### {name}")
        lines.append("")
        if not pairs:
            lines.append("_No jack pairs represented._")
            lines.append("")
            continue
        lines.append("| Upper | Upper connection | Lower | Lower connection | Mode |")
        lines.append("|---:|---|---:|---|---|")
        for pair in pairs:
            lower = pair["lower_n"] if pair["lower_n"] is not None else "—"
            lines.append(
                "| {u} | {uc} | {l} | {lc} | {mode} |".format(
                    u=pair["upper_n"],
                    uc=_cell(_conn_display(pair["upper_conn"], pair.get("status", ""))),
                    l=lower,
                    lc=_cell(_conn_display(pair["lower_conn"], pair.get("status", ""))),
                    mode=_mode_display(pair["mode"]),
                )
            )
        lines.append("")
    return "\n".join(lines)


def render_patchbays_mermaid(data: dict[str, Any] | None = None) -> str:
    """Deterministic Mermaid for represented patchbay connectivity."""
    doc = data if data is not None else patchbay_state.load_raw()
    bays = doc.get("patchbays") or {}
    lines = [
        "%% GENERATED FROM data/patchbays.yaml BY `uv run rig render`.",
        "%% DO NOT EDIT DIRECTLY.",
        "flowchart TB",
    ]
    for name, bay in bays.items():
        pairs = patchbay_state.list_pairs(name, doc)
        safe = name.replace("-", "")
        if not pairs:
            status = str(bay.get("status", "undocumented")).replace("_", " ")
            lines.append(f'  {safe}["{name}: {status}"]')
            continue
        lines.append(f"  subgraph {safe}[{name} represented connectivity]")
        lines.append("    direction TB")
        for pair in pairs:
            u = pair["upper_n"]
            lower_n = pair["lower_n"]
            uc = _conn_display(pair["upper_conn"], pair.get("status", ""))
            lc = _conn_display(pair["lower_conn"], pair.get("status", ""))
            mode = _mode_display(pair["mode"])
            uid = f"{safe}U{u}"
            lid = f"{safe}L{lower_n if lower_n is not None else 'x'}"
            lines.append(f'    {uid}["{u} {uc}"]')
            if lower_n is not None:
                lines.append(f'    {lid}["{lower_n} {lc}"]')
                edge = "no source" if pair["upper_conn"] in (None, "") else f"mode {mode.lower()}"
                lines.append(f"    {uid} -.->|{edge}| {lid}")
        lines.append("  end")
    lines.append("")
    return "\n".join(lines)


def render_tascam_section(data: dict[str, Any] | None = None) -> str:
    doc = data if data is not None else channel_state.load_raw()
    tascam = doc.get("tascam") or {}
    lines = [
        "<!-- GENERATED FROM data/channel-map.yaml BY `uv run rig render`. "
        "DO NOT EDIT THIS SECTION DIRECTLY. -->",
        "",
        "| Input | Track Name | Source | Type | Status |",
        "|---:|---|---|---|---|",
    ]
    for key in sorted(
        tascam.keys(), key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))
    ):
        meta = tascam[key]
        source = meta.get("source")
        lines.append(
            "| {ch} | {name} | {src} | {typ} | {st} |".format(
                ch=key,
                name=_cell(meta.get("name")),
                src=_cell(source) if source is not None else "—",
                typ=_cell(meta.get("type")),
                st=_cell(meta.get("status")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_alesis_section(data: dict[str, Any] | None = None) -> str:
    doc = data if data is not None else channel_state.load_raw()
    alesis = doc.get("alesis") or {}
    lines = [
        "<!-- GENERATED FROM data/channel-map.yaml BY `uv run rig render`. "
        "DO NOT EDIT THIS SECTION DIRECTLY. -->",
        "",
        "| Channel | Source | AUX SEND | Status |",
        "|---|---|---|---|",
    ]

    def sort_key(k: Any) -> tuple:
        s = str(k)
        if s.isdigit():
            return (0, int(s), "")
        return (1, s, "")

    for key in sorted(alesis.keys(), key=sort_key):
        meta = alesis[key]
        aux = meta.get("aux_send")
        aux_s = "Yes" if aux is True else ("No" if aux is False else "—")
        source = meta.get("source")
        lines.append(
            "| {ch} | {src} | {aux} | {st} |".format(
                ch=key,
                src=_cell(source) if source is not None else "UNASSIGNED",
                aux=aux_s,
                st=_cell(meta.get("status")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_tascam_mermaid(data: dict[str, Any] | None = None) -> str:
    doc = data if data is not None else channel_state.load_raw()
    tascam = doc.get("tascam") or {}
    lines = [
        "%% GENERATED FROM data/channel-map.yaml BY `uv run rig render`.",
        "%% DO NOT EDIT DIRECTLY.",
        "flowchart TB",
    ]
    for key in sorted(
        tascam.keys(), key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))
    ):
        meta = tascam[key]
        name = meta.get("name") or "UNASSIGNED"
        source = meta.get("source")
        label = f"TASCAM {key}: {name}"
        if source:
            label = f"TASCAM {key}: {source}"
        safe = f"T{key}".replace("/", "_")
        lines.append(f'  {safe}["{label}"]')
    lines.append("")
    return "\n".join(lines)


def format_current_preview(preview) -> str:
    if str(preview.domain).startswith("routing") and preview.message.strip():
        lines = [
            preview.message.rstrip(),
            "",
            "This modifies authoritative CURRENT state.",
        ]
        if preview.affected_files:
            lines.append("Affected files:")
            for f in preview.affected_files:
                lines.append(f"  {f}")
        return "\n".join(lines) + "\n"
    lines = [
        "CURRENT UPDATE",
        "",
        f"Target: {preview.target}",
        f"Domain: {preview.domain}",
        "",
        "Before:",
    ]
    for k, v in preview.before.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("After:")
    for k, v in preview.after.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("This modifies authoritative CURRENT state.")
    if preview.affected_files:
        lines.append("Affected files:")
        for f in preview.affected_files:
            lines.append(f"  {f}")
    return "\n".join(lines) + "\n"
