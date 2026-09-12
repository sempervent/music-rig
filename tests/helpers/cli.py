"""CliRunner wrappers for human and bot CLI invocations."""

from __future__ import annotations

from typing import Any

from typer.testing import CliRunner

from music_rig.cli import app

_runner = CliRunner()


def invoke_rig_human(*args: str, **kwargs: Any):
    """Invoke ``rig`` as a human (no ``--am-bot``)."""
    return _runner.invoke(app, list(args), **kwargs)


def invoke_rig_bot(*args: str, **kwargs: Any):
    """Invoke ``rig`` as a bot (prepends ``--am-bot``)."""
    return _runner.invoke(app, ["--am-bot", *args], **kwargs)
