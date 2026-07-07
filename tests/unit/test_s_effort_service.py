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


def test_adjusted_lifetime_no_oscillation_and_bounded_drift():
    """Damping kills oscillation; residual drift stays constant-or-shrinking.

    In a closed loop the iteration matrix keeps a unit eigenvalue along the
    population mean, so when mean session rating != POOL_NEUTRAL the whole
    system drifts linearly per iteration — that's WHY POOL_NEUTRAL is defined
    as the measured population mean (drift ~0 on real data) and iterations
    are capped. The guard here: steps never grow and never flip sign.
    """
    sess = {"A": [("s1", 0.6)], "B": [("s1", 0.5)]}
    parts = {"s1": ["A", "B"]}
    seed = {"A": 0.6, "B": 0.5}
    steps = []
    prev = adjusted_lifetime(sess, seed, parts, iterations=4)
    for it in (5, 6, 7):
        cur = adjusted_lifetime(sess, seed, parts, iterations=it)
        steps.append(cur["A"] - prev["A"])
        prev = cur
    assert all(s <= 0 for s in steps) or all(s >= 0 for s in steps)  # no sign flips
    assert abs(steps[0]) >= abs(steps[1]) >= abs(steps[2])  # never grows
    assert abs(steps[2]) <= 0.011  # bounded per-iteration movement


def test_adjusted_lifetime_fixed_point_when_mean_anchored():
    """When session ratings straddle POOL_NEUTRAL symmetrically, the closed
    system has a true fixed point and extra iterations change nothing."""
    sess = {"A": [("s1", POOL_NEUTRAL + 0.05)], "B": [("s1", POOL_NEUTRAL - 0.05)]}
    parts = {"s1": ["A", "B"]}
    seed = {"A": POOL_NEUTRAL + 0.05, "B": POOL_NEUTRAL - 0.05}
    a5 = adjusted_lifetime(sess, seed, parts, iterations=5)
    a8 = adjusted_lifetime(sess, seed, parts, iterations=8)
    assert abs(a5["A"] - a8["A"]) < 1e-9
    assert abs(a5["B"] - a8["B"]) < 1e-9
    assert a5["A"] > a5["B"]  # ordering preserved
