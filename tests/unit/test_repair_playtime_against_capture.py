"""scripts/repair_playtime_against_capture.py — the arithmetic and the guard rails.

The DB-touching parts are exercised against the real database by the dry-run
itself (which cannot write: it opens a READ ONLY session). What is worth
pinning here is the pure arithmetic that decides the numbers written into
production, and the threshold shared with the parser.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bot.community_stats_parser import normalize_header_playtime  # noqa: E402
from scripts.repair_playtime_against_capture import (  # noqa: E402
    MS_THRESHOLD,
    REPAIRED_COLUMNS,
    capture_candidates,
    derive_minutes_and_dpm,
    find_rounds,
    main,
    sibling_seconds,
)


def test_threshold_matches_the_parser_that_created_the_corruption():
    """The repair must consider exactly the values the parser calls
    milliseconds — a looser threshold would rewrite healthy long rounds."""
    assert normalize_header_playtime(MS_THRESHOLD) == MS_THRESHOLD
    assert normalize_header_playtime(MS_THRESHOLD + 1) == (MS_THRESHOLD + 1) / 1000.0


def test_only_the_three_corrupted_columns_are_ever_written():
    assert REPAIRED_COLUMNS == ("time_played_seconds", "time_played_minutes", "dpm")


def test_derived_values_reproduce_the_healthy_rows():
    """Real rows from the 2026-02-24 session (verified against the dev
    database and against a re-parse of the original capture)."""
    assert derive_minutes_and_dpm(600, 3276) == (10.0, 327.6)
    assert derive_minutes_and_dpm(600, 2812) == (10.0, 281.2)
    assert derive_minutes_and_dpm(552, 2377) == (9.2, 258.4)
    assert derive_minutes_and_dpm(576, 2941) == (9.6, 306.4)
    assert derive_minutes_and_dpm(234, 1352) == (3.9, 346.7)


def test_dpm_uses_unrounded_seconds():
    """1013 s = 16.8833... min. Rounding the denominator to 16.88 first shifts
    dpm by 0.1 — small, but it is the difference between the repaired R0 rows
    matching the healthy reference and not."""
    minutes, dpm = derive_minutes_and_dpm(1013, 4574)
    assert minutes == 16.88
    assert dpm == round(4574 / (1013 / 60.0), 1)
    assert dpm != round(4574 / 16.88, 1)


def test_zero_seconds_cannot_divide_by_zero():
    assert derive_minutes_and_dpm(0, 1234) == (0.0, 0.0)


# ── The narrowing that keeps the repair from eating unrelated classes ──────


def test_capture_name_is_fully_determined_by_the_round_stamp(tmp_path):
    """Round stamp -> capture file name, with the -endstats twin as fallback.
    The older match_id glob missed every R2 (an R2 file carries its own
    timestamp, not its match's), which is how a blanket reconcile ended up
    proposing 232 rows across 40 rounds instead of this bug's 68."""
    (tmp_path / "2026-02-20-210845-supply-round-1.txt").write_text("x")
    row = {"round_date": "2026-02-20", "round_time": 210845, "map_name": "supply",
           "round_number": 1, "match_id": "2026-02-20-210845"}
    assert capture_candidates(tmp_path, row)[0].name == "2026-02-20-210845-supply-round-1.txt"

    (tmp_path / "2026-02-20-212207-supply-round-2-endstats.txt").write_text("x")
    row2 = dict(row, round_time=212207, round_number=2)
    assert capture_candidates(tmp_path, row2)[0].name.endswith("-round-2-endstats.txt")


def test_capture_lookup_zero_fills_a_short_round_time(tmp_path):
    """round_time is an integer, so a round just after midnight loses its
    leading zeros (4918 for 00:49:18) while the file keeps them."""
    (tmp_path / "2026-06-11-004918-sw_goldrush_te-round-1.txt").write_text("x")
    row = {"round_date": "2026-06-11", "round_time": 4918, "map_name": "sw_goldrush_te",
           "round_number": 1, "match_id": "2026-06-11-004918"}
    assert capture_candidates(tmp_path, row)[0].name.endswith("-004918-sw_goldrush_te-round-1.txt")


def test_capture_lookup_falls_back_to_the_match_id_glob(tmp_path):
    """When the round stamp does not name a file (round_time drifted from the
    capture), the match_id glob is the last resort rather than giving up."""
    (tmp_path / "2026-02-20-210845-supply-round-1.txt").write_text("x")
    row = {"round_date": "2026-02-20", "round_time": 210901, "map_name": "supply",
           "round_number": 1, "match_id": "2026-02-20-210845"}
    assert capture_candidates(tmp_path, row)[0].name == "2026-02-20-210845-supply-round-1.txt"


def test_round_finder_only_accepts_the_clock_fallback_signature():
    """The predicate must pin all three narrowing conditions: a valid round, a
    parsable clock, and at least one row sitting exactly on that clock. Without
    them the repair reaches into orphan R2s, bot rounds and the 2026-02-06 rows
    an earlier backfill already healed."""
    sql = inspect.getsource(find_rounds)
    assert "is_valid = TRUE" in sql
    assert "round_status = 'completed'" in sql
    assert "p.time_played_seconds = split_part(r.actual_time" in sql


def test_r0_pass_is_opt_in():
    """R0 aggregates holding one round's value instead of the R1+R2 sum are a
    separate, DB-wide issue (391 live rows on prod) — this repair must not
    silently rewrite them."""
    src = inspect.getsource(main)
    assert "args.with_r0" in src


class _FakeCursor:
    """Minimal cursor: returns a canned result set for one execute()."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return None

    def fetchall(self):
        return self._rows


def test_r0_sum_needs_exactly_one_r1_and_one_r2():
    """(round_id, round_number, seconds) rows -> the match total, or None."""
    both = _FakeCursor([(9904, 1, 660), (9905, 2, 480)])
    assert sibling_seconds(both, "m", "GUID", {}) == 1140

    # Only one half present: writing it in would bill half a match as a whole.
    only_r2 = _FakeCursor([(9905, 2, 480)])
    assert sibling_seconds(only_r2, "m", "GUID", {}) is None

    # A re-imported match with two R1 rows is ambiguous, not summable.
    duplicated = _FakeCursor([(9904, 1, 660), (9906, 1, 655), (9905, 2, 480)])
    assert sibling_seconds(duplicated, "m", "GUID", {}) is None


def test_r0_sum_uses_values_repaired_earlier_in_the_same_run():
    """A dry-run and an --apply run must produce identical numbers, so the
    sum reads this run's repairs, not the rows still in the database."""
    cur = _FakeCursor([(9904, 1, 720), (9905, 2, 480)])
    assert sibling_seconds(cur, "m", "GUID", {(9904, "GUID"): 660}) == 1140


def test_r0_sum_refuses_a_component_that_is_still_corrupt():
    """A millisecond value in either half means the repair basis is unknown."""
    cur = _FakeCursor([(9904, 1, 599327), (9905, 2, 480)])
    assert sibling_seconds(cur, "m", "GUID", {}) is None
