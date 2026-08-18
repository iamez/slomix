"""The recap must name the player the page's board puts first.

The Smart Stats page ranks players by win contribution (PWC) and falls back to
kill impact (KIS) only where PWC does not exist — sessions before March 2026
have no proximity data at all. The recap sentence, however, still named the KIS
leader. Measured against dev on 2026-08-16, **4 of the last 10 sessions** had a
different leader under each metric (141, 138, 136, 135; session 138: KIS said
`bronze`, PWC said `.lgz`), so heading and prose named two different players
for the same night.

These tests pin the choice, its fallback, and the sentence that reports it —
the number quoted has to be the number the pick was made by, or the same
disagreement reappears one level down.
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling_service import StorytellingService


class _Scope:
    gaming_session_id = 138
    dates = ("2026-07-21",)

    def round_key_arrays(self):
        return ([1_700_000_000], ["supply"], [1])

    def round_key_filter_sql(self, start):
        return f"(round_start_unix, map_name, round_number) IN (SELECT * FROM unnest(${start}))"


class _DB:
    """Only the maps-played query matters here; everything else returns empty."""

    async def fetch_all(self, query, params=()):
        if "FROM rounds" in " ".join(str(query).split()):
            return [("etl_supply",)]
        return []

    async def fetch_one(self, query, params=()):
        return None


# KIS leader and PWC leader are deliberately different players.
_KIS_BOARD = [
    {"guid": "AAAA1111" + "0" * 24, "name": "bronze", "total_kis": 418.0, "kills": 60},
    {"guid": "BBBB2222" + "0" * 24, "name": ".lgz", "total_kis": 250.0, "kills": 40},
]


def _service(pwc_players, *, pwc_raises=False, stats=None, archetypes=None):
    class Svc(StorytellingService):
        def __init__(self):
            self.db = _DB()

        async def compute_session_kis_for_gsid(self, gsid):
            return None

        async def get_kis_leaderboard(self, scope, limit=50):
            self.kis_limits = getattr(self, "kis_limits", [])
            self.kis_limits.append(limit)
            return list(_KIS_BOARD)

        async def classify_players(self, scope, board):
            return (
                archetypes if archetypes is not None else {
                    _KIS_BOARD[0]["guid"]: "frontline_warrior",
                    _KIS_BOARD[1]["guid"]: "objective_specialist",
                },
                stats if stats is not None else {
                    _KIS_BOARD[0]["guid"]: {"dpm": 300, "revives_given": 0},
                    _KIS_BOARD[1]["guid"]: {"dpm": 250, "revives_given": 0},
                },
            )

        async def compute_win_contribution(self, scope):
            if pwc_raises:
                raise RuntimeError("proximity tables unavailable")
            return {"players": list(pwc_players)}

        async def detect_moments(self, scope, limit=1):
            return []

        async def compute_team_synergy(self, scope):
            return {}

        async def _collect_session_arc(self, gsid, seed):
            return None

        async def _collect_human_thread(self, board, seed):
            return ""

    return Svc()


async def test_the_recap_names_the_win_contribution_leader_not_the_kis_leader():
    svc = _service([
        {"guid": _KIS_BOARD[1]["guid"], "name": ".lgz", "total_pwc": 2.14},
        {"guid": _KIS_BOARD[0]["guid"], "name": "bronze", "total_pwc": 1.90},
    ])

    out = await svc.generate_narrative(_Scope())

    assert ".lgz" in out["narrative"]
    assert "bronze" not in out["narrative"]
    # Classification is relative to the session average, so the board request
    # must be the WHOLE session (limit=0) — a page size here would make the
    # averages, and every archetype derived from them, a function of it.
    assert svc.kis_limits == [0]


async def test_the_sentence_quotes_the_number_the_pick_was_made_by():
    """Naming by PWC while quoting KIS is the same bug one level down."""
    svc = _service([{"guid": _KIS_BOARD[1]["guid"], "name": ".lgz", "total_pwc": 2.14}])

    narrative = (await svc.generate_narrative(_Scope()))["narrative"]

    assert "2.14 win contribution" in narrative
    assert "KIS" not in narrative


async def test_a_session_without_win_contribution_falls_back_to_kill_impact():
    """Proximity exists only from March 2026; before that the KIS board IS the
    board, and the page shows it that way."""
    svc = _service([])

    narrative = (await svc.generate_narrative(_Scope()))["narrative"]

    assert "bronze" in narrative
    assert "418 kill impact" in narrative


async def test_an_all_zero_win_contribution_board_also_falls_back():
    """`players` present but every total_pwc == 0 is not a ranking."""
    svc = _service([{"guid": _KIS_BOARD[1]["guid"], "name": ".lgz", "total_pwc": 0.0}])

    narrative = (await svc.generate_narrative(_Scope()))["narrative"]

    assert "418 kill impact" in narrative


async def test_a_failing_pwc_query_still_produces_a_recap():
    """Naming the KIS leader is wrong in 4 sessions of 10; raising is wrong in
    all of them."""
    svc = _service([], pwc_raises=True)

    out = await svc.generate_narrative(_Scope())

    assert out["status"] == "ok"
    assert "bronze" in out["narrative"]


async def test_the_guid_match_survives_the_short_form_the_two_tables_disagree_on():
    """KIS reads storytelling_kill_impact, PWC reads player_comprehensive_stats.
    The page matches them on the lowercased 8-char prefix; so must this."""
    svc = _service([{"guid": "bbbb2222", "name": ".lgz", "total_pwc": 2.14}])

    narrative = (await svc.generate_narrative(_Scope()))["narrative"]

    assert ".lgz" in narrative
    # the archetype came from the KIS entry it was matched to
    assert "objective specialist" in narrative


async def test_a_leader_with_no_tracked_kills_gets_no_invented_dpm():
    """A PWC leader absent from the KIS board has no PCS row here — "0 DPM"
    would read as a measurement instead of a missing one."""
    svc = _service([{"guid": "CCCC3333" + "0" * 24, "name": "newcomer", "total_pwc": 3.0}])

    narrative = (await svc.generate_narrative(_Scope()))["narrative"]

    assert "newcomer" in narrative
    assert "DPM" not in narrative
    assert "3.00 win contribution" in narrative


@pytest.mark.parametrize("seed_name", ["a", "bb", "ccc"])
async def test_every_phrasing_variant_carries_the_metric(seed_name):
    """Three variants exist to avoid template fatigue; a variant that dropped
    the number would silently un-say what the pick was based on."""
    from website.backend.services.storytelling.narrative import (
        _MVP_LEADS,
        _MVP_LEADS_NO_DPM,
    )

    for template in _MVP_LEADS + _MVP_LEADS_NO_DPM:
        assert "{metric}" in template
        assert "KIS" not in template
