"""Parimutuel predictions (VISION_2026 Sprint S4 "TEKMA").

Valueless-points betting on the session winner. One changeable bet per market
per user; winners split the total pool proportionally to their stake. No real
value — pure engagement (vision R1 §3.1, Twitch-style parimutuel).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from website.backend.dependencies import get_db, require_admin, require_user
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.middleware.auth_helpers import require_ajax_csrf_header

router = APIRouter()

STARTER_BALANCE = 100
_CHOICES = ("team_a", "team_b")


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
            "SELECT id, status FROM parimutuel_markets WHERE id = ? FOR UPDATE",
            (market_id,),
        )
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        if market[1] != "open":
            raise HTTPException(status_code=400, detail="Market is not open for betting")

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
    row = await db.fetch_one(
        """
        INSERT INTO parimutuel_markets
            (gaming_session_id, session_date, team_a_label, team_b_label, created_by_user_id)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id
        """,
        (int(gsid) if gsid else None, p.get("session_date"),
         (p.get("team_a_label") or "Team A").strip()[:40],
         (p.get("team_b_label") or "Team B").strip()[:40], created_by),
    )
    return {"status": "ok", "market_id": int(row[0])}


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

    # One transaction: lock the market row up front so two concurrent settles
    # can't both pass the status check (double-pay) and a mid-loop failure rolls
    # back every payout instead of leaving the market half-settled.
    async with db.transaction():
        market = await db.fetch_one(
            "SELECT id, gaming_session_id, status FROM parimutuel_markets "
            "WHERE id = ? FOR UPDATE",
            (market_id,),
        )
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        if market[2] == "settled":
            raise HTTPException(status_code=400, detail="Market already settled")
        gsid = market[1]

        outcome = (payload.get("outcome") or "").strip()
        if not outcome and gsid:
            # Auto from session_results.winning_team (1 -> team_a, 2 -> team_b).
            wr = await db.fetch_one(
                "SELECT winning_team FROM session_results WHERE gaming_session_id = ? "
                "ORDER BY session_end DESC NULLS LAST LIMIT 1",
                (int(gsid),),
            )
            if wr and wr[0] in (1, 2):
                outcome = "team_a" if int(wr[0]) == 1 else "team_b"
        if outcome not in (*_CHOICES, "void"):
            raise HTTPException(status_code=400, detail="outcome must be team_a|team_b|void (or resolvable)")

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
