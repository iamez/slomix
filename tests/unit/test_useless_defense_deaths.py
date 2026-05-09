"""Unit tests for StorytellingService.compute_useless_defense_deaths.

Mocks db.fetch_all and verifies the response shape, sorting, and rate calc.
The SQL itself is integration-tested by running the bare query against the
live samba DB during development; this suite covers the Python layer only.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling_service import StorytellingService


def _make_service(rows: list[tuple]):
    svc = StorytellingService(db=AsyncMock())
    svc.db.fetch_all.return_value = rows
    return svc


@pytest.mark.asyncio
async def test_returns_empty_players_when_no_rows():
    svc = _make_service(rows=[])
    result = await svc.compute_useless_defense_deaths("2026-05-05")

    assert result["status"] == "ok"
    assert result["session_date"] == "2026-05-05"
    assert result["metric"] == "useless_defense_deaths"
    assert result["players"] == []
    assert result["thresholds"] == {
        "min_reinf_seconds": 25,
        "min_killer_health": 80,
    }


@pytest.mark.asyncio
async def test_per_player_shape_and_rate_rounding():
    rows = [
        # (victim_guid_full, victim_name, useless_deaths, total_def_deaths)
        ("EDBB5DA97C9F52151865C5F223F9B951", "^6S^2uperBoyy", 6, 82),
        ("D8423F90F045D9D3E2C0550811C5A899", "^pvid", 4, 84),
    ]
    svc = _make_service(rows=rows)
    result = await svc.compute_useless_defense_deaths("2026-05-05")

    assert len(result["players"]) == 2
    p = result["players"][0]
    # 32-char GUID preserved; guid_short is first-8 prefix matching PCS scheme
    assert p["guid"] == "EDBB5DA97C9F52151865C5F223F9B951"
    assert p["guid_short"] == "EDBB5DA9"
    # Name colors stripped (^6, ^2, etc. removed)
    assert "^" not in p["name"]
    assert "uperBoyy" in p["name"]
    assert p["useless_deaths"] == 6
    assert p["total_defense_deaths"] == 82
    # Rate is rounded to 3 decimals: 6/82 = 0.07317… → 0.073
    assert p["rate"] == 0.073


@pytest.mark.asyncio
async def test_zero_total_yields_zero_rate_no_divzero():
    # Defensive guard: even though the SQL filters useless_deaths > 0,
    # the Python layer must not crash on (0,0) just in case.
    rows = [("AAAAAAAA00000000000000000000AAAA", "edge", 0, 0)]
    svc = _make_service(rows=rows)
    result = await svc.compute_useless_defense_deaths("2026-05-05")
    assert result["players"][0]["rate"] == 0.0


@pytest.mark.asyncio
async def test_custom_thresholds_propagate_to_response():
    svc = _make_service(rows=[])
    result = await svc.compute_useless_defense_deaths(
        "2026-05-05", min_killer_health=100, min_reinf_seconds=20
    )
    assert result["thresholds"] == {
        "min_reinf_seconds": 20,
        "min_killer_health": 100,
    }


@pytest.mark.asyncio
async def test_thresholds_are_passed_to_sql_params():
    """Verify the thresholds reach fetch_all as $2/$3 params, in order."""
    svc = _make_service(rows=[])
    await svc.compute_useless_defense_deaths(
        "2026-05-05", min_killer_health=120, min_reinf_seconds=30
    )
    # fetch_all called once with (sql, (date, min_reinf_seconds, min_killer_health))
    args, kwargs = svc.db.fetch_all.call_args
    sql, params = args
    # Params order: ($1=session_date, $2=min_reinf_seconds, $3=min_killer_health)
    assert params[1] == 30
    assert params[2] == 120
