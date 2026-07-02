"""Parimutuel predictions (VISION_2026 Sprint S4 "TEKMA").

Valueless-points betting on the session winner. One changeable bet per market
per user; winners split the total pool proportionally to their stake. No real
value — pure engagement (vision R1 §3.1, Twitch-style parimutuel).
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from website.backend.dependencies import get_db, require_admin, require_user
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.middleware.auth_helpers import require_ajax_csrf_header

router = APIRouter()

STARTER_BALANCE = 100
_CHOICES = ("team_a", "team_b")

# Cached presence of the roster columns added in migration 011 (so the code is
# safe to deploy before the migration is applied — it just falls back to the
# legacy positional winning_team mapping until the columns exist). A mutable
# container (not a reassigned `global`) so we mutate, never rebind, the module
# name — avoids CodeQL's unused-global false positive.
_roster_cols_cache: dict[str, bool] = {}


async def _has_roster_cols(db) -> bool:
    # Cache ONLY the positive result: while the columns are absent we re-check
    # each call (open/settle are infrequent), so once migration 011 is applied
    # roster-binding activates WITHOUT needing a web-process restart. On any error
    # (e.g. a non-PostgreSQL adapter where information_schema isn't queryable) we
    # return False and fall back to the legacy positional mapping.
    if _roster_cols_cache.get("present"):
        return True
    try:
        row = await db.fetch_one(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'parimutuel_markets' "
            "AND column_name IN ('team_a_guids', 'team_b_guids')"
        )
        present = bool(row and int(row[0]) >= 2)
    except Exception:
        present = False
    if present:
        _roster_cols_cache["present"] = True
    return present


def _parse_guids(raw) -> set[str]:
    """Parse a stored roster (JSON array or comma list of GUIDs) into a set of
    short (8-char) GUIDs for overlap matching."""
    if not raw:
        return set()
    items: list = []
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        s = str(raw).strip()
        if s.startswith("["):
            try:
                items = json.loads(s)
            except (ValueError, TypeError):
                items = []
        else:
            items = [p for p in s.replace(";", ",").split(",")]
    return {str(g).strip()[:8].upper() for g in items if str(g).strip()}


def _serialize_roster(v):
    """Store a roster for the DB. Lists/tuples are JSON-encoded; a string is
    kept verbatim (it may already be JSON or a comma list — _parse_guids reads
    both). Avoids json.dumps turning 'A,B' into the unparseable '"A,B"'."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return json.dumps(list(v))
    return str(v)


async def _resolve_outcome(db, market_id: int, winning_team: int,
                           team_1_guids, team_2_guids) -> str:
    """Map a session's winning_team to the market's team_a/team_b.

    Roster-bound when the market stored its rosters (migration 011): match the
    winning roster against team_a_guids/team_b_guids by GUID overlap, so a
    wrong-side payout can't happen from the positional winning_team=1->team_a
    assumption. Falls back to that positional mapping when no rosters are bound
    (pre-migration, market opened without rosters, or an ambiguous tie).
    """
    positional = "team_a" if winning_team == 1 else "team_b"
    if not await _has_roster_cols(db):
        return positional
    mrow = await db.fetch_one(
        "SELECT team_a_guids, team_b_guids FROM parimutuel_markets WHERE id = ?",
        (market_id,),
    )
    if not mrow or not (mrow[0] or mrow[1]):
        return positional
    a_set, b_set = _parse_guids(mrow[0]), _parse_guids(mrow[1])
    win_set = _parse_guids(team_1_guids if winning_team == 1 else team_2_guids)
    if not win_set or not (a_set or b_set):
        return positional
    overlap_a, overlap_b = len(win_set & a_set), len(win_set & b_set)
    if overlap_a == overlap_b:
        return positional
    return "team_a" if overlap_a > overlap_b else "team_b"


async def _wallet(db, user_id: int) -> dict:
    """Fetch the user's wallet, bootstrapping a starter balance on first use."""
    row = await db.fetch_one(
        "SELECT balance, lifetime_earned FROM user_points WHERE user_id = ?",
        (user_id,),
    )
    if row is None:
        await db.execute(
            "INSERT INTO user_points (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT (user_id) DO NOTHING",
            (user_id, STARTER_BALANCE),
        )
        return {"balance": STARTER_BALANCE, "lifetime_earned": 0}
    return {"balance": int(row[0]), "lifetime_earned": int(row[1])}


async def _pool_split(db, market_id: int) -> dict:
    rows = await db.fetch_all(
        "SELECT choice, COALESCE(SUM(amount), 0), COUNT(*) FROM parimutuel_bets "
        "WHERE market_id = ? GROUP BY choice",
        (market_id,),
    )
    split = {"team_a": {"pool": 0, "bets": 0}, "team_b": {"pool": 0, "bets": 0}}
    for choice, pool, n in (rows or []):
        if choice in split:
            split[choice] = {"pool": int(pool), "bets": int(n)}
    split["total_pool"] = split["team_a"]["pool"] + split["team_b"]["pool"]
    return split


async def _market_row(db, market_id: int):
    return await db.fetch_one(
        "SELECT id, gaming_session_id, session_date, team_a_label, team_b_label, "
        "status, outcome, total_pool FROM parimutuel_markets WHERE id = ?",
        (market_id,),
    )


def _market_dict(row, split, my_bet) -> dict:
    return {
        "id": int(row[0]),
        "gaming_session_id": row[1],
        "session_date": str(row[2]) if row[2] else None,
        "team_a_label": row[3],
        "team_b_label": row[4],
        "status": row[5],
        "outcome": row[6],
        "pool": split,
        "my_bet": my_bet,
    }


@router.get("/wallet")
async def get_wallet(request: Request, user: dict = Depends(require_user),
                     db: DatabaseAdapter = Depends(get_db)):
    try:
        uid = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed user session")
    return {"status": "ok", **await _wallet(db, uid)}


@router.get("/market/current")
async def get_current_market(request: Request, db: DatabaseAdapter = Depends(get_db)):
    """Latest open market (or most recent if none open) + my bet if logged in."""
    row = await db.fetch_one(
        "SELECT id, gaming_session_id, session_date, team_a_label, team_b_label, "
        "status, outcome, total_pool FROM parimutuel_markets "
        "ORDER BY (status = 'open') DESC, id DESC LIMIT 1",
    )
    if not row:
        return {"status": "ok", "market": None}
    split = await _pool_split(db, int(row[0]))
    my_bet = None
    user = request.session.get("user") if hasattr(request, "session") else None
    if user and user.get("id") is not None:
        try:
            b = await db.fetch_one(
                "SELECT choice, amount, payout, status FROM parimutuel_bets "
                "WHERE market_id = ? AND user_id = ?",
                (int(row[0]), int(user["id"])),
            )
            if b:
                my_bet = {"choice": b[0], "amount": int(b[1]), "payout": int(b[2]), "status": b[3]}
        except (TypeError, ValueError):
            my_bet = None
    return {"status": "ok", "market": _market_dict(row, split, my_bet)}


@router.post("/market/{market_id}/bet")
async def place_bet(
    request: Request,
    market_id: int,
    payload: dict,
    user: dict = Depends(require_user),
    db: DatabaseAdapter = Depends(get_db),
):
    """Place/change a bet (one per market). Refunds the old stake on change."""
    require_ajax_csrf_header(request)
    try:
        uid = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed user session")

    choice = ((payload or {}).get("choice") or "").strip()
    amount = (payload or {}).get("amount")
    if choice not in _CHOICES:
        raise HTTPException(status_code=400, detail="choice must be team_a or team_b")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount must be an integer")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    # Everything below is one transaction: lock the market + wallet rows so the
    # debit / bet upsert / pool update are atomic and concurrent bets (same user
    # or settle-in-flight) can't race into a lost update or overspend.
    async with db.transaction():
        market = await db.fetch_one(
            "SELECT id, status, closes_at, gaming_session_id "
            "FROM parimutuel_markets WHERE id = ? FOR UPDATE",
            (market_id,),
        )
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        if market[1] != "open":
            raise HTTPException(status_code=400, detail="Market is not open for betting")
        # Hindsight-betting cutoff: a market that is still 'open' but whose
        # close time has passed — or whose session result is already recorded —
        # would let someone bet with the outcome known, fabricating points and a
        # permanent 'Oracle' season award. Block new/changed bets in that window.
        closes_at = market[2]
        if closes_at is not None and datetime.now() >= closes_at:  # noqa: DTZ005 - naive column
            raise HTTPException(status_code=400, detail="Betting has closed for this market")
        m_gsid = market[3]
        if m_gsid:
            result_known = await db.fetch_one(
                "SELECT 1 FROM session_results WHERE gaming_session_id = ? "
                "AND winning_team IN (1, 2) LIMIT 1",
                (int(m_gsid),),
            )
            if result_known:
                raise HTTPException(status_code=400, detail="Result is in — betting is closed")

        # Ensure the wallet row exists, then lock it (FOR UPDATE can't lock a
        # missing row, so bootstrap first).
        await db.execute(
            "INSERT INTO user_points (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT (user_id) DO NOTHING",
            (uid, STARTER_BALANCE),
        )
        wallet_row = await db.fetch_one(
            "SELECT balance FROM user_points WHERE user_id = ? FOR UPDATE",
            (uid,),
        )
        balance = int(wallet_row[0])

        existing = await db.fetch_one(
            "SELECT amount FROM parimutuel_bets WHERE market_id = ? AND user_id = ?",
            (market_id, uid),
        )
        # Changing a bet refunds the old stake first.
        refund = int(existing[0]) if existing else 0
        effective = balance + refund
        if amount > effective:
            raise HTTPException(status_code=400, detail=f"Insufficient points (have {effective})")

        new_balance = effective - amount
        await db.execute(
            "UPDATE user_points SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (new_balance, uid),
        )
        await db.execute(
            """
            INSERT INTO parimutuel_bets (market_id, user_id, choice, amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (market_id, user_id) DO UPDATE
            SET choice = EXCLUDED.choice, amount = EXCLUDED.amount,
                updated_at = CURRENT_TIMESTAMP
            """,
            (market_id, uid, choice, amount),
        )
        split = await _pool_split(db, market_id)
        await db.execute(
            "UPDATE parimutuel_markets SET total_pool = ? WHERE id = ?",
            (split["total_pool"], market_id),
        )
    return {"status": "ok", "balance": new_balance, "choice": choice,
            "amount": amount, "pool": split}


@router.get("/leaderboard")
async def get_bets_leaderboard(limit: int = 10, db: DatabaseAdapter = Depends(get_db)):
    limit = max(1, min(limit, 50))
    rows = await db.fetch_all(
        """
        SELECT up.user_id, up.balance, up.lifetime_earned,
               COALESCE(pl.display_name, pl.player_name) AS name
        FROM user_points up
        LEFT JOIN player_links pl ON pl.discord_id = up.user_id
        ORDER BY up.lifetime_earned DESC, up.balance DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"status": "ok", "players": [
        {"name": r[3] or f"User {r[0]}", "balance": int(r[1]), "lifetime_earned": int(r[2])}
        for r in (rows or [])
    ]}


@router.post("/market")
async def open_market(
    request: Request,
    payload: dict | None = None,
    user: dict = Depends(require_admin),
    db: DatabaseAdapter = Depends(get_db),
):
    """Open a session-winner market (admin)."""
    require_ajax_csrf_header(request)
    p = payload or {}
    try:
        created_by = int(user["id"])
    except (TypeError, ValueError):
        created_by = None
    gsid = p.get("gaming_session_id")
    cols = ["gaming_session_id", "session_date", "team_a_label", "team_b_label", "created_by_user_id"]
    vals = [int(gsid) if gsid else None, p.get("session_date"),
            (p.get("team_a_label") or "Team A").strip()[:40],
            (p.get("team_b_label") or "Team B").strip()[:40], created_by]
    # Bind rosters so settle resolves the winner by overlap, not position
    # (migration 011). Guarded so this is safe before the migration is applied.
    if await _has_roster_cols(db):
        cols += ["team_a_guids", "team_b_guids"]
        vals += [_serialize_roster(p.get("team_a_guids")),
                 _serialize_roster(p.get("team_b_guids"))]
    placeholders = ", ".join(["?"] * len(cols))
    row = await db.fetch_one(
        f"INSERT INTO parimutuel_markets ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",  # nosec B608 - cols are hardcoded literals
        tuple(vals),
    )
    return {"status": "ok", "market_id": int(row[0])}


class SettleSkip(Exception):
    """A settle precondition wasn't met (market missing / already settled /
    outcome unresolvable). Non-fatal: the admin endpoint maps it to an HTTP error,
    the auto-settle loop just skips the market. `code` is one of
    'not_found' | 'already_settled' | 'unresolved'."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


async def settle_market_locked(db, market_id: int, outcome_override: str | None = None) -> dict:
    """Core settle + payout for one market. MUST be called inside a
    ``db.transaction()`` (the caller owns the transaction so a mid-payout failure
    rolls back every write). Locks the market row, resolves the outcome (explicit
    override else auto from session_results, roster-bound via _resolve_outcome),
    pays winners / refunds on void-or-no-winners, marks the market settled.
    Raises SettleSkip when a precondition isn't met. Shared by the admin endpoint
    and the auto-settle loop so the payout math lives in exactly one place."""
    market = await db.fetch_one(
        "SELECT id, gaming_session_id, status FROM parimutuel_markets "
        "WHERE id = ? FOR UPDATE",
        (market_id,),
    )
    if not market:
        raise SettleSkip("not_found", "Market not found")
    if market[2] == "settled":
        raise SettleSkip("already_settled", "Market already settled")
    gsid = market[1]

    outcome = (outcome_override or "").strip()
    if not outcome and gsid:
        # Auto-resolve from session_results, roster-bound when available
        # (not a positional winning_team=1->team_a assumption — see
        # _resolve_outcome / migration 011).
        wr = await db.fetch_one(
            "SELECT winning_team, team_1_guids, team_2_guids FROM session_results "
            "WHERE gaming_session_id = ? ORDER BY session_end DESC NULLS LAST LIMIT 1",
            (int(gsid),),
        )
        if wr and wr[0] in (1, 2):
            outcome = await _resolve_outcome(db, market_id, int(wr[0]), wr[1], wr[2])
    if outcome not in (*_CHOICES, "void"):
        raise SettleSkip("unresolved", "outcome must be team_a|team_b|void (or resolvable)")

    bets = await db.fetch_all(
        "SELECT id, user_id, choice, amount FROM parimutuel_bets WHERE market_id = ?",
        (market_id,),
    )
    bets = bets or []
    total_pool = sum(int(b[3]) for b in bets)
    winning_pool = sum(int(b[3]) for b in bets if b[2] == outcome)

    # No winners (or void) -> refund every stake.
    refund_all = outcome == "void" or winning_pool == 0

    # Resolve each bet's payout. For the winner split, floor division leaves a
    # remainder (< number of winners); hand it out +1 at a time to the largest
    # stakes (tie-break by bet id) so sum(payouts) == total_pool exactly.
    resolved = []  # (bid, uid, payout, status, net)
    if refund_all:
        for bid, uid, _choice, amount in bets:
            resolved.append((bid, uid, int(amount), "refunded", 0))
    else:
        winners = [(b[0], b[1], int(b[3])) for b in bets if b[2] == outcome]
        losers = [(b[0], b[1], int(b[3])) for b in bets if b[2] != outcome]
        floor = {bid: (amount * total_pool) // winning_pool
                 for bid, _uid, amount in winners}
        remainder = total_pool - sum(floor.values())
        order = sorted(winners, key=lambda w: (-w[2], w[0]))
        for i in range(remainder):
            floor[order[i % len(order)][0]] += 1
        for bid, uid, amount in winners:
            payout = floor[bid]
            resolved.append((bid, uid, payout, "won", payout - amount))
        for bid, uid, amount in losers:
            resolved.append((bid, uid, 0, "lost", 0))

    for bid, uid, payout, status, net in resolved:
        await db.execute(
            "UPDATE parimutuel_bets SET payout = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payout, status, bid),
        )
        if payout > 0:
            # Credit the wallet (bettor always has a row from place_bet; upsert
            # is defensive). DO UPDATE adds onto the existing balance.
            await db.execute(
                """
                INSERT INTO user_points (user_id, balance, lifetime_earned)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE
                SET balance = user_points.balance + EXCLUDED.balance,
                    lifetime_earned = user_points.lifetime_earned + EXCLUDED.lifetime_earned,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (int(uid), payout, max(0, net)),
            )

    await db.execute(
        "UPDATE parimutuel_markets SET status = 'settled', outcome = ?, "
        "settled_at = CURRENT_TIMESTAMP WHERE id = ?",
        (outcome, market_id),
    )
    return {"status": "ok", "outcome": outcome, "total_pool": total_pool,
            "winning_pool": winning_pool, "refunded": refund_all, "bets": len(bets)}


@router.post("/market/{market_id}/settle")
async def settle_market(
    request: Request,
    market_id: int,
    payload: dict | None = None,
    user: dict = Depends(require_admin),
    db: DatabaseAdapter = Depends(get_db),
):
    """Settle a market and pay out winners (admin). Atomic + race-safe."""
    require_ajax_csrf_header(request)
    payload = payload or {}
    # One transaction: the row lock in settle_market_locked stops two concurrent
    # settles from double-paying, and a mid-payout failure rolls back every write.
    try:
        async with db.transaction():
            return await settle_market_locked(db, market_id, payload.get("outcome"))
    except SettleSkip as exc:
        raise HTTPException(
            status_code=404 if exc.code == "not_found" else 400,
            detail=exc.detail,
        )
