"""Explicit save outcomes — never silently return to view after apply attempts."""

from __future__ import annotations

from enum import Enum


class SaveOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    CONCURRENT_MODIFICATION = "CONCURRENT_MODIFICATION"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    @property
    def ok(self) -> bool:
        return self is SaveOutcome.SUCCESS
