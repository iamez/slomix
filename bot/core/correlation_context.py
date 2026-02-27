"""Async correlation ID context for end-to-end tracing."""

import contextvars
import uuid

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str:
    """Get or create a correlation ID for the current async context."""
    cid = _correlation_id.get()
    if cid is None:
        cid = uuid.uuid4().hex[:8]
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current async context."""
    _correlation_id.set(cid)
