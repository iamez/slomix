"""The session clock on /basics — start of the first counted round, end of
the last (start + measured duration), midnight crossing, and the dual form
of rounds.round_time."""
from __future__ import annotations

from website.backend.routers import sessions_router as sr


def _row(round_time, duration, actual_time=None):
    # (id, map, round_number, winner, date, round_time, actual_time, round_start_unix, measured duration)
    return (1, "supply", 1, 2, "2026-08-23", round_time, actual_time, None, duration)


def test_start_is_the_first_file_time_minus_its_duration_and_end_is_the_last_file_time():
    # round_time is the stats file's write time ≈ the round's END (round_canonical.py)
    rows = [_row("20:05:10", 600), _row("21:40:00", 480)]
    assert sr._session_clock(rows) == {"start": "19:55", "end": "21:40", "span_seconds": 6290}


def test_the_duration_falls_back_to_the_parsed_actual_time_like_every_other_duration():
    rows = [_row("20:05:10", None, "8:20"), _row("21:40:00", None, "7:00")]
    assert sr._session_clock(rows)["start"] == "19:56"


def test_the_six_digit_form_reads_the_same_as_the_colon_form():
    assert sr._session_clock([_row("200510", 600)]) == sr._session_clock([_row("20:05:10", 600)])
    assert sr._round_time_hms("4918") == (0, 49, 18)  # zero-padded: 00:49:18, not 49:18


def test_an_evening_across_midnight_keeps_the_span_positive():
    rows = [_row("23:30:00", 600), _row("00:10:00", 300)]
    out = sr._session_clock(rows)
    assert out["start"] == "23:20" and out["end"] == "00:10" and out["span_seconds"] == 3000
    # and a first round that itself straddled midnight
    assert sr._session_clock([_row("00:03:00", 600)])["start"] == "23:53"


def test_missing_times_or_duration_answer_null_not_a_guess():
    assert sr._session_clock([]) == {"start": None, "end": None, "span_seconds": None}
    assert sr._session_clock([_row(None, 600)]) == {"start": None, "end": None, "span_seconds": None}
    out = sr._session_clock([_row("20:00:00", None)])
    assert out["start"] is None and out["end"] == "20:00" and out["span_seconds"] is None


def test_a_pause_in_the_first_round_moves_the_start_back_by_its_length():
    """The duration excludes pauses (shared/round_time.py), so a paused first
    round would otherwise put the start late and the span short by the pause."""
    rows = [_row("20:05:10", 600), _row("21:40:00", 480)]
    plain = sr._session_clock(rows)
    paused = sr._session_clock(rows, first_round_pause_seconds=120)
    assert plain["start"] == "19:55"
    assert paused["start"] == "19:53"
    assert paused["span_seconds"] == plain["span_seconds"] + 120
    assert paused["end"] == plain["end"]


def test_the_pause_helper_reads_the_webhook_list_in_both_of_its_forms():
    assert sr._pause_seconds(None) == 0
    assert sr._pause_seconds('[{"n": 1, "start": 100, "end": 160, "sec": 60}]') == 60
    assert sr._pause_seconds([{"n": 1, "start": 100, "end": 160}, {"sec": 30}]) == 90
