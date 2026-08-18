"""/skill/composite must apply the same round-quality gate as every other KPI.

Excluding bots by NAME is not the same thing. Session 121 carries one round
flagged `is_valid = FALSE` whose 53 kills inflated the composite by 8-16 % for
the four real players in it (SuperBoyy 147 -> 135 kills, qmr 128 -> 108) —
invisible without the gate, because those players are not bots.

The gate lives in SQL fragments chosen by the scope branch, so these tests
assert on the SQL the endpoint builds rather than on a fake result set.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import skill_router


class CapturingDB:
    """Captures every SQL statement, returns nothing useful."""

    def __init__(self):
        self.queries: list[str] = []

    async def fetch_all(self, query: str, params=None) -> list:
        self.queries.append(" ".join(query.split()))
        return []

    async def fetch_one(self, query: str, params=None) -> Any:
        self.queries.append(" ".join(query.split()))
        return ("2026-08-11",)

    async def fetch_val(self, query: str, params=None) -> Any:
        self.queries.append(" ".join(query.split()))
        return None


def _build_app(db: CapturingDB) -> FastAPI:
    app = FastAPI()

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(skill_router.router, prefix="/api")
    return app


async def _call(db: CapturingDB, query: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(f"/api/skill/composite{query}")


def _joined(db: CapturingDB) -> str:
    return "\n".join(db.queries)


@pytest.mark.asyncio
async def test_gsid_scope_excludes_invalid_and_bot_rounds():
    db = CapturingDB()
    resp = await _call(db, "?gaming_session_id=121")

    assert resp.status_code == 200
    sql = _joined(db)
    assert "r.is_valid IS DISTINCT FROM FALSE" in sql
    assert "r.is_bot_round IS DISTINCT FROM TRUE" in sql
    # The proximity round set is gated too, not only the PCS aggregate — the
    # metrics are built from both.
    assert "is_valid IS DISTINCT FROM FALSE" in sql.split("round_id IN (SELECT id FROM rounds")[1]


@pytest.mark.asyncio
async def test_legacy_date_scope_is_gated_as_well():
    """The date path cannot separate two sessions on one day — that is its
    known limitation — but an invalid round must not count on either path."""
    db = CapturingDB()
    resp = await _call(db, "?session_date=2026-08-11")

    assert resp.status_code == 200
    sql = _joined(db)
    assert "r.is_valid IS DISTINCT FROM FALSE" in sql
    assert "r.is_bot_round IS DISTINCT FROM TRUE" in sql
    assert "JOIN rounds r ON r.id = p.round_id" in sql


@pytest.mark.asyncio
async def test_bot_name_filters_are_kept_not_replaced():
    """The name filters catch bots inside rounds the bot flag never marked;
    the round gate catches invalid rounds full of real players. Both are needed."""
    db = CapturingDB()
    await _call(db, "?gaming_session_id=144")

    sql = _joined(db)
    assert "NOT LIKE 'OMNIBOT%'" in sql
    assert "NOT LIKE '[BOT]%'" in sql
