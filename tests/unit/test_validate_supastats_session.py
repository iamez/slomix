from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_supastats_session as validator


FIXTURE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "supastats_validation_2026-03-05.json"
)


def test_build_player_snapshot_rows_prefers_explicit_supastats_tmp_fields():
    rows = validator.build_player_snapshot_rows(
        [
            {
                "player_name": "Player One",
                "player_guid": "guid-1",
                "damage_given": 12345,
                "damage_received": 12000,
                "kills": 50,
                "kill_assists": 12,
                "gibs": 10,
                "self_kills": 5,
                "deaths": 40,
                "kd": 1.25,
                "tmp_pct": 51.5,
                "supastats_tmp_pct": 78.7,
                "supastats_tmp_ratio": 0.787,
            }
        ]
    )

    assert rows == [
        {
            "player_name": "Player One",
            "player_guid": "guid-1",
            "damage_given": 12345,
            "damage_received": 12000,
            "kills": 50,
            "kill_assists": 12,
            "gibs": 10,
            "self_kills": 5,
            "deaths": 40,
            "kd": 1.25,
            "supastats_tmp_pct": 78.7,
            "supastats_tmp_ratio": 0.787,
        }
    ]


def test_build_match_pair_rows_splits_repeated_maps_into_distinct_pairs():
    round_rows = [
        {"round_id": 1, "map_name": "te_escape2", "round_number": 1, "round_start_unix": 10, "duration_seconds": 215},
        {"round_id": 2, "map_name": "te_escape2", "round_number": 2, "round_start_unix": 20, "duration_seconds": 177},
        {"round_id": 3, "map_name": "te_escape2", "round_number": 1, "round_start_unix": 30, "duration_seconds": 380},
        {"round_id": 4, "map_name": "te_escape2", "round_number": 2, "round_start_unix": 40, "duration_seconds": 211},
        {"round_id": 5, "map_name": "te_escape2", "round_number": 1, "round_start_unix": 50, "duration_seconds": 265},
        {"round_id": 6, "map_name": "te_escape2", "round_number": 2, "round_start_unix": 60, "duration_seconds": 181},
    ]

    assert validator.build_match_pair_rows(round_rows) == [
        {
            "order": 1,
            "map_name": "te_escape2",
            "round_ids": [1, 2],
            "round_numbers": [1, 2],
            "durations": [215, 177],
        },
        {
            "order": 2,
            "map_name": "te_escape2",
            "round_ids": [3, 4],
            "round_numbers": [1, 2],
            "durations": [380, 211],
        },
        {
            "order": 3,
            "map_name": "te_escape2",
            "round_ids": [5, 6],
            "round_numbers": [1, 2],
            "durations": [265, 181],
        },
    ]


def test_compare_snapshots_matches_fixture_and_reports_path_on_change():
    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    actual = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert validator.compare_snapshots(actual, expected) == []

    actual["players"][1]["damage_given"] += 1
    mismatches = validator.compare_snapshots(actual, expected)

    assert mismatches == [
        "root.players[1].damage_given: expected 31247, got 31248"
    ]
