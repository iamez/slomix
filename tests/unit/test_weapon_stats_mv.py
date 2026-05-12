"""Tests for the A8 weapon_stats_mv feature flag + refresh helper."""

from __future__ import annotations

import pytest

from website.backend.routers import records_weapons as api_router
from website.backend.services import weapon_stats_mv_refresh as mv_module


class _FakeDB:
    """Minimal fake DB supporting fetch_all() / execute() with scripted behavior."""

    def __init__(self, rows=None, fetch_error=None, execute_error=None):
        self._rows = rows or []
        self._fetch_error = fetch_error
        self._execute_error = execute_error
        self.queries: list[str] = []
        self.executed: list[str] = []
        self._fetch_calls = 0

    async def fetch_all(self, query: str, params=()):
        self.queries.append(query)
        self._fetch_calls += 1
        # Raise only on the first call so a fallback can succeed.
        if self._fetch_error is not None and self._fetch_calls == 1:
            err = self._fetch_error
            self._fetch_error = None
            raise err
        return self._rows

    async def execute(self, query: str, params=()):
        self.executed.append(query)
        if self._execute_error is not None:
            err = self._execute_error
            self._execute_error = None
            raise err
        return None


# ---------------------------------------------------------------------------
# refresh_weapon_stats_mv
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_runs_concurrent_by_default():
    db = _FakeDB()
    ok = await mv_module.refresh_weapon_stats_mv(db)
    assert ok is True
    assert db.executed == ["REFRESH MATERIALIZED VIEW CONCURRENTLY weapon_stats_mv"]


@pytest.mark.asyncio
async def test_refresh_noop_when_mv_missing():
    db = _FakeDB(
        execute_error=Exception(
            'relation "weapon_stats_mv" does not exist'
        )
    )
    ok = await mv_module.refresh_weapon_stats_mv(db)
    assert ok is False  # graceful no-op


@pytest.mark.asyncio
async def test_refresh_falls_back_to_blocking_on_initial_populate():
    # First REFRESH CONCURRENTLY raises "has not been populated"; second
    # (non-concurrent) succeeds.
    db = _FakeDB(
        execute_error=Exception(
            "CONCURRENTLY cannot be used when the materialized view has "
            "not been populated"
        )
    )
    ok = await mv_module.refresh_weapon_stats_mv(db)
    assert ok is True
    assert db.executed == [
        "REFRESH MATERIALIZED VIEW CONCURRENTLY weapon_stats_mv",
        "REFRESH MATERIALIZED VIEW weapon_stats_mv",
    ]


@pytest.mark.asyncio
async def test_refresh_handles_none_db():
    ok = await mv_module.refresh_weapon_stats_mv(None)
    assert ok is False


@pytest.mark.asyncio
async def test_refresh_swallows_unexpected_errors():
    db = _FakeDB(execute_error=Exception("some unrelated transient db error"))
    ok = await mv_module.refresh_weapon_stats_mv(db)
    assert ok is False  # warning logged, no raise


# ---------------------------------------------------------------------------
# Feature flag parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("", False),
        ("nope", False),
    ],
)
def test_use_weapon_stats_mv_enabled(monkeypatch, raw, expected):
    monkeypatch.setenv("USE_WEAPON_STATS_MV", raw)
    assert mv_module.use_weapon_stats_mv_enabled() is expected


def test_use_weapon_stats_mv_default_off(monkeypatch):
    monkeypatch.delenv("USE_WEAPON_STATS_MV", raising=False)
    assert mv_module.use_weapon_stats_mv_enabled() is False


# ---------------------------------------------------------------------------
# Router integration — fallback when flag OFF (default behavior preserved)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_weapon_stats_falls_back_when_flag_off(monkeypatch):
    monkeypatch.setenv("USE_WEAPON_STATS_MV", "false")
    db = _FakeDB(
        [
            ("WS_MP40", 120, 32, 550, 300, 54.6),
            ("WS_THOMPSON", 90, 21, 400, 210, 52.5),
        ]
    )

    payload = await api_router.get_weapon_stats(period="all", limit=20, db=db)

    assert len(payload) == 2
    assert payload[0]["weapon_key"] == "mp40"
    # When flag is off, the router must hit the live table, not the MV.
    assert db.queries, "expected at least one query"
    assert all("weapon_comprehensive_stats" in q for q in db.queries)
    assert all("weapon_stats_mv" not in q for q in db.queries)


@pytest.mark.asyncio
async def test_get_weapon_stats_uses_mv_when_flag_on(monkeypatch):
    monkeypatch.setenv("USE_WEAPON_STATS_MV", "true")
    db = _FakeDB(
        [
            ("WS_MP40", 120, 32, 550, 300, 54.6),
        ]
    )

    payload = await api_router.get_weapon_stats(period="all", limit=20, db=db)

    assert len(payload) == 1
    assert payload[0]["weapon_key"] == "mp40"
    # MV-pathway query must reference weapon_stats_mv, not the live table.
    assert db.queries, "expected at least one query"
    assert db.queries[0].count("weapon_stats_mv") >= 1
    assert "weapon_comprehensive_stats" not in db.queries[0]


@pytest.mark.asyncio
async def test_get_weapon_stats_falls_back_when_mv_missing(monkeypatch):
    """If USE_WEAPON_STATS_MV=true but the MV does not exist, we must fall back."""
    monkeypatch.setenv("USE_WEAPON_STATS_MV", "true")
    db = _FakeDB(
        rows=[("WS_MP40", 120, 32, 550, 300, 54.6)],
        fetch_error=Exception('relation "weapon_stats_mv" does not exist'),
    )

    payload = await api_router.get_weapon_stats(period="all", limit=20, db=db)

    assert len(payload) == 1
    assert payload[0]["weapon_key"] == "mp40"
    # Two queries: MV (failed) then live fallback.
    assert len(db.queries) == 2
    assert "weapon_stats_mv" in db.queries[0]
    assert "weapon_comprehensive_stats" in db.queries[1]
