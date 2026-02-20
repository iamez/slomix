from __future__ import annotations

from pathlib import Path

import pytest

from bot.services.session_timing_shadow_service import SessionTimingShadowService


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def fetch_all(self, query, params):
        normalized = " ".join(query.split()).lower()
        self.calls.append((normalized, params))

        if "from rounds r" in normalized:
            return [
                (101, "supply", 1, 540),
                (102, "oasis", 2, None),
            ]

        if "from player_comprehensive_stats p" in normalized:
            return [
                (101, "AAAABBBB1111", "Alpha", 300, 140, 100),
                (101, "CCCCDDDD2222", "Beta", 200, 50, 30),
                (102, "AAAABBBB1111", "Alpha", 280, 80, 40),
                (102, "EEEEFFFF3333", "Gamma", 220, 70, 20),
            ]

        if "from lua_spawn_stats" in normalized:
            return [
                (101, "AAAABBBBZZZZ", 180),
                (101, "CCCCDDDDYYYY", 60),
                (102, "AAAABBBBWWWW", 350),
            ]

        raise AssertionError(f"Unexpected query: {query}")


def test_compute_shadow_values_invariants():
    capped = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=300,
        old_dead_seconds=120,
        old_denied_playtime=90,
        lua_dead_seconds=999,
        lua_round_duration_seconds=200,
    )

    assert capped.new_dead_seconds == 200
    assert capped.new_denied_playtime == 50
    assert 0 <= capped.new_dead_seconds <= 200
    assert 0 <= capped.new_denied_playtime <= (300 - capped.new_dead_seconds)
    assert "lua_dead_capped_to_plausible_limit" in capped.fallback_reason

    negative = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=200,
        old_dead_seconds=60,
        old_denied_playtime=42,
        lua_dead_seconds=-30,
        lua_round_duration_seconds=500,
    )

    assert negative.new_dead_seconds == 0
    assert negative.new_denied_playtime == 60
    assert negative.new_dead_seconds >= 0
    assert negative.new_denied_playtime >= 0
    assert "lua_dead_negative_clamped" in negative.fallback_reason

    missing = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=220,
        old_dead_seconds=70,
        old_denied_playtime=20,
        lua_dead_seconds=None,
        lua_round_duration_seconds=None,
        lua_missing_reason="lua_missing_for_round",
    )

    assert missing.new_dead_seconds == 70
    assert missing.new_denied_playtime == 20
    assert missing.fallback_reason == "lua_missing_for_round"


@pytest.mark.asyncio
async def test_compare_session_outputs_stable_aggregation_and_fallbacks(tmp_path):
    service = SessionTimingShadowService(_FakeDB(), artifact_dir=tmp_path / "timing_shadow")

    result = await service.compare_session([102, 101])

    assert result.session_ids == (101, 102)
    assert result.overall_coverage_percent == 75.0
    assert len(result.player_rounds) == 4
    assert len(result.player_summaries) == 3
    assert result.artifact_path is not None
    assert Path(result.artifact_path).exists()

    row_by_key = {(row.round_id, row.player_guid): row for row in result.player_rounds}
    assert row_by_key[(102, "EEEEFFFF3333")].fallback_reason == "lua_missing_for_guid_prefix"
    assert row_by_key[(102, "AAAABBBB1111")].new_dead_seconds == 280
    assert "lua_dead_capped_to_plausible_limit" in row_by_key[(102, "AAAABBBB1111")].fallback_reason

    round_diags = {diag.round_id: diag for diag in result.round_diagnostics}
    assert round_diags[101].coverage_percent == 100.0
    assert round_diags[102].coverage_percent == 50.0
    assert round_diags[102].fallback_reason_counts["lua_missing_for_guid_prefix"] == 1

    alpha = service.get_player_summary(result, "AAAABBBB1111")
    assert alpha is not None
    assert alpha.new_dead_seconds == 460
    assert alpha.dead_diff_seconds == 240

    top = service.top_n_diff_summary(result, n=2)
    assert len(top) == 2
    assert top[0].player_guid == "AAAABBBB1111"

    cached = await service.compare_session([101, 102])
    assert cached is result
    assert len(list((tmp_path / "timing_shadow").glob("*.csv"))) == 1
