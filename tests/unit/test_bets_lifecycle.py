"""Unit tests for betting auto-lifecycle pure helpers (Faza B2).

The DB paths (_live_gsid / _two_teams / maybe_open_market) are exercised
end-to-end against a live database; here we cover the pure, DB-free helpers.
"""
from datetime import date

from website.backend.services.bets_lifecycle import _coerce_date, _label_from_names


class TestLabelFromNames:
    def test_list_of_names(self):
        assert _label_from_names(["immoo{", ".olz", "wiseBoy"], "Team A") == "immoo{, .olz, wiseBoy"

    def test_json_string_names(self):
        assert _label_from_names('["KaNii", "vid"]', "Team B") == "KaNii, vid"

    def test_empty_falls_back(self):
        assert _label_from_names([], "Team A") == "Team A"
        assert _label_from_names(None, "Team B") == "Team B"

    def test_blanks_filtered(self):
        assert _label_from_names(["  ", "vid", ""], "Team A") == "vid"

    def test_truncated_to_40(self):
        long = [f"player{i}" for i in range(20)]
        out = _label_from_names(long, "Team A")
        assert len(out) <= 40

    def test_fallback_also_truncated(self):
        assert len(_label_from_names([], "X" * 80)) == 40


class TestCoerceDate:
    def test_none(self):
        assert _coerce_date(None) is None

    def test_date_passthrough(self):
        d = date(2026, 6, 30)
        assert _coerce_date(d) is d

    def test_iso_string(self):
        assert _coerce_date("2026-06-30") == date(2026, 6, 30)

    def test_datetime_string_prefix(self):
        assert _coerce_date("2026-06-30 22:03:51") == date(2026, 6, 30)

    def test_garbage_returns_none(self):
        assert _coerce_date("not-a-date") is None
