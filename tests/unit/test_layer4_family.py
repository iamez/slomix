"""§8 as code: the rules the harness must obey before any layer-4 number is
believed. Synthetic data with a known planted signal, a known null, and the
traps the spec names (between-round confounds, ties at the median, a lone
individual interval)."""
from __future__ import annotations

import random

from website.backend.services import layer4_family as l4
from website.backend.services.layer4_family import Candidate, Row


def _round(rid, block, values, wins, key="2026-01-01"):
    return [Row(block=block, round_id=rid, player=f"p{i}", won=w, metrics={"m": v}, order_key=key) for i, (v, w) in enumerate(zip(values, wins))]


class TestRoundSpread:
    def test_upper_half_minus_lower_half(self):
        rows = _round(1, 1, [1, 2, 3, 4], [0, 0, 1, 1])
        assert l4.round_spread(rows, "m") == 1.0

    def test_players_at_the_median_join_neither_half(self):
        # 5 players, median = 3: the player AT 3 is on no side
        rows = _round(1, 1, [1, 2, 3, 4, 5], [0, 0, 1, 1, 1])
        assert l4.round_spread(rows, "m") == 1.0

    def test_too_few_measured_players_is_none_not_zero(self):
        assert l4.round_spread(_round(1, 1, [1, 2, 3], [0, 1, 1]), "m") is None
        rows = _round(1, 1, [1, 2, None, None], [0, 1, 1, 0])
        assert l4.round_spread(rows, "m") is None

    def test_a_metric_everyone_shares_has_no_spread(self):
        # ⛔ §8.1: round length, map, opponent quality are the same for all;
        # a within-round split of a constant cannot produce a side.
        assert l4.round_spread(_round(1, 1, [7, 7, 7, 7], [1, 1, 0, 0]), "m") is None


class TestSplitBlocks:
    def test_whole_blocks_chronologically_and_the_cutoff_is_published(self):
        rows = []
        for b, key in enumerate(["2026-03-01", "2026-01-01", "2026-02-01", "2026-04-01", "2026-05-01"]):
            rows += _round(b * 10, b, [1, 2, 3, 4], [0, 0, 1, 1], key)
        disc, conf, cutoff = l4.split_blocks(rows, 0.7)
        assert disc == {1, 2, 0}          # the three earliest
        assert conf == {3, 4}
        assert cutoff == "2026-04-01"
        assert not (disc & conf)


class TestBootstrapAndVerdict:
    @staticmethod
    def _corpus(signal: float, seed=1, blocks=30, rounds_per_block=6, players=6):
        rng = random.Random(seed)  # noqa: S311
        rows = []
        rid = 0
        for b in range(blocks):
            key = f"2026-{1 + b // 10:02d}-{1 + b % 10:02d}"
            for _ in range(rounds_per_block):
                rid += 1
                # half the players win; a planted signal raises the metric of winners
                wins = [1] * (players // 2) + [0] * (players - players // 2)
                vals = [rng.gauss(signal * w, 1.0) for w in wins]
                rows += _round(rid, b, vals, wins, key)
        return rows

    def test_a_planted_signal_ships_and_a_null_does_not(self):
        rows = self._corpus(signal=1.5)
        for r in rows:
            # the negative control: a seeded uniform that knows nothing of the outcome
            r.metrics["n"] = random.Random(hash((r.round_id, r.player)) & 0xFFFF).random()  # noqa: S311
        cands = [Candidate("m", "planted", "positive", kind="positive_control"), Candidate("n", "noise", "positive", kind="negative_control")]
        out = l4.analyse(rows, cands, resamples=300, seed=7)
        by = {t["id"]: t for t in out["table"]}
        assert by["m"]["verdict"] == "ships", by["m"]
        assert by["n"]["verdict"].startswith("fails"), by["n"]

    def test_the_wrong_frozen_direction_fails_even_when_the_effect_is_strong(self):
        rows = self._corpus(signal=1.5)
        out = l4.analyse(rows, [Candidate("m", "planted", "negative")], resamples=200, seed=3)
        assert out["table"][0]["verdict"] == "fails: discovery direction"

    def test_the_bootstrap_is_deterministic_for_a_seed_and_shares_one_draw(self):
        rows = self._corpus(signal=0.8)
        a = l4.block_bootstrap(rows, ["m"], resamples=100, seed=5)
        b = l4.block_bootstrap(rows, ["m"], resamples=100, seed=5)
        assert a == b
        # the family widens the interval: the max-T critical value over two
        # candidates is never below the one over a single candidate
        for r in rows:
            r.metrics["n"] = -r.metrics["m"]
        two = l4.block_bootstrap(rows, ["m", "n"], resamples=100, seed=5)
        assert two["m"]["t_crit"] >= a["m"]["t_crit"] - 1e-12
        assert two["m"]["point"] == a["m"]["point"]

    def test_unmeasured_is_a_verdict_not_a_pass(self):
        c = Candidate("x", "nothing", "positive")
        assert l4.verdict(c, {"point": None}, {"point": None, "sim95": None}) == "unmeasured"


class TestManifest:
    def test_the_hash_follows_the_family_and_nothing_else(self):
        cands = [Candidate("a", "f", "positive", {"k": 1})]
        one = l4.manifest(cands, cutoff="2026-08-01", outcome="round won", filters=["x"], seed=1, resamples=10)
        same = l4.manifest(cands, cutoff="2026-08-01", outcome="round won", filters=["x"], seed=1, resamples=10)
        other = l4.manifest([Candidate("a", "f", "positive", {"k": 2})], cutoff="2026-08-01", outcome="round won", filters=["x"], seed=1, resamples=10)
        assert one["sha256"] == same["sha256"]
        assert one["sha256"] != other["sha256"]
        assert one["candidates"][0]["expected_direction"] == "positive"
