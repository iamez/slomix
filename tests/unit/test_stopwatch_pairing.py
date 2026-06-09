"""Unit tests for the deterministic stopwatch round pairer.

Encodes the ET:Legacy stopwatch invariant: R1 precedes R2 of the same map;
an R2 with no R1 is an anomaly; an R1 with no R2 is an abandoned match.
"""
from __future__ import annotations

from bot.core.stopwatch_pairing import (
    Match,
    RoundRec,
    derive_match_id,
    pair_rounds,
)

BASE = 1_700_000_000  # arbitrary epoch anchor


def _r(
    rid: int,
    rn: int,
    *,
    session: int | None = 1,
    map_name: str = "etl_frostbite",
    start: int | None = None,
    end: int | None = None,
    date: str | None = "2026-02-20",
    time: str | None = None,
) -> RoundRec:
    return RoundRec(
        id=rid,
        gaming_session_id=session,
        map_name=map_name,
        round_number=rn,
        round_start_unix=start,
        round_end_unix=end,
        round_date=date,
        round_time=time,
    )


def _statuses(res) -> list[str]:
    return sorted(m.status for m in res.matches)


def test_basic_pair():
    """R1 then R2 of same map within window → one complete match."""
    rounds = [
        _r(1, 1, start=BASE, end=BASE + 300, time="214916"),
        _r(2, 2, start=BASE + 330, end=BASE + 600, time="215609"),
    ]
    res = pair_rounds(rounds)
    assert res.summary() == {"matches_total": 1, "complete": 1, "abandoned_r1": 0, "orphan_r2": 0}
    m = res.complete[0]
    assert m.r1.id == 1 and m.r2.id == 2
    # match_id = R1's date-HHMMSS (live-path format)
    assert m.match_id == "2026-02-20-214916"


def test_match_id_is_r1_date_time():
    """Shared match_id must come from R1's date+time (live-path format)."""
    r1 = _r(1, 1, start=BASE, time="214916")
    assert derive_match_id(r1) == "2026-02-20-214916"


def test_lonely_r1_is_abandoned():
    """R1 with no following R2 in the session → abandoned_r1."""
    res = pair_rounds([_r(1, 1, start=BASE, end=BASE + 300)])
    assert _statuses(res) == ["abandoned_r1"]
    assert res.abandoned_r1[0].r1.id == 1
    assert res.abandoned_r1[0].r2 is None


def test_lonely_r2_is_orphan():
    """R2 with no preceding R1 → orphan_r2 (lost R1 anomaly)."""
    res = pair_rounds([_r(2, 2, start=BASE + 330)])
    assert _statuses(res) == ["orphan_r2"]
    assert res.orphan_r2[0].r2.id == 2
    assert res.orphan_r2[0].r1 is None


def test_map_replayed_twice_in_session():
    """Same map played twice back-to-back → two complete matches."""
    rounds = [
        _r(1, 1, start=BASE + 0, end=BASE + 300),
        _r(2, 2, start=BASE + 330, end=BASE + 600),
        _r(3, 1, start=BASE + 700, end=BASE + 1000),
        _r(4, 2, start=BASE + 1030, end=BASE + 1300),
    ]
    res = pair_rounds(rounds)
    assert res.summary()["complete"] == 2
    assert res.summary()["matches_total"] == 2
    pairs = {(m.r1.id, m.r2.id) for m in res.complete}
    assert pairs == {(1, 2), (3, 4)}


def test_r2_outside_window_does_not_pair():
    """An R2 far beyond the window → R1 abandoned, R2 orphan (not paired)."""
    rounds = [
        _r(1, 1, start=BASE, end=BASE + 300),
        _r(2, 2, start=BASE + 300 + 60 * 60),  # 1h after R1 end > 45min window
    ]
    res = pair_rounds(rounds)
    assert _statuses(res) == ["abandoned_r1", "orphan_r2"]


def test_r2_different_map_does_not_pair():
    """Open R1 of map A, then R2 of map B → A abandoned, B orphan."""
    rounds = [
        _r(1, 1, map_name="etl_frostbite", start=BASE, end=BASE + 300),
        _r(2, 2, map_name="te_escape2", start=BASE + 330),
    ]
    res = pair_rounds(rounds)
    assert _statuses(res) == ["abandoned_r1", "orphan_r2"]
    assert res.abandoned_r1[0].map_name == "etl_frostbite"
    assert res.orphan_r2[0].map_name == "te_escape2"


def test_two_r1_in_a_row_first_is_abandoned():
    """R1, R1, R2 → first R1 abandoned, second R1 pairs with R2."""
    rounds = [
        _r(1, 1, start=BASE, end=BASE + 300),
        _r(2, 1, start=BASE + 400, end=BASE + 700),
        _r(3, 2, start=BASE + 730, end=BASE + 1000),
    ]
    res = pair_rounds(rounds)
    assert res.summary()["complete"] == 1
    assert res.summary()["abandoned_r1"] == 1
    assert res.complete[0].r1.id == 2 and res.complete[0].r2.id == 3
    assert res.abandoned_r1[0].r1.id == 1


def test_fallback_to_date_time_when_no_unix():
    """No round_start_unix → ordering + pairing via date/time still works."""
    rounds = [
        _r(2, 2, start=None, time="215609"),
        _r(1, 1, start=None, time="214916"),
    ]
    res = pair_rounds(rounds)
    assert res.summary()["complete"] == 1
    assert res.complete[0].r1.id == 1 and res.complete[0].r2.id == 2


def test_midnight_crossover_via_unix():
    """R1 at 23:59, R2 at 00:03 next day — unix keeps them ordered + paired."""
    r1_unix = BASE
    rounds = [
        _r(1, 1, start=r1_unix, end=r1_unix + 200, date="2026-02-20", time="235900"),
        _r(2, 2, start=r1_unix + 240, date="2026-02-21", time="000300"),
    ]
    res = pair_rounds(rounds)
    assert res.summary()["complete"] == 1


def test_sessions_are_isolated():
    """An R1 in session 1 never pairs with an R2 in session 2."""
    rounds = [
        _r(1, 1, session=1, start=BASE),
        _r(2, 2, session=2, start=BASE + 330),
    ]
    res = pair_rounds(rounds)
    assert _statuses(res) == ["abandoned_r1", "orphan_r2"]


def test_round_zero_ignored():
    """R0 (match summary) rows are not play rounds and are ignored."""
    rounds = [
        _r(1, 1, start=BASE, end=BASE + 300),
        _r(2, 2, start=BASE + 330, end=BASE + 600),
        _r(3, 0, start=BASE),  # R0 summary
    ]
    res = pair_rounds(rounds)
    assert res.summary()["matches_total"] == 1
    assert res.complete[0].r1.id == 1


def test_real_te_escape2_session_91():
    """Regression from real data (te_escape2, session 91, 2026-02-20):
    five back-to-back games, all should pair into five complete matches."""
    times = [
        ("214916", "215609"),
        ("220049", "220421"),
        ("220757", "221131"),
        ("233347", "233901"),
        ("234418", "234926"),
    ]
    rounds: list[RoundRec] = []
    rid = 1
    base = BASE
    for i, (t1, t2) in enumerate(times):
        # space games ~10 min apart so windows are clean
        s1 = base + i * 600
        s2 = s1 + 200
        rounds.append(_r(rid, 1, map_name="te_escape2", start=s1, end=s1 + 180, time=t1))
        rounds.append(_r(rid + 1, 2, map_name="te_escape2", start=s2, end=s2 + 180, time=t2))
        rid += 2
    res = pair_rounds(rounds)
    assert res.summary() == {
        "matches_total": 5,
        "complete": 5,
        "abandoned_r1": 0,
        "orphan_r2": 0,
    }
    # all distinct match_ids
    assert len({m.match_id for m in res.matches}) == 5


def test_match_status_property():
    """Match.status reflects which rounds are present."""
    r = _r(1, 1)
    assert Match("x", "m", 1, r, r).status == "complete"
    assert Match("x", "m", 1, r, None).status == "abandoned_r1"
    assert Match("x", "m", 1, None, r).status == "orphan_r2"
