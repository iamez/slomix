"""OIS — Objective Impact Score v0 (owner answer A2).

KIS stays kill-only; OIS credits the non-kill objective work. Pin the scoring
contract and the session aggregation, including the contested-construction
multiplier and bot/validity gates.
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling.ois import (
    CONSTRUCTION_BASE,
    CONTESTED_MULT,
    DEFUSE_BASE,
    DOC_RETURN_BASE,
    RETURN_FAST_MULT,
    RETURN_SLOW_MULT,
    OisService,
    construction_score,
    defuse_score,
    doc_return_score,
)


def test_doc_return_speed_tiers():
    assert doc_return_score(500) == DOC_RETURN_BASE * RETURN_FAST_MULT
    assert doc_return_score(5_000) == DOC_RETURN_BASE
    assert doc_return_score(20_000) == DOC_RETURN_BASE * RETURN_SLOW_MULT
    assert doc_return_score(None) == DOC_RETURN_BASE  # unknown delay = neutral


def test_defuse_and_construction():
    assert defuse_score() == DEFUSE_BASE
    assert construction_score(contested=False) == CONSTRUCTION_BASE
    assert construction_score(contested=True) == CONSTRUCTION_BASE * CONTESTED_MULT


def test_kis_scale_alignment():
    """A fast doc return must be worth about a carrier kill (KIS 3.0),
    never more than a carrier chain (5.0) — OIS lives on the KIS scale."""
    assert 3.0 <= doc_return_score(0) <= 5.0
    assert 1.0 <= construction_score(True) <= 3.0


class FakeDB:
    def __init__(self):
        self.returns = [("AAAA1111", "engi", 1_000)]           # fast return
        # (g8, name, event_type, round_start_unix, round_number, map_name,
        # event_time) — canonical round key includes map_name/round_number
        # (codex, PR #478 follow-up audit finding #4)
        self.events = [
            ("BBBB2222", "defuser", "dynamite_defuse", 111, 1, "te_escape2", 50_000),
            ("AAAA1111", "engi", "construction_complete", 111, 1, "te_escape2", 52_000),
        ]
        # (round_start_unix, map_name, round_number, kill_time_ms)
        self.kills = [(111, "te_escape2", 1, 55_000)]  # within 10s of the construction

    async def fetch_all(self, query, params=()):
        if "proximity_carrier_return" in query:
            return self.returns
        if "proximity_construction_event" in query:
            return self.events
        if "storytelling_kill_impact" in query:
            return self.kills
        return []


@pytest.mark.asyncio
async def test_session_aggregation():
    svc = OisService(FakeDB())
    rows = await svc.compute_session_ois("2026-07-07")
    by_guid = {r["player_guid"]: r for r in rows}

    engi = by_guid["AAAA1111"]
    assert engi["doc_returns"] == 1
    assert engi["constructions"] == 1
    expected = doc_return_score(1_000) + construction_score(contested=True)
    assert engi["ois_total"] == pytest.approx(expected, abs=1e-3)

    defuser = by_guid["BBBB2222"]
    assert defuser["defuses"] == 1
    assert defuser["ois_total"] == pytest.approx(DEFUSE_BASE)

    assert rows[0]["ois_total"] >= rows[-1]["ois_total"]  # sorted desc
    assert all(r["formula_version"] == "ois-v0.1" for r in rows)


@pytest.mark.asyncio
async def test_empty_session():
    class EmptyDB(FakeDB):
        def __init__(self):
            self.returns, self.events, self.kills = [], [], []

    rows = await OisService(EmptyDB()).compute_session_ois("2026-07-07")
    assert rows == []


class CollidingRoundDB(FakeDB):
    """Two DIFFERENT rounds sharing the same round_start_unix (collision) —
    the canonical key (round_start_unix, map_name, round_number) must keep
    them separate (codex, PR #478 follow-up audit finding #4)."""

    def __init__(self):
        super().__init__()
        self.returns = []  # isolate the contested-construction signal
        # construction on te_escape2/round_start_unix=111 — no kill nearby
        # on THIS map/round; a kill exists at the SAME round_start_unix but
        # a DIFFERENT map, which must NOT count as contested.
        self.events = [
            ("AAAA1111", "engi", "construction_complete", 111, 1, "te_escape2", 52_000),
        ]
        self.kills = [(111, "sw_goldrush_te", 1, 55_000)]  # different map!


@pytest.mark.asyncio
async def test_contested_does_not_cross_maps_on_shared_round_start_unix():
    rows = await OisService(CollidingRoundDB()).compute_session_ois("2026-07-07")
    engi = next(r for r in rows if r["player_guid"] == "AAAA1111")
    # must score as UNCONTESTED — the kill on the other map must not match
    assert engi["ois_total"] == pytest.approx(construction_score(contested=False))
