"""R2 differential contract for the dead-time fields.

This file previously contained three tests, 297 lines, and **no assertions**.
All three printed their own verdicts -- including `❌ FAIL` lines -- and
pytest reported three passes. What CI had been printing, unread:

    ❌ FAIL: time_dead_minutes 12.0 != expected 7.0
    ❌ FAIL: time_dead_ratio 48.0% != expected 28.0%
    ❌ FAIL: Death ratio 180.0% exceeds 100%!

Both of those first two "failures" were the test being wrong, not the parser.
The old fixture called the R2 file's `time_dead_minutes` "Total dead both
rounds" and expected the parser to subtract R1 from it. It does not, and it
should not: `time_dead_minutes` is in `R2_ONLY_FIELDS`, because the Lua
resets the accumulator in `et_InitGame`.

Measured across 6,450 R1/R2 player pairs: **R2 < R1 in 4,847 of them
(75.1%)**. A cumulative field cannot decrease, so the per-round reading is
the right one and the old expectation was a false belief nothing could
contradict.

The third line is a real defect, and it is asserted as such below.
"""

import pytest

from bot.community_stats_parser import R2_ONLY_FIELDS, C0RNP0RN3StatsParser


def _round(num, *, played, dead, ratio, name="qmr", guid="ABC123"):
    return {
        "players": [{
            "name": name, "guid": guid, "team": 1 if num == 1 else 2,
            "kills": 10, "deaths": 5, "damage_given": 1000,
            "damage_received": 500, "headshots": 2,
            "objective_stats": {
                "time_played_minutes": played,
                "time_dead_minutes": dead,
                "time_dead_ratio": ratio,
            },
            "weapon_stats": {},
        }],
        "map_name": "supply", "map_time": 1200, "actual_time": "20:00",
        "round_outcome": "Axis", "round_num": num, "success": True,
        "defender_team": 1, "winner_team": 2,
    }


def _differential(r1, r2):
    result = C0RNP0RN3StatsParser().calculate_round_2_differential(r1, r2)
    return result["players"][0]["objective_stats"]


def test_time_dead_minutes_is_declared_per_round():
    """The contract this file exists to protect, stated where it lives."""
    assert "time_dead_minutes" in R2_ONLY_FIELDS


def test_the_r2_file_value_is_used_as_is_not_subtracted():
    """R2_ONLY means the R2 file already holds R2's own dead time.

    Subtracting R1 here would produce 7.0 and would be wrong -- and on real
    data it would go NEGATIVE in three quarters of pairs, because R2 is
    usually the shorter half.
    """
    obj = _differential(
        _round(1, played=20.0, dead=5.0, ratio=25.0),
        _round(2, played=45.0, dead=12.0, ratio=26.67),
    )
    assert obj["time_dead_minutes"] == pytest.approx(12.0), (
        "the R2 value must be taken as-is; 7.0 would mean R1 was subtracted "
        "from a field that is already per-round")
    # time_played_minutes IS cumulative, so this one really is a subtraction.
    assert obj["time_played_minutes"] == pytest.approx(25.0)


def test_the_ratio_is_recomputed_from_the_r2_only_values():
    """Percentages cannot be subtracted, so the parser rebuilds this one from
    the two minute figures it just settled: 12.0 / 25.0 = 48%."""
    obj = _differential(
        _round(1, played=20.0, dead=5.0, ratio=25.0),
        _round(2, played=45.0, dead=12.0, ratio=26.67),
    )
    assert obj["time_dead_ratio"] == pytest.approx(48.0, abs=0.5)


def test_the_ratio_is_not_capped_and_that_is_where_the_over_100_rows_come_from():
    """A known defect, pinned rather than left to print into a log nobody reads.

    When the R2 file reports more dead time than played time, the recomputed
    ratio simply exceeds 100. The old test asserted nothing and printed
    "❌ FAIL: Death ratio 180.0% exceeds 100%!" while passing.

    This is not hypothetical: 43 stored rows carry a ratio above 100, the
    worst at 3690%. `pcs_time_dead_ratio_out_of_range` in the plausibility
    audit reports them.

    Change this test the day the parser starts clamping -- it is the record of
    what today's behaviour actually is, not an endorsement of it.
    """
    obj = _differential(
        _round(1, played=10.0, dead=2.0, ratio=20.0),
        _round(2, played=20.0, dead=18.0, ratio=90.0),
    )
    assert obj["time_dead_ratio"] > 100.0, (
        "if this now fails, the parser has started clamping the ratio -- good "
        "news; update this test and re-check the audit rule")
    assert obj["time_dead_minutes"] == pytest.approx(18.0)


def test_a_dead_time_larger_than_the_round_survives_the_differential():
    """The companion to the above, in minutes rather than percent.

    Nothing in the parser stops `time_dead_minutes` exceeding
    `time_played_minutes`. Consumers paper over it at read time with
    LEAST(dead, played), but season leaders and all-time rankings read the raw
    column -- which is how a row claiming 580 minutes dead in a 7-minute round
    reached the top of one.
    """
    obj = _differential(
        _round(1, played=10.0, dead=2.0, ratio=20.0),
        _round(2, played=20.0, dead=18.0, ratio=90.0),
    )
    assert obj["time_dead_minutes"] > obj["time_played_minutes"], (
        "if this now fails, the parser has started bounding dead time by "
        "played time; update this test and the audit rule with it")
