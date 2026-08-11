"""Unit tests for ET Rating sample-size shrinkage (FIX 8).

Covers the pure shrink_rating() function, the FIX 8 canary on the real
2026-08-11 rated pool (kept as a frozen fixture — no database required),
and the compute_all_ratings() integration (fake DB, single fetch_all).

FIX 8 canary (docs/research/FIX_ME_2026-08-11.md): a player with < 20 rounds
must not rank above a player with > 500 rounds, unless the RAW rating
difference exceeds twice the standard error of the low-sample estimate
(SE = pool std of raw ratings / sqrt(n)).
"""

import statistics
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.skill_rating_service import (
    MIN_ROUNDS,
    SHRINKAGE_K,
    compute_all_ratings,
    get_tier,
    shrink_rating,
)

# ---------------------------------------------------------------------------
# Frozen fixture: player_skill_ratings as of 2026-08-11 (the pool the FIX 8
# evidence was measured on). (display_name, raw et_rating, games_rated).
# ---------------------------------------------------------------------------
POOL_2026_08_11 = [
    ("squaze you dumbass", 0.8123, 96),
    ("vid", 0.7688, 1674),
    ("SuperBoyy", 0.7292, 1566),
    ("bronzelow-", 0.7285, 931),
    ("ownator", 0.655, 45),
    ("olz", 0.6419, 1738),
    ("Cru3lzor.", 0.6312, 516),
    ("i p k i s s", 0.63, 8),
    ("//^?/M.Demonslayer", 0.625, 14),
    (".wjs", 0.6169, 979),
    ("s&o.lgz", 0.6138, 1280),
    ("Zlatorog", 0.6081, 56),
    ("XI-WANG", 0.5969, 796),
    ("endekk", 0.5962, 1033),
    ("Peep", 0.5958, 10),
    ("-slo.carniee-", 0.5954, 885),
    ("KaNii...", 0.5862, 298),
    ("immoo{", 0.5819, 87),
    ("G4rch4", 0.551, 6),
    ("'^/fnx", 0.5135, 10),
    ("//^?/M.Gekku", 0.4915, 10),
    ("-C3jZi", 0.4867, 6),
    ("v_kt_r", 0.4419, 442),
    ("//^?/M.rAzzdOG", 0.4354, 14),
    ("konrad!", 0.4338, 10),
    ("Imbecil", 0.3631, 5),
    ("MrAvAc", 0.3546, 6),
    ("KaNii", 0.2729, 30),
    ("Rakun", 0.2548, 14),
]

POOL_MEAN = sum(r for _, r, _ in POOL_2026_08_11) / len(POOL_2026_08_11)
POOL_SD = statistics.stdev(r for _, r, _ in POOL_2026_08_11)


def _canary_violations(k: float) -> list[tuple]:
    """FIX 8 canary over the frozen pool for a given shrinkage K.

    Returns (low_name, low_n, high_name, high_n) for every pair where a
    < 20-round player ranks above a > 500-round player without the raw-rating
    gap exceeding 2 SE of the low-sample estimate.
    """
    shrunk = sorted(
        ((name, shrink_rating(raw, n, POOL_MEAN, k), n, raw)
         for name, raw, n in POOL_2026_08_11),
        key=lambda x: -x[1],
    )
    violations = []
    for i, (lo_name, _lo_s, lo_n, lo_raw) in enumerate(shrunk):
        if lo_n >= 20:
            continue
        for hi_name, _hi_s, hi_n, hi_raw in shrunk[i + 1:]:
            if hi_n <= 500:
                continue
            two_se = 2 * POOL_SD / (lo_n ** 0.5)
            if lo_raw - hi_raw <= two_se:
                violations.append((lo_name, lo_n, hi_name, hi_n))
    return violations


# ===========================================================================
# shrink_rating — pure function
# ===========================================================================

class TestShrinkRating:
    def test_exact_formula(self):
        # (10*0.8 + 40*0.5) / 50 = 28/50 = 0.56
        assert shrink_rating(0.8, 10, 0.5, k=40) == pytest.approx(0.56)

    def test_zero_rounds_returns_pool_mean(self):
        assert shrink_rating(0.9, 0, 0.55) == pytest.approx(0.55)

    def test_negative_rounds_clamped_to_zero(self):
        assert shrink_rating(0.9, -5, 0.55) == pytest.approx(0.55)

    def test_k_zero_disables_shrinkage(self):
        assert shrink_rating(0.9, 3, 0.55, k=0) == 0.9

    def test_k_negative_disables_shrinkage(self):
        assert shrink_rating(0.9, 3, 0.55, k=-1) == 0.9

    def test_default_k_is_shrinkage_k(self):
        assert shrink_rating(0.8, 10, 0.5) == pytest.approx(
            shrink_rating(0.8, 10, 0.5, k=SHRINKAGE_K))

    def test_result_between_rating_and_pool_mean(self):
        for n in (1, 8, 40, 500):
            s = shrink_rating(0.9, n, 0.5)
            assert 0.5 < s < 0.9
            s = shrink_rating(0.2, n, 0.5)
            assert 0.2 < s < 0.5

    def test_monotone_in_rounds_above_mean(self):
        """More evidence → less shrinkage: above-mean ratings rise with n."""
        vals = [shrink_rating(0.9, n, 0.5) for n in (1, 10, 40, 200, 2000)]
        assert vals == sorted(vals)

    def test_equal_weight_at_n_equals_k(self):
        """At n == K the player and the prior each carry half the weight."""
        s = shrink_rating(0.9, SHRINKAGE_K, 0.5)
        assert s == pytest.approx((0.9 + 0.5) / 2)

    def test_large_n_barely_moves(self):
        """A 1,700-round veteran keeps their rating (< 0.005 shift)."""
        assert abs(shrink_rating(0.7688, 1674, POOL_MEAN) - 0.7688) < 0.005

    def test_rating_at_pool_mean_is_fixed_point(self):
        assert shrink_rating(0.55, 7, 0.55) == pytest.approx(0.55)


# ===========================================================================
# FIX 8 canary on the frozen 2026-08-11 pool
# ===========================================================================

class TestFix8Canary:
    def test_raw_ratings_violate_canary(self):
        """Sanity: WITHOUT shrinkage the documented anomalies exist
        (i p k i s s @ 8 rounds above .wjs @ 979, etc.)."""
        violations = _canary_violations(k=0)
        assert len(violations) > 0
        assert ("i p k i s s", 8, ".wjs", 979) in violations

    def test_shrunk_ratings_pass_canary(self):
        """With SHRINKAGE_K there is no <20-round player above a >500-round
        player within 2 SE — the FIX 8 acceptance criterion."""
        assert _canary_violations(k=SHRINKAGE_K) == []

    def test_documented_anomalies_fixed(self):
        """The specific FIX 8 evidence pairs flip the right way."""
        shrunk = {name: shrink_rating(raw, n, POOL_MEAN)
                  for name, raw, n in POOL_2026_08_11}
        assert shrunk[".wjs"] > shrunk["i p k i s s"]
        assert shrunk[".wjs"] > shrunk["//^?/M.Demonslayer"]
        assert shrunk["-slo.carniee-"] > shrunk["Peep"]
        assert shrunk["olz"] > shrunk["i p k i s s"]

    def test_veteran_ratings_stable(self):
        """>1,000-round players shift by < 0.005 rating points."""
        for name, raw, n in POOL_2026_08_11:
            if n > 1000:
                assert abs(shrink_rating(raw, n, POOL_MEAN) - raw) < 0.005, name

    def test_tier_boundaries_still_valid(self):
        """Every shrunk rating maps to a tier, and tiers stay ordered when
        players are ranked by shrunk rating (no boundary breakage)."""
        tier_order = ["elite", "veteran", "experienced", "regular", "newcomer"]
        ranked = sorted(
            (shrink_rating(raw, n, POOL_MEAN) for _, raw, n in POOL_2026_08_11),
            reverse=True,
        )
        indices = [tier_order.index(get_tier(s)) for s in ranked]
        assert indices == sorted(indices)


# ===========================================================================
# compute_all_ratings integration (fake DB)
# ===========================================================================

def _row(guid, name, rounds, dpm, kpr):
    """A compute_all_ratings SQL row: guid, name, rounds + 15 metric columns.

    Only dpm/kpr vary; the other 13 metrics are constant so percentile ranks
    are driven by the two varying metrics.
    """
    return (
        guid, name, rounds,
        dpm, kpr, 1.0,        # dpm, kpr, dpr
        0.5, 0.5, 0.5, 0.5,   # revive, objective, survival, useful
        30.0,                 # accuracy
        1.0, 1.0, 0.1, 0.1,   # denied, kill_quality, crossfire, trade
        0.1, 0.1, 0.5,        # permanence, clutch, spawn_timing
    )


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows
        self.queries = []

    async def fetch_all(self, query, params=()):
        self.queries.append((query, params))
        return self._rows


@pytest.mark.asyncio
async def test_compute_all_ratings_applies_shrinkage():
    """A 6-round wonder with the best raw stats must drop below a 900-round
    veteran with slightly weaker raw stats; et_rating_raw keeps the unshrunk
    value and et_rating equals the shrinkage formula exactly."""
    rows = [
        _row("guid_new", "newcomer", 6, 500.0, 3.0),     # best raw stats, n=6
        _row("guid_vet", "veteran", 900, 450.0, 2.5),    # close behind, n=900
        _row("guid_mid", "midtable", 200, 300.0, 1.5),
        _row("guid_low", "lowtable", 400, 200.0, 1.0),
    ]
    results = await compute_all_ratings(_FakeDB(rows))
    by_guid = {p["player_guid"]: p for p in results}

    # Raw ordering: the 6-round player has the best unshrunk rating.
    assert by_guid["guid_new"]["et_rating_raw"] > by_guid["guid_vet"]["et_rating_raw"]

    # Published (shrunk) ordering flips: evidence outweighs the hot sample.
    assert by_guid["guid_vet"]["et_rating"] > by_guid["guid_new"]["et_rating"]

    # et_rating is exactly the Bayesian formula over the cohort's raw mean.
    pool_mean = sum(p["et_rating_raw"] for p in results) / len(results)
    for p in results:
        expected = shrink_rating(p["et_rating_raw"], p["rounds"], pool_mean)
        assert p["et_rating"] == pytest.approx(expected, abs=1e-4), p["player_guid"]

    # Result list is sorted by the published (shrunk) rating.
    ratings = [p["et_rating"] for p in results]
    assert ratings == sorted(ratings, reverse=True)


@pytest.mark.asyncio
async def test_compute_all_ratings_single_player_is_own_prior():
    """A one-player cohort shrinks toward itself — rating unchanged."""
    results = await compute_all_ratings(_FakeDB([_row("g1", "solo", 10, 400.0, 2.0)]))
    assert len(results) == 1
    assert results[0]["et_rating"] == pytest.approx(results[0]["et_rating_raw"], abs=1e-4)


@pytest.mark.asyncio
async def test_compute_all_ratings_empty_pool():
    assert await compute_all_ratings(_FakeDB([])) == []


def test_min_rounds_unchanged():
    """FIX 8 keeps the hard gate at 5 — shrinkage is the soft gate."""
    assert MIN_ROUNDS == 5


def test_shrinkage_k_in_documented_band():
    """K was chosen empirically inside the 30–50 band (FIX 8); the canary
    first passes at K≈15 on the frozen pool, so 30–50 carries ≥2× margin."""
    assert 30 <= SHRINKAGE_K <= 50
    assert _canary_violations(k=SHRINKAGE_K) == []
