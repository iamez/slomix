"""Phase 6, slice 2 — the backend is the arbiter of the hand-written types.

No availability/bets handler declares a response_model, so openapi carries
no schema for them and the manual-type drift checker has nothing to check.
The app's fixtures for the WRITE responses (link-token, subscriptions POST/
DELETE, campaigns POST, bet POST) and for market shapes the dev server does
not currently hold (an OPEN market with a pool, a SETTLED one) are therefore
produced here, by replaying each handler in its existing unit harness, and
diffed against the committed JSON under src/app/pages/__fixtures__/.

Regenerate with UPDATE_FIXTURES=1 (the diff in git is the review). Values a
replay cannot hold still — the random token, every timestamp — are pinned
to sentinels before the comparison, so a fixture changes only when the
SHAPE or a deterministic value changes.

The linked-tier GET fixtures (*_linked.json, promotions_preview.json) are
recorded from the live dev server as the e2e sentinel instead
(scripts/record_api_corpus.py --sentinel) — this file checks those against
the same harness for key parity, so a recording and a replay can never
disagree about a field silently.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.unit.test_availability_promotions_router import FakePromotionDB
from tests.unit.test_availability_promotions_router import _build_app as _build_promo_app
from tests.unit.test_availability_promotions_router import _login as _promo_login
from tests.unit.test_availability_router import FakeAvailabilityDB, _build_app, _login, _xhr_headers
from tests.unit.test_bets_router import _db, _pb_market, _req
from website.backend.routers import availability as availability_router
from website.backend.routers.bets_router import get_current_market, place_bet

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "website" / "frontend" / "src" / "app" / "pages" / "__fixtures__"
UPDATE = os.getenv("UPDATE_FIXTURES") == "1"

# Keys whose values a replay cannot hold still. Pinned, not dropped: the
# fixture must still SHOW the field exists and what type it carries.
_VOLATILE = {
    "token": "e2e-link-token-value",
    "expires_at": "2026-02-19T12:30:00",
    "created_at": "2026-02-19T12:00:00",
    "updated_at": "2026-02-19T12:00:00",
    "run_at": "2026-02-19T19:45:00+00:00",
    "sent_at": None,
    "reminder_2045_cet": "2026-02-19T19:45:00+00:00",
    "start_2100_cet": "2026-02-19T20:00:00+00:00",
    "voice_check_after_start": "2026-02-19T20:05:00+00:00",
}


def _pin(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (_VOLATILE[k] if k in _VOLATILE and v is not None else _pin(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_pin(v) for v in value]
    return value


def _check(name: str, produced: dict) -> None:
    """Compare (or, under UPDATE_FIXTURES=1, write) one fixture."""
    path = FIXTURES / name
    expected = _pin(produced)
    if UPDATE:
        path.write_text(json.dumps(expected, separators=(",", ":")) + "\n", encoding="utf-8")
    assert path.exists(), f"{name} missing — run with UPDATE_FIXTURES=1"
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed == expected, (
        f"{name} drifted from the handler — UPDATE_FIXTURES=1 regenerates; the diff is the review"
    )


@pytest.mark.asyncio
async def test_link_token_and_subscription_write_fixtures():
    db = FakeAvailabilityDB()
    db.player_links.add(-1)
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, user_id=-1, username="e2e-owner", linked=True)

        token = await client.post(
            "/api/availability/link-token",
            json={"channel_type": "telegram", "ttl_minutes": 30},
            headers=_xhr_headers(),
        )
        assert token.status_code == 200
        _check("api_availability_link_token.json", token.json())

        # The 429 body is the sentence the page renders verbatim.
        again = await client.post(
            "/api/availability/link-token",
            json={"channel_type": "telegram", "ttl_minutes": 30},
            headers=_xhr_headers(),
        )
        assert again.status_code == 429
        assert again.json()["detail"].startswith("Link token was generated recently. Try again in ")

        # Confirm through the bot's callback so the subscription POST has a
        # verified channel to enable.
        confirm = await client.post(
            "/api/availability/link-confirm",
            json={"channel_type": "telegram", "token": token.json()["token"], "channel_address": "123456789"},
        )
        assert confirm.status_code == 200

        sub = await client.post(
            "/api/availability/subscriptions",
            json={"channel_type": "telegram", "enabled": True, "preferences": {}},
            headers=_xhr_headers(),
        )
        assert sub.status_code == 200
        _check("api_availability_subscriptions_post.json", sub.json())

        # Settings POST answers with the same payload as GET — pinned as key
        # parity with the live-recorded linked GET, not as a second fixture.
        settings = await client.post(
            "/api/availability/settings",
            json={"sound_enabled": False, "timezone": "Europe/Ljubljana", "telegram_notify": True},
            headers=_xhr_headers(),
        )
        assert settings.status_code == 200
        recorded = json.loads((FIXTURES / "api_availability_settings_linked.json").read_text(encoding="utf-8"))
        assert set(settings.json()) == set(recorded)
        assert [s["channel_type"] for s in settings.json()["subscriptions"]] == [
            s["channel_type"] for s in recorded["subscriptions"]
        ]
        assert set(settings.json()["subscriptions"][0]) == set(recorded["subscriptions"][0])

        gone = await client.delete("/api/availability/subscriptions/telegram", headers=_xhr_headers())
        assert gone.status_code == 200
        _check("api_availability_subscriptions_channel_type_delete.json", gone.json())

        # And the recorded subscriptions GET has the harness's keys.
        listed = await client.get("/api/availability/subscriptions")
        recorded_subs = json.loads(
            (FIXTURES / "api_availability_subscriptions_linked.json").read_text(encoding="utf-8")
        )
        assert set(listed.json()) == set(recorded_subs)
        assert set(listed.json()["subscriptions"][0]) == set(recorded_subs["subscriptions"][0])


@pytest.mark.asyncio
async def test_promotion_preview_and_campaign_fixtures(monkeypatch):
    db = FakePromotionDB()
    db.current_date = date(2026, 2, 19)
    for uid, name, status, opt_in in (
        (11, "Alpha", "LOOKING", True),
        (12, "Bravo", "AVAILABLE", True),
        (13, "Charlie", "MAYBE", True),
        (14, "Delta", "LOOKING", False),
    ):
        db.seed_availability(user_id=uid, user_name=name, entry_date=db.current_date, status=status)
        db.seed_preference(user_id=uid, allow_promotions=opt_in, preferred_channel="any")
        db.player_links[uid] = {"player_name": name, "discord_username": name.lower()}

    # configured_promoter_ids() keeps only isdigit() tokens, so the sentinel's
    # -1 cannot be a configured promoter here; on the dev box it is one via
    # user_permissions.tier instead (scripts/e2e_sentinel_rows.py). The
    # promoter's id appears in no preview/campaign body, so 77 is fine.
    monkeypatch.setenv("PROMOTER_DISCORD_IDS", "77")
    transport = httpx.ASGITransport(app=_build_promo_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _promo_login(client, user_id=77, linked=True)

        preview = await client.get(
            "/api/availability/promotions/preview",
            params={"include_available": "true", "include_maybe": "true"},
        )
        assert preview.status_code == 200
        body = preview.json()
        # Delta opted out — the preview must not name them.
        assert {r["display_name"] for r in body["recipients_preview"]} == {"Alpha", "Bravo", "Charlie"}
        # The fake returns rows in dict order, not the SQL ORDER BY — sort so
        # the fixture is stable across runs.
        body["recipients_preview"].sort(key=lambda r: r["display_name"])
        _check("api_availability_promotions_preview_with_recipients.json", body)
        # Same keys as the live recording (which had zero recipients that day).
        recorded = json.loads((FIXTURES / "api_availability_promotions_preview.json").read_text(encoding="utf-8"))
        assert set(body) == set(recorded)

        created = await client.post(
            "/api/availability/promotions/campaigns",
            json={"include_available": True, "include_maybe": False, "dry_run": False},
            headers=_xhr_headers(),
        )
        assert created.status_code == 200
        _check("api_availability_promotions_campaigns.json", created.json())

        second = await client.post(
            "/api/availability/promotions/campaigns",
            json={"include_available": True, "include_maybe": False, "dry_run": False},
            headers=_xhr_headers(),
        )
        assert second.status_code == 409
        assert "already" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_active_campaign_payload_fixture():
    """GET /promotions/campaign with a campaign: _campaign_payload replayed on
    the row and job tuples it selects (the promotions fake stops at inserts)."""
    created = datetime(2026, 2, 19, 12, 0, 0, tzinfo=UTC)
    row = (
        7, date(2026, 2, 19), "Europe/Ljubljana", "21:00:00", -1, -1,
        False, True, False, "scheduled", 3, {"discord": 2, "telegram": 1, "signal": 0}, [], created, created,
    )
    run_at = datetime(2026, 2, 19, 19, 45, 0, tzinfo=UTC)
    jobs = [
        (1, "send_reminder_2045", run_at, "pending", 0, 5, None, None),
        (2, "send_start_2100", run_at + timedelta(minutes=15), "pending", 0, 5, None, None),
        (3, "voice_check_2100", run_at + timedelta(minutes=20), "pending", 0, 5, None, None),
    ]
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=row)
    db.fetch_all = AsyncMock(return_value=jobs)
    payload = await availability_router._campaign_payload(db, 7)  # noqa: SLF001 — the handler's own serializer IS the subject
    _check("api_availability_promotions_campaign_active.json", {"campaign": payload})


@pytest.mark.asyncio
async def test_market_fixtures_open_settled_and_bet():
    market_open = (7, 150, date(2026, 9, 2), "Axis side", "Allied side", "open", None, 200)
    pool_rows = [("team_a", 120, 3), ("team_b", 80, 2)]

    db = _db()
    db.fetch_one = AsyncMock(side_effect=[market_open, ("team_a", 20, 0, "open")])
    db.fetch_all = AsyncMock(return_value=pool_rows)
    current = await get_current_market(_req(-1), db)
    assert current["market"]["pool"]["total_pool"] == 200
    assert current["market"]["my_bet"]["status"] == "open"
    _check("api_bets_market_current_open.json", current)

    db = _db()
    db.fetch_one = AsyncMock(side_effect=[market_open, None])
    db.fetch_all = AsyncMock(return_value=pool_rows)
    unbet = await get_current_market(_req(-1), db)
    assert unbet["market"]["my_bet"] is None
    _check("api_bets_market_current_open_no_bet.json", unbet)

    market_settled = (7, 150, date(2026, 9, 2), "Axis side", "Allied side", "settled", "team_b", 200)
    db = _db()
    db.fetch_one = AsyncMock(side_effect=[market_settled, ("team_a", 20, 0, "lost")])
    db.fetch_all = AsyncMock(return_value=pool_rows)
    settled = await get_current_market(_req(-1), db)
    assert settled["market"]["outcome"] == "team_b"
    _check("api_bets_market_current_settled.json", settled)

    # place_bet: market lock, wallet balance, no existing bet -> new pool.
    db = _db()
    db.fetch_one = AsyncMock(side_effect=[_pb_market(mid=7), (100,), None])
    db.fetch_all = AsyncMock(return_value=[("team_a", 140, 4), ("team_b", 80, 2)])
    placed = await place_bet(_req(-1), 7, {"choice": "team_a", "amount": 20}, {"id": -1}, db)
    assert placed["balance"] == 80
    _check("api_bets_market_market_id_bet.json", placed)
