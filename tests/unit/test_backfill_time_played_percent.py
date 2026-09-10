"""Unit tests for scripts/backfill_time_played_percent.py.

The database-touching part is exercised by the preview itself, which opens a
READ ONLY session and therefore cannot write. What is worth pinning here is
everything that decides *which* rows get touched and *what* is written --
the parts where a quiet widening would be invisible until after an --apply.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.backfill_time_played_percent import (  # noqa: E402
    IMPLAUSIBLE_ABOVE,
    REPAIRED_COLUMNS,
    TARGET_SQL,
    _sql_literal,
    build_artifacts,
    stats_file_for,
)


def test_only_one_column_is_ever_written():
    """A data repair that can reach more columns than it claims is how a fix
    turns into an incident."""
    assert REPAIRED_COLUMNS == ("time_played_percent",)


def test_target_rows_are_only_the_zeros():
    """Re-running must never overwrite a value someone measured. The gate is
    the difference between this script and
    tools/slomix_backfill.py time-played-percent, which has no gate and would
    rewrite every matched row."""
    assert "p.time_played_percent = 0" in TARGET_SQL
    assert "p.time_played_seconds > 0" in TARGET_SQL


def test_round_zero_is_excluded():
    """R0 rows also hold zeros, nothing reads them, and filling them would
    lend them the appearance of a real source."""
    assert "r.round_number IN (1, 2)" in TARGET_SQL


def test_unhealthy_rounds_are_excluded():
    assert "r.is_valid IS DISTINCT FROM FALSE" in TARGET_SQL
    assert "'orphan_r2'" in TARGET_SQL
    assert "'cancelled'" in TARGET_SQL


def test_capture_name_is_fully_determined_by_the_round_stamp(tmp_path):
    """round_date + round_time reproduce the capture filename. If this ever
    drifts, the script silently reports 'capture file missing' for everything
    instead of failing."""
    name = "2026-03-29-133257-sw_goldrush_te-round-1.txt"
    (tmp_path / name).write_text("x", encoding="utf-8")

    found = stats_file_for(tmp_path, "2026-03-29", "133257", "sw_goldrush_te", 1)
    assert found is not None and found.name == name

    assert stats_file_for(tmp_path, "2026-03-29", "133258", "sw_goldrush_te", 1) is None
    assert stats_file_for(tmp_path, "2026-03-29", "133257", "sw_goldrush_te", 2) is None


def test_orphan_r2_is_never_a_source(monkeypatch, tmp_path):
    """An R2 whose R1 partner is missing carries RAW CUMULATIVE percentages.
    Writing those as if they described R2 alone is precisely the inflation
    this whole investigation is about."""
    import scripts.backfill_time_played_percent as mod

    class _Parser:
        def parse_stats_file(self, _path):
            return {
                "is_orphan_r2": True,
                "players": [
                    {"guid": "ABCD1234",
                     "objective_stats": {"time_played_percent": 91.0}}
                ],
            }

    monkeypatch.setattr(
        "bot.community_stats_parser.C0RNP0RN3StatsParser", _Parser, raising=True)
    assert mod.parsed_percentages(tmp_path / "whatever.txt") == ("orphan_r2", {})


def test_a_healthy_file_yields_uppercase_guid_keys(monkeypatch, tmp_path):
    import scripts.backfill_time_played_percent as mod

    class _Parser:
        def parse_stats_file(self, _path):
            return {
                "players": [
                    {"guid": "abcd1234",
                     "objective_stats": {"time_played_percent": 79.6}},
                    # A zero here means the file itself has no value; it must
                    # not become a written zero.
                    {"guid": "EEEE5678",
                     "objective_stats": {"time_played_percent": 0}},
                ]
            }

    monkeypatch.setattr(
        "bot.community_stats_parser.C0RNP0RN3StatsParser", _Parser, raising=True)
    assert mod.parsed_percentages(tmp_path / "whatever.txt") == (
        "ok", {"ABCD1234": 79.6})


def test_the_implausible_threshold_leaves_headroom_for_rounding_only():
    """Measured on this corpus: R1 tops out at exactly 100.0 and two R2 rows
    out of 4,668 land at 101.2 -- rounding in the differential. The threshold
    has to admit 100.0 and reject 101.2, and must not be so wide that a truly
    broken value slips through."""
    assert 100.0 < IMPLAUSIBLE_ABOVE < 101.2


def test_sql_literal_escapes_quotes():
    assert _sql_literal("O'Brien") == "'O''Brien'"
    assert _sql_literal(79.6) == "79.6"
    assert _sql_literal(None) == "NULL"


@pytest.mark.parametrize("bad", ["DELETE", "TRUNCATE", "DROP"])
def test_target_query_only_reads(bad):
    assert bad not in TARGET_SQL.upper()


def test_a_parse_failure_is_not_reported_as_an_orphan(monkeypatch, tmp_path):
    """Collapsing "could not parse" into "orphan R2" would file every real
    parse problem under a line of the preview that reads as expected. Three
    outcomes, three names."""
    import scripts.backfill_time_played_percent as mod

    class _Parser:
        def parse_stats_file(self, _path):
            return {"players": []}

    monkeypatch.setattr(
        "bot.community_stats_parser.C0RNP0RN3StatsParser", _Parser, raising=True)
    reason, data = mod.parsed_percentages(tmp_path / "whatever.txt")
    assert reason == "unparsed" and data == {}


def test_rollback_only_reverts_the_value_this_run_wrote():
    """An unconditional `WHERE id = ...` rollback, run after someone has
    legitimately corrected the row, would set a good value back to zero."""
    backup, repair = build_artifacts([(42, 79.64, "vid", "2026-04-01", "supply")], "S")

    assert ("UPDATE player_comprehensive_stats SET time_played_percent = 0 "
            "WHERE id = 42 AND time_played_percent = 79.6;") in backup
    assert ("UPDATE player_comprehensive_stats SET time_played_percent = 79.6 "
            "WHERE id = 42 AND time_played_percent = 0;") in repair

    # Both sides are transactional, and neither may touch anything else.
    for side in (backup, repair):
        assert side[1] == "BEGIN;" and side[-1] == "COMMIT;"
        assert all("player_comprehensive_stats" in s
                   for s in side if s.startswith("UPDATE"))


def test_rollback_is_not_a_blanket_update():
    """Pin the guard itself: the id alone must never be the whole condition."""
    backup, _ = build_artifacts([(7, 50.0, "x", "d", "m")], "S")
    statements = [s for s in backup if s.startswith("UPDATE")]
    assert statements, "no UPDATE generated -- the test cannot see its subject"
    for statement in statements:
        assert "AND time_played_percent =" in statement
