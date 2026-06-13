"""Unit tests for parimutuel betting (S4-C)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.bets_router import (
    STARTER_BALANCE,
    _wallet,
    place_bet,
    settle_market,
)


def _req(uid=None):
    r = MagicMock()
    r.headers = {"x-requested-with": "XMLHttpRequest"}
    r.session = {"user": {"id": uid}} if uid is not None else {}
    return r


def _market(status="open", mid=1, gsid=None, total=0):
    # id, gaming_session_id, session_date, a_label, b_label, status, outcome, total_pool
    return (mid, gsid, None, "Reds", "Blues", status, None, total)


@pytest.mark.asyncio
async def test_wallet_bootstraps_starter_balance():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)  # no wallet yet
    res = await _wallet(db, 7)
    assert res == {"balance": STARTER_BALANCE, "lifetime_earned": 0}
    db.execute.assert_awaited()  # inserted the row


@pytest.mark.asyncio
async def test_place_bet_rejects_bad_choice_and_amount():
    db = AsyncMock()
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_c", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 0}, {"id": 7}, db)
    with pytest.raises(HTTPException):
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": "x"}, {"id": 7}, db)


@pytest.mark.asyncio
async def test_place_bet_requires_open_market():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=_market(status="settled"))
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 5}, {"id": 7}, db)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_place_bet_requires_csrf():
    req = _req(7)
    req.headers = {}
    with pytest.raises(HTTPException) as e:
        await place_bet(req, 1, {"choice": "team_a", "amount": 5}, {"id": 7}, AsyncMock())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_place_bet_insufficient_balance():
    db = AsyncMock()
    # market open, wallet=10, no existing bet, tries 50
    db.fetch_one = AsyncMock(side_effect=[
        _market(),                       # _market_row
        (10, 0),                         # _wallet
        None,                            # existing bet
    ])
    with pytest.raises(HTTPException) as e:
        await place_bet(_req(7), 1, {"choice": "team_a", "amount": 50}, {"id": 7}, db)
    assert e.value.status_code == 400
    assert "Insufficient" in e.value.detail


@pytest.mark.asyncio
async def test_place_bet_change_refunds_old_stake():
    db = AsyncMock()
    # market open, wallet balance=20, existing bet 60 -> effective=80, new bet 80 ok
    db.fetch_one = AsyncMock(side_effect=[
        _market(),       # _market_row
        (20, 0),         # _wallet
        (60,),           # existing bet amount
    ])
    db.fetch_all = AsyncMock(return_value=[("team_a", 80, 1)])  # _pool_split after upsert
    res = await place_bet(_req(7), 1, {"choice": "team_a", "amount": 80}, {"id": 7}, db)
    assert res["balance"] == 0  # 20 + 60 - 80
    assert res["pool"]["total_pool"] == 80


@pytest.mark.asyncio
async def test_settle_proportional_payout():
    """U1 80 on team_a, U2 40 on team_b; team_a wins -> U1 gets full 120 pool."""
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=_market(status="open"))
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
async def test_settle_no_winner_refunds_all():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=_market(status="open"))
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
async def test_settle_blocks_double_settle():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=_market(status="settled"))
    with pytest.raises(HTTPException) as e:
        await settle_market(_req(101), 1, {"outcome": "team_a"}, {"id": 101}, db)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_settle_auto_outcome_from_session_results():
    db = AsyncMock()
    db.fetch_one = AsyncMock(side_effect=[
        _market(status="open", gsid=42),   # _market_row
        (2,),                              # winning_team=2 -> team_b
    ])
    db.fetch_all = AsyncMock(return_value=[])  # no bets
    res = await settle_market(_req(101), 1, {}, {"id": 101}, db)
    assert res["outcome"] == "team_b"


@pytest.mark.asyncio
async def test_settle_rejects_unresolvable_outcome():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=_market(status="open", gsid=None))
    with pytest.raises(HTTPException) as e:
        await settle_market(_req(101), 1, {}, {"id": 101}, db)
    assert e.value.status_code == 400
