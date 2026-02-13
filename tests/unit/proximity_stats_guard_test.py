from proximity.parser.parser import PlayerTrack, ProximityParserV4


def test_get_stats_handles_zero_duration_tracks():
    parser = ProximityParserV4(output_dir=".")
    parser.metadata["map_name"] = "supply"
    parser.metadata["round_num"] = 1

    # Track exists but has no valid life window (duration_ms == 0)
    parser.player_tracks = [
        PlayerTrack(
            guid="guid-1",
            name="Player One",
            team="axis",
            player_class="SOLDIER",
            spawn_time=0,
            death_time=None,
            first_move_time=None,
            death_type=None,
            sample_count=0,
        )
    ]

    stats = parser.get_stats()
    assert stats["total_tracks"] == 1
    assert stats["avg_life_ms"] == 0
