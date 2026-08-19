"""scripts/repair_ms_playtime_rows.py — the arithmetic and the guard rails.

The DB-touching parts are exercised against the real database by the dry-run
itself (which cannot write: it opens a READ ONLY session). What is worth
pinning here is the pure arithmetic that decides the numbers written into
production, and the threshold shared with the parser.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bot.community_stats_parser import normalize_header_playtime  # noqa: E402
from scripts.repair_ms_playtime_rows import (  # noqa: E402
    MS_THRESHOLD,
    REPAIRED_COLUMNS,
    derive_minutes_and_dpm,
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
