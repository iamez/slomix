from __future__ import annotations

import pytest

from bot.services.session_embed_builder import SessionEmbedBuilder


@pytest.mark.asyncio
async def test_session_overview_embed_renders_old_new_timing_when_dual_enabled():
    builder = SessionEmbedBuilder(show_timing_dual=True)
    player_row = (
        "Alpha",        # player_name
        "GUID1234",     # player_guid
        20,             # kills
        10,             # deaths
        400.0,          # dpm
        120,            # hits
        240,            # shots
        30,             # total_hs
        18,             # hsk
        900,            # total_seconds
        300,            # total_time_dead (old)
        180,            # total_denied (old)
        6,              # total_gibs
        4,              # total_revives_given
        2,              # total_times_revived
        2000,           # total_damage_received
        4500,           # total_damage_given
        8,              # total_useful_kills
        2,              # total_double_kills
        1,              # total_triple_kills
        0,              # total_quad_kills
        0,              # total_multi_kills
        0,              # total_mega_kills
        1,              # total_self_kills
        0,              # total_full_selfkills
        0,              # total_kill_assists (optional trailing value)
    )

    embed = await builder.build_session_overview_embed(
        latest_date="2026-02-16",
        all_players=[player_row],
        maps_played="supply",
        rounds_played=2,
        player_count=1,
        team_1_name="Team A",
        team_2_name="Team B",
        team_1_score=0,
        team_2_score=0,
        hardcoded_teams=False,
        timing_dual_by_guid={
            "GUID1234": {
                "new_time_dead_seconds": 360,
                "new_denied_seconds": 240,
                "missing_reason": "",
            }
        },
        timing_dual_meta={
            "rounds_total": 2,
            "rounds_with_telemetry": 2,
            "reason": "OK",
        },
        show_timing_dual=True,
    )

    players_field = embed.fields[0].value
    assert "💀O" in players_field
    assert "N" in players_field
    assert "Δ" in players_field
    assert "⏳O" in players_field
