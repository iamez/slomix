"""`types=` on /storytelling/moments (docs/design/20 §7 slice 5): the filter
runs on the full pool BEFORE the director's cut, the cache key carries it,
and an unknown type is a 422 — a typo must not read as "no escorts"."""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import storytelling_router
from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling import moments as moments_module
from website.backend.services.storytelling.moments import _MomentsMixin

START = 1787858291


def _m(mtype: str, stars: int, player: str, t: int = 0) -> dict:
    return {"type": mtype, "impact_stars": stars, "player": player, "time_ms": t,
            "round_number": 1, "map_name": "supply", "narrative": f"{player} {mtype}", "detail": {}}


POOL = [_m("team_wipe", 5, f"w{i}", i * 1000) for i in range(12)] + [
    _m("escort_mover", 3, "squAziii", 700000), _m("escort_mover", 4, "olz", 650000),
]


def _scope() -> GamingSessionScope:
    return GamingSessionScope(
        gaming_session_id=154, dates=("2026-08-27",),
        round_keys=((START, "supply", 1),), accepted_round_count=1, distinct_map_names=("supply",),
    )


def _svc(pool):
    svc = _MomentsMixin.__new__(_MomentsMixin)

    async def collect(_scope):
        return [dict(m) for m in pool]

    svc._collect_moments = collect  # noqa: SLF001 — the seam above the detectors, as the cache tests use it
    return svc


@pytest.fixture(autouse=True)
def _clear_cache():
    moments_module._MOMENTS_CACHE.clear()  # noqa: SLF001
    yield
    moments_module._MOMENTS_CACHE.clear()  # noqa: SLF001


def test_the_filter_runs_on_the_pool_before_the_cut():
    svc = _svc(POOL)
    cut = asyncio.run(svc.detect_moments(_scope(), limit=10))
    assert all(m["type"] == "team_wipe" for m in cut) and len(cut) == 10   # the escorts lose the default cut
    escorts = asyncio.run(svc.detect_moments(_scope(), limit=10, types=("escort_mover",)))
    assert [m["player"] for m in escorts] == ["olz", "squAziii"]           # both, 4★ first
    assert all(m["type"] == "escort_mover" for m in escorts)


def test_the_cache_key_carries_the_types():
    svc = _svc(POOL)
    a = asyncio.run(svc.detect_moments(_scope(), limit=10))
    b = asyncio.run(svc.detect_moments(_scope(), limit=10, types=("escort_mover",)))
    c = asyncio.run(svc.detect_moments(_scope(), limit=10, types=("escort_mover",)))
    assert a != b and b is c   # two answers for two keys; the second escort call is the cached object
    keys = set(moments_module._MOMENTS_CACHE)  # noqa: SLF001
    assert (154, 10) in keys and (154, 10, ("escort_mover",)) in keys   # the old key shape survives


class _FakeService:
    def __init__(self, db):
        self.calls = []

    async def detect_moments(self, scope, limit=10, types=None):
        self.calls.append((limit, types))
        pool = POOL if types is None else [m for m in POOL if m["type"] in set(types)]
        return pool[:limit]


async def _get(path: str):
    app = FastAPI()
    app.include_router(storytelling_router.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: object()

    async def scope_override():
        return _scope()

    app.dependency_overrides[storytelling_router.resolve_story_scope] = scope_override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.get(path)


def test_the_router_keeps_only_the_requested_types_and_echoes_them(monkeypatch):
    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeService)
    r = asyncio.run(_get("/api/storytelling/moments?gaming_session_id=154&types=escort_mover"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["types"] == ["escort_mover"] and body["total"] == 2
    assert {m["type"] for m in body["moments"]} == {"escort_mover"}
    # Without the parameter the answer keeps its old shape: no `types` key at all.
    r2 = asyncio.run(_get("/api/storytelling/moments?gaming_session_id=154"))
    assert r2.status_code == 200 and "types" not in r2.json()


def test_an_unknown_type_is_a_422_that_names_the_known_ones(monkeypatch):
    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeService)
    r = asyncio.run(_get("/api/storytelling/moments?gaming_session_id=154&types=escort_mover,nope"))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["unknown_types"] == ["nope"] and "escort_mover" in detail["known_types"]
    # An empty list after trimming is a 422 too — `types=` is not "no filter".
    r2 = asyncio.run(_get("/api/storytelling/moments?gaming_session_id=154&types=,"))
    assert r2.status_code == 422
