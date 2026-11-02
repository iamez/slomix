"""
Tests for PlayerTrack computed metrics (duration_ms, sprint_percentage, avg_speed).

The current implementation uses simple sample-count-based calculations:
- sprint_percentage: count of sprint=1 samples / total samples * 100
- avg_speed: mean of non-zero speeds across all samples
"""
from proximity.parser.parser import PathPoint, PlayerTrack


def _point(time_ms: int, speed: float, sprint: int) -> PathPoint:
    return PathPoint(
        time=time_ms,
        x=float(time_ms),
        y=0.0,
        z=0.0,
        health=100,
        speed=speed,
        weapon=8,
        stance=0,
        sprint=sprint,
        event="sample",
    )


def test_player_track_metrics_handle_zero_spawn_time():
    """Raw elapsed spans must be invariant under an origin shift, including zero."""
    track_zero = PlayerTrack(
        guid="g1",
        name="Zero Spawn",
        team="AXIS",
        player_class="MEDIC",
        spawn_time=0,
        death_time=3000,
        first_move_time=500,
        death_type="killed",
        sample_count=4,
        path=[
            PathPoint(0, 0.0, 0.0, 0.0, 100, 0.0, 8, 0, 0, "spawn"),
            _point(500, 100.0, 1),
            _point(1500, 50.0, 0),
            PathPoint(3000, 1500.0, 0.0, 0.0, 0, 0.0, 8, 0, 0, "killed"),
        ],
    )

    assert track_zero.duration_ms == 3000
    assert track_zero.time_to_first_move_ms == 500

    # With spawn_time=1, duration works correctly
    track = PlayerTrack(
        guid="g1b",
        name="Normal Spawn",
        team="AXIS",
        player_class="MEDIC",
        spawn_time=1,
        death_time=3001,
        first_move_time=501,
        death_type="killed",
        sample_count=4,
        path=[
            PathPoint(1, 0.0, 0.0, 0.0, 100, 0.0, 8, 0, 0, "spawn"),
            _point(501, 100.0, 1),
            _point(1501, 50.0, 0),
            PathPoint(3001, 1500.0, 0.0, 0.0, 0, 0.0, 8, 0, 0, "killed"),
        ],
    )
    assert track.duration_ms == 3000
    assert track.time_to_first_move_ms == 500


def test_raw_first_move_zero_is_not_missing():
    track = PlayerTrack("G", "Synthetic", "AXIS", "MEDIC", 0, 100, 0, "world", 0)
    assert track.time_to_first_move_ms == 0
    track.first_move_time = None
    assert track.time_to_first_move_ms is None
    track.death_time = None
    # Keep the historical duration fallback; it is not proof of zero active time.
    assert track.duration_ms == 0


def test_player_track_metrics_are_sample_count_based():
    """sprint_percentage and avg_speed use sample counts, not duration weighting."""
    track = PlayerTrack(
        guid="g2",
        name="Weighted Runner",
        team="ALLIES",
        player_class="ENGINEER",
        spawn_time=1000,
        death_time=4000,
        first_move_time=1500,
        death_type="round_end",
        sample_count=4,
        path=[
            PathPoint(1000, 0.0, 0.0, 0.0, 100, 0.0, 8, 0, 0, "spawn"),
            _point(1500, 120.0, 1),
            _point(2500, 60.0, 0),
            PathPoint(4000, 2500.0, 0.0, 0.0, 100, 0.0, 8, 0, 0, "round_end"),
        ],
    )

    # sprint_percentage: 1 out of 4 samples has sprint=1 -> 25.0%
    assert round(track.sprint_percentage, 1) == 25.0
    # avg_speed: non-zero speeds are 120.0, 60.0 -> mean = 90.0
    assert round(track.avg_speed, 1) == 90.0
