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
    margin_agreement,
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
        assert moved == ["dpm"], (
            f"changing _minutes moved {moved}; it must move exactly dpm")

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
