"""Round-duration single source of truth (RCA 2026-08-18).

rounds.actual_time is the stopwatch TARGET (g_nextTimeLimit header field),
not a measurement — on surrender rounds it carries the full timelimit / R1's
time, which inflated 15% of round durations for months. These tests pin the
three fixes:

1. shared.round_time — the COALESCE(duration, parse(actual_time)) contract,
2. parser header field 9 — MILLISECONDS, not seconds (reading ms as s made
   every 9-field round clamp to the timelimit),
3. stopwatch scoring — outcome from winner/defender + surrender, tiebreak by
   measured durations (an inflated actual_time no longer decides map wins).
"""
from __future__ import annotations

from bot.community_stats_parser import normalize_header_playtime
from bot.services.stopwatch_scoring_service import StopwatchScoringService
from shared.round_time import (
    parse_mmss,
    round_duration_seconds,
    round_duration_sql,
)

# ── shared.round_time ────────────────────────────────────────────────

def test_parse_mmss():
    assert parse_mmss("4:02") == 242
    assert parse_mmss("12:00") == 720
    assert parse_mmss(" 0:30 ") == 30
    assert parse_mmss("0") is None
    assert parse_mmss("") is None
    assert parse_mmss(None) is None
    assert parse_mmss("4:2") is None  # seconds must be two digits
    assert parse_mmss("4:60") is None  # a clock never renders :60
    assert parse_mmss("1:99") is None  # corrupt header data, not a duration


def test_round_duration_prefers_measurement():
    # measured value wins even when actual_time disagrees (surrender case)
    assert round_duration_seconds(370, "8:27") == 370
    # missing measurement -> header text fallback
    assert round_duration_seconds(None, "8:27") == 507
    assert round_duration_seconds(0, "8:27") == 507
    # nothing usable -> None (unknown, never zero)
    assert round_duration_seconds(None, "0") is None


def test_round_duration_sql_matches_python_contract():
    sql = round_duration_sql("r")
    assert "NULLIF(r.actual_duration_seconds, 0)" in sql
    assert "split_part(r.actual_time" in sql
    # The two used to be written separately and disagreed on corrupt clocks:
    # SQL took `[0-9]{2}` seconds, so "4:60" parsed to 300 s in a query and
    # to None in Python, while the module docstring said the SQL mirrors it.
    # Substring assertions could not see that — they checked the shape, not
    # the rule. This compares the SAME strings through both sides.
    import re as _re

    sql_pattern = _re.search(r"actual_time ~ '([^']+)'", sql).group(1)
    for clock, valid in [
        ("8:27", True), ("0:00", True), ("12:59", True),
        ("4:60", False), ("4:99", False), ("4:6", False), ("abc", False),
    ]:
        sql_ok = _re.match(sql_pattern, clock) is not None
        py_ok = parse_mmss(clock) is not None
        assert sql_ok == py_ok == valid, (
            f"{clock!r}: sql={sql_ok} python={py_ok}, expected {valid}"
        )
    # no bind placeholders — must be safe under both ? and $n adapters
    # (the lone `$` regex anchor inside the quoted literal is fine)
    assert "?" not in sql
    assert not any(f"${d}" in sql for d in "123456789")


# ── parser header field 9 (ms) ───────────────────────────────────────

def test_header_playtime_field_is_milliseconds():
    # real sample: 2026-08-17 etl_frostbite R1, header ...\4:02\241533
    assert normalize_header_playtime("241533") == 241.533
    assert int(normalize_header_playtime("241533")) == 241  # ~= 4:02


def test_header_playtime_legacy_seconds_and_garbage():
    assert normalize_header_playtime("242") == 242.0  # legacy whole seconds
    assert normalize_header_playtime("-58000") is None  # et_ShutdownGame path
    assert normalize_header_playtime("0") is None
    assert normalize_header_playtime("abc") is None
    assert normalize_header_playtime(None) is None
    # non-finite floats must not leak into int() downstream (coderabbit)
    assert normalize_header_playtime("inf") is None
    assert normalize_header_playtime("1e309") is None  # overflows to inf
    assert normalize_header_playtime("nan") is None


# ── stopwatch scoring: surrender-aware map winner ────────────────────

def _svc() -> StopwatchScoringService:
    return StopwatchScoringService(db_adapter=None)


def _round(**kw) -> dict:
    base = {
        'time_limit': '0',  # dead column in modern rounds — must not matter
        'actual_time': None,
        'actual_duration_seconds': None,
        'surrender_team': None,
        'lua_time_limit_minutes': 12,
        'winner_team': None,
        'defender_team': None,
    }
    base.update(kw)
    return base


def test_surrendered_r2_is_not_a_set_time():
    # Canary: supply 2026-07-29 — R2 attackers surrendered at 370s, but
    # actual_time carried R1's 8:27. Old code called both rounds
    # "completed" and gave the map to R1 attackers by tie; the outcome was
    # right only by luck and the description lied. Winner/defender now
    # decides: R1 attackers completed, R2 attackers full-held.
    svc = _svc()
    r1 = _round(actual_time='8:27', actual_duration_seconds=506,
                winner_team=1, defender_team=2)      # attackers (1?) won
    r2 = _round(actual_time='8:27', actual_duration_seconds=370,
                winner_team=1, defender_team=1,      # defenders held
                surrender_team=2)
    t1, t2, desc = svc.calculate_map_score_from_rounds(r1, r2)
    assert (t1, t2) == (2, 0)
    assert 'fullhold' in desc.lower()
    # and the displayed times are the measured ones, not the inflated
    # header (8:26 = 506s measured; r2 shows as fullhold in the desc)
    assert '8:26' in desc


def test_both_completed_faster_measured_time_wins():
    svc = _svc()
    r1 = _round(actual_duration_seconds=600, winner_team=2, defender_team=1)
    r2 = _round(actual_duration_seconds=470, winner_team=1, defender_team=2)
    t1, t2, desc = svc.calculate_map_score_from_rounds(r1, r2)
    assert (t1, t2) == (0, 2)
    assert '7:50' in desc


def test_double_fullhold_is_a_draw():
    svc = _svc()
    r1 = _round(actual_duration_seconds=720, winner_team=1, defender_team=1)
    r2 = _round(actual_duration_seconds=720, winner_team=2, defender_team=2)
    assert svc.calculate_map_score_from_rounds(r1, r2)[:2] == (1, 1)


def test_surrender_signal_alone_means_no_completion():
    # winner/defender missing (legacy rows) but lua recorded a surrender:
    # the attackers did NOT set a time, whatever the clock says.
    svc = _svc()
    r1 = _round(actual_time='5:00', winner_team=1, defender_team=2)
    r2 = _round(actual_time='5:00', surrender_team=1)
    t1, t2, _ = svc.calculate_map_score_from_rounds(r1, r2)
    assert (t1, t2) == (2, 0)


def test_one_undecidable_round_falls_back_to_legacy_scoring():
    # r2 has literally no outcome data (no winner/defender, no surrender,
    # no duration) — must NOT be guessed as "fullhold"; the whole match
    # falls back to the legacy time-based table (coderabbit, PR #770).
    svc = _svc()
    r1 = _round(time_limit='10:00', actual_time='5:00',
                actual_duration_seconds=300,
                winner_team=1, defender_team=2, lua_time_limit_minutes=None)
    r2 = _round(time_limit='10:00', actual_time='7:00',
                lua_time_limit_minutes=None)
    t1, t2, _ = svc.calculate_map_score_from_rounds(r1, r2)
    # legacy table: both times < limit -> both "complete", faster wins
    assert (t1, t2) == (2, 0)


def test_no_outcome_data_falls_back_to_legacy_time_scoring():
    svc = _svc()
    r1 = _round(time_limit='10:00', actual_time='5:00',
                lua_time_limit_minutes=None)
    r2 = _round(time_limit='10:00', actual_time='7:00',
                lua_time_limit_minutes=None)
    t1, t2, _ = svc.calculate_map_score_from_rounds(r1, r2)
    assert (t1, t2) == (2, 0)  # same answer the legacy table test expects
