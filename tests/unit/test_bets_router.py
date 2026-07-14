"""Unit tests for parimutuel betting (S4-C)."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import bets_router as bets
from website.backend.routers.bets_router import (
    STARTER_BALANCE,
    _wallet,
    place_bet,
    settle_market,
)


def _db():
    """AsyncMock db whose .transaction() is a no-op async CM yielding the db,
    so `async with db.transaction():` works (all calls share the same mock)."""
    db = AsyncMock()

    @asynccontextmanager
    async def _tx():
        yield db

    db.transaction = lambda: _tx()
    return db


def _req(uid=None):
    r = MagicMock()
    r.headers = {"x-requested-with": "XMLHttpRequest"}
    r.session = {"user": {"id": uid}} if uid is not None else {}
    return r


def _pb_market(status="open", mid=1, closes_at=None, gsid=None):
    # place_bet locks: SELECT id, status, closes_at, gaming_session_id ... FOR UPDATE
    # Default gsid=None so the hindsight-cutoff result-known check is skipped
    # (no extra fetch_one) on the happy path.
    return (mid, status, closes_at, gsid)


def _settle_market(status="open", gsid=None, mid=1):
    # settle_market locks: SELECT id, gaming_session_id, status ... FOR UPDATE
    return (mid, gsid, status)


@pytest.mark.asyncio
async def test_wallet_bootstraps_starter_balance():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)  # no wallet yet
    res = await _wallet(db, 7)
    assert res == {"balance": STARTER_BALANCE, "lifetime_earned": 0}
    db.execute.assert_awaited()  # inserted the row


@pytest.mark.asyncio
async def test_place_bet_rejects_bad_choice_and_amount():
    db = _db()
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_c", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 0}, {"id": 7}, db)
    with pytest.raises(HTTPException):
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": "x"}, {"id": 7}, db)


@pytest.mark.asyncio
async def test_place_bet_requires_open_market():
    db = _db()
    db.fetch_one = AsyncMock(return_value=_pb_market(status="settled"))
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_place_bet_rejects_after_closes_at():
    """Hindsight cutoff: an open market past its closes_at takes no new bets."""
    from datetime import datetime, timedelta
    db = _db()
    past = datetime.now() - timedelta(minutes=5)  # noqa: DTZ005 - naive col
    db.fetch_one = AsyncMock(return_value=_pb_market(closes_at=past))
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400
    assert "closed" in e.value.detail.lower()


@pytest.mark.asyncio
async def test_place_bet_rejects_when_result_known():
    """Hindsight cutoff: once session_results has a winner, betting is closed."""
    db = _db()
    db.fetch_one = AsyncMock(side_effect=[
        _pb_market(gsid=42),   # market lock (open, no closes_at)
        (1,),                  # session_results result-known probe
    ])
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400
    assert "Result is in" in e.value.detail


@pytest.mark.asyncio
async def test_place_bet_rejects_after_map1_despite_future_closes_at():
    """§6.4b live cutoff: an auto-market (closes_at set) whose map 1 has already ended
    takes no bets even if its stored fallback closes_at is still in the future — closing
    the gap between map 1 ending and the lifecycle tick that flips the market closed."""
    from datetime import datetime, timedelta
    db = _db()
    future = datetime.now() + timedelta(minutes=15)  # noqa: DTZ005 - naive col
    db.fetch_one = AsyncMock(side_effect=[
        _pb_market(closes_at=future, gsid=42),  # market lock (open, future fallback)
        (1,),                                    # map-1 R2 completed probe
    ])
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400
    assert "closed" in e.value.detail.lower()


@pytest.mark.asyncio
async def test_place_bet_requires_csrf():
    req = _req(7)
    req.headers = {}
    with pytest.raises(HTTPException) as e:
        await place_bet(req, 1, {"choice": "team_a", "amount": 5}, {"id": 7}, _db())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_place_bet_insufficient_balance():
    db = _db()
    # market(open, FOR UPDATE), wallet balance=10 (FOR UPDATE), no existing bet
    db.fetch_one = AsyncMock(side_effect=[
        _pb_market(),    # market lock
        (10,),           # wallet balance after bootstrap
        None,            # existing bet
    ])
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 50}, {"id": 7}, db)
    assert e.value.status_code == 400
    assert "Insufficient" in e.value.detail


@pytest.mark.asyncio
async def test_place_bet_change_refunds_old_stake():
    db = _db()
    # market open, wallet balance=20, existing bet 60 -> effective=80, new bet 80 ok
    db.fetch_one = AsyncMock(side_effect=[
        _pb_market(),    # market lock
        (20,),           # wallet balance
        (60,),           # existing bet amount
    ])
    db.fetch_all = AsyncMock(return_value=[("team_a", 80, 1)])  # _pool_split after upsert
    res = await place_bet(_req(7), 1, {"choice": "team_a", "amount": 80}, {"id": 7}, db)
    assert res["balance"] == 0  # 20 + 60 - 80
    assert res["pool"]["total_pool"] == 80


@pytest.mark.asyncio
async def test_settle_proportional_payout():
    """U1 80 on team_a, U2 40 on team_b; team_a wins -> U1 gets full 120 pool."""
    db = _db()
    db.fetch_one = AsyncMock(return_value=_settle_market(status="open"))
    db.fetch_all = AsyncMock(return_value=[
        (10, 101, "team_a", 80),
        (11, 102, "team_b", 40),
    ])
    res = await settle_market(_req(101), 1, {"outcome": "team_a"}, {"id": 101}, db)
    assert res["total_pool"] == 120 and res["winning_pool"] == 80
    assert res["refunded"] is False
    # winner credit upsert: (uid, payout=120, net=40)
    credits = [c.args for c in db.execute.await_args_list
               if "INSERT INTO user_points" in c.args[0]]
    assert len(credits) == 1
    assert credits[0][1][1] == 120 and credits[0][1][2] == 40


@pytest.mark.asyncio
async def test_settle_remainder_is_fully_distributed():
    """3 equal winners (10 each) + 1 loser (5): pool 35, winning 30.
    Floor = 35*10//30 = 11 each -> 33; remainder 2 -> +1 to two largest.
    sum(payouts) must equal total_pool (35) exactly."""
    db = _db()
    db.fetch_one = AsyncMock(return_value=_settle_market(status="open"))
    db.fetch_all = AsyncMock(return_value=[
        (10, 101, "team_a", 10),
        (11, 102, "team_a", 10),
        (12, 103, "team_a", 10),
        (13, 104, "team_b", 5),
    ])
    res = await settle_market(_req(101), 1, {"outcome": "team_a"}, {"id": 101}, db)
    assert res["total_pool"] == 35
    payouts = [c.args[1][1] for c in db.execute.await_args_list
               if "INSERT INTO user_points" in c.args[0]]
    assert sum(payouts) == 35  # no points vanish to floor division
    assert sorted(payouts) == [11, 12, 12]  # remainder went to the two lowest bids


@pytest.mark.asyncio
async def test_settle_no_winner_refunds_all():
    db = _db()
    db.fetch_one = AsyncMock(return_value=_settle_market(status="open"))
    db.fetch_all = AsyncMock(return_value=[
        (10, 101, "team_a", 30),
        (11, 102, "team_a", 50),
    ])
    res = await settle_market(_req(101), 1, {"outcome": "team_b"}, {"id": 101}, db)
    assert res["refunded"] is True
    # both refunded their stake, net 0
    credits = [c.args[1] for c in db.execute.await_args_list
               if "INSERT INTO user_points" in c.args[0]]
    assert {c[1] for c in credits} == {30, 50}     # payout == stake
    assert all(c[2] == 0 for c in credits)         # no lifetime gain on refund


@pytest.mark.asyncio
async def test_settle_blocks_double_settle_after_lock():
    """The status re-check happens on the FOR UPDATE-locked row, so a second
    concurrent settle sees 'settled' and is rejected (no double-pay)."""
    db = _db()
    db.fetch_one = AsyncMock(return_value=_settle_market(status="settled"))
    with pytest.raises(HTTPException) as e:
        await settle_market(_req(101), 1, {"outcome": "team_a"}, {"id": 101}, db)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_settle_auto_outcome_from_session_results():
    bets._roster_cols_cache.clear()  # not yet cached → _has_roster_cols re-checks
    db = _db()
    db.fetch_one = AsyncMock(side_effect=[
        _settle_market(status="open", gsid=42),    # market lock
        (2, None, None),                           # winning_team=2 -> team_b (no rosters)
        (0,),                                      # information_schema: roster cols absent
    ])
    db.fetch_all = AsyncMock(return_value=[])  # no bets
    res = await settle_market(_req(101), 1, {}, {"id": 101}, db)
    assert res["outcome"] == "team_b"  # legacy positional fallback
    bets._roster_cols_cache.clear()  # reset cache so it doesn't leak into later tests


@pytest.mark.asyncio
async def test_settle_roster_bound_outcome_overrides_position():
    """When rosters are bound (migration 011), the winner is resolved by roster
    overlap — so winning_team=1 maps to team_b if team_b holds that roster, not
    the positional team_a."""
    bets._roster_cols_cache["present"] = True
    db = _db()
    db.fetch_one = AsyncMock(side_effect=[
        _settle_market(status="open", gsid=42),                 # market lock
        (1, "AAAA1111,BBBB2222", "CCCC3333"),                   # winner=team_1 roster
        ("CCCC3333", "AAAA1111,BBBB2222"),                      # market team_a_guids, team_b_guids
    ])
    db.fetch_all = AsyncMock(return_value=[])
    res = await settle_market(_req(101), 1, {}, {"id": 101}, db)
    # winning roster (AAAA/BBBB) overlaps market team_b, so outcome is team_b
    # even though winning_team==1 would be team_a positionally.
    assert res["outcome"] == "team_b"
    bets._roster_cols_cache.clear()  # reset cache for other tests


@pytest.mark.asyncio
async def test_settle_rejects_unresolvable_outcome():
    db = _db()
    db.fetch_one = AsyncMock(return_value=_settle_market(status="open", gsid=None))
    with pytest.raises(HTTPException) as e:
        await settle_market(_req(101), 1, {}, {"id": 101}, db)
    assert e.value.status_code == 400
