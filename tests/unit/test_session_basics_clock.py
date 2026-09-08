"""The session clock on /basics — start of the first counted round, end of
the last (start + measured duration), midnight crossing, and the dual form
of rounds.round_time."""
from __future__ import annotations

from website.backend.routers import sessions_router as sr


def _row(round_time, duration):
    return (1, "supply", 1, 2, "2026-08-23", round_time, None, None, duration)


def test_start_end_and_span_from_the_first_and_last_counted_rounds():
    rows = [_row("20:05:10", 600), _row("21:40:00", 480)]
    assert sr._session_clock(rows) == {"start": "20:05", "end": "21:48", "span_seconds": 6170}


def test_the_six_digit_form_reads_the_same_as_the_colon_form():
    assert sr._session_clock([_row("200510", 600)]) == sr._session_clock([_row("20:05:10", 600)])
    assert sr._round_time_hms("4918") == (0, 49, 18)  # zero-padded: 00:49:18, not 49:18


def test_an_evening_across_midnight_keeps_the_span_positive():
    rows = [_row("23:30:00", 600), _row("00:10:00", 300)]
    out = sr._session_clock(rows)
    assert out["start"] == "23:30" and out["end"] == "00:15" and out["span_seconds"] == 2700


def test_missing_times_or_duration_answer_null_not_a_guess():
    assert sr._session_clock([]) == {"start": None, "end": None, "span_seconds": None}
    assert sr._session_clock([_row(None, 600)]) == {"start": None, "end": None, "span_seconds": None}
    out = sr._session_clock([_row("20:00:00", None)])
    assert out["start"] == "20:00" and out["end"] is None and out["span_seconds"] is None
