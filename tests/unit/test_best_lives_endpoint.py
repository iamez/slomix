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
