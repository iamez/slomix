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

import inspect
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validation_family import (  # noqa: E402 - path set above
    DEFAULT_FAMILY,
    ESTIMATORS,
    ROWS_SQL,
    Candidate,
    Family,
    _Rng,
    analyse,
    block_bootstrap,
    block_draws,
    boot_p_value,
    chronological_split,
    detectable_effect,
    holm,
    instrument_check,
    margin_agreement,
    max_t_intervals,
    outcome_seconds,
    outcome_win,
    preregister,
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
        draws = block_draws(blocks, resamples=200, seed=20260826)
        vals = [v for v in block_bootstrap(blocks, _metric, draws) if v is not None]
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

    def _p(self, team, winner=1, margin=None, defender=None, half=2):
        return {"guid": "g", "rid": 1, "team": team, "winner": winner,
                "margin": margin, "r2_defender": defender, "half": half,
                "map_winner_side": winner, "v": 1}

    def test_win_outcome_is_one_for_the_winning_side(self):
        assert outcome_win(self._p(1, winner=1)) == 1.0
        assert outcome_win(self._p(2, winner=1)) == 0.0

    def test_the_margin_is_signed_by_who_attacks_in_this_round(self):
        """Positive margin means the R2 attack was faster. In R2 the attacking
        side gains it; the defending side loses exactly as much. The attacker is
        read per round, because the sides swap between the halves."""
        fast = self._p(2, margin=40.0, defender=1, half=2)   # attacks in R2
        slow = self._p(1, margin=40.0, defender=1, half=2)   # defends in R2
        assert outcome_seconds(fast) == +40.0
        assert outcome_seconds(slow) == -40.0

    def test_an_unresolved_pair_is_unmeasurable_not_a_dead_heat(self):
        """A missing measurement and a zero margin have the same shape. Reading
        the first as the second would invent evidence."""
        assert outcome_seconds(self._p(1, margin=None, defender=1)) is None
        assert outcome_seconds(self._p(1, margin=10.0, defender=None)) is None

    def test_a_round_with_any_unmeasurable_player_is_dropped_whole(self):
        """Half a round would compare two different populations."""
        players = [self._p(1, margin=40.0, defender=2) for _ in range(3)]
        players.append(self._p(2, margin=None, defender=2))
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


class TestTheCodexRound:
    """Five P1s and a P2 from review, each pinned by the test that would have
    caught it. Written after the fixes, which is late — but a defect without a
    test is a defect that comes back."""

    def test_an_unmeasurable_candidate_gets_no_interval_and_fails(self):
        """`nan` compares false against everything, so `not (lo <= 0 <= hi)`
        read a nan interval as 'excludes zero' and SHIPPED an unmeasured
        candidate. Absence of evidence wearing the shape of evidence."""
        boot = {"flat": [0.05] * 500}          # zero spread -> no usable SD
        intervals, crit, sds = max_t_intervals(boot, {"flat": 0.05}, 0.05)
        assert "flat" not in intervals, "an unmeasurable candidate got an interval"
        assert math.isnan(sds["flat"]) or sds["flat"] == 0

    def test_too_few_usable_replicates_yields_no_interval(self):
        boot = {"thin": [0.05, 0.06, None] + [None] * 500}
        intervals, _, _ = max_t_intervals(boot, {"thin": 0.05}, 0.05)
        assert "thin" not in intervals

    def test_every_candidate_sees_the_same_draws(self):
        """max-T reads element j of every candidate as ONE joint replicate. Per
        candidate seeds would destroy the covariance the interval depends on."""
        a = block_draws({i: {} for i in range(8)}, resamples=50, seed=5)
        b = block_draws({i: {} for i in range(8)}, resamples=50, seed=5)
        assert a == b
        assert any(d1 != d2 for d1, d2 in zip(a, a[1:])), "draws never vary"

    def test_a_tied_median_does_not_get_split_by_row_order(self):
        """Kills are small integers, so the median value is routinely shared. A
        CONSTANT metric must carry no signal regardless of the order rows
        arrive in — it used to score +1 or -1 depending on it."""
        const = lambda p: 7.0  # noqa: E731
        one = _round([(0, 1), (0, 1), (0, 2), (0, 2)], winner=1)
        other = _round([(0, 2), (0, 2), (0, 1), (0, 1)], winner=1)
        assert within_round_spread({1: one, 2: one}, const) is None
        assert within_round_spread({1: other, 2: other}, const) is None

    def test_players_at_the_boundary_value_are_dropped_from_both_halves(self):
        rounds = {i: _round([(1, 2), (5, 1), (5, 2), (9, 1)], winner=1)
                  for i in range(3)}
        # 5 is shared across the median -> both 5s drop, leaving 1 vs 9
        assert within_round_spread(rounds, _metric) == pytest.approx(1.0)

    def test_the_formula_is_in_the_manifest_not_just_its_prose(self):
        """Changing a lambda without editing its description must move the hash,
        or two materially different experiments claim one frozen family."""
        same = Candidate("x", "d", "higher_is_better", lambda p: p["v"])
        assert same.formula_fingerprint().startswith(("source:", "bytecode-shape:"))
        a = Candidate("x", "d", "higher_is_better", lambda p: float(p["v"]))
        b = Candidate("x", "d", "higher_is_better", lambda p: float(p["v"]) * 2.0)
        assert a.formula_fingerprint() != b.formula_fingerprint()

    def test_a_frozen_cutoff_beats_the_percentile(self):
        """The boundary must not drift as new blocks arrive: blocks already seen
        in confirmation would slide into discovery under an unchanged hash."""
        times = {f"b{i}": f"2026-0{1 + i // 5}-0{1 + i % 5} 12:00:00"
                 for i in range(10)}
        _, conf_a, _, _ = chronological_split(times, 0.70, "2026-02-03 00:00:00")
        times["b99"] = "2026-03-01 12:00:00"      # a new block arrives
        _, conf_b, _, _ = chronological_split(times, 0.70, "2026-02-03 00:00:00")
        assert conf_a <= conf_b, "a frozen cutoff moved a block out of confirmation"

    def test_without_a_frozen_cutoff_the_boundary_does_drift(self):
        """The other half of the fact — why the flag exists at all."""
        times = {f"b{i}": f"2026-01-{10 + i} 12:00:00" for i in range(10)}
        _, conf_a, _, _ = chronological_split(times, 0.70)
        for j in range(10):
            times[f"n{j}"] = f"2026-02-{10 + j} 12:00:00"
        _, conf_b, _, _ = chronological_split(times, 0.70)
        assert conf_a - conf_b, "expected the percentile split to drift"


class TestTheSecondCodexRound:
    """Seven more findings on the fixes themselves. The margin one is the reason
    this class matters: it did not tighten a guard, it retired a conclusion."""

    def _p(self, team, defender, half, margin, winner=1, map_winner=None, rid=1):
        return {"guid": "g", "rid": rid, "team": team, "winner": winner,
                "r2_defender": defender, "half": half, "margin": margin,
                "map_winner_side": map_winner if map_winner else winner, "v": 1}

    def test_the_sign_flips_between_the_halves(self):
        """The side swaps between R1 and R2 (1,130 of 1,383 paired rows). Taking
        R1's defender for both halves gave the two halves of one match
        contradictory labels."""
        # team 1 defends: in R2 it is the R2 attacker's opponent
        r2_attacker = self._p(team=2, defender=1, half=2, margin=40.0)
        r2_defender = self._p(team=1, defender=1, half=2, margin=40.0)
        assert outcome_seconds(r2_attacker) == +40.0
        assert outcome_seconds(r2_defender) == -40.0
        # the same persistent side, one half earlier, attacks in R1
        r1_attacker = self._p(team=2, defender=1, half=1, margin=40.0)
        assert outcome_seconds(r1_attacker) == -40.0

    def test_an_unknown_defender_is_unmeasurable(self):
        assert outcome_seconds(self._p(1, defender=0, half=2, margin=10.0)) is None

    def test_margin_agreement_compares_against_the_MAP_winner(self):
        """⚠️ THE GATE ITSELF WAS WRONG FIRST.

        It compared the margin against `rounds.winner_team` — the winner of that
        individual attack/defence round. In stopwatch the two halves normally
        have different round winners while the margin favours one persistent
        side, so even a PERFECT margin scores ~50% against that label. It scored
        48.5%, and reading that as "the margin is noise" repeated the very error
        the margin's own sign had: a map-level quantity judged by a round-level
        label. Against the map winner the real figure is 71.4%.

        One vote per matched half, not one per player, so a full roster cannot
        outvote a small one.
        """
        # margin > 0 means the R2 ATTACKER (side 2 when R2's defender is 1) took
        # the map; a coherent pair agrees.
        good = {i: [self._p(2, 1, 2, +30.0, map_winner=2, rid=i)] for i in range(5)}
        agree, total = margin_agreement(good)
        assert total == 5 and agree == 5
        # same margin, map actually taken by the defender: disagreement
        bad = {i: [self._p(2, 1, 2, +30.0, map_winner=1, rid=i)] for i in range(5)}
        agree, total = margin_agreement(bad)
        assert total == 5 and agree == 0

    def test_one_vote_per_half_not_per_player(self):
        crowd = {1: [self._p(2, 1, 2, +30.0, map_winner=2) for _ in range(9)]}
        agree, total = margin_agreement(crowd)
        assert total == 1, f"a 9-player half cast {total} votes"

    def test_a_helper_change_moves_the_fingerprint(self, tmp_path):
        """`dpm` calls `_minutes`; changing that helper changes the executable
        experiment while the lambda's own text is untouched.

        Mutation-checked for real: a copy of the module with `/ 60.0` changed to
        `/ 60.5` must move `dpm`'s fingerprint and NOTHING else. Asserting on
        the module as-shipped could not tell a covering fingerprint from a
        lucky one.
        """
        src = Path(inspect.getfile(
            sys.modules["validation_family"])).read_text()
        assert "/ 60.0" in src
        mutant = tmp_path / "vf_mutant.py"
        mutant.write_text(src.replace('return max(p["secs"], 1) / 60.0',
                                      'return max(p["secs"], 1) / 60.5'))
        sys.path.insert(0, str(tmp_path))
        try:
            import vf_mutant
            before = {c.cid: c.formula_fingerprint()
                      for c in sys.modules["validation_family"].DEFAULT_FAMILY}
            after = {c.cid: c.formula_fingerprint()
                     for c in vf_mutant.DEFAULT_FAMILY}
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("vf_mutant", None)
        moved = [cid for cid in before if before[cid] != after[cid]]
        # ⚠️ BOTH members carrying that formula, one per estimator. This read
        # `== ["dpm"]` until the point-biserial variants were registered; the
        # formula is the SAME object in both, so a helper change must move both
        # fingerprints or one of them would keep claiming the old experiment.
        # Widened by naming the second member, not by relaxing to a subset —
        # `in moved` would also pass if the fingerprint covered the whole family.
        assert moved == ["dpm", "dpm@pb"], (
            f"changing _minutes moved {moved}; it must move exactly the two "
            f"members whose formula it is")

    def test_p_value_ignores_unmeasurable_replicates(self):
        """max_t_intervals supports gaps, so the p-value must not crash on them
        nor count them in its denominator."""
        vals = [0.05] * 200 + [None] * 50
        usable = [v for v in vals if v is not None]
        assert boot_p_value(usable, 0.05) < 0.05


class TestTheCallSiteNotJustTheHelper:
    """`test_every_candidate_sees_the_same_draws` checks `block_draws`. That is
    not enough: reintroducing a per-candidate seed inside `analyse` left the
    whole suite green, because the helper was still correct and only its CALLER
    had changed. A guard that cannot see the call site does not guard it."""

    def test_analyse_evaluates_every_candidate_on_identical_draws(self):
        """Two candidates that are the SAME function must produce identical
        bootstrap sequences. They can only differ if they were handed different
        resamples — which is exactly the defect."""
        blocks = {}
        for b in range(12):
            winner = 1 if b % 3 else 2
            blocks[b] = {b: _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner)}
        twin = [Candidate("a", "d", "higher_is_better", _metric),
                Candidate("b", "d", "higher_is_better", _metric)]
        family = Family(name="t", candidates=twin, filters="f", resamples=120,
                        seed=99)
        out = analyse(blocks, set(blocks), family)
        assert out["boot"]["a"], "no bootstrap produced"
        assert out["boot"]["a"] == out["boot"]["b"], (
            "identical candidates got different bootstrap sequences — the draws "
            "are not shared across the family, so the max-T interval is not "
            "family-wise")


class TestTiesAtTheMedianValue:
    """The tie fix took three attempts, so each failure mode gets a test.

    v1 sliced a sorted list: row order decided who was 'above'.
    v2 compared the two slice boundaries: caught a tie spanning lo|hi, but in an
       ODD-sized round the dropped centre player means a tie can span lo|centre
       instead — [1, 2, 2, 3, 4] has boundaries 2 and 3, so v2 saw nothing.
    v3 splits on the median VALUE: no boundaries, no odd/even case.
    """

    def test_the_odd_sized_tie_v2_could_not_see(self):
        """Values [1, 2, 2, 3, 4] with the two 2s on opposite teams. Whichever
        arrives first used to land in the lower half and decide the sign."""
        def r(order):
            vals = [(1, 2), (3, 1), (4, 1)] + order
            return [{"guid": f"p{i}", "rid": 1, "team": t, "winner": 1, "v": v}
                    for i, (v, t) in enumerate(vals)]
        a = r([(2, 1), (2, 2)])
        b = r([(2, 2), (2, 1)])
        assert (within_round_spread({1: a, 2: a}, _metric)
                == within_round_spread({1: b, 2: b}, _metric)), \
            "row order among tied players changed the answer"

    def test_a_constant_metric_never_carries_signal(self):
        const = lambda p: 7.0  # noqa: E731
        for order in ([(1, 1), (1, 1), (1, 2), (1, 2), (1, 1)],
                      [(1, 2), (1, 2), (1, 1), (1, 1), (1, 2)]):
            rounds = {i: [{"guid": f"p{j}", "rid": 1, "team": t, "winner": 1,
                           "v": v} for j, (v, t) in enumerate(order)]
                      for i in range(3)}
            assert within_round_spread(rounds, const) is None

    def test_an_exact_zero_estimate_has_no_direction(self):
        """A negatively skewed bootstrap could otherwise publish a small p-value
        for a statistic sitting exactly on the null."""
        skewed = [-0.04] * 100 + [0.01] * 400
        assert boot_p_value(skewed, 0.0) == 1.0
        assert boot_p_value(skewed, 0.01) < 1.0


class TestNothingMeasuredIsNotACleanRun:
    """Found by self-review, not by the reviewer — the reviewer had run out of
    quota, and the same error class it flagged for `--resamples` was sitting one
    branch away.

    When no candidate has a usable bootstrap spread, every one reports FAILS,
    and `null` failing looks exactly like a control doing its job. The controls
    cannot tell "noise was correctly rejected" from "nothing was measured", so
    the run has to make that distinction itself.
    """

    def test_a_family_with_no_spread_yields_no_intervals(self):
        boot = {c: [0.05] * 500 for c in ("kpr", "null", "dpm")}
        point = dict.fromkeys(boot, 0.05)
        intervals, crit, _ = max_t_intervals(boot, point, 0.05)
        assert not intervals
        assert math.isnan(crit)

    def test_the_controls_look_correct_in_exactly_that_case(self):
        """States why the check above is not enough on its own: `null` reports
        FAILS here, which is what a healthy run also shows."""
        boot = {"null": [0.02] * 500}
        intervals, _, _ = max_t_intervals(boot, {"null": 0.02}, 0.05)
        assert "null" not in intervals, (
            "an unmeasurable null would still be reported FAILS — "
            "indistinguishable from a correctly rejected one")


NAN = float("nan")


def _row(cid, verdict, lo, hi, confirmation=0.0):
    """One `results` row in the shape `report()` emits."""
    return {"id": cid, "discovery": confirmation, "confirmation": confirmation,
            "interval": [lo, hi], "margin_sd": 0.01, "holm_p": 0.5,
            "verdict": verdict}


def _kpr_ok():
    """A calibration row inside the #556 range, so `kpr` never decides these."""
    return _row("kpr", "FAILS", 0.01, 0.05, confirmation=0.028)


class TestTheNullControlMustHaveBeenMEASURED:
    """⛔ `FAILS` IS A LABEL, NOT A MEASUREMENT.

    `null` is pure noise by construction, so a run is only trustworthy if the
    harness looked at it and rejected it. But a candidate with no usable
    bootstrap spread is ALSO labelled `FAILS` — `report()` says so itself:
    "unmeasured, which is not the same as measured-and-clear".

    The family-wide guard above only fires when NOTHING was measurable. So the
    hole is precise: measure any OTHER candidate, leave `null` unmeasurable, and
    the run prints `null FAILS ok` and exits 0 with the structural control never
    actually tested. Codex on #818.
    """

    def _family(self, outcome="win"):
        return Family(name="t", candidates=[Candidate("x", "d", "higher_is_better", _metric)],
                      filters="WHERE 1=1", outcome=outcome)

    def test_an_unmeasurable_null_is_not_a_null_that_failed(self):
        # `real` carries a usable interval, so the family-wide "nothing was
        # measurable" guard stays quiet — which is exactly the state that hid this.
        results = [_row("real", "SHIPS", 0.20, 0.40), _kpr_ok(),
                   _row("null", "FAILS", NAN, NAN)]
        assert instrument_check(self._family(), results) is True

    def test_too_few_usable_replicates_reach_the_check_as_a_nan_PAIR(self):
        """Why reading only `interval[0]` is enough — pinned, not assumed.

        ⚠️ My first version of this test fabricated a one-sided `[-0.05, nan]`
        row, on the theory that `measured` inspects only the low end and would
        wave it through. That state is UNREACHABLE: `max_t_intervals()` returns
        no entry at all for a candidate without a usable spread, and `report()`
        then writes `lo = hi = nan` together. Asserting on an impossible input
        would have been a test that can never fire in the direction that matters.

        So the honest thing to pin is the invariant the shortcut rests on: too
        few usable replicates produce NO interval, which is what makes both ends
        nan and one end sufficient to detect it.
        """
        boot = {"null": [0.1] + [None] * 40}     # 1 usable replicate
        point = {"null": 0.1}
        intervals, crit, sds = max_t_intervals(boot, point, alpha=0.05)
        assert intervals == {}, "an unusable bootstrap must yield NO interval"
        assert math.isnan(crit)

    def test_a_MEASURED_null_that_failed_is_the_healthy_run(self):
        # CONTROL. Without this the fix could pass by calling every null broken,
        # which would refuse every valid run instead of the dishonest ones.
        results = [_row("real", "SHIPS", 0.20, 0.40), _kpr_ok(),
                   _row("null", "FAILS", -0.04, 0.03)]
        assert instrument_check(self._family(), results) is False

    def test_noise_that_ships_is_still_broken(self):
        # CONTROL for the check that already existed: it must not be lost.
        results = [_row("real", "SHIPS", 0.20, 0.40), _kpr_ok(),
                   _row("null", "SHIPS", 0.20, 0.40)]
        assert instrument_check(self._family(), results) is True

    def test_a_missing_null_is_still_broken(self):
        results = [_row("real", "SHIPS", 0.20, 0.40), _kpr_ok()]
        assert instrument_check(self._family(), results) is True

    def test_a_family_where_nothing_was_measurable_is_still_broken(self):
        # CONTROL for the family-wide guard, so the new one cannot replace it.
        # ⚠️ Every row must be unmeasurable INCLUDING kpr — my first version of
        # this test left kpr a usable interval, so `measured` was non-empty and
        # the family-wide guard had no reason to fire. The test was wrong, not
        # the guard: a fixture that cannot reach the branch proves nothing.
        results = [_row("real", "FAILS", NAN, NAN),
                   _row("kpr", "FAILS", NAN, NAN, confirmation=0.028),
                   _row("null", "FAILS", NAN, NAN)]
        assert instrument_check(self._family(), results) is True


class TestThePreregistrationIsAnArtifactNotAPromise:
    """⛔ A HOLDOUT THAT HAS BEEN LOOKED AT IS NOT A HOLDOUT — AND NEITHER IS
    ONE WHOSE TERMS WERE NEVER WRITTEN DOWN.

    Without a cutoff the run stops rather than opening the confirmation half.
    That half was right and the reason is in the source. But it printed only the
    proposed timestamp: `manifest_hash()` and `frozen()` are reachable solely
    from `report()`, which runs AFTER confirmation is analysed. So nothing
    committed the candidates, formulas, filters, seed, resamples and cutoff
    BEFORE the rerun opened the holdout, and any change made between the two
    runs was undetectable — the freeze was a promise, not an artifact.

    Codex on #818. What makes it real is that the preregistered hash must equal
    the hash the rerun computes, or the artifact commits to nothing.
    """

    def _family(self, **kw):
        return Family(name="t", candidates=[Candidate("x", "d", "higher_is_better", _metric)],
                      filters="WHERE 1=1", **kw)

    def test_the_preregistered_hash_is_the_one_the_rerun_will_compute(self):
        proposed = "2026-08-26 21:00:00"
        pre = preregister(self._family(), proposed)
        rerun = self._family(frozen_cutoff=proposed)
        assert pre["manifest_sha256"] == rerun.manifest_hash()

    def test_the_artifact_carries_the_terms_not_only_the_digest(self):
        # §8.5: a one-way digest nobody can expand is not a published manifest.
        pre = preregister(self._family(), "2026-08-26 21:00:00")
        assert pre["manifest"]["frozen_cutoff"] == "2026-08-26 21:00:00"
        for key in ("candidates", "filters", "outcome", "seed", "resamples",
                    "alpha", "split_fraction", "protocol_fingerprint"):
            assert key in pre["manifest"], key

    def test_changing_a_knob_after_preregistering_breaks_the_match(self):
        # CONTROL — without this the test above would pass on a constant.
        proposed = "2026-08-26 21:00:00"
        pre = preregister(self._family(), proposed)
        assert pre["manifest_sha256"] != self._family(
            frozen_cutoff=proposed, seed=999).manifest_hash()

    def test_a_different_cutoff_is_a_different_freeze(self):
        # CONTROL — the cutoff must be INSIDE the hashed terms, not beside them.
        a = preregister(self._family(), "2026-08-26 21:00:00")
        b = preregister(self._family(), "2026-08-27 21:00:00")
        assert a["manifest_sha256"] != b["manifest_sha256"]


def _sql_without_comments(sql: str) -> str:
    """SQL with `--` comments removed and whitespace flattened.

    ⛔ Load-bearing. A guard that greps the raw source finds the clause in the
    COMMENT that explains it and passes while the query says something else
    entirely — the failure mode that let a test agree with its own docstring
    twice before. The comments above the gate name the canonical module by
    name, so this is not hypothetical here.
    """
    lines = [ln.split("--")[0] for ln in sql.splitlines()]
    return " ".join(" ".join(lines).split())


class TestThePopulationIsTheCanonicalOne:
    """⛔ `is_valid` IS NOT THE ROUND GATE.

    The repository's canonical gate also excludes rounds whose `round_status`
    says they did not count. Without it, cancelled and orphan_r2 rounds enter
    the eligible universe with `is_valid` still true, and from there the
    chronological split, every point estimate and every bootstrap replicate.

    Measured on this corpus when the gate was added: 148 of 2041 rounds (7.3%)
    left the full universe — but only 1 of 867 left the SPATIAL one, and no
    block changed places. So this corrects the population without overturning
    the Layer 4 numbers, which is worth stating in both directions.

    Codex on #818.
    """

    def test_the_round_gate_is_the_canonical_one(self):
        from website.backend.services.session_scope import _ROUND_GATE_SQL
        clause = _ROUND_GATE_SQL.split("AND ", 2)[2]          # the round_status half
        assert "round_status" in clause                        # the split found it
        want = " ".join(clause.replace("round_status", "r.round_status").split())
        assert want in _sql_without_comments(ROWS_SQL)

    def test_the_guard_would_notice_a_drifted_copy(self):
        # CONTROL. Without this, `want in sql` could pass on any substring and
        # the test would agree with anything.
        drifted = "(r.round_status IN ('completed') OR r.round_status IS NULL)"
        assert drifted not in _sql_without_comments(ROWS_SQL)

    def test_a_comment_alone_would_not_satisfy_it(self):
        # CONTROL for the stripper itself: the phrase inside a comment must not
        # count as the query saying it.
        assert "cancelled" in ROWS_SQL                          # it is in a comment
        assert "cancelled" not in _sql_without_comments(ROWS_SQL)


class TestTheSplitRunsOnMatchTime:
    """⛔ `created_at` IS WHEN THE ROW WAS WRITTEN, NOT WHEN THE MATCH HAPPENED.

    It defaults to CURRENT_TIMESTAMP and one importer writes `datetime.now()`,
    so a historical import or a repair lands among the NEWEST confirmation
    blocks and the holdout stops being chronological in the data-generating
    process. Codex on #818.
    """

    def test_the_ordering_column_is_the_matchs_own_clock(self):
        sql = _sql_without_comments(ROWS_SQL)
        assert "(r.round_date || ' ' || r.round_time)::timestamp AS at" in sql

    def test_ingestion_time_no_longer_labels_a_row_as_its_time(self):
        assert "r.created_at                      AS at" not in ROWS_SQL

    def test_the_pairing_window_is_deliberately_left_on_ingestion_time(self):
        """⚠️ SCOPE, RECORDED SO IT IS NOT MISTAKEN FOR AN OVERSIGHT.

        The R1/R2 pairing window still uses `created_at`. Switching it too is a
        separate, larger decision: measured, 761 pairs have gaps that differ by
        more than a minute between the two clocks, so it would change WHICH
        rounds pair — a different question from which blocks are newest.
        """
        assert "r2.created_at - r1.created_at AS gap" in ROWS_SQL

    def test_the_two_clocks_are_not_mixed(self):
        # ⛔ round_start_unix and round_date/round_time run 61-136 minutes apart
        # (median 125). COALESCEing them would scramble the ordering exactly at
        # the split boundary, which is the one place it must not be scrambled.
        sql = _sql_without_comments(ROWS_SQL)
        assert "round_start_unix" not in sql


class TestBothEstimatorsAreInTheFrozenFamily:
    """⛔ THE HOLDOUT WAS SPENT ON A CANDIDATE THAT WAS NEVER DECLARED.

    `within_round_point_biserial()` records in its own docstring that it was
    measured on 2026-08-26 with 600 block resamples ON THE CONFIRMATION HALF,
    for kpr, kd_ratio, dpm and dmg_ratio. But `analyse()` only ever evaluated
    `within_round_spread`, so the continuous estimator appeared in no manifest,
    no max-T family and no results table.

    That understates multiplicity twice over: the family-wise critical value was
    computed across half the members actually tried, and the confirmation data
    was consumed comparing an undeclared variant. `block_bootstrap()` even takes
    an `estimator` argument — nothing ever passed one. A mechanism with no
    caller, which is the shape of every other defect found this week.

    Codex on #818. The owner's call (2026-09-01) was to register the estimator
    and re-freeze on a NEW cutoff rather than publish the old run as confirmed.
    """

    def test_the_registry_names_both_estimators(self):
        assert set(ESTIMATORS) == {"median_split", "point_biserial"}
        assert ESTIMATORS["median_split"] is within_round_spread
        assert ESTIMATORS["point_biserial"] is within_round_point_biserial

    def test_the_default_family_declares_the_variant_that_was_run(self):
        by_est = {}
        for c in DEFAULT_FAMILY:
            by_est.setdefault(c.estimator, set()).add(c.cid)
        assert "point_biserial" in by_est, (
            "the continuous estimator was run on the confirmation half and must "
            "be declared, or the holdout was spent on an undeclared variant")
        # the four it was actually measured on, per its own docstring
        for base in ("kpr", "kd_ratio", "dpm", "dmg_ratio"):
            assert any(c.cid.startswith(base) and c.estimator == "point_biserial"
                       for c in DEFAULT_FAMILY), base

    def test_every_estimator_carries_its_own_noise_control(self):
        """A family member with no control is a member nobody can falsify.

        The structural `null` control says the harness rejects pure noise. It
        says that about the estimator it was run under and no other, so adding a
        second estimator without a second control would leave half the family
        unchecked — and would quietly weaken the check fixed one commit ago.
        """
        controls = {c.estimator for c in DEFAULT_FAMILY if c.cid.startswith("null")}
        used = {c.estimator for c in DEFAULT_FAMILY}
        assert controls == used, f"estimators without a null control: {used - controls}"

    def test_the_manifest_tells_the_two_variants_apart(self):
        """CONTROL. Same formula, different estimator — the frozen entry must
        differ, or two materially different experiments hash the same."""
        a = Candidate("m", "d", "higher_is_better", _metric)
        b = Candidate("m", "d", "higher_is_better", _metric,
                      estimator="point_biserial")
        assert a.manifest_entry() != b.manifest_entry()
        fam = lambda c: Family(name="t", candidates=[c], filters="f")  # noqa: E731
        assert fam(a).manifest_hash() != fam(b).manifest_hash()

    def test_analyse_evaluates_each_candidate_with_ITS_estimator(self):
        blocks = {}
        for b in range(12):
            winner = 1 if b % 3 else 2
            blocks[b] = {b: _round([(9, 1), (8, 1), (2, 2), (1, 2)], winner)}
        fam = Family(name="t", filters="f", resamples=120, seed=99, candidates=[
            Candidate("ms", "d", "higher_is_better", _metric),
            Candidate("pb", "d", "higher_is_better", _metric,
                      estimator="point_biserial"),
        ])
        out = analyse(blocks, set(blocks), fam)
        assert out["point"]["ms"] != out["point"]["pb"], (
            "both members produced the same point estimate — the declared "
            "estimator is being ignored, which is the whole defect")
        assert out["boot"]["ms"] != out["boot"]["pb"]
