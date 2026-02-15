from __future__ import annotations

from greatshot.scanner.api import _extract_player_stats
from greatshot.contracts.types import DemoEvent


def test_extract_player_stats_supports_aliases_and_tpm_fields():
    match_stats = [
        {
            "playerStats": [
                {
                    "cleanName": "Alpha",
                    "kills": "10",
                    "deaths": "5",
                    "damageGiven": "2345",
                    "damageReceived": "987",
                    "accuracy": "37.5",
                    "timePlayedMinutes": "7.5",
                    "headshotKills": "2",
                },
                {
                    "cleanName": "Beta",
                    "kills": 3,
                    "deaths": 4,
                    "shotsFired": 100,
                    "shotsHit": 45,
                    "time_played_seconds": 300,
                },
            ]
        }
    ]

    stats = _extract_player_stats(match_stats=match_stats, timeline=[])

    alpha = stats["Alpha"]
    assert alpha["damage_given"] == 2345
    assert alpha["damage_received"] == 987
    assert alpha["accuracy"] == 37.5
    assert alpha["time_played_seconds"] == 450
    assert alpha["time_played_minutes"] == 7.5
    assert alpha["tpm"] == 7.5
    assert alpha["headshots"] == 2

    beta = stats["Beta"]
    assert beta["accuracy"] == 45.0
    assert beta["time_played_seconds"] == 300
    assert beta["time_played_minutes"] == 5.0
    assert beta["tpm"] == 5.0


def test_extract_player_stats_keeps_timeline_fallback_behavior():
    timeline = [
        DemoEvent(t_ms=1000, type="kill", attacker="Gamma", victim="Delta", hit_region="head"),
        DemoEvent(t_ms=2000, type="kill", attacker="Gamma", victim="Epsilon"),
    ]

    stats = _extract_player_stats(match_stats=[], timeline=timeline)

    gamma = stats["Gamma"]
    assert gamma["kills"] == 2
    assert gamma["headshots"] == 1
    assert gamma["time_played_seconds"] is None
    assert gamma["tpm"] is None

    delta = stats["Delta"]
    assert delta["deaths"] == 1
