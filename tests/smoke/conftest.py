"""Auto-apply the ``smoke`` marker to every test under ``tests/smoke/``."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    marker = pytest.mark.smoke
    for item in items:
        path = Path(str(item.fspath))
        if "smoke" in path.parts:
            item.add_marker(marker)
