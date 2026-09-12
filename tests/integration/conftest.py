"""Auto-apply the ``integration`` marker to every test under ``tests/integration/``."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    marker = pytest.mark.integration
    for item in items:
        path = Path(str(item.fspath))
        if "integration" in path.parts:
            item.add_marker(marker)
