"""TUI / service error formatting. Stack traces only when RIG_DEBUG or --debug."""

from __future__ import annotations

import os
import traceback
from typing import Any


_DEBUG = False


def set_debug(enabled: bool) -> None:
    global _DEBUG
    _DEBUG = bool(enabled)
    if enabled:
        os.environ["RIG_DEBUG"] = "1"
    elif os.environ.get("RIG_DEBUG") == "1" and not enabled:
        # Leave env alone if user set it externally and CLI did not force off
        pass


def is_debug() -> bool:
    if _DEBUG:
        return True
    return os.environ.get("RIG_DEBUG", "").strip() in {"1", "true", "TRUE", "yes", "YES"}


def format_error(exc: BaseException, *, prefix: str = "") -> str:
    """User-facing error string; include traceback only in debug mode."""
    msg = str(exc).strip() or exc.__class__.__name__
    if prefix:
        msg = f"{prefix}{msg}"
    if is_debug():
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return f"{msg}\n{tb}".rstrip()
    return msg


def debug_log(message: str, **fields: Any) -> None:
    if not is_debug():
        return
    extra = " ".join(f"{k}={v!r}" for k, v in fields.items())
    line = f"[RIG_DEBUG] {message}"
    if extra:
        line = f"{line} {extra}"
    print(line, flush=True)
