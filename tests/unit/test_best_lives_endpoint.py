"""Unit tests for the Life Cards transform (Good Night plan rank 9).

The kills-per-life ranking lives in SQL; these cover the pure Python transform
`_build_life_cards` (colour stripping, life-seconds rounding, narrative) and the
`_parse_date` guard. The endpoint itself is rate-limited (@limiter.limit needs a
real Request), so we test the extracted helper, not the decorated coroutine.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.storytelling_router import _build_life_cards, _parse_date


def _row(**kw):
    base = {"guid": "ABC12345", "name": "^1.lgz", "map_name": "etl_sp_delivery",
            "round_number": 2, "life_ms": 59000, "kills": 8}
    base.update(kw)
    return base


class TestBuildLifeCards:
    def test_builds_cards(self):
        cards = _build_life_cards([_row(), _row(name="qmr", kills=7, life_ms=158000,
                                               map_name="sw_goldrush_te", guid="DEF")])
        assert len(cards) == 2
        first = cards[0]
        assert first["name"] == ".lgz"          # ET colour codes stripped
        assert first["kills"] == 8
        assert first["life_seconds"] == 59        # 59000ms -> 59s
        assert first["guid"] == "ABC12345"
        assert "8 kills in one life (59s)" in first["narrative"]
        assert "etl sp delivery" in first["narrative"]  # underscores humanised

    def test_guid_shortened_for_profile_route(self):
        # 32-char proximity GUID -> 8-char so the #/profile link resolves against
        # the 8-char player_comprehensive_stats GUID.
        card = _build_life_cards([_row(guid="1C747DF1A037D2AFECCB6ED063DF44E7")])[0]
        assert card["guid"] == "1C747DF1"

    def test_empty(self):
        assert _build_life_cards([]) == []
        assert _build_life_cards(None) == []

    def test_rounds_life_seconds(self):
        assert _build_life_cards([_row(life_ms=59600)])[0]["life_seconds"] == 60

    def test_missing_name_falls_back_to_guid(self):
        assert _build_life_cards([_row(name=None, guid="DEADBEEF00")])[0]["name"] == "DEADBEEF"

    def test_missing_map_name(self):
        card = _build_life_cards([_row(map_name=None)])[0]
        assert "the map" in card["narrative"]


class TestParseDate:
    def test_valid(self):
        from datetime import date
        assert _parse_date("2026-07-13") == date(2026, 7, 13)

    def test_bad_format_raises_400(self):
        with pytest.raises(Exception) as exc:
            _parse_date("not-a-date")
        assert getattr(exc.value, "status_code", None) == 400


class _FakeScopeDB:
    """Serves the one fetch_all the payload builder runs. Rows mimic the SQL
    shape (dict rows, as the adapter returns them)."""

    def __init__(self, rows):
        self._rows = rows
        self.queries = []

    async def fetch_all(self, query, params=()):
        self.queries.append(query)
        return self._rows


def _scope():
    from website.backend.services.session_scope import GamingSessionScope
    return GamingSessionScope(
        gaming_session_id=154,
        dates=("2026-08-27",),
        round_keys=((500, "etl_adlernest", 1), (600, "etl_adlernest", 2)),
        accepted_round_count=2,
        distinct_map_names=("etl_adlernest",),
    )


class TestQualifyingTotal:
    """`total` is len(lives) AFTER the cut — a field named total that is not
    a total, kept for wire compatibility. `qualifying_total` counts every
    life that cleared the minimum, so the UI can disclose the cutoff
    ("top 5 of N"). Codex on #842.
    """

    @pytest.mark.asyncio
    async def test_qualifying_total_counts_past_the_cut(self):
        from website.backend.routers.storytelling_router import _best_lives_payload
        rows = [_row(guid=f"GUID{i:04d}AA", kills=8 - i) for i in range(7)]
        payload = await _best_lives_payload(_scope(), 5, _FakeScopeDB(rows))
        assert payload["qualifying_total"] == 7
        assert len(payload["lives"]) == 5
        # The historical field keeps its historical meaning.
        assert payload["total"] == 5
        assert payload["qualifying_total"] > payload["total"]
        # The published threshold is the one the SQL enforces.
        from website.backend.routers.storytelling_router import _BEST_LIFE_MIN_KILLS
        assert payload["min_kills"] == _BEST_LIFE_MIN_KILLS

    @pytest.mark.asyncio
    async def test_short_session_counts_equal(self):
        from website.backend.routers.storytelling_router import _best_lives_payload
        rows = [_row(guid=f"GUID{i:04d}BB", kills=5) for i in range(3)]
        payload = await _best_lives_payload(_scope(), 5, _FakeScopeDB(rows))
        assert payload["qualifying_total"] == 3
        assert payload["total"] == 3
