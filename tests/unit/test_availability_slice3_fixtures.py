"""Phase 6, slice 3 — the backend arbitrates the admin market types.

Slice 2 built the bettor's half of the market and left the admin's half in
legacy availability.js: opening a market (:2353-2368) and settling it
(:2370-2386). Slice 3 moves both, which needs three shapes the committed
fixtures did not hold:

  * an ACCESS payload with ``is_admin`` true — every existing access fixture
    has it false, so nothing could render the controls;
  * ``POST /api/bets/market`` — ``{status, market_id}``;
  * ``POST /api/bets/market/{id}/settle`` — the payout summary.

Same contract as ``test_availability_slice2_fixtures``: each shape is
produced by replaying the real handler, then diffed against the JSON under
``src/app/pages/__fixtures__/``. Regenerate with ``UPDATE_FIXTURES=1``; the
git diff is the review.

⛔⛔ THE ADMIN FIXTURE CANNOT USE THE HOUSE TEST USER. Every other
availability fixture is recorded as ``website_user_id: -1``, and ``-1`` can
never be an admin: ``configured_admin_ids`` keeps a token only when
``token.isdigit()`` (auth_helpers.py:53-64), and ``"-1".isdigit()`` is False.
A fixture generated with the usual id would therefore have come back
``is_admin: false``, the page would have rendered nothing, and the test would
have passed for a reason that has nothing to do with the code under it — the
same shape as an empty collection satisfying a guarantee. The admin tier uses
a positive id, and ``test_the_house_test_user_can_never_be_admin`` pins the
reason so a later reader does not "tidy" it back to -1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.unit.test_availability_router import FakeAvailabilityDB, _build_app, _login
from tests.unit.test_bets_router import _db, _req
from website.backend.middleware.auth_helpers import configured_admin_ids
from website.backend.routers.bets_router import open_market, settle_market

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "website" / "frontend" / "src" / "app" / "pages" / "__fixtures__"
UPDATE = os.getenv("UPDATE_FIXTURES") == "1"

#: A positive id, for the isdigit reason in this module's docstring.
ADMIN_ID = 424242


def _check(name: str, produced: dict) -> None:
    """Compare (or, under UPDATE_FIXTURES=1, write) one fixture."""
    path = FIXTURES / name
    if UPDATE:
        path.write_text(json.dumps(produced, separators=(",", ":")) + "\n", encoding="utf-8")
    assert path.exists(), f"{name} missing — run with UPDATE_FIXTURES=1"
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed == produced, (
        f"{name} drifted from the handler — UPDATE_FIXTURES=1 regenerates; the diff is the review"
    )


def test_the_house_test_user_can_never_be_admin(monkeypatch):
    """The control for this module's central assumption, and it must fail.

    If a later change made ``-1`` admissible, the admin fixture could quietly
    be regenerated with the house user and every slice-3 UI test would then be
    asserting against a non-admin payload while still passing.
    """
    monkeypatch.setenv("WEBSITE_ADMIN_DISCORD_IDS", "-1,424242")
    ids = configured_admin_ids()
    assert -1 not in ids, "a negative id became admissible — the admin fixture's id choice is now unsound"
    assert ADMIN_ID in ids


@pytest.mark.asyncio
async def test_admin_access_fixture(monkeypatch):
    monkeypatch.setenv("WEBSITE_ADMIN_DISCORD_IDS", str(ADMIN_ID))
    db = FakeAvailabilityDB()
    db.player_links.add(ADMIN_ID)
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=ADMIN_ID, username="e2e-admin", linked=True)
        res = await client.get("/api/availability/access")
        assert res.status_code == 200
        body = res.json()
        # The point of the fixture, asserted before it is written: a
        # regenerated file that says False would otherwise be committed
        # silently and every UI test below would go vacuous.
        assert body["is_admin"] is True, f"the replay did not produce an admin: {body}"
        _check("api_availability_access_admin.json", body)


@pytest.mark.asyncio
async def test_open_market_fixture():
    db = _db()
    db.fetch_one = AsyncMock(return_value=(4242,))
    # _has_roster_cols probes the schema; False keeps the insert to the columns
    # that exist before migration 011, which is the shape the response does not
    # depend on either way.
    db.fetch_all = AsyncMock(return_value=[])
    res = await open_market(_req(ADMIN_ID), {}, {"id": ADMIN_ID}, db)
    _check("api_bets_market_open.json", res)


@pytest.mark.asyncio
async def test_settle_market_fixture():
    """A settle with a real winner AND a loser: total_pool > winning_pool, so
    the fixture shows both figures differing. A void or a no-winner settle
    would set them equal and hide the distinction the type documents."""
    db = _db()
    db.fetch_one = AsyncMock(return_value=(1, None, "open"))
    db.fetch_all = AsyncMock(return_value=[
        (10, 101, "team_a", 30),
        (11, 102, "team_b", 20),
    ])
    res = await settle_market(_req(ADMIN_ID), 1, {"outcome": "team_a"}, {"id": ADMIN_ID}, db)
    assert res["total_pool"] != res["winning_pool"], "the fixture must show the two pools differing"
    assert res["refunded"] is False
    _check("api_bets_market_settle.json", res)
