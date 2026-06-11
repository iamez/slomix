"""Unit tests for scripts/backfill_killer_reinf.py pure helpers."""

from scripts.backfill_killer_reinf import implied_team_clocks, recompute_killer_reinf


def _victim_row(team: str, kill_time: int, interval: int, offset: int) -> tuple:
    """Synthesize a victim-side row whose ttn encodes (interval, offset)."""
    ttn = interval - ((offset + kill_time) % interval)
    return (team, kill_time, interval, ttn)


class TestImpliedTeamClocks:
    def test_recovers_known_clocks(self):
        # E2E-audit-like clocks: ALLIES 25000/14000, AXIS 30000/6000.
        rows = [
            _victim_row("ALLIES", t, 25000, 14000) for t in (3000, 41000, 90500)
        ] + [
            _victim_row("AXIS", t, 30000, 6000) for t in (12000, 55000)
        ]
        clocks = implied_team_clocks(rows)
        assert clocks["ALLIES"] == (14000, 25000)
        assert clocks["AXIS"] == (6000, 30000)

    def test_modal_vote_beats_rounding_noise(self):
        # Two rows quantize to 14000, one noisy row 60ms off lands on 14050.
        rows = [
            _victim_row("ALLIES", 3000, 25000, 14000),
            _victim_row("ALLIES", 41000, 25000, 14000),
            ("ALLIES", 90500, 25000, 25000 - ((14060 + 90500) % 25000)),
        ]
        assert implied_team_clocks(rows)["ALLIES"] == (14000, 25000)

    def test_zero_interval_rows_ignored(self):
        assert implied_team_clocks([("AXIS", 5000, 0, 1234)]) == {}


class TestRecomputeKillerReinf:
    def test_matches_lua_formula(self):
        # interval 30000, offset 6000, kill at 12000:
        # 30000 - ((6000+12000) % 30000) = 12000 ms -> 12.0 s
        assert recompute_killer_reinf(12000, 6000, 30000) == 12.0

    def test_wraps_modulo(self):
        # offset+kill spans several waves: 30000 - ((6000+95000) % 30000)
        # = 30000 - 11000 = 19000 -> 19.0
        assert recompute_killer_reinf(95000, 6000, 30000) == 19.0

    def test_f1_bug_shape_offset_zero_differs(self):
        # The buggy value used offset 0; with a real offset it must differ.
        buggy = recompute_killer_reinf(12000, 0, 30000)
        fixed = recompute_killer_reinf(12000, 6000, 30000)
        assert buggy == 18.0
        assert fixed == 12.0
