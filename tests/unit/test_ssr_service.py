"""SSR v0 — Situational Skill Rating aggregate (owner answer A4).

Pin the group-relative semantics: tie-aware percentiles, min-session gate,
partial coverage (missing components average over what exists), and the
lower-is-better inversion for the ms metrics.
"""
from __future__ import annotations

import pytest

from website.backend.services.ssr_service import (
    MIN_SESSIONS,
    SsrService,
    _pct_ranks,
)


def test_pct_ranks_tie_aware_and_inverted():
    pcts = _pct_ranks({"a": 10.0, "b": 20.0, "c": 20.0, "d": 40.0})
    assert pcts["d"] == 1.0
    assert pcts["a"] == 0.0
    assert pcts["b"] == pcts["c"] == pytest.approx(0.5, abs=1e-6)

    ms = _pct_ranks({"fast": 200.0, "slow": 900.0}, lower_is_better=True)
    assert ms["fast"] == 1.0 and ms["slow"] == 0.0


class FakeDB:
    """Three rated players (>=MIN_SESSIONS) + one below the gate."""

    async def fetch_all(self, query, params=()):
        if "COUNT(DISTINCT r.gaming_session_id)" in query:
            return [("AAAA1111", "alpha", MIN_SESSIONS + 5),
                    ("BBBB2222", "bravo", MIN_SESSIONS),
                    ("CCCC3333", "^1char^7lie", MIN_SESSIONS + 1),
                    ("DDDD4444", "rookie", MIN_SESSIONS - 1)]
        if "is_carrier_kill OR is_during_push" in query:
            return [("AAAA1111", 100.0, 50.0),   # share 0.5
                    ("BBBB2222", 100.0, 20.0),   # share 0.2
                    ("DDDD4444", 100.0, 90.0)]   # below gate -> ignored
        if "proximity_combat_position" in query:
            return [("AAAA1111", 30.0), ("CCCC3333", 10.0)]
        if "proximity_carrier_return" in query:
            return [("BBBB2222", 4)]
        if "proximity_construction_event" in query:
            return [("BBBB2222", "dynamite_defuse", 2)]
        if "proximity_kill_outcome" in query and "gibbed" in query:
            return [("AAAA1111", 0.4), ("BBBB2222", 0.2), ("CCCC3333", 0.3)]
        if "proximity_aim_lock" in query:
            return [("AAAA1111", 850.0), ("CCCC3333", 1100.0)]
        if "player_track" in query:
            return [("AAAA1111", 225.0), ("BBBB2222", 150.0)]
        return []


@pytest.mark.asyncio
async def test_compute_aggregates_group_relative():
    res = await SsrService(FakeDB()).compute()
    assert res["formula_version"] == "ssr-v0.1"
    by = {p["player_guid"]: p for p in res["players"]}

    assert "DDDD4444" not in by, "below min-session gate must not be rated"
    assert res["rated"] == 3

    alpha = by["AAAA1111"]
    # alpha has every component except OIS (no objective events in fixture)
    assert alpha["coverage"] == "5/6"
    assert alpha["components"]["ois_ps"]["pct"] is None
    # bravo is the only OIS holder -> pct 1.0
    assert by["BBBB2222"]["components"]["ois_ps"]["pct"] == 1.0
    # spawn: bravo 150 beats alpha 225 (lower is better)
    assert alpha["components"]["spawn_ready_ms"]["pct"] == 0.0
    assert by["BBBB2222"]["components"]["spawn_ready_ms"]["pct"] == 1.0
    # acq: alpha 850 beats charlie 1100
    assert alpha["components"]["target_acq_ms"]["pct"] == 1.0

    # coverage gate: a player with <3 components must not be rated
    assert all(int(p["coverage"].split("/")[0]) >= 3 for p in res["players"])

    charlie = by["CCCC3333"]
    assert charlie["name"] == "charlie" or "^" not in charlie["name"]
    # charlie lacks share/ois/spawn -> partial coverage, still rated
    assert charlie["coverage"] != "6/6"
    assert 0.0 <= charlie["ssr"] <= 1.0

    ssrs = [p["ssr"] for p in res["players"]]
    assert ssrs == sorted(ssrs, reverse=True)


@pytest.mark.asyncio
async def test_empty_db():
    class Empty:
        async def fetch_all(self, q, p=()):
            return []
    res = await SsrService(Empty()).compute()
    assert res["rated"] == 0 and res["players"] == []
