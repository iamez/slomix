"""Betting market auto-lifecycle (VISION_2026 Sprint S4 "TEKMA" — Faza B2).

Web-side background loop that auto-OPENS a parimutuel session-winner market when a
live gaming session with two teams is detected, so an admin no longer has to open
one by hand every session. No bot changes, no cron, and — deliberately — no writes
on any read endpoint (get_current_market stays read-only); the work runs in this
loop instead.

Everything here is best-effort and idempotent:
- opens at most one market per gaming_session_id (race-safe INSERT ... WHERE NOT
  EXISTS, so two workers / two ticks can't double-open),
- only fires while the session is "live" (last round within BETS_LIVE_WITHIN_SECONDS),
- binds the real rosters (migration 011) so settle resolves the winner by overlap,
  falling back to a roster-less market when the columns aren't there yet,
- never raises out of the loop.

Auto-SETTLE is intentionally left to the existing admin endpoint for now (its payout
split is unit-tested); wiring it into this loop is the natural follow-up.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import date
from typing import Any

from website.backend.env_utils import getenv_int
from website.backend.logging_config import get_app_logger

# Reuse the single source of truth for roster-column detection + serialization so
# auto-open and the admin open_market can never diverge.
from website.backend.routers.bets_router import _has_roster_cols, _serialize_roster

logger = get_app_logger("services.bets_lifecycle")

# A live session's most recent round must be within this many seconds of now for
# auto-open to fire (default 90 min — comfortably covers the 60-min session gap
# plus a round in progress). Env-overridable.
_DEFAULT_LIVE_WITHIN = 90 * 60

# Namespace for the per-session pg_advisory_xact_lock that serializes concurrent
# auto-opens (int4). Arbitrary fixed constant.
_BETS_LOCK_NS = 0x6265747


def _label_from_names(names: Any, fallback: str) -> str:
    """Human label from a jsonb player_names array (e.g. 'immoo{, .olz, wiseBoy'),
    truncated to the column width. Falls back to the generic team name."""
    items: list = []
    if isinstance(names, (list, tuple)):
        items = list(names)
    elif isinstance(names, str) and names.strip().startswith("["):
        with contextlib.suppress(ValueError, TypeError):
            items = json.loads(names)
    cleaned = [str(n).strip() for n in items if str(n).strip()]
    label = ", ".join(cleaned)
    return label[:40] if label else fallback[:40]


async def _live_gsid(db, live_within_seconds: int) -> int | None:
    """gaming_session_id of the most recent session whose latest round is within
    live_within_seconds of now, else None."""
    # The single most-recent round's session IS the live session — take just that
    # row (index-friendly) instead of aggregating the whole rounds table each tick.
    row = await db.fetch_one(
        "SELECT gaming_session_id, round_start_unix "
        "FROM rounds "
        "WHERE gaming_session_id IS NOT NULL AND round_start_unix IS NOT NULL "
        "ORDER BY round_start_unix DESC LIMIT 1"
    )
    if not row or row[1] is None:
        return None
    gsid, last_unix = int(row[0]), int(row[1])
    if int(time.time()) - last_unix > live_within_seconds:
        return None
    return gsid


async def _two_teams(db, gsid: int):
    """Return (a_label, a_guids_json, b_label, b_guids_json) for a gaming session
    from its session-level (map_name='ALL') team rows, or None when there isn't a
    clean two-team split."""
    rows = await db.fetch_all(
        "SELECT team_name, player_guids, player_names FROM session_teams "
        "WHERE gaming_session_id = ? AND map_name = 'ALL' "
        "ORDER BY team_name",
        (gsid,),
    )
    if not rows or len(rows) != 2:
        return None
    (a_name, a_guids, a_names), (b_name, b_guids, b_names) = rows[0], rows[1]
    return (
        _label_from_names(a_names, a_name or "Team A"),
        _serialize_roster(a_guids),
        _label_from_names(b_names, b_name or "Team B"),
        _serialize_roster(b_guids),
    )


def _coerce_date(value):
    """round_date is stored as a 'YYYY-MM-DD' string, but parimutuel_markets.session_date
    is a real DATE column (asyncpg wants a datetime.date, not a str). Coerce; return
    None on anything unparseable."""
    if value is None or isinstance(value, date):
        return value
    with contextlib.suppress(ValueError, TypeError):
        return date.fromisoformat(str(value)[:10])
    return None


async def _session_date(db, gsid: int):
    row = await db.fetch_one(
        "SELECT MAX(round_date) FROM rounds WHERE gaming_session_id = ?", (gsid,)
    )
    return _coerce_date(row[0]) if row else None


async def maybe_open_market(db, live_within_seconds: int) -> int | None:
    """Open a session-winner market for the current live session if one isn't open
    yet. Returns the new market id, or None when nothing was opened. Never raises."""
    if db is None:
        return None
    try:
        gsid = await _live_gsid(db, live_within_seconds)
        if gsid is None:
            return None
        # One market per session, EVER — match ANY status, not just 'open'. Guarding
        # only on 'open' would re-open a fresh market if an admin settled/closed the
        # session's market while its last round was still inside the live window.
        existing = await db.fetch_one(
            "SELECT id FROM parimutuel_markets "
            "WHERE gaming_session_id = ? LIMIT 1",
            (gsid,),
        )
        if existing:
            return None
        # Don't open a market for a session whose result is already recorded — a web
        # restart can land here while a finalized session's last round is still inside
        # the live window, and place_bet rejects betting once session_results.winning_team
        # exists (bets_router). Opening one would show an "open" market nobody can bet on.
        if await db.fetch_one(
            "SELECT 1 FROM session_results "
            "WHERE gaming_session_id = ? AND winning_team IN (1, 2) LIMIT 1",
            (gsid,),
        ):
            logger.debug("bets auto-open: gsid %s already finalized — skipping", gsid)
            return None
        teams = await _two_teams(db, gsid)
        if teams is None:
            logger.debug("bets auto-open: gsid %s has no clean 2-team roster yet", gsid)
            return None
        a_label, a_guids, b_label, b_guids = teams
        sess_date = await _session_date(db, gsid)

        if await _has_roster_cols(db):
            sql = (
                "INSERT INTO parimutuel_markets "
                "(gaming_session_id, session_date, team_a_label, team_b_label, "
                " team_a_guids, team_b_guids, status) "
                "SELECT ?, ?, ?, ?, ?, ?, 'open' "
                "WHERE NOT EXISTS (SELECT 1 FROM parimutuel_markets "
                "  WHERE gaming_session_id = ?) "
                "RETURNING id"
            )
            params = (gsid, sess_date, a_label, b_label, a_guids, b_guids, gsid)
        else:
            sql = (
                "INSERT INTO parimutuel_markets "
                "(gaming_session_id, session_date, team_a_label, team_b_label, status) "
                "SELECT ?, ?, ?, ?, 'open' "
                "WHERE NOT EXISTS (SELECT 1 FROM parimutuel_markets "
                "  WHERE gaming_session_id = ?) "
                "RETURNING id"
            )
            params = (gsid, sess_date, a_label, b_label, gsid)

        # There's no unique constraint on gaming_session_id, and INSERT ... WHERE
        # NOT EXISTS is NOT atomic across concurrent transactions (under READ
        # COMMITTED both can see no row and both insert). Serialize the check+insert
        # per session with a transaction-scoped advisory lock, so multiple web
        # workers / ticks can't split bets across duplicate open markets. The
        # in-lock re-check (and the WHERE NOT EXISTS) make it idempotent.
        async with db.transaction():
            await db.execute("SELECT pg_advisory_xact_lock(?, ?)", (_BETS_LOCK_NS, int(gsid)))
            if await db.fetch_one(
                "SELECT id FROM parimutuel_markets WHERE gaming_session_id = ? LIMIT 1",
                (gsid,),
            ):
                return None
            row = await db.fetch_one(sql, params)
            if not row:
                return None
            market_id = int(row[0])
        logger.info(
            "bets auto-open: opened market %s for gsid %s (%s vs %s)",
            market_id, gsid, a_label, b_label,
        )
        return market_id
    except asyncio.CancelledError:
        raise  # never swallow cancellation (it's BaseException, but be explicit)
    except Exception as exc:  # best-effort — never break the loop
        logger.warning("bets auto-open failed: %s", exc)
        return None


async def bets_lifecycle_loop(db_factory: Any, interval_seconds: int | None = None) -> None:
    """Background loop that auto-opens betting markets on an interval.

    db_factory may be a DatabaseAdapter or a zero-arg callable returning one.
    Disabled when interval <= 0 (the default), so it's opt-in via
    BETS_LIFECYCLE_SECONDS.
    """
    if interval_seconds is None:
        interval_seconds = getenv_int("BETS_LIFECYCLE_SECONDS", 0)
    if interval_seconds <= 0:
        logger.debug("bets lifecycle loop disabled (interval=%s)", interval_seconds)
        return

    live_within = getenv_int("BETS_LIVE_WITHIN_SECONDS", _DEFAULT_LIVE_WITHIN)
    logger.info(
        "bets lifecycle loop starting (interval=%ss, live_within=%ss)",
        interval_seconds, live_within,
    )
    try:
        while True:
            db = db_factory() if callable(db_factory) else db_factory
            with contextlib.suppress(Exception):
                await maybe_open_market(db, live_within)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("bets lifecycle loop cancelled")
        raise
