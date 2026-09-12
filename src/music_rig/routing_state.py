"""Typed CURRENT mutations for data/routing.yaml named_paths."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from music_rig.models import (
    CurrentPreview,
    MidiEvidenceStatus,
    NamedPath,
    PathTreeNode,
    RoutingBranch,
    RoutingDocument,
    RoutingNode,
)
from music_rig.store import ROUTING_PATH, StoreError, _dump_yaml, parse_existing_yaml

ROUTING_HEADER = (
    "# High-level CURRENT routes. Pedal detail: docs/pedal-chains.md. "
    "Patchbays: data/patchbays.yaml.\n"
    "# named_paths: structured CLI CURRENT topology "
    "(canonical for path mutations / projections).\n"
    "# Do not infer CURRENT updates from freeform changes or inbox notes.\n"
)

_NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$", re.IGNORECASE)


def _extract_leading_comment_header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = 0
    saw_comment = False
    while idx < len(lines):
        stripped = lines[idx].lstrip()
        if stripped.startswith("#"):
            saw_comment = True
            idx += 1
            continue
        if stripped == "" and (saw_comment or idx == 0):
            idx += 1
            continue
        break
    if not saw_comment:
        return ""
    return "".join(lines[:idx])


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or ROUTING_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_document(path: Path | None = None) -> RoutingDocument:
    return RoutingDocument.model_validate(load_raw(path))


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = ROUTING_HEADER
    if existing_text is not None:
        extracted = _extract_leading_comment_header(existing_text)
        if extracted:
            header = extracted
            if not header.endswith("\n"):
                header += "\n"
    body = _dump_yaml(data)
    return header + body if header else body


def node_display(node: RoutingNode) -> str:
    label = node.label
    if node.mode:
        label = f"{label} [{node.mode}]"
    return label


def chain_text(nodes: list[RoutingNode]) -> str:
    if not nodes:
        return "(empty)"
    return " -> ".join(node_display(n) for n in nodes)


def semantic_fingerprint(doc: RoutingDocument | dict[str, Any]) -> dict[str, Any]:
    """Topology fingerprint for migration / regression checks (ids + order + attach)."""
    if isinstance(doc, dict):
        doc = RoutingDocument.model_validate(doc)
    out: dict[str, Any] = {}
    for path_id, path in sorted(doc.named_paths.items()):
        branches: dict[str, Any] = {}
        for bid, branch in sorted(path.branches.items()):
            branches[bid] = {
                "label": branch.label,
                "attach": branch.attach,
                "position": branch.position,
                "nodes": [
                    {
                        "id": n.id,
                        "label": n.label,
                        "mode": n.mode,
                        "note": n.note,
                        "signal": n.signal,
                    }
                    for n in branch.nodes
                ],
            }
        out[path_id] = {
            "label": path.label,
            "status": path.status,
            "route_ref": path.route_ref,
            "branches": branches,
        }
    return out


def validate_routing_doc(
    data: dict[str, Any], *, inventory_path: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["routing document must be a mapping"]
    named = data.get("named_paths")
    if named is None:
        return errors
    if not isinstance(named, dict):
        errors.append("named_paths must be a mapping")
        return errors
    if len(named) != len({str(k).lower() for k in named}):
        errors.append("named path IDs must be unique (case-insensitive)")

    for path_id, raw_path in named.items():
        pid = str(path_id)
        if not pid.strip():
            errors.append("named path ID must not be empty")
            continue
        try:
            path = NamedPath.model_validate(raw_path)
        except Exception as exc:  # noqa: BLE001 — collect validation messages
            errors.append(f"path {pid}: {exc}")
            continue
        branch_ids = list(path.branches.keys())
        if len(branch_ids) != len({b.lower() for b in branch_ids}):
            errors.append(f"path {pid}: duplicate branch IDs")
        node_ids: list[str] = []
        for bid, branch in path.branches.items():
            if not bid.strip():
                errors.append(f"path {pid}: empty branch id")
            if branch.position not in ("before", "after"):
                errors.append(
                    f"path {pid} branch {bid}: position must be 'before' or 'after'"
                )
            if bid != "main" and not branch.attach:
                errors.append(f"path {pid} branch {bid}: non-main branch requires attach")
            if bid == "main" and branch.attach:
                errors.append(f"path {pid}: main branch must not set attach")
            for node in branch.nodes:
                if not _NODE_ID_RE.match(node.id):
                    errors.append(
                        f"path {pid}: invalid node id {node.id!r} "
                        "(use letters, digits, ._-)"
                    )
                node_ids.append(node.id.lower())
        if len(node_ids) != len(set(node_ids)):
            errors.append(f"path {pid}: duplicate node IDs within path")
        # attach targets must exist on some branch in this path
        known = {n.id for b in path.branches.values() for n in b.nodes}
        for bid, branch in path.branches.items():
            if branch.attach and branch.attach not in known:
                errors.append(
                    f"path {pid} branch {bid}: attach {branch.attach!r} "
                    "does not match a node id in this path"
                )
        # cycle detection via attach graph (branch attach -> parent node -> branch)
        if _has_attach_cycle(path):
            errors.append(f"path {pid}: cyclic branch attach structure")
    try:
        from music_rig.store import load_inventory

        inventory = load_inventory(inventory_path)
    except StoreError:
        inventory = None
    if inventory is not None:
        for path_id, raw_path in named.items():
            try:
                path = NamedPath.model_validate(raw_path)
            except Exception:
                continue
            for branch_id, branch in path.branches.items():
                for node in branch.nodes:
                    if node.gear_ref and inventory.resolve(node.gear_ref) is None:
                        errors.append(
                            f"path {path_id} branch {branch_id}: gear_ref "
                            f"{node.gear_ref!r} does not resolve in inventory"
                        )
    return errors


def _has_attach_cycle(path: NamedPath) -> bool:
    """Detect cycles if a branch somehow attaches into its own descendant subtree."""
    node_to_branch: dict[str, str] = {}
    for bid, branch in path.branches.items():
        for node in branch.nodes:
            node_to_branch[node.id] = bid

    def walk(bid: str, stack: set[str]) -> bool:
        if bid in stack:
            return True
        stack = stack | {bid}
        branch = path.branches[bid]
        for node in branch.nodes:
            for child_id, child in path.branches.items():
                if child.attach == node.id and walk(child_id, stack):
                    return True
        return False

    return any(walk(bid, set()) for bid in path.branches)


def path_to_display_tree(path: NamedPath) -> PathTreeNode:
    """Build a Rich/Markdown display tree from branch sequences."""

    def node_label(node: RoutingNode) -> str:
        text = node_display(node)
        if node.note:
            text = f"{text} — {node.note}"
        return text

    def attached(parent_id: str) -> list[tuple[str, RoutingBranch]]:
        items = [
            (bid, b)
            for bid, b in path.branches.items()
            if bid != "main" and b.attach == parent_id
        ]
        # stable: before-position first (YAML order preserved via dict order)
        before = [(i, b) for i, b in items if b.position != "after"]
        after = [(i, b) for i, b in items if b.position == "after"]
        return before + after

    def branch_chain_as_tree(branch: RoutingBranch) -> PathTreeNode:
        if not branch.nodes:
            return PathTreeNode(label=branch.label, children=[])
        return _seq_to_tree(branch.nodes)

    def _seq_to_tree(nodes: list[RoutingNode]) -> PathTreeNode:
        if not nodes:
            return PathTreeNode(label="(empty)", children=[])

        def build(index: int) -> PathTreeNode:
            node = nodes[index]
            children: list[PathTreeNode] = []
            before = [(i, b) for i, b in attached(node.id) if b.position != "after"]
            after = [(i, b) for i, b in attached(node.id) if b.position == "after"]
            for _bid, br in before:
                if not br.nodes:
                    children.append(PathTreeNode(label=br.label, children=[]))
                else:
                    children.append(
                        PathTreeNode(
                            label=br.label,
                            children=[branch_chain_as_tree(br)],
                        )
                    )
            if index + 1 < len(nodes):
                children.append(build(index + 1))
            for _bid, br in after:
                if not br.nodes:
                    children.append(PathTreeNode(label=br.label, children=[]))
                else:
                    children.append(
                        PathTreeNode(
                            label=br.label,
                            children=[branch_chain_as_tree(br)],
                        )
                    )
            return PathTreeNode(label=node_label(node), children=children)

        return build(0)

    main = path.branches["main"]
    return _seq_to_tree(main.nodes)


def format_branch_list(path_id: str, path: NamedPath) -> str:
    lines = [path_id, ""]
    for bid, branch in path.branches.items():
        attach = f" (attach:{branch.attach})" if branch.attach else ""
        lines.append(f"{bid:<14} {branch.label}{attach}")
    return "\n".join(lines) + "\n"


def get_named_path(data: dict[str, Any], path_id: str) -> tuple[str, NamedPath]:
    named = data.get("named_paths")
    if not isinstance(named, dict):
        raise StoreError("routing.yaml missing named_paths")
    key = path_id.strip().lower()
    raw = named.get(key)
    if raw is None:
        available = ", ".join(sorted(str(k) for k in named)) or "(none)"
        raise StoreError(f"Unknown path {path_id!r}. Available: {available}")
    return key, NamedPath.model_validate(raw)


def resolve_branch(path: NamedPath, branch_id: str | None) -> tuple[str, RoutingBranch]:
    bid = (branch_id or "main").strip().lower()
    branch = path.branches.get(bid)
    if branch is None:
        available = ", ".join(sorted(path.branches)) or "(none)"
        raise StoreError(f"Unknown branch {branch_id!r}. Available: {available}")
    return bid, branch


def resolve_node(branch: RoutingBranch, token: str) -> tuple[int, RoutingNode]:
    token_l = token.strip().lower()
    matches: list[tuple[int, RoutingNode]] = []
    for i, node in enumerate(branch.nodes):
        if node.id.lower() == token_l or node.label.lower() == token_l:
            matches.append((i, node))
        elif token_l and token_l in node.id.lower():
            matches.append((i, node))
        elif token_l and token_l in node.label.lower():
            matches.append((i, node))
    # Prefer exact id, then exact label, then unique substring
    exact_id = [(i, n) for i, n in matches if n.id.lower() == token_l]
    if len(exact_id) == 1:
        return exact_id[0]
    exact_label = [(i, n) for i, n in matches if n.label.lower() == token_l]
    if len(exact_label) == 1:
        return exact_label[0]
    # unique by id among substring matches
    uniq: dict[str, tuple[int, RoutingNode]] = {}
    for i, n in matches:
        uniq[n.id.lower()] = (i, n)
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    if not matches:
        raise StoreError(f"Node {token!r} not found in branch.")
    raise StoreError(
        f"Ambiguous node {token!r}. Matches: "
        + ", ".join(sorted({n.id for _, n in matches}))
    )


def _placement_index(
    nodes: list[RoutingNode],
    *,
    before: str | None,
    after: str | None,
    first: bool,
    last: bool,
    moving_id: str | None = None,
) -> int:
    flags = sum(bool(x) for x in (before, after, first, last))
    if flags != 1:
        raise StoreError("Specify exactly one of --before, --after, --first, --last.")
    work = list(nodes)
    if moving_id:
        work = [n for n in work if n.id.lower() != moving_id.lower()]
    if first:
        return 0
    if last:
        return len(work)
    if before:
        idx, _ = resolve_node(RoutingBranch(label="tmp", nodes=work), before)
        return idx
    assert after is not None
    idx, _ = resolve_node(RoutingBranch(label="tmp", nodes=work), after)
    return idx + 1


def _set_path(data: dict[str, Any], path_id: str, path: NamedPath) -> None:
    named = data.setdefault("named_paths", {})
    payload = path.model_dump(mode="json", exclude_none=True)
    named[path_id] = payload


def _preview(
    *,
    domain: str,
    target: str,
    before_path: NamedPath,
    after_path: NamedPath,
    path_id: str,
    branch_id: str,
    message: str,
) -> CurrentPreview:
    before_chain = chain_text(before_path.branches[branch_id].nodes)
    after_chain = chain_text(after_path.branches[branch_id].nodes)
    before_fp = semantic_fingerprint(
        RoutingDocument(routes={}, named_paths={path_id: before_path})
    )
    after_fp = semantic_fingerprint(
        RoutingDocument(routes={}, named_paths={path_id: after_path})
    )
    changed = before_fp != after_fp
    msg = message
    if branch_id != "main" and "No other" not in message:
        msg = f"{message}\n\nNo other {path_id} branches change."
    return CurrentPreview(
        domain=domain,
        target=target,
        before={"path": path_id, "branch": branch_id, "chain": before_chain},
        after={"path": path_id, "branch": branch_id, "chain": after_chain},
        changed=changed,
        affected_files=["data/routing.yaml"],
        message=msg,
    )


def propose_move(
    path_id: str,
    node_token: str,
    *,
    branch: str | None = None,
    before: str | None = None,
    after: str | None = None,
    first: bool = False,
    last: bool = False,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(routing_path))
    errors = validate_routing_doc(raw)
    if errors:
        raise StoreError("Routing validation failed: " + "; ".join(errors))
    pid, named = get_named_path(raw, path_id)
    bid, _branch = resolve_branch(named, branch)
    _idx, moving = resolve_node(named.branches[bid], node_token)
    insert_at = _placement_index(
        named.branches[bid].nodes,
        before=before,
        after=after,
        first=first,
        last=last,
        moving_id=moving.id,
    )
    new_nodes = [n for n in named.branches[bid].nodes if n.id != moving.id]
    new_nodes.insert(insert_at, moving)
    new_branches = dict(named.branches)
    new_branches[bid] = RoutingBranch(
        label=named.branches[bid].label,
        nodes=new_nodes,
        attach=named.branches[bid].attach,
        position=named.branches[bid].position,
    )
    after_path = NamedPath(
        label=named.label,
        status=named.status,
        route_ref=named.route_ref,
        notes=named.notes,
        branches=new_branches,
    )
    _set_path(raw, pid, after_path)
    preview = _preview(
        domain="routing.order",
        target=f"{pid}/{bid}/{moving.id}",
        before_path=named,
        after_path=after_path,
        path_id=pid,
        branch_id=bid,
        message=(
            f"CURRENT ROUTING UPDATE\n\nPath: {pid}\nBranch: {bid}\n"
            f"Node: {moving.id} ({moving.label})\n\n"
            f"Before:\n{chain_text(named.branches[bid].nodes)}\n\n"
            f"After:\n{chain_text(after_path.branches[bid].nodes)}"
        ),
    )
    return preview, raw


def propose_insert(
    path_id: str,
    node_id: str,
    *,
    label: str | None = None,
    branch: str | None = None,
    before: str | None = None,
    after: str | None = None,
    first: bool = False,
    last: bool = False,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(routing_path))
    pid, named = get_named_path(raw, path_id)
    bid, br = resolve_branch(named, branch)
    nid = node_id.strip()
    if not _NODE_ID_RE.match(nid):
        raise StoreError(f"Invalid node id {nid!r}")
    existing_ids = {n.id.lower() for b in named.branches.values() for n in b.nodes}
    if nid.lower() in existing_ids:
        raise StoreError(f"Node id {nid!r} already exists on path {pid}.")
    new_node = RoutingNode(id=nid, label=(label or nid).strip())
    insert_at = _placement_index(
        br.nodes, before=before, after=after, first=first, last=last
    )
    new_nodes = list(br.nodes)
    new_nodes.insert(insert_at, new_node)
    new_branches = dict(named.branches)
    new_branches[bid] = RoutingBranch(
        label=br.label,
        nodes=new_nodes,
        attach=br.attach,
        position=br.position,
    )
    after_path = NamedPath(
        label=named.label,
        status=named.status,
        route_ref=named.route_ref,
        notes=named.notes,
        branches=new_branches,
    )
    _set_path(raw, pid, after_path)
    preview = _preview(
        domain="routing.insert",
        target=f"{pid}/{bid}/{nid}",
        before_path=named,
        after_path=after_path,
        path_id=pid,
        branch_id=bid,
        message=(
            f"CURRENT ROUTING UPDATE\n\nPath: {pid}\nBranch: {bid}\n"
            f"Insert: {nid} ({new_node.label})\n\n"
            f"This updates CURRENT routing only — inventory is unchanged.\n\n"
            f"Before:\n{chain_text(named.branches[bid].nodes)}\n\n"
            f"After:\n{chain_text(after_path.branches[bid].nodes)}"
        ),
    )
    return preview, raw


def propose_remove(
    path_id: str,
    node_token: str,
    *,
    branch: str | None = None,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(routing_path))
    pid, named = get_named_path(raw, path_id)
    bid, br = resolve_branch(named, branch)
    _idx, node = resolve_node(br, node_token)
    # refuse removing a node that other branches attach to
    dependents = [
        child_id
        for child_id, child in named.branches.items()
        if child.attach == node.id
    ]
    if dependents:
        raise StoreError(
            f"Cannot remove {node.id}: branches still attach to it "
            f"({', '.join(dependents)}). Re-attach or clear those branches first "
            "(branch create/delete is out of Stage 6 scope)."
        )
    new_nodes = [n for n in br.nodes if n.id != node.id]
    new_branches = dict(named.branches)
    new_branches[bid] = RoutingBranch(
        label=br.label,
        nodes=new_nodes,
        attach=br.attach,
        position=br.position,
    )
    after_path = NamedPath(
        label=named.label,
        status=named.status,
        route_ref=named.route_ref,
        notes=named.notes,
        branches=new_branches,
    )
    _set_path(raw, pid, after_path)
    preview = _preview(
        domain="routing.remove",
        target=f"{pid}/{bid}/{node.id}",
        before_path=named,
        after_path=after_path,
        path_id=pid,
        branch_id=bid,
        message=(
            f"CURRENT ROUTING UPDATE\n\nPath: {pid}\nBranch: {bid}\n"
            f"Remove: {node.id} ({node.label})\n\n"
            f"This removes the device from this CURRENT path only.\n"
            f"Inventory ownership is unchanged.\n\n"
            f"Before:\n{chain_text(named.branches[bid].nodes)}\n\n"
            f"After:\n{chain_text(after_path.branches[bid].nodes)}"
        ),
    )
    return preview, raw


def propose_set_mode(
    path_id: str,
    node_token: str,
    mode: str,
    *,
    branch: str | None = None,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(routing_path))
    pid, named = get_named_path(raw, path_id)
    bid, br = resolve_branch(named, branch)
    idx, node = resolve_node(br, node_token)
    new_mode = mode.strip()
    if not new_mode:
        raise StoreError("Mode must be a non-empty string.")
    updated = RoutingNode(
        id=node.id,
        label=node.label,
        mode=new_mode,
        note=node.note,
        signal=node.signal,
        gear_ref=node.gear_ref,
        kind=node.kind,
    )
    new_nodes = list(br.nodes)
    new_nodes[idx] = updated
    new_branches = dict(named.branches)
    new_branches[bid] = RoutingBranch(
        label=br.label,
        nodes=new_nodes,
        attach=br.attach,
        position=br.position,
    )
    after_path = NamedPath(
        label=named.label,
        status=named.status,
        route_ref=named.route_ref,
        notes=named.notes,
        branches=new_branches,
    )
    _set_path(raw, pid, after_path)
    preview = CurrentPreview(
        domain="routing.mode",
        target=f"{pid}/{bid}/{node.id}",
        before={"mode": node.mode},
        after={"mode": new_mode},
        changed=(node.mode or "") != new_mode,
        affected_files=["data/routing.yaml"],
        message=(
            f"CURRENT ROUTING UPDATE\n\nPath: {pid}\nBranch: {bid}\n"
            f"Node: {node.id}\n\nMode before: {node.mode or '(none)'}\n"
            f"Mode after:  {new_mode}"
        ),
    )
    return preview, raw


def propose_batch(
    path_id: str,
    mutations: list[dict[str, Any]],
    *,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    """Apply a list of {op, ...} mutations in memory for verify wizard."""
    raw = copy.deepcopy(data if data is not None else load_raw(routing_path))
    pid, before_named = get_named_path(raw, path_id)
    preview_last: CurrentPreview | None = None
    for mut in mutations:
        op = mut["op"]
        if op == "move":
            preview_last, raw = propose_move(
                pid,
                mut["node"],
                branch=mut.get("branch"),
                before=mut.get("before"),
                after=mut.get("after"),
                first=bool(mut.get("first")),
                last=bool(mut.get("last")),
                data=raw,
            )
        elif op == "insert":
            preview_last, raw = propose_insert(
                pid,
                mut["node"],
                label=mut.get("label"),
                branch=mut.get("branch"),
                before=mut.get("before"),
                after=mut.get("after"),
                first=bool(mut.get("first")),
                last=bool(mut.get("last")),
                data=raw,
            )
        elif op == "remove":
            preview_last, raw = propose_remove(
                pid,
                mut["node"],
                branch=mut.get("branch"),
                data=raw,
            )
        else:
            raise StoreError(f"Unknown batch op {op!r}")
    _pid, after_named = get_named_path(raw, pid)
    lines = ["CURRENT ROUTING VERIFY BATCH", "", f"Path: {pid}", ""]
    for bid in before_named.branches:
        lines.append(f"[{bid}]")
        lines.append(f"  Before: {chain_text(before_named.branches[bid].nodes)}")
        lines.append(f"  After:  {chain_text(after_named.branches[bid].nodes)}")
        lines.append("")
    before_fp = semantic_fingerprint(
        RoutingDocument(routes={}, named_paths={pid: before_named})
    )
    after_fp = semantic_fingerprint(
        RoutingDocument(routes={}, named_paths={pid: after_named})
    )
    changed = before_fp != after_fp
    preview = CurrentPreview(
        domain="routing.verify",
        target=pid,
        before={"fingerprint": before_fp},
        after={"fingerprint": after_fp},
        changed=changed,
        affected_files=["data/routing.yaml"],
        message="\n".join(lines).rstrip(),
    )
    if preview_last is None and not mutations:
        preview = CurrentPreview(
            domain="routing.verify",
            target=pid,
            before={"path": pid},
            after={"path": pid},
            changed=False,
            affected_files=[],
            message=f"Path {pid}: no routing changes proposed.",
        )
    return preview, raw


def propose_set_path_evidence(
    path_id: str,
    evidence: MidiEvidenceStatus | str,
    *,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    """Set NamedPath.evidence only — does not invent topology."""
    status = (
        evidence
        if isinstance(evidence, MidiEvidenceStatus)
        else MidiEvidenceStatus(str(evidence).strip().upper())
    )
    raw = copy.deepcopy(data if data is not None else load_raw(routing_path))
    pid, named = get_named_path(raw, path_id)
    before = {
        "path": pid,
        "status": named.status,
        "evidence": named.evidence.value if named.evidence else None,
    }
    updated = NamedPath(
        label=named.label,
        status=named.status,
        route_ref=named.route_ref,
        notes=named.notes,
        evidence=status,
        branches=named.branches,
    )
    _set_path(raw, pid, updated)
    after = {
        "path": pid,
        "status": updated.status,
        "evidence": status.value,
    }
    preview = CurrentPreview(
        domain="routing.path_evidence",
        target=pid,
        before=before,
        after=after,
        changed=before != after,
        affected_files=["data/routing.yaml", "docs/current-routing.md"],
        message=f"Path {pid} evidence → {status.value}",
    )
    return preview, raw
