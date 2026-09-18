"""Read the committed HTTP cache generation; no schema creation or DB writes."""

import asyncio
import os

from shared.runtime_events import event_stream_enabled
from website.backend.dependencies import get_db_pool

GENERATION_READ_TIMEOUT_SECONDS = 1.0


def runtime_http_cache_enabled() -> bool:
    return event_stream_enabled() and all(
        os.getenv(flag, "false").strip().lower() == "true"
        for flag in ("RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "RUNTIME_HTTP_CACHE_NAMESPACE_ENABLED")
    )


async def read_http_cache_generation() -> int:
    """Use the current shared adapter (not an import-time pool snapshot).

    Missing migration/row/pool, permission failures and timeout propagate so the
    caller bypasses caching. This observes the consumer effect, not journal lag.
    """
    adapter = get_db_pool()
    if adapter is None:
        raise RuntimeError("Runtime cache generation database unavailable")
    generation = await asyncio.wait_for(
        adapter.fetch_val(
            "SELECT generation FROM runtime_cache_generations WHERE cache_name = ?",
            ("http_api",),
        ),
        timeout=GENERATION_READ_TIMEOUT_SECONDS,
    )
    if type(generation) is not int or generation < 0:
        raise ValueError("Runtime cache generation missing or invalid")
    return generation
