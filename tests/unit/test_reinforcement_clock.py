from __future__ import annotations

from website.backend.services.reinforcement_clock import (
    ClockInference,
    PlayerLife,
    QualifiedSpawn,
    ReviveObservation,
    SpawnLanding,
    TimingObservation,
    circular_residual_ms,
    cluster_spawn_landings,
    infer_clock,
    qualify_normal_spawns,
    timing_exclusion_reason,
    validate_clock,
    validate_round_clocks,
    validated_clock_tuple,
)


def _timing(
    time_ms: int,
    *,
    team: str = "AXIS",
    interval_ms: int = 30_000,
    offset_ms: int = 6_000,
    score: float = 0.5,
) -> TimingObservation:
    return TimingObservation(
        team=team,
        kill_time_ms=time_ms,
        interval_ms=interval_ms,
        time_to_next_spawn_ms=interval_ms - ((offset_ms + time_ms) % interval_ms),
        spawn_timing_score=score,
    )


def _life(
    row_id: int,
    guid: str,
    spawn_ms: int,
    death_ms: int | None,
    death_type: str | None,
    team: str = "AXIS",
) -> PlayerLife:
    return PlayerLife(row_id, guid, team, spawn_ms, death_ms, death_type)


def test_infer_clock_requires_exact_unanimity() -> None:
    observations = [_timing(time_ms) for time_ms in (1_000, 9_000, 21_000)]
    inference = infer_clock("AXIS", observations)

    assert inference.status == "internally_consistent_unvalidated"
    assert inference.offset_ms == 6_000
    assert inference.interval_ms == 30_000

    conflicting = observations + [
        TimingObservation("AXIS", 4_000, 30_000, 19_000, 0.5),
    ]
    inference = infer_clock("AXIS", conflicting)
    assert inference.status == "inconsistent"
    assert inference.offset_ms is None
    assert inference.distinct_candidates_ms == (6_000, 7_000)


def test_infer_clock_never_uses_mode_or_cross_interval_vote() -> None:
    modal = [_timing(time_ms) for time_ms in (1_000, 2_000, 3_000)]
    modal.append(TimingObservation("AXIS", 4_000, 30_000, 19_000, 0.5))
    assert infer_clock("AXIS", modal).status == "inconsistent"

    mixed_intervals = [_timing(1_000), _timing(2_000), _timing(3_000, interval_ms=20_000)]
    inference = infer_clock("AXIS", mixed_intervals)
    assert inference.status == "inconsistent"
    assert inference.interval_ms is None


def test_infer_clock_filters_sentinel_and_requires_three_rows() -> None:
    observations = [
        _timing(1_000),
        _timing(2_000),
        _timing(3_000, score=0.0),
        TimingObservation("AXIS", 4_000, 0, 0, 0.0),
    ]
    inference = infer_clock("AXIS", observations)
    assert inference.status == "insufficient"
    assert inference.observation_count == 2


def test_timing_exclusion_reason_rejects_impossible_bounds() -> None:
    assert timing_exclusion_reason(
        TimingObservation("AXIS", -1, 10_000, 5_000, 0.5)
    ) == "negative_kill_time"
    assert timing_exclusion_reason(
        TimingObservation("AXIS", 1, 10_000, 10_001, 0.5)
    ) == "time_to_next_spawn_out_of_range"
    assert timing_exclusion_reason(
        TimingObservation("SPECTATOR", 1, 10_000, 5_000, 0.5)
    ) == "unknown_team"


def test_qualify_normal_spawns_excludes_non_death_and_team_change() -> None:
    lives = [
        _life(1, "A", 0, 1_000, "killed"),
        _life(2, "A", 30_000, 31_000, "disconnect"),
        _life(3, "A", 60_000, None, None),
        _life(4, "B", 0, 1_000, "killed"),
        _life(5, "B", 30_000, None, None, "ALLIES"),
    ]
    result = qualify_normal_spawns(lives)

    assert [(spawn.player_guid, spawn.time_ms) for spawn in result.spawns] == [("A", 30_000)]
    assert dict(result.exclusions) == {
        "initial_join": 2,
        "reconnect_or_shutdown": 1,
        "team_change": 1,
    }


def test_qualify_normal_spawns_rejects_entire_overlapping_player() -> None:
    lives = [
        _life(1, "A", 0, 20_000, "killed"),
        _life(2, "A", 10_000, 30_000, "killed"),
        _life(3, "A", 40_000, None, None),
    ]
    result = qualify_normal_spawns(lives)
    assert result.spawns == ()
    assert dict(result.exclusions)["ambiguous_overlapping_lives"] == 2


def test_qualify_normal_spawns_labels_post_revive_gap() -> None:
    lives = [
        _life(1, "A", 0, 10_000, "killed"),
        _life(2, "A", 30_000, None, None),
    ]
    result = qualify_normal_spawns(lives, [ReviveObservation("A", 12_000)])
    assert len(result.spawns) == 1
    assert result.spawns[0].follows_post_revive_gap is True


def test_cluster_spawn_landings_has_bounded_diameter() -> None:
    spawns = [
        QualifiedSpawn("A", "AXIS", 10_000, False),
        QualifiedSpawn("B", "AXIS", 10_200, True),
        QualifiedSpawn("C", "AXIS", 10_400, False),
    ]
    clustering = cluster_spawn_landings(spawns)
    landings = clustering.landings
    assert [(landing.time_ms, landing.spawn_count) for landing in landings] == [
        (10_100, 2),
        (10_400, 1),
    ]
    assert landings[0].post_revive_spawn_count == 1


def test_cluster_spawn_landings_reports_duplicate_player_exclusion() -> None:
    clustering = cluster_spawn_landings(
        [
            QualifiedSpawn("A", "AXIS", 10_000, False),
            QualifiedSpawn("A", "AXIS", 10_100, False),
        ]
    )
    assert clustering.landings == ()
    assert dict(clustering.exclusions) == {"duplicate_player_in_landing": 2}


def test_validate_clock_requires_independent_support_and_frozen_ratio() -> None:
    inference = ClockInference(
        team="AXIS",
        status="internally_consistent_unvalidated",
        observation_count=5,
        interval_ms=10_000,
        offset_ms=0,
        distinct_intervals_ms=(10_000,),
        distinct_candidates_ms=(0,),
    )
    unsupported = validate_clock(
        inference,
        [SpawnLanding("AXIS", 10_100, 2, 0), SpawnLanding("AXIS", 19_900, 1, 0)],
    )
    assert unsupported.status == "internally_consistent_unvalidated"
    assert validated_clock_tuple(unsupported) is None

    supported = validate_clock(
        inference,
        [
            SpawnLanding("AXIS", 10_100, 2, 0),
            SpawnLanding("AXIS", 19_900, 1, 0),
            SpawnLanding("AXIS", 30_250, 2, 1),
        ],
    )
    assert supported.status == "validated"
    assert supported.residuals_ms == (100, 100, 250)
    assert validated_clock_tuple(supported) == (0, 10_000)

    failed = validate_clock(
        inference,
        [
            SpawnLanding("AXIS", 10_100, 1, 0),
            SpawnLanding("AXIS", 19_900, 1, 0),
            SpawnLanding("AXIS", 33_000, 1, 0),
        ],
    )
    assert failed.status == "validation_failed"


def test_circular_residual_wraps_at_interval_boundary() -> None:
    assert circular_residual_ms(9_900, 0, 10_000) == 100
    assert circular_residual_ms(10_100, 0, 10_000) == 100


def test_validate_round_clocks_never_exposes_failed_team() -> None:
    timings = [_timing(time_ms) for time_ms in (1_000, 2_000, 3_000)]
    lives = [
        _life(1, "A", 0, 1_000, "killed"),
        _life(2, "A", 7_000, 8_000, "killed"),
        _life(3, "A", 14_000, 15_000, "killed"),
        _life(4, "A", 21_000, None, None),
    ]
    validations = validate_round_clocks(timings, lives)
    assert validations["AXIS"].status == "validation_failed"
    assert validated_clock_tuple(validations["AXIS"]) is None
