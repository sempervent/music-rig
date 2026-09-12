"""Agent transaction / provider error codes."""

from __future__ import annotations


class AgentError(Exception):
    """Base agent subsystem error with a stable code."""

    code: str = "AGENT_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class PlanConflictError(AgentError):
    code = "PLAN_CONFLICT"

    def __init__(
        self,
        message: str,
        *,
        operation_ids: tuple[str, str],
        conflict_key: str,
    ) -> None:
        super().__init__(message, code=self.code)
        self.operation_ids = operation_ids
        self.conflict_key = conflict_key


class ConcurrentModificationError(AgentError):
    code = "CONCURRENT_MODIFICATION"


class ProviderTimeoutError(AgentError):
    code = "PROVIDER_TIMEOUT"


class ProviderInvalidResponseError(AgentError):
    code = "PROVIDER_INVALID_RESPONSE"


class ProviderNotConfiguredError(AgentError):
    code = "PROVIDER_NOT_CONFIGURED"
