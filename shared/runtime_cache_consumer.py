"""Durable HTTP-cache generation effect, not a listener or website integration."""

import os
from dataclasses import dataclass

from shared.runtime_events import event_stream_enabled

CONSUMER = "http-cache-generation-v1"
CACHE_NAME = "http_api"
SUPPORTED_EVENTS = (
    "round_stats_imported", "round_timing_reconciled", "round_status_changed",
    "round_endstats_changed", "round_lua_corrected",
)


@dataclass(frozen=True)
class CacheConsumption:
    status: str
    processed: int
    generation: int | None
    unsupported_pending: int | None


async def consume_http_cache_events(conn, *, batch_size=100):
    """Commit one bounded batch, including receipts and generation together.

    Native PostgreSQL connection, no caller-held transaction. Consumers serialize
    on the generation row; journal IDs are NOT commit-order cursors. Unsupported
    event/schema pairs remain unacknowledged and are explicitly counted, rather
    than starving supported events. This does not invalidate any process cache.
    Batch size bounds processed rows, not scan work. The unsupported count is
    sampled by its statement; concurrent producers may add more before return.
    """
    if not event_stream_enabled() or os.getenv("RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "false").strip().lower() != "true":
        return CacheConsumption("disabled", 0, None, None)
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 1000:
        raise ValueError("Cache consumer batch size must be an integer from 1 to 1000")
    if conn.is_in_transaction():
        raise RuntimeError("Cache consumer requires its own transaction")
    async with conn.transaction():
        await conn.execute("""
            INSERT INTO runtime_cache_generations (cache_name) VALUES ($1)
            ON CONFLICT (cache_name) DO NOTHING
        """, CACHE_NAME)
        generation = await conn.fetchval("""
            SELECT generation FROM runtime_cache_generations WHERE cache_name=$1 FOR UPDATE
        """, CACHE_NAME)
        unsupported = await conn.fetchval("""
            SELECT count(*) FROM runtime_events e
            WHERE (e.schema_version<>1 OR NOT (e.event_type=ANY($2::text[])))
              AND NOT EXISTS (SELECT 1 FROM runtime_consumer_receipts r
                              WHERE r.consumer_name=$1 AND r.event_id=e.id)
        """, CONSUMER, list(SUPPORTED_EVENTS))
        rows = await conn.fetch("""
            SELECT e.id FROM runtime_events e
            WHERE e.schema_version=1 AND e.event_type=ANY($2::text[])
              AND NOT EXISTS (SELECT 1 FROM runtime_consumer_receipts r
                              WHERE r.consumer_name=$1 AND r.event_id=e.id)
            ORDER BY e.id LIMIT $3
        """, CONSUMER, list(SUPPORTED_EVENTS), batch_size)
        event_ids = [row["id"] for row in rows]
        if event_ids:
            generation = await conn.fetchval("""
                UPDATE runtime_cache_generations
                SET generation=generation+1, updated_at=clock_timestamp()
                WHERE cache_name=$1 RETURNING generation
            """, CACHE_NAME)
            await conn.execute("""
                INSERT INTO runtime_consumer_receipts (consumer_name, event_id)
                SELECT $1, batch.id FROM unnest($2::bigint[]) AS batch(id)
            """, CONSUMER, event_ids)
        status = "advanced" if event_ids else ("unsupported" if unsupported else "idle")
    return CacheConsumption(status, len(event_ids), generation, unsupported)
