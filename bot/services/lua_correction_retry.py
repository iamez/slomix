"""Explicit DB-only bounded repair steps; no task loop or live activation."""

import os
import re

import asyncpg

from bot.services.lua_correction_service import apply_retained_lua_correction, lua_correction_events_enabled


def _configured_source():
    if not lua_correction_events_enabled() or os.getenv("LUA_CORRECTION_REPAIR_ENABLED", "false").strip().lower() != "true":
        return None
    source = os.getenv("LUA_CORRECTION_SOURCE_KEY", "")
    if not re.fullmatch(r"[a-z0-9_.:-]{1,64}", source):
        raise ValueError("Invalid correction repair source identity")
    return source


async def seed_lua_correction_attempts(adapter):
    """Discover up to 100 unseen inputs; no commit-order cursor or payload read.

    Call separately from repair transactions, never with input/identity locks.
    """
    source = _configured_source()
    if source is None:
        return []
    rows = await adapter.fetch_all("""
        INSERT INTO lua_correction_attempts (input_id)
        SELECT i.id FROM lua_correction_inputs i
        WHERE i.source_key=?
          AND NOT EXISTS (SELECT 1 FROM lua_correction_attempts a WHERE a.input_id=i.id)
          AND NOT EXISTS (SELECT 1 FROM lua_correction_receipts r WHERE r.input_id=i.id)
        ORDER BY i.id LIMIT 100
        ON CONFLICT (input_id) DO NOTHING RETURNING input_id
    """, (source,))
    return [row[0] for row in rows]


async def run_next_lua_correction_attempt(adapter):
    """Commit one due outcome with repair/receipt, or return disabled/idle.

    Lock order: attempt -> identity -> input -> round -> players. Intake and
    direct repair must never acquire an attempt lock after identity/input locks.
    Rejections are quarantined, not necessarily corrupt payloads (canonical
    identity conflicts also raise ValueError). Unexpected errors are durably
    deferred, then re-raised. Call without an outer transaction: otherwise the
    caller still owns final commit and locks. The timeout bounds lock waits in
    repair only, not total query execution time or connection acquisition.
    """
    source = _configured_source()
    if source is None:
        return "disabled"
    async with adapter.transaction():
        row = await adapter.fetch_one("""
            SELECT a.input_id, a.attempts FROM lua_correction_attempts a
            JOIN lua_correction_inputs i ON i.id=a.input_id
            WHERE i.source_key=? AND NOT a.terminal AND a.next_due_at<=clock_timestamp()
            ORDER BY a.next_due_at, a.input_id LIMIT 1
            FOR UPDATE OF a SKIP LOCKED
        """, (source,))
        if row is None:
            return "idle"
        input_id, attempts = row
        previous_timeout = await adapter.fetch_val("SELECT current_setting('lock_timeout')")
        unexpected = None
        try:
            async with adapter.transaction():
                await adapter.fetch_val("SELECT set_config('lock_timeout', '250ms', true)")
                outcome = await apply_retained_lua_correction(adapter, source, input_id)
        except asyncpg.LockNotAvailableError:
            outcome = "contended"
        except ValueError:
            outcome = "rejected"
        except asyncpg.PostgresError:
            outcome = "database_error"
        except Exception as exc:
            outcome = "unexpected_error"
            unexpected = exc
        # On failure the savepoint rolled back; on success restore the setting.
        await adapter.fetch_val("SELECT set_config('lock_timeout', ?, true)", (previous_timeout,))
        attempts += outcome != "contended"
        terminal = outcome in {
            "applied", "already_applied", "missing_input", "ambiguous_round",
            "conflicting_revision", "rejected",
        } or attempts >= 5
        delay = 5 if outcome == "contended" else min(30 * 2 ** max(attempts - 1, 0), 480)
        await adapter.execute("""
            UPDATE lua_correction_attempts
            SET attempts=?, outcome=?, terminal=?,
                next_due_at=clock_timestamp() + (? * INTERVAL '1 second'), updated_at=clock_timestamp()
            WHERE input_id=?
        """, (attempts, outcome, terminal, delay, input_id))
    if unexpected is not None:
        raise unexpected
    return outcome
