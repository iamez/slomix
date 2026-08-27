"""⛔ THE INSTRUMENT MUST FAIL ITS OWN CONTROLS BEFORE IT JUDGES ANYTHING.

`scripts/validation_family.py` executes §8 of the Spider Web spec — the protocol
that retired 13 of 18 `prox_score` metrics in #556, two of which ranked players
BACKWARDS. A harness that hands out verdicts is only worth its verdicts if it
still says NO to things that are known to be nothing.

The most valuable test here is `test_resampler_actually_varies_the_sample`.
The first version of this harness drew blocks from a hand-rolled LCG. With 16
confirmation blocks — the exact size of the Layer 4 universe — the low four bits
of that generator have period 16, so every bootstrap resample drew the SAME
permutation of all 16 blocks. Variance collapsed to zero, the intervals came
back [nan, nan], and every candidate "shipped", including the pure-noise control.
Nothing in a green test suite would have shown that; the control did.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validation_family import (  # noqa: E402 - path set above
    Candidate,
    Family,
    _Rng,
    block_bootstrap,
    boot_p_value,
    chronological_split,
    detectable_effect,
    holm,
    max_t_intervals,
    outcome_seconds,
    outcome_win,
    within_round_point_biserial,
    within_round_spread,
)


def _round(vals_by_player, winner=1):
    """One round: [(metric_value, team)] -> the row shape the harness reads."""
    return [{"guid": f"p{i}", "rid": 1, "team": t, "winner": winner, "v": v}
            for i, (v, t) in enumerate(vals_by_player)]


_metric = lambda p: p["v"]  # noqa: E731 - one-line test metric


class TestTheResamplerIsNotDegenerate:
    @pytest.mark.parametrize("n", [2, 4, 8, 16, 32, 64])
    def test_resampler_actually_varies_the_sample(self, n):
        """Powers of two are where the old generator died. Draw 8n values and
        require that the second block of n is not a replay of the first."""
        rng = _Rng(20260826)
        draws = [rng.next_below(n) for _ in range(8 * n)]
        assert draws[:n] != draws[n:2 * n], (
            f"n={n}: the resampler repeats with period {n} — every bootstrap "
            f"sample would be identical and every variance would be zero")
        assert len(set(draws)) > 1

    def test_same_seed_reproduces_the_published_table(self):
        a = [_Rng(7).next_below(16) for _ in range(50)]
        b = [_Rng(7).next_below(16) for _ in range(50)]
        assert a == b, "a published seed must reproduce the published result"

    def test_different_seeds_disagree(self):
        a = [_Rng(1).next_below(16) for _ in range(50)]
        b = [_Rng(2).next_below(16) for _ in range(50)]
        assert a != b

    def test_bootstrap_of_varied_blocks_has_nonzero_spread(self):
        """End-to-end version of the bug: 16 blocks, real spread expected."""
        blocks = {}
        for b in range(16):
            # blocks differ: in half of them the high-metric side wins
            winner = 1 if b % 2 == 0 else 2
            blocks[b] = {b: _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner)}
        vals = block_bootstrap(blocks, _metric, resamples=200, seed=20260826)
        assert len(vals) > 100
        assert len(set(vals)) > 1, "every resample produced the same number"


class TestTheMeasurementIsWithinRound:
    def test_a_metric_that_marks_the_winners_scores_positive(self):
        rounds = {i: _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner=1)
                  for i in range(10)}
        assert within_round_spread(rounds, _metric) == pytest.approx(1.0)

    def test_a_metric_that_marks_the_losers_scores_negative(self):
        rounds = {i: _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner=2)
                  for i in range(10)}
        assert within_round_spread(rounds, _metric) == pytest.approx(-1.0)

    def test_a_round_too_small_to_split_is_skipped_not_guessed(self):
        assert within_round_spread({1: _round([(9, 1), (1, 2)])}, _metric) is None

    def test_rounds_with_no_measurable_players_are_excluded(self):
        rounds = {i: _round([(9, 1), (8, 1), (2, 2), (1, 2)]) for i in range(3)}
        assert within_round_spread(rounds, lambda p: None) is None


class TestTheSplitIsChronologicalAndWhole:
    def test_earliest_blocks_discover_and_the_latest_stay_untouched(self):
        times = {f"b{i}": i for i in range(10)}
        disc, conf, ordered, cut = chronological_split(times, 0.70)
        assert len(disc) == 7 and len(conf) == 3
        assert max(times[b] for b in disc) < min(times[b] for b in conf), (
            "a later block leaked into discovery — the halves are not "
            "chronologically separated")

    def test_no_block_appears_in_both_halves(self):
        times = {f"b{i}": i for i in range(50)}
        disc, conf, _, _ = chronological_split(times, 0.70)
        assert not (disc & conf)


class TestFamilyWiseError:
    def test_the_critical_value_exceeds_the_single_candidate_one(self):
        """The whole point of §8.4: testing five things costs more than one.

        Compared like with like — the same distribution, one member versus five.
        An absolute threshold of 1.96 would be the wrong assertion: max-T of a
        BOUNDED distribution can sit below 1.96 and still be the correct
        family-wise value. What must hold is that five costs more than one.
        """
        rng = random.Random(4242)  # noqa: S311  # nosec B311 - test fixture
        draws = {i: [rng.gauss(0.0, 1.0) for _ in range(4000)] for i in range(5)}
        point = {f"c{i}": 0.0 for i in range(5)}

        one = {"c0": draws[0]}
        _, crit_one, _ = max_t_intervals(one, {"c0": 0.0}, 0.05)
        _, crit_five, _ = max_t_intervals({f"c{i}": draws[i] for i in range(5)},
                                          point, 0.05)
        assert crit_five > crit_one, (
            f"testing five candidates ({crit_five:.3f}) cost no more than "
            f"testing one ({crit_one:.3f}) — the family-wise penalty is absent")

    def test_holm_is_monotone_and_never_shrinks_a_p_value(self):
        raw = {"a": 0.001, "b": 0.02, "c": 0.30}
        adj = holm(raw, 0.05)
        assert all(adj[k] >= raw[k] for k in raw)
        assert adj["a"] <= adj["b"] <= adj["c"]

    def test_a_bootstrap_that_straddles_zero_is_not_significant(self):
        vals = [(-1) ** i * 0.01 for i in range(500)]
        assert boot_p_value(vals, 0.001) > 0.05

    def test_a_bootstrap_far_from_zero_is(self):
        assert boot_p_value([0.05] * 500, 0.05) < 0.05


class TestTheManifestIsAFreeze:
    def _family(self, **kw):
        cands = [Candidate("x", "d", "higher_is_better", _metric)]
        return Family(name="t", candidates=cands, filters="WHERE 1=1", **kw)

    def test_the_same_family_hashes_the_same(self):
        assert self._family().manifest_hash() == self._family().manifest_hash()

    @pytest.mark.parametrize("change", [
        {"seed": 999}, {"resamples": 10}, {"split_fraction": 0.5}, {"alpha": 0.01},
    ])
    def test_changing_any_frozen_knob_moves_the_hash(self, change):
        """§8.3: retuning after seeing confirmation is a NEW hypothesis. The
        hash is what makes that visible instead of deniable."""
        assert self._family().manifest_hash() != self._family(**change).manifest_hash()

    def test_changing_a_candidate_moves_the_hash(self):
        base = self._family()
        other = Family(name="t", filters="WHERE 1=1",
                       candidates=[Candidate("y", "d", "higher_is_better", _metric)])
        assert base.manifest_hash() != other.manifest_hash()


class TestTheFloorIsPublished:
    def test_a_smaller_sample_raises_the_detectable_effect(self):
        assert detectable_effect(0.05) > detectable_effect(0.02)

    def test_an_unmeasurable_sd_gives_no_false_comfort(self):
        assert math.isnan(detectable_effect(float("nan")))


class TestTheAlternativeEstimator:
    """`within_round_point_biserial` exists as a measured alternative, not a
    replacement — see its docstring for why it lost. These tests pin its
    behaviour so it stays honest if anyone revisits it."""

    def test_it_agrees_with_the_reference_on_direction(self):
        rounds = {i: _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner=1)
                  for i in range(10)}
        assert within_round_point_biserial(rounds, _metric) > 0
        assert within_round_spread(rounds, _metric) > 0

    def test_a_round_where_everyone_shares_an_outcome_is_skipped(self):
        """No within-round information about winning exists there. Scoring it as
        zero would be an absence read as evidence."""
        same = [{"guid": f"p{i}", "rid": 1, "team": 1, "winner": 1, "v": i}
                for i in range(6)]
        assert within_round_point_biserial({1: same}, _metric) is None

    def test_a_constant_metric_carries_no_signal(self):
        rounds = {i: _round([(5, 1), (5, 1), (5, 2), (5, 2)], winner=1)
                  for i in range(5)}
        assert within_round_point_biserial(rounds, _metric) is None


class TestTheOutcomeDefinition:
    """§8.3 freezes the OUTCOME as well as the formula. Win/loss is one bit per
    round; the stopwatch margin is a continuous measurement of the same match.
    Which one is used changes the answer, so it changes the manifest hash."""

    def _p(self, team, winner=1, margin=None, r2_attacker=None):
        return {"guid": "g", "rid": 1, "team": team, "winner": winner,
                "margin": margin, "r2_attacker": r2_attacker, "v": 1}

    def test_win_outcome_is_one_for_the_winning_side(self):
        assert outcome_win(self._p(1, winner=1)) == 1.0
        assert outcome_win(self._p(2, winner=1)) == 0.0

    def test_the_margin_is_signed_by_which_side_attacked_in_r2(self):
        """Positive margin means the R2 attack was faster. That side gains it;
        the other side loses exactly as much."""
        fast = self._p(1, margin=40.0, r2_attacker=1)
        slow = self._p(2, margin=40.0, r2_attacker=1)
        assert outcome_seconds(fast) == +40.0
        assert outcome_seconds(slow) == -40.0

    def test_an_unresolved_pair_is_unmeasurable_not_a_dead_heat(self):
        """A missing measurement and a zero margin have the same shape. Reading
        the first as the second would invent evidence."""
        assert outcome_seconds(self._p(1, margin=None, r2_attacker=1)) is None
        assert outcome_seconds(self._p(1, margin=10.0, r2_attacker=None)) is None

    def test_a_round_with_any_unmeasurable_player_is_dropped_whole(self):
        """Half a round would compare two different populations."""
        players = [self._p(1, margin=40.0, r2_attacker=1) for _ in range(3)]
        players.append(self._p(2, margin=None, r2_attacker=1))
        for i, p in enumerate(players):
            p["v"] = i
        assert within_round_spread({1: players}, _metric, outcome_seconds) is None

    def test_changing_the_outcome_moves_the_manifest_hash(self):
        cands = [Candidate("x", "d", "higher_is_better", _metric)]
        a = Family(name="t", candidates=cands, filters="f", outcome="win")
        b = Family(name="t", candidates=cands, filters="f", outcome="seconds")
        assert a.manifest_hash() != b.manifest_hash()


class TestOnePlayerRowPerRound:
    """The R1/R2 window admits more than one partner — the same map replayed in
    a session gives one R1 two or three candidate R2s (189 rounds on the live
    database). Joining that naively duplicates every player row in those rounds,
    and a duplicated player is counted twice inside the very comparison that is
    supposed to be within-round. The SQL de-duplicates with DISTINCT ON; this
    test states the invariant that de-duplication exists to protect."""

    def test_a_duplicated_player_can_change_the_answer(self):
        """Why the invariant matters.

        Note the "can": the first version of this test asserted that duplication
        ALWAYS moves the number, and it failed. A median split is robust — when
        the two sides are cleanly separated, a repeated row lands in the half it
        already dominated and the result is unchanged. It bites on the mixed
        rounds, which is where the measurement is actually doing work, so a
        duplicate corrupts precisely the rounds that carry the signal.
        """
        mixed = _round([(9, 1), (2, 1), (8, 2), (1, 2)], winner=1)
        doubled = mixed + [dict(mixed[0])]
        # two rounds: the estimator needs more than one to return a mean
        assert within_round_spread({1: mixed, 2: mixed}, _metric) == pytest.approx(0.0)
        assert (within_round_spread({1: doubled, 2: doubled}, _metric)
                == pytest.approx(0.5))

    def test_a_cleanly_separated_round_absorbs_the_duplicate(self):
        """The other half of the same fact, so nobody reads the test above as
        'duplication is always visible'. It is not, which is why the SQL
        de-duplicates instead of relying on the measurement to notice."""
        clean = _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner=1)
        doubled = clean + [dict(clean[0])]
        assert (within_round_spread({1: clean, 2: clean}, _metric)
                == within_round_spread({1: doubled, 2: doubled}, _metric))
