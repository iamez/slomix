"""s.effort pure-math tests (K-D; formulas per owner-approved backtest v0.1)."""
from __future__ import annotations

from website.backend.services.s_effort_service import (
    POOL_NEUTRAL,
    adjusted_lifetime,
    pool_strength_A,
    s_effort,
    s_performance,
)


def test_effort_at_pool_level_is_scale_of_rating():
    # playing exactly at pool strength -> effort == sess/pool == 1 when equal
    assert s_effort(0.564, 0.564) == 1.0
    assert s_effort(0.6, 0.5) == 1.2


def test_performance_neutralizes_lifetime():
    # average player (lifetime == NEUTRAL) performing at pool level -> 1.0
    eff = s_effort(POOL_NEUTRAL, POOL_NEUTRAL)
    assert abs(s_performance(eff, POOL_NEUTRAL) - 1.0) < 1e-9


def test_pool_A_is_leave_one_out():
    assert pool_strength_A([0.5, 0.6, 0.7], 0.7) == 0.55
    # self removed only once even if duplicated rating values exist
    assert pool_strength_A([0.6, 0.6, 0.6], 0.6) == 0.6


def test_zero_or_missing_pool_returns_none():
    assert s_effort(0.6, 0) is None
    assert pool_strength_A([0.6], 0.6) is None


def test_adjusted_lifetime_harder_pool_is_plus():
    # two players, identical session ratings; P faced a stronger co-pool than Q
    sess = {"P": [("s1", 0.5)], "Q": [("s2", 0.5)]}
    parts = {"s1": ["P", "STRONG"], "s2": ["Q", "WEAK"]}
    seed = {"P": 0.5, "Q": 0.5, "STRONG": 0.8, "WEAK": 0.3}
    adj = adjusted_lifetime(sess, seed, parts, iterations=1)
    assert adj["P"] > adj["Q"]  # harder pool = PLUS (owner sign correction)


def test_adjusted_lifetime_volume_does_not_inflate():
    # same per-session performance, one player has 3x the sessions -> equal adj
    sess = {
        "A": [("s1", 0.6)],
        "B": [("s2", 0.6), ("s3", 0.6), ("s4", 0.6)],
    }
    parts = {k: [p, "X"] for k, p in
             (("s1", "A"), ("s2", "B"), ("s3", "B"), ("s4", "B"))}
    seed = {"A": 0.6, "B": 0.6, "X": POOL_NEUTRAL}
    adj = adjusted_lifetime(sess, seed, parts, iterations=3)
    assert abs(adj["A"] - adj["B"]) < 1e-9  # AVG, never a sum


def test_adjusted_lifetime_converges():
    sess = {"A": [("s1", 0.6)], "B": [("s1", 0.5)]}
    parts = {"s1": ["A", "B"]}
    seed = {"A": 0.6, "B": 0.5}
    a5 = adjusted_lifetime(sess, seed, parts, iterations=5)
    a6 = adjusted_lifetime(sess, seed, parts, iterations=6)
    assert abs(a5["A"] - a6["A"]) < 0.01
