"""Betting market auto-lifecycle (VISION_2026 Sprint S4 "TEKMA" — Faza B2).

Web-side background loop that manages the full parimutuel session-winner lifecycle
so an admin no longer has to touch it by hand:
- auto-OPENS a market when a live gaming session with two teams is detected (with a
  §6.4b closes_at cutoff = end of map 1, or a short fallback window before map 1 ends),
- auto-CLOSES betting (status='closed') once map 1 finishes, stamping the real cutoff, and
- auto-SETTLES a market (open or closed) once its session result is recorded.
No bot changes, no cron, and — deliberately — no writes on any read endpoint
(get_current_market stays read-only); the work runs in this loop instead.

Everything here is best-effort and idempotent:
- opens at most one market per gaming_session_id (race-safe INSERT ... WHERE NOT
  EXISTS + a per-session advisory lock, so two workers / ticks can't double-open),
- only opens while the session is "live" (last round within BETS_LIVE_WITHIN_SECONDS)
  and its result isn't already recorded,
- binds the real rosters (migration 011) so settle resolves the winner by overlap,
  falling back to a roster-less market when the columns aren't there yet,
- settle reuses the admin endpoint's exact payout core (settle_market_locked), one
  transaction per market,
- never raises out of the loop.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import date, datetime, timedelta
from typing import Any

from website.backend.env_utils import getenv_int
from website.backend.logging_config import get_app_logger

# Reuse the single source of truth for roster-column detection + serialization so
# auto-open and the admin open_market can never diverge, and the shared settle core
# so auto-settle uses the exact same payout math as the admin endpoint.
from website.backend.routers.bets_router import (
    SettleSkip,
    _has_roster_cols,
    _serialize_roster,
    settle_market_locked,
)

logger = get_app_logger("services.bets_lifecycle")

# A live session's most recent round must be within this many seconds of now for
# auto-open to fire (default 90 min — comfortably covers the 60-min session gap
# plus a round in progress). Env-overridable.
_DEFAULT_LIVE_WITHIN = 90 * 60

# Namespace for the per-session pg_advisory_xact_lock that serializes concurrent
# auto-opens (int4). Arbitrary fixed constant.
_BETS_LOCK_NS = 0x6265747

# When a market auto-opens BEFORE the session's first map has finished, bets close
# this many minutes after open (fallback). Once map 1 has completed, closes_at is the
# real end-of-map-1 instead — bets only before/at the evening start (Oracle award
# integrity, FULL_REVIEW §6.4 option b). Env-overridable via BETS_CLOSE_AFTER_MINUTES.
_DEFAULT_CLOSE_AFTER_MIN = 20


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


async def _map1_closes_at(db, gsid: int):
    """Betting cutoff = end of the session's FIRST complete map (FULL_REVIEW §6.4
    option b): once map 1 is over the evening is underway, so no more bets.

    Returns a naive LOCAL datetime — parimutuel_markets.closes_at is a naive column and
    bets_router compares it against datetime.now() (also naive local), so
    datetime.fromtimestamp() (naive, server-local timezone) is the matching convention.
    Returns None when map 1's R2 isn't finished yet, so the caller falls back to
    now + BETS_CLOSE_AFTER_MINUTES.

    'Completed' matches the repo-wide predicate (website_session_data_service): a real
    'completed'/'substitution' round OR a legacy row with NULL round_status — otherwise
    an already-finished older map 1 looks unfinished and the cutoff wrongly falls back.
    Orders by round_start_unix (not round_date/round_time) so NULL-column ordering can't
    differ across engines and it matches the unix-based cutoff math below."""
    row = await db.fetch_one(
        "SELECT round_start_unix, actual_duration_seconds FROM rounds "
        "WHERE gaming_session_id = ? AND round_number = 2 AND is_valid "
        "  AND (round_status IN ('completed', 'substitution') OR round_status IS NULL) "
        "  AND round_start_unix IS NOT NULL "
        "ORDER BY round_start_unix LIMIT 1",
        (gsid,),
    )
    if not row or row[0] is None:
        return None
    # naive, server-local — matches the naive closes_at column + bets_router comparison
    return datetime.fromtimestamp(int(row[0]) + int(row[1] or 0))  # noqa: DTZ006


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
        # Cutoff (FULL_REVIEW §6.4b): end of map 1 if it's already finished, else a
        # short fallback window from now — so bets close near the evening's start.
        closes_at = await _map1_closes_at(db, gsid)
        if closes_at is None:
            closes_at = datetime.now() + timedelta(  # noqa: DTZ005 - naive local matches column
                minutes=getenv_int("BETS_CLOSE_AFTER_MINUTES", _DEFAULT_CLOSE_AFTER_MIN)
            )
        elif closes_at <= datetime.now():  # noqa: DTZ005 - naive local matches column
            # Map 1 already ended (we only started seeing this live session mid-/post-map-2):
            # the betting window has passed, so don't open a market that place_bet would
            # immediately reject — the UIs gate on status=='open' and can't see closes_at,
            # so an expired-but-open market only fails after a user submits a bet.
            logger.debug(
                "bets auto-open: gsid %s map-1 cutoff already passed (%s) — skipping",
                gsid, closes_at,
            )
            return None

        if await _has_roster_cols(db):
            sql = (
                "INSERT INTO parimutuel_markets "
                "(gaming_session_id, session_date, team_a_label, team_b_label, "
                " team_a_guids, team_b_guids, status, closes_at) "
                "SELECT ?, ?, ?, ?, ?, ?, 'open', ? "
                "WHERE NOT EXISTS (SELECT 1 FROM parimutuel_markets "
                "  WHERE gaming_session_id = ?) "
                "RETURNING id"
            )
            params = (gsid, sess_date, a_label, b_label, a_guids, b_guids, closes_at, gsid)
        else:
            sql = (
                "INSERT INTO parimutuel_markets "
                "(gaming_session_id, session_date, team_a_label, team_b_label, status, closes_at) "
                "SELECT ?, ?, ?, ?, 'open', ? "
                "WHERE NOT EXISTS (SELECT 1 FROM parimutuel_markets "
                "  WHERE gaming_session_id = ?) "
                "RETURNING id"
            )
            params = (gsid, sess_date, a_label, b_label, closes_at, gsid)

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


async def maybe_close_after_map1(db) -> int:
    """Close an auto-opened market for betting once its map 1 has finished (§6.4b).

    Auto-open uses a future now + BETS_CLOSE_AFTER_MINUTES fallback window until map 1's
    end is known. Once map 1 is over this flips the market to status='closed' and stamps
    closes_at with the real end-of-map-1, so:
      - the frontends (which show betting controls only while status=='open') stop
        advertising an expired market as open, and
      - place_bet (which rejects any non-'open' market) refuses further bets,
    while auto-settle still resolves it (its scan includes 'closed').

    Scoped to auto-opened markets (created_by_user_id IS NULL, and closes_at IS NOT NULL
    — only auto-open sets closes_at), so admin markets are never touched. Idempotent (the
    scan only sees status='open'). Best-effort — never raises out."""
    if db is None:
        return 0
    try:
        rows = await db.fetch_all(
            "SELECT id, gaming_session_id FROM parimutuel_markets "
            "WHERE status = 'open' AND created_by_user_id IS NULL "
            "  AND gaming_session_id IS NOT NULL AND closes_at IS NOT NULL"
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("bets close-after-map1 scan failed: %s", exc)
        return 0

    closed = 0
    for row in rows or []:
        market_id, gsid = int(row[0]), int(row[1])
        try:
            map1_end = await _map1_closes_at(db, gsid)
            if map1_end is None:
                continue  # map 1 not finished yet — leave the market open
            await db.execute(
                "UPDATE parimutuel_markets SET status = 'closed', closes_at = ? "
                "WHERE id = ? AND status = 'open'",
                (map1_end, market_id),
            )
            closed += 1
            logger.info(
                "bets close-after-map1: market %s closed (map 1 ended %s)",
                market_id, map1_end,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # one bad market must not stop the rest
            logger.warning("bets close-after-map1 failed for market %s: %s", market_id, exc)
    return closed


async def maybe_settle_markets(db) -> int:
    """Auto-settle every still-open market whose gaming session already has a
    recorded result. Uses the shared settle_market_locked (same payout math as the
    admin endpoint), one transaction per market. A decisive result (winning_team
    1/2) auto-resolves the winner; a draw (winning_team 0) settles as 'void' so the
    stakes are refunded instead of leaving the market open forever. Returns how many
    were settled. Best-effort — never raises out."""
    if db is None:
        return 0
    try:
        rows = await db.fetch_all(
            "SELECT m.id, "
            "  (SELECT sr.winning_team FROM session_results sr "
            "   WHERE sr.gaming_session_id = m.gaming_session_id "
            "   ORDER BY sr.session_end DESC NULLS LAST LIMIT 1) AS winning_team "
            "FROM parimutuel_markets m "
            "WHERE m.status IN ('open', 'closed') AND m.gaming_session_id IS NOT NULL"
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("bets auto-settle scan failed: %s", exc)
        return 0

    settled = 0
    for row in rows or []:
        winning_team = row[1]
        if winning_team is None:
            continue  # session result not recorded yet — leave the market open
        market_id = int(row[0])
        # 1/2 -> auto-resolve the winner; anything else (draw = 0) -> void/refund.
        override = None if int(winning_team) in (1, 2) else "void"
        try:
            async with db.transaction():
                result = await settle_market_locked(db, market_id, override)
            settled += 1
            logger.info(
                "bets auto-settle: market %s -> %s (pool=%s, bets=%s)",
                market_id, result.get("outcome"), result.get("total_pool"),
                result.get("bets"),
            )
        except SettleSkip:
            continue  # already settled / unresolved between scan and lock — skip
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # one bad market must not stop the rest
            logger.warning("bets auto-settle failed for market %s: %s", market_id, exc)
    return settled


async def bets_lifecycle_loop(db_factory: Any, interval_seconds: int | None = None) -> None:
    """Background loop that auto-opens and auto-settles betting markets on an
    interval.

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
            with contextlib.suppress(Exception):
                await maybe_close_after_map1(db)
            with contextlib.suppress(Exception):
                await maybe_settle_markets(db)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("bets lifecycle loop cancelled")
        raise
