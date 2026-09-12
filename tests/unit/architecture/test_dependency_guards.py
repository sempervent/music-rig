"""Architecture dependency guards — keep domain layers free of UI/CLI imports."""

from __future__ import annotations

import ast
from pathlib import Path

from music_rig.store import ROOT

SRC = ROOT / "src" / "music_rig"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
            # also full module for music_rig.* checks
            mods.add(node.module)
    return mods


def _py_files(package: Path) -> list[Path]:
    return sorted(p for p in package.rglob("*.py") if p.name != "__pycache__")


def test_reconciliation_core_must_not_import_cli_or_tui():
    """reconciliation package (excluding nothing) must not pull CLI or TUI."""
    recon = SRC / "reconciliation"
    forbidden_prefixes = ("music_rig.cli", "music_rig.tui")
    forbidden_roots = {"cli", "tui"}
    offenders: list[str] = []
    for path in _py_files(recon):
        mods = _imported_modules(path)
        for mod in mods:
            if mod in forbidden_roots or mod.startswith(forbidden_prefixes):
                offenders.append(f"{path.relative_to(ROOT)} imports {mod}")
            if mod == "music_rig":
                # bare music_rig import is ok; check from music_rig import cli
                pass
        src = path.read_text(encoding="utf-8")
        if re_search_cli_tui(src):
            offenders.append(f"{path.relative_to(ROOT)} references music_rig.cli/tui")
    assert not offenders, "\n".join(offenders)


def re_search_cli_tui(src: str) -> bool:
    import re

    return bool(
        re.search(
            r"from music_rig\.(cli|tui)\b|import music_rig\.(cli|tui)\b",
            src,
        )
    )


def test_operations_must_not_import_rich_or_textual():
    """operation_registry / operations / preparers stay presentation-free."""
    targets = [
        SRC / "reconciliation" / "operations.py",
        SRC / "reconciliation" / "operation_registry.py",
        SRC / "reconciliation" / "preparers.py",
        SRC / "reconciliation" / "operation_renderer.py",
    ]
    # operation_renderer may format strings without rich — still ban rich/textual
    forbidden = {"rich", "textual"}
    offenders: list[str] = []
    for path in targets:
        if not path.exists():
            continue
        mods = _imported_modules(path)
        hit = mods & forbidden
        if hit:
            offenders.append(f"{path.name}: {sorted(hit)}")
        src = path.read_text(encoding="utf-8")
        if "from rich" in src or "import rich" in src or "import textual" in src:
            offenders.append(f"{path.name}: rich/textual string import")
    assert not offenders, "\n".join(offenders)
