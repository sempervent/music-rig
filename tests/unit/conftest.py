"""Auto-apply the ``unit`` marker to every test under ``tests/unit/``."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    marker = pytest.mark.unit
    for item in items:
        path = Path(str(item.fspath))
        if "unit" in path.parts:
            item.add_marker(marker)
