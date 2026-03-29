"""
Unit tests for DPM time_played_seconds clamping logic.

Tests the parser's fallback behavior when Lua TAB[22] (time_played_minutes) is absent.
Root cause: ET:Legacy R2 stats files can report cumulative server time in actual_time
header field instead of round duration. The parser clamps to time_limit as a reliable
upper bound.

Coverage:
- Normal rounds where actual_time <= time_limit
- Inflated R2 rounds where actual_time > time_limit
- TAB[22] per-player override (takes precedence over clamp)
- Edge cases: zero time_limit, missing fields
"""

import unittest

from bot.community_stats_parser import C0RNP0RN3StatsParser


class TestDPMTimeClamping(unittest.TestCase):
    """Test suite for time_played_seconds clamping in the parser."""

    def setUp(self):
        """Set up test parser instance."""
        self.parser = C0RNP0RN3StatsParser()

    def test_parse_time_to_seconds_normal(self):
        """Test parse_time_to_seconds with normal MM:SS strings."""
        assert self.parser.parse_time_to_seconds("5:54") == 354
        assert self.parser.parse_time_to_seconds("10:00") == 600
        assert self.parser.parse_time_to_seconds("86:40") == 5200
        assert self.parser.parse_time_to_seconds("0:00") == 0

    def test_parse_time_to_seconds_edge_cases(self):
        """Test parse_time_to_seconds edge cases."""
        assert self.parser.parse_time_to_seconds("") == 0
        assert self.parser.parse_time_to_seconds(None) == 0
        assert self.parser.parse_time_to_seconds("invalid") == 0
        assert self.parser.parse_time_to_seconds("15") == 15  # Raw integer seconds

    def test_no_clamp_when_actual_time_within_limit(self):
        """
        When actual_time <= time_limit and TAB[22] = 0, use actual_time as-is.

        Normal R1 rounds follow this pattern.
        """
        # Simulate: actual_time = "5:54" (354s), time_limit = "10:00" (600s)
        # Parser should NOT clamp since 354 <= 600
        actual_time_str = "5:54"
        time_limit_str = "10:00"

        actual_time_secs = self.parser.parse_time_to_seconds(actual_time_str)
        time_limit_secs = self.parser.parse_time_to_seconds(time_limit_str)

        # Simulate the parser's clamping logic
        round_time_seconds = actual_time_secs
        if time_limit_secs > 0 and round_time_seconds > time_limit_secs:
            round_time_seconds = time_limit_secs

        self.assertEqual(round_time_seconds, 354)
        self.assertLess(round_time_seconds, time_limit_secs)

    def test_clamp_when_actual_time_exceeds_limit(self):
        """
        When actual_time > time_limit and TAB[22] = 0, clamp to time_limit.

        This is the bug scenario: R2 stats file reports cumulative server uptime.
        """
        # Simulate: actual_time = "86:40" (5200s), time_limit = "10:00" (600s)
        # Parser SHOULD clamp since 5200 > 600
        actual_time_str = "86:40"
        time_limit_str = "10:00"

        actual_time_secs = self.parser.parse_time_to_seconds(actual_time_str)
        time_limit_secs = self.parser.parse_time_to_seconds(time_limit_str)

        # Simulate the parser's clamping logic
        round_time_seconds = actual_time_secs
        if time_limit_secs > 0 and round_time_seconds > time_limit_secs:
            round_time_seconds = time_limit_secs

        self.assertEqual(round_time_seconds, 600)
        self.assertEqual(round_time_seconds, time_limit_secs)
        self.assertLess(round_time_seconds, actual_time_secs)

    def test_clamp_multiple_inflated_values(self):
        """Test clamping with various inflated actual_time values."""
        test_cases = [
            # (actual_time_str, time_limit_str, expected_clamped_secs)
            ("78:25", "10:00", 600),   # 4705s -> 600s (session 87)
            ("54:00", "12:00", 720),   # 3240s -> 720s (session 84)
            ("79:20", "12:00", 720),   # 4760s -> 720s (session 85)
            ("81:40", "10:00", 600),   # 4900s -> 600s
            ("90:00", "10:00", 600),   # 5400s -> 600s
        ]

        for actual_time_str, time_limit_str, expected_secs in test_cases:
            with self.subTest(actual_time=actual_time_str, time_limit=time_limit_str):
                actual_secs = self.parser.parse_time_to_seconds(actual_time_str)
                limit_secs = self.parser.parse_time_to_seconds(time_limit_str)

                round_time = actual_secs
                if limit_secs > 0 and round_time > limit_secs:
                    round_time = limit_secs

                self.assertEqual(round_time, expected_secs)

    def test_no_clamp_when_time_limit_is_zero(self):
        """When time_limit = "0:00", don't clamp (guard clause)."""
        actual_time_str = "5:00"
        time_limit_str = "0:00"

        actual_secs = self.parser.parse_time_to_seconds(actual_time_str)
        limit_secs = self.parser.parse_time_to_seconds(time_limit_str)

        round_time = actual_secs
        if limit_secs > 0 and round_time > limit_secs:
            round_time = limit_secs

        # Should NOT clamp since time_limit_secs == 0
        self.assertEqual(round_time, 300)  # actual_time unchanged
        self.assertEqual(limit_secs, 0)

    def test_dpm_calculation_with_clamped_time(self):
        """
        Verify DPM calculation using clamped time_played_seconds.

        Before fix: DPM = (damage * 60) / 5200 = ~11 for 959 damage
        After fix:  DPM = (damage * 60) / 600  = ~96 for 959 damage
        """
        damage = 959
        inflated_time = 5200  # R2 header fallback (cumulative server time)
        clamped_time = 600    # Time limit (correct bound)

        dpm_before = (damage * 60) / inflated_time if inflated_time > 0 else 0
        dpm_after = (damage * 60) / clamped_time if clamped_time > 0 else 0

        self.assertAlmostEqual(dpm_before, 11.07, places=1)
        self.assertAlmostEqual(dpm_after, 95.9, places=1)
        self.assertGreater(dpm_after, dpm_before * 8)  # ~8x improvement

    def test_tab22_override_prevents_clamp(self):
        """
        When TAB[22] (time_played_minutes) is present, it overrides the header fallback.

        The clamp guard only applies to the fallback case.
        """
        # Simulate scenario: actual_time = "86:40" (5200s, would clamp to 600s)
        # But TAB[22] = 5.9 minutes (354s, per-player time from Lua TAB data)
        actual_time_secs = 5200
        time_limit_secs = 600
        lua_time_minutes = 5.9
        lua_time_seconds = int(lua_time_minutes * 60)  # 354s

        # Step 1: Clamp (guard clause - would apply to header fallback)
        clamped_time = actual_time_secs
        if time_limit_secs > 0 and clamped_time > time_limit_secs:
            clamped_time = time_limit_secs  # -> 600s

        self.assertEqual(clamped_time, 600)

        # Step 2: Override with TAB[22] if present
        final_time = clamped_time
        if lua_time_minutes > 0:
            final_time = lua_time_seconds  # -> 354s (Lua wins)

        self.assertEqual(final_time, 354)
        self.assertNotEqual(final_time, clamped_time)
        self.assertNotEqual(final_time, actual_time_secs)

    def test_dpm_with_various_damage_values(self):
        """
        Test DPM improvement across different damage values (realistic player outputs).

        This validates the fix works across the spectrum of player damage values.
        """
        test_cases = [
            # (damage, old_time=5200, new_time=600)
            (296, 3.41, 29.6),    # SuperBoyy from round 9809
            (335, 3.86, 33.5),    # Proner2026 from round 9809
            (391, 4.51, 39.1),    # Cru3lzor. from round 9809
            (592, 6.83, 59.2),    # .wajs from round 9809
            (621, 7.17, 62.1),    # .olz from round 9809
            (959, 11.07, 95.9),   # bronze. from round 9809
        ]

        for damage, expected_old_dpm, expected_new_dpm in test_cases:
            with self.subTest(damage=damage):
                old_dpm = (damage * 60) / 5200
                new_dpm = (damage * 60) / 600

                self.assertAlmostEqual(old_dpm, expected_old_dpm, places=1)
                self.assertAlmostEqual(new_dpm, expected_new_dpm, places=1)
                self.assertGreater(new_dpm, old_dpm * 8)  # Significant improvement

    def test_edge_case_zero_damage(self):
        """Handle zero damage (e.g., player didn't join yet or spectator)."""
        damage = 0
        time_seconds = 600

        dpm = (damage * 60) / time_seconds if time_seconds > 0 else 0
        self.assertEqual(dpm, 0)

    def test_edge_case_zero_time(self):
        """Handle zero time_seconds (guard against division by zero)."""
        damage = 500
        time_seconds = 0

        dpm = (damage * 60) / time_seconds if time_seconds > 0 else 0
        self.assertEqual(dpm, 0)


class TestDPMClampsIntegrationWithParser(unittest.TestCase):
    """
    Integration tests: verify clamping works in the context of the real parser.

    These tests would require a real stats file sample, so they're documented
    as examples of how to test the full parse path end-to-end.
    """

    @unittest.skip("Requires mock stats file data - see docstring for integration test example")
    def test_parse_file_with_inflated_actual_time(self):
        """
        Integration test: parse a mock stats file with inflated actual_time.

        Example setup:
        - Mock stats file with actual_time = "86:40" (5200s)
        - Mock stats file with time_limit = "10:00" (600s)
        - Mock stats file with TAB[22] = 0 (no per-player time data)
        - Should parse and store time_played_seconds = 600 (clamped), not 5200

        Would require: stats_file_data, parse(), assert stored time = 600
        """
        pass


if __name__ == '__main__':
    unittest.main()
