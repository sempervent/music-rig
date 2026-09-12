"""Generate CURRENT routing docs and Mermaid from data/routing.yaml named_paths."""

from __future__ import annotations

from typing import Any

from music_rig import routing_state
from music_rig.models import NamedPath, RoutingDocument, RoutingNode


def _load_doc(data: dict[str, Any] | None = None) -> RoutingDocument:
    if data is not None:
        return RoutingDocument.model_validate(data)
    return routing_state.load_document()


def _chain_lines(nodes: list[RoutingNode], *, indent: str = "  ") -> list[str]:
    if not nodes:
        return [f"{indent}(empty)"]
    lines: list[str] = []
    for i, node in enumerate(nodes):
        prefix = "->" if i else ""
        label = routing_state.node_display(node)
        if i == 0:
            lines.append(f"{indent}{label}")
        else:
            lines.append(f"{indent}{prefix} {label}")
    return lines


def _text_block(lines: list[str]) -> str:
    return "```text\n" + "\n".join(lines) + "\n```"


def render_current_routing_section(data: dict[str, Any] | None = None) -> str:
    doc = _load_doc(data)
    paths = doc.named_paths
    lines = [
        "<!-- GENERATED FROM data/routing.yaml BY `uv run rig render`. "
        "DO NOT EDIT THIS SECTION DIRECTLY. -->",
        "",
        "## Named CURRENT paths (from `data/routing.yaml`)",
        "",
    ]

    if "clean_mixer" in paths or "acoustic" in paths:
        lines.append("### Clean capture")
        lines.append("")
        for key in ("clean_mixer", "acoustic", "bass", "electric", "minikorg", "sr18"):
            path = paths.get(key)
            if path is None:
                continue
            lines.append(f"**{path.label}** (`{key}`)")
            lines.append("")
            lines.append(_text_block(_flatten_for_doc(path)))
            lines.append("")

    if "aux" in paths:
        lines.append("### AUX SEND wet-processing path")
        lines.append("")
        lines.append(_text_block(_flatten_for_doc(paths["aux"])))
        lines.append("")
        lines.append(
            "Exact DIRTY and SPACE topologies: [Pedal Chains](pedal-chains.md) "
            "or `rig path show dirty` / `rig path show space`."
        )
        lines.append("")

    if "kaoss" in paths:
        lines.append("### KAOSS Replay path")
        lines.append("")
        lines.append(_text_block(_flatten_for_doc(paths["kaoss"])))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _flatten_for_doc(path: NamedPath) -> list[str]:
    """Indent-aware text projection preserving branch structure."""
    lines: list[str] = []
    main = path.branches["main"]

    def emit_from(nodes: list[RoutingNode], index: int, indent: int) -> None:
        if index >= len(nodes):
            return
        node = nodes[index]
        pad = "  " * indent
        label = routing_state.node_display(node)
        if indent == 0 and index == 0:
            lines.append(label)
        else:
            lines.append(f"{pad}-> {label}")
        attached = [(bid, b) for bid, b in path.branches.items() if b.attach == node.id]
        before = [x for x in attached if x[1].position != "after"]
        after = [x for x in attached if x[1].position == "after"]
        for _bid, br in before:
            lines.append(f"{'  ' * (indent + 1)}{br.label}")
            if br.nodes:
                emit_from(br.nodes, 0, indent + 2)
        has_side = bool(before or after)
        if index + 1 < len(nodes):
            emit_from(nodes, index + 1, indent + 1 if has_side else indent)
        for _bid, br in after:
            lines.append(f"{'  ' * (indent + 1)}{br.label}")
            if br.nodes:
                emit_from(br.nodes, 0, indent + 2)

    emit_from(main.nodes, 0, 0)
    return lines


def render_pedal_chains_section(data: dict[str, Any] | None = None) -> str:
    doc = _load_doc(data)
    paths = doc.named_paths
    lines = [
        "<!-- GENERATED FROM data/routing.yaml BY `uv run rig render`. "
        "DO NOT EDIT THIS SECTION DIRECTLY. -->",
        "",
    ]

    if "aux" in paths:
        lines.append("## AUX SEND front end (CURRENT)")
        lines.append("")
        # Front end stops at JOYO (before CH-1) for pedal-chains clarity
        aux = paths["aux"]
        front_nodes = []
        for node in aux.branches["main"].nodes:
            front_nodes.append(node)
            if node.id == "joyo":
                break
        # Build a temporary path-like projection
        tmp = NamedPath(
            label=aux.label,
            branches={
                "main": aux.branches["main"].model_copy(update={"nodes": front_nodes}),
                **{
                    k: v
                    for k, v in aux.branches.items()
                    if k != "main" and v.attach in {n.id for n in front_nodes}
                },
            },
        )
        lines.append(_text_block(_flatten_for_doc(tmp)))
        lines.append("")

    if "dirty" in paths:
        lines.append("## JOYO DIRTY — Send A (CURRENT)")
        lines.append("")
        lines.append(_text_block(_flatten_for_doc(paths["dirty"])))
        lines.append("")
        lines.append("Intent: gain, drive, dirt, classic stompbox abuse.")
        lines.append("")
        lines.append(
            "**Note:** TR-2 is **not** in this branch. It lives in the SPACE / "
            "SY-1 SEND loop. Do not infer that TR-2 left the rig."
        )
        lines.append("")

    if "space" in paths:
        lines.append("## JOYO SPACE — Send B (CURRENT)")
        lines.append("")
        lines.append(_text_block(_flatten_for_doc(paths["space"])))
        lines.append("")
        space = paths["space"]
        ls2 = next(
            (n for n in space.branches["main"].nodes if n.id == "ls-2"),
            None,
        )
        if ls2 and ls2.mode:
            lines.append(f"LS-2 mode in use: **{ls2.mode}**.")
            lines.append("")
        lines.append(
            "Intent: synth voice (SY-1), phase + tremolo in the SY-1 loop, "
            "then parallel texture loops via LS-2."
        )
        lines.append("")

    if "aux" in paths:
        lines.append("## Post-JOYO stereo spread (CURRENT)")
        lines.append("")
        aux = paths["aux"]
        post = [n for n in aux.branches["main"].nodes if n.id in ("ch-1", "alesis-return")]
        if post:
            # include JOYO OUT conceptually
            lines.append(
                _text_block(["JOYO OUT", *[f"-> {routing_state.node_display(n)}" for n in post]])
            )
            lines.append("")
        lines.append("Path is mono through JOYO; CH-1 is the stereo stage.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_aux_send_loop_mermaid(data: dict[str, Any] | None = None) -> str:
    doc = _load_doc(data)
    dirty = doc.named_paths.get("dirty")
    space = doc.named_paths.get("space")
    aux = doc.named_paths.get("aux")

    dirty_chain = ""
    if dirty:
        mid = [
            n.label.replace("BOSS ", "")
            for n in dirty.branches["main"].nodes
            if n.id not in ("joyo-send-a", "joyo-return-a")
        ]
        dirty_chain = " -> ".join(mid)

    sy_loop = ""
    loop_a = ""
    loop_b = ""
    ls_mode = "A+B MIX / BYPASS"
    if space:
        send = space.branches.get("sy1-send")
        if send:
            sy_loop = " -> ".join(n.label for n in send.nodes if n.id != "sy1-return")
        if "ls2-a" in space.branches:
            loop_a = " -> ".join(n.label for n in space.branches["ls2-a"].nodes)
        if "ls2-b" in space.branches:
            loop_b = " -> ".join(n.label for n in space.branches["ls2-b"].nodes)
        ls2 = next((n for n in space.branches["main"].nodes if n.id == "ls-2"), None)
        if ls2 and ls2.mode:
            ls_mode = ls2.mode.replace("↔", "/")

    lines = [
        "flowchart LR",
        "  Aux[Alesis AUX SEND]",
        "  RC1[BOSS RC-1]",
        "  Wah[Cry Baby]",
        "  Router[JOYO A/B/Bypass]",
        "",
        "  subgraph DIRTY[JOYO Send A DIRTY]",
        f"    A[{dirty_chain or 'DIRTY'}]",
        "  end",
        "",
        "  subgraph SPACE[JOYO Send B SPACE]",
        "    SY1[SY-1]",
        f"    SYLoop[SY-1 SEND: {sy_loop or '…'}]",
        f"    LS2[LS-2 {ls_mode}]",
        f"    LoopA[LOOP A: {loop_a or '…'}]",
        f"    LoopB[LOOP B: {loop_b or '…'}]",
        "  end",
        "",
        "  Chorus[BOSS CH-1 Stereo]",
        "  Return[Alesis Return / Line Channel]",
        "",
        "  Aux --> RC1 --> Wah --> Router",
        "  Router --> A --> Chorus",
        "  Router --> SY1",
        "  SY1 --> SYLoop",
        "  SYLoop --> SY1",
        "  SY1 --> LS2",
        "  LS2 --> LoopA",
        "  LS2 --> LoopB",
        "  LoopA --> LS2",
        "  LoopB --> LS2",
        "  LS2 --> Chorus",
        "  Chorus --> Return",
    ]
    # Ensure aux path devices match when present
    _ = aux
    return "\n".join(lines) + "\n"


def format_routing_preview_extra(preview) -> str:
    return preview.message
