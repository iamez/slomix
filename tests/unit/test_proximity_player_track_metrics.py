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
    track = PlayerTrack(
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

    assert track.duration_ms == 3000
    assert track.time_to_first_move_ms == 500


def test_player_track_metrics_are_duration_weighted():
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

    assert round(track.sprint_percentage, 1) == 33.3
    assert round(track.avg_speed, 1) == 70.0
