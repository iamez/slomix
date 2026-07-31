from __future__ import annotations

from datetime import date

from scripts.analyze_reinforcement_clock import analyze


def _round_fields(round_id: int, session_date: date) -> dict:
    return {
        "round_id": round_id,
        "session_date": session_date,
        "map_name": "etl_adlernest",
        "linked_round_number": 1,
        "is_valid": True,
        "is_bot_round": False,
        "round_status": "completed",
    }


def _timing_row(
    row_id: int,
    round_id: int,
    session_date: date,
    kill_time: int,
    *,
    offset: int = 0,
) -> dict:
    interval = 10_000
    return {
        "id": row_id,
        **_round_fields(round_id, session_date),
        "victim_team": "AXIS",
        "victim_guid": "A" * 32,
        "victim_name": "player",
        "kill_time": kill_time,
        "enemy_spawn_interval": interval,
        "time_to_next_spawn": interval - ((offset + kill_time) % interval),
        "spawn_timing_score": 0.5,
        "created_at": None,
    }


def _life_row(
    row_id: int,
    round_id: int,
    session_date: date,
    guid: str,
    spawn: int,
    death: int | None,
    event: str | None,
) -> dict:
    return {
        "id": row_id,
        **_round_fields(round_id, session_date),
        "player_guid": guid,
        "player_name": "player",
        "team": "AXIS",
        "spawn_time_ms": spawn,
        "death_time_ms": death,
        "death_type": event,
        "created_at": None,
    }


def test_analyze_separates_chronological_confirmation() -> None:
    timing = []
    lives = []
    row_id = 0
    for round_id, session_date in ((1, date(2026, 7, 27)), (2, date(2026, 7, 29))):
        timing.extend(
            _timing_row(row_id + index, round_id, session_date, kill_time)
            for index, kill_time in enumerate((1_000, 2_000, 3_000))
        )
        for wave_index, spawn in enumerate((0, 10_000, 20_000, 30_000)):
            row_id += 1
            lives.append(
                _life_row(
                    row_id,
                    round_id,
                    session_date,
                    "A" * 31 + str(round_id),
                    spawn,
                    spawn + 1_000 if wave_index < 3 else None,
                    "killed" if wave_index < 3 else None,
                )
            )

    result = analyze(timing, lives, [])
    assert result["discovery"]["validated_groups"] == 1
    assert result["confirmation"]["validated_groups"] == 1
    assert result["confirmation"]["residual_median_ms"] == 0


def test_analyze_reports_unlinked_bot_and_round_filter_counts() -> None:
    base = _timing_row(1, 1, date(2026, 7, 29), 1_000)
    unlinked = {**base, "id": 2, "round_id": None, "linked_round_number": None}
    bot = {**base, "id": 3, "victim_guid": "OMNIBOT0" + "0" * 24}
    rejected = {**base, "id": 4, "is_valid": False}

    result = analyze([unlinked, bot, rejected], [], [])
    assert result["filter_counts"] == {
        "timing_bot_player": 1,
        "timing_rejected_round": 1,
        "timing_unlinked": 1,
    }


def test_analyze_keeps_raw_bot_only_inconsistency_visible() -> None:
    session_date = date(2026, 3, 25)
    rows = [
        {
            **_timing_row(index, 1, session_date, kill_time),
            "victim_guid": "OMNIBOT0" + "0" * 24,
            "time_to_next_spawn": time_to_next,
        }
        for index, (kill_time, time_to_next) in enumerate(
            ((1_000, 9_000), (2_000, 8_000), (3_000, 6_000)),
            start=1,
        )
    ]
    result = analyze(rows, [], [])
    raw = result["raw_internal_consistency"]
    assert raw["inconsistent_group_count"] == 1
    assert raw["inconsistent_bot_only_count"] == 1
    assert result["all"]["round_team_groups"] == 0
