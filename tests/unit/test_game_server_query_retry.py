"""getstatus is one unacknowledged UDP datagram each way.

In 30 days of the bot's polling, 10 of 8,697 samples came back "offline" and 6 of
those were isolated singletons with a healthy sample either side — downtime
recorded in server_status_history that never happened.

The delay in front of the retry is the substance of this fix, not an afterthought:
20 queries 0.2 s apart lost 10 %, the same 20 queries 3 s apart lost 0 %, because
the engine rate-limits repeated getstatus from one source. An immediate resend
would land back in that limiter. With the 0.75 s pause, a 0.2 s-apart burst that
scored 18/20 raw scored 20/20 (measured 2026-08-15).

These tests pin the retry, the pause, and — just as importantly — the cases that
must NOT be retried.
"""
from __future__ import annotations

import pytest

from website.backend.services import game_server_query as Q
from website.backend.services.game_server_query import ServerStatus, query_game_server


def _fake_once(results):
    """Hand back canned outcomes in order, recording the call count."""
    calls = {"n": 0}

    def _once(_host, _port, _timeout):
        calls["n"] += 1
        return results[min(calls["n"] - 1, len(results) - 1)]

    return _once, calls


def test_a_lost_datagram_does_not_become_server_down(monkeypatch):
    monkeypatch.setattr(Q.time, "sleep", lambda _s: None)
    once, calls = _fake_once([
        ServerStatus(online=False, error="Server not responding"),
        ServerStatus(online=True, map_name="supply", ping_ms=6),
    ])
    monkeypatch.setattr(Q, "_query_once", once)

    status = query_game_server("puran.hehe.si")

    assert status.online is True
    assert status.map_name == "supply"
    assert calls["n"] == 2


def test_an_answer_costs_exactly_one_round_trip(monkeypatch):
    """The common case must not pay for the retry."""
    once, calls = _fake_once([ServerStatus(online=True, map_name="supply")])
    monkeypatch.setattr(Q, "_query_once", once)

    assert query_game_server("puran.hehe.si").online is True
    assert calls["n"] == 1


def test_a_genuinely_dead_server_is_still_reported_down(monkeypatch):
    monkeypatch.setattr(Q.time, "sleep", lambda _s: None)
    once, calls = _fake_once([ServerStatus(online=False, error="Server not responding")])
    monkeypatch.setattr(Q, "_query_once", once)

    status = query_game_server("puran.hehe.si")

    assert status.online is False
    assert status.error == "Server not responding"
    assert calls["n"] == 2      # tried, then believed the silence


def test_dns_failure_is_not_retried(monkeypatch):
    """A name that does not resolve will not resolve on the second try either —
    retrying only doubles the wait before the same answer."""
    once, calls = _fake_once([ServerStatus(online=False, error="DNS resolution failed")])
    monkeypatch.setattr(Q, "_query_once", once)

    status = query_game_server("nope.invalid")

    assert status.error == "DNS resolution failed"
    assert calls["n"] == 1


@pytest.mark.parametrize("attempts,expected", [(1, 1), (3, 3), (0, 1)])
def test_attempts_is_honoured_and_never_zero(monkeypatch, attempts, expected):
    monkeypatch.setattr(Q.time, "sleep", lambda _s: None)
    once, calls = _fake_once([ServerStatus(online=False, error="Server not responding")])
    monkeypatch.setattr(Q, "_query_once", once)

    query_game_server("puran.hehe.si", attempts=attempts)

    assert calls["n"] == expected


def test_the_retry_waits_before_resending(monkeypatch):
    """Without the pause the resend lands in the engine's rate limiter, which is
    what dropped the first answer — the retry would then confirm its own failure."""
    slept: list[float] = []
    monkeypatch.setattr(Q.time, "sleep", lambda s: slept.append(s))
    once, _ = _fake_once([
        ServerStatus(online=False, error="Server not responding"),
        ServerStatus(online=True, map_name="supply"),
    ])
    monkeypatch.setattr(Q, "_query_once", once)

    query_game_server("puran.hehe.si")

    assert slept == [pytest.approx(0.75)]


def test_a_successful_first_answer_never_sleeps(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(Q.time, "sleep", lambda s: slept.append(s))
    once, _ = _fake_once([ServerStatus(online=True, map_name="supply")])
    monkeypatch.setattr(Q, "_query_once", once)

    query_game_server("puran.hehe.si")

    assert slept == []


def test_dns_failure_does_not_even_wait(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(Q.time, "sleep", lambda s: slept.append(s))
    once, _ = _fake_once([ServerStatus(online=False, error="DNS resolution failed")])
    monkeypatch.setattr(Q, "_query_once", once)

    query_game_server("nope.invalid")

    assert slept == []


@pytest.mark.parametrize("bad_delay", [-1.0, float("inf"), float("nan")])
def test_a_broken_delay_becomes_no_delay_not_an_immediate_resend(monkeypatch, bad_delay):
    """A negative delay would silently restore the behaviour this fix removes,
    and inf would hang or raise inside time.sleep. Neither may reach sleep()."""
    slept: list[float] = []
    monkeypatch.setattr(Q.time, "sleep", lambda s: slept.append(s))
    once, calls = _fake_once([
        ServerStatus(online=False, error="Server not responding"),
        ServerStatus(online=True, map_name="supply"),
    ])
    monkeypatch.setattr(Q, "_query_once", once)

    status = query_game_server("puran.hehe.si", retry_delay=bad_delay)

    assert slept == []          # never handed a bad value to sleep
    assert calls["n"] == 2      # still retried
    assert status.online is True


def test_attempts_zero_still_queries_once(monkeypatch, caplog):
    """attempts=0 means one attempt, not none — and with one attempt the retry
    log never runs, so "no /0 in the log" alone would also pass if the function
    silently did nothing. Assert the query itself."""
    monkeypatch.setattr(Q.time, "sleep", lambda _s: None)
    once, calls = _fake_once([ServerStatus(online=False, error="Server not responding")])
    monkeypatch.setattr(Q, "_query_once", once)

    with caplog.at_level("DEBUG", logger=Q.logger.name):
        status = query_game_server("puran.hehe.si", attempts=0)

    assert calls["n"] == 1
    assert status.online is False
    assert "/0" not in caplog.text


def test_the_logged_denominator_is_the_normalised_total(monkeypatch, caplog):
    """This one actually reaches the retry log, so it can check what it says."""
    monkeypatch.setattr(Q.time, "sleep", lambda _s: None)
    once, calls = _fake_once([ServerStatus(online=False, error="Server not responding")])
    monkeypatch.setattr(Q, "_query_once", once)

    with caplog.at_level("DEBUG", logger=Q.logger.name):
        query_game_server("puran.hehe.si", attempts=3)

    assert calls["n"] == 3
    assert "attempt 1/3" in caplog.text
    assert "attempt 2/3" in caplog.text
    # The last failure is not a "retrying" line — there is nothing after it.
    assert "attempt 3/3" not in caplog.text
