"""Strict reconstruction and independent validation of ET reinforcement clocks.

The timing rows and the inferred offset come from the same Lua calculation, so
internal agreement alone cannot establish accuracy. A clock becomes usable only
after its predicted wave landings agree with independent ``player_track`` spawn
callbacks under the frozen ``reinforcement-clock-v1`` protocol below.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

CLOCK_PROTOCOL_VERSION = "reinforcement-clock-v1"
MIN_INTERNAL_OBSERVATIONS = 3
LANDING_CLUSTER_JITTER_MS = 250
MIN_VALIDATION_LANDINGS = 3
VALIDATION_RESIDUAL_TOLERANCE_MS = 250
MIN_VALIDATION_PASS_RATIO = 0.90

NORMAL_DEATH_EVENTS = frozenset({"killed", "selfkill", "fallen", "world", "teamkill"})
PLAYING_TEAMS = frozenset({"AXIS", "ALLIES"})


@dataclass(frozen=True)
class TimingObservation:
    team: str
    kill_time_ms: int
    interval_ms: int
    time_to_next_spawn_ms: int | None
    spawn_timing_score: float | None = None


@dataclass(frozen=True)
class PlayerLife:
    row_id: int
    player_guid: str
    team: str
    spawn_time_ms: int
    death_time_ms: int | None
    death_type: str | None


@dataclass(frozen=True)
class ReviveObservation:
    player_guid: str
    time_ms: int


@dataclass(frozen=True)
class QualifiedSpawn:
    player_guid: str
    team: str
    time_ms: int
    follows_post_revive_gap: bool


@dataclass(frozen=True)
class SpawnLanding:
    team: str
    time_ms: int
    spawn_count: int
    post_revive_spawn_count: int


@dataclass(frozen=True)
class ClockInference:
    team: str
    status: str
    observation_count: int
    interval_ms: int | None
    offset_ms: int | None
    distinct_intervals_ms: tuple[int, ...]
    distinct_candidates_ms: tuple[int, ...]


@dataclass(frozen=True)
class ClockValidation:
    team: str
    status: str
    interval_ms: int | None
    offset_ms: int | None
    timing_observation_count: int
    landing_count: int
    spawn_observation_count: int
    post_revive_spawn_count: int
    passing_landing_count: int
    pass_ratio: float | None
    residuals_ms: tuple[int, ...]


@dataclass(frozen=True)
class SpawnQualification:
    spawns: tuple[QualifiedSpawn, ...]
    exclusions: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class LandingClustering:
    landings: tuple[SpawnLanding, ...]
    exclusions: tuple[tuple[str, int], ...]


def infer_clock(team: str, observations: Iterable[TimingObservation]) -> ClockInference:
    """Infer one exact offset, rejecting sparse or internally conflicting rows."""
    candidates: list[int] = []
    intervals: list[int] = []
    for observation in observations:
        if observation.team != team:
            continue
        if timing_exclusion_reason(observation) is not None:
            continue
        interval = int(observation.interval_ms)
        time_to_next_value = observation.time_to_next_spawn_ms
        if time_to_next_value is None:
            raise AssertionError("usable timing unexpectedly lacks time_to_next_spawn")
        time_to_next = int(time_to_next_value)
        intervals.append(interval)
        candidates.append(
            (interval - time_to_next - int(observation.kill_time_ms)) % interval
        )

    distinct_intervals = tuple(sorted(set(intervals)))
    distinct_candidates = tuple(sorted(set(candidates)))
    common = {
        "team": team,
        "observation_count": len(candidates),
        "distinct_intervals_ms": distinct_intervals,
        "distinct_candidates_ms": distinct_candidates,
    }
    if len(candidates) < MIN_INTERNAL_OBSERVATIONS:
        return ClockInference(
            status="insufficient",
            interval_ms=distinct_intervals[0] if len(distinct_intervals) == 1 else None,
            offset_ms=None,
            **common,
        )
    if len(distinct_intervals) != 1 or len(distinct_candidates) != 1:
        return ClockInference(
            status="inconsistent",
            interval_ms=distinct_intervals[0] if len(distinct_intervals) == 1 else None,
            offset_ms=None,
            **common,
        )
    return ClockInference(
        status="internally_consistent_unvalidated",
        interval_ms=distinct_intervals[0],
        offset_ms=distinct_candidates[0],
        **common,
    )


def timing_exclusion_reason(observation: TimingObservation) -> str | None:
    """Return the first fail-closed reason a timing row cannot infer a clock."""
    if observation.team not in PLAYING_TEAMS:
        return "unknown_team"
    if int(observation.kill_time_ms) < 0:
        return "negative_kill_time"
    interval = int(observation.interval_ms or 0)
    if interval <= 0:
        return "non_positive_interval"
    if observation.time_to_next_spawn_ms is None:
        return "missing_time_to_next_spawn"
    time_to_next = int(observation.time_to_next_spawn_ms)
    if time_to_next <= 0 or time_to_next > interval:
        return "time_to_next_spawn_out_of_range"
    if (
        observation.spawn_timing_score is not None
        and float(observation.spawn_timing_score) <= 0.0
    ):
        return "non_positive_spawn_timing_score"
    return None


def qualify_normal_spawns(
    lives: Iterable[PlayerLife],
    revives: Iterable[ReviveObservation] = (),
) -> SpawnQualification:
    """Select non-initial normal spawn callbacks with explicit exclusions.

    Any overlapping lives make the whole player-round ambiguous. A later track
    must follow a normal terminal obituary on the same team. Reconnect,
    shutdown, round-end and unknown terminal states never qualify.
    """
    lives_by_guid: dict[str, list[PlayerLife]] = defaultdict(list)
    revives_by_guid: dict[str, list[int]] = defaultdict(list)
    for life in lives:
        lives_by_guid[life.player_guid].append(life)
    for revive in revives:
        revives_by_guid[revive.player_guid].append(int(revive.time_ms))

    exclusions: Counter[str] = Counter()
    qualified: list[QualifiedSpawn] = []
    for guid, player_lives in lives_by_guid.items():
        ordered = sorted(player_lives, key=lambda life: (life.spawn_time_ms, life.row_id))
        exclusions["initial_join"] += 1
        ambiguous_overlap = any(
            previous.death_time_ms is None
            or current.spawn_time_ms < previous.death_time_ms
            for previous, current in zip(ordered, ordered[1:])
        )
        if ambiguous_overlap:
            exclusions["ambiguous_overlapping_lives"] += max(len(ordered) - 1, 0)
            continue

        player_revives = sorted(revives_by_guid.get(guid, ()))
        for previous, current in zip(ordered, ordered[1:]):
            if current.spawn_time_ms < 0:
                exclusions["negative_spawn_time"] += 1
                continue
            if previous.death_time_ms is None:
                exclusions["missing_prior_death_time"] += 1
                continue
            if previous.death_type not in NORMAL_DEATH_EVENTS:
                reason = (
                    "reconnect_or_shutdown"
                    if previous.death_type in {"disconnect", "shutdown"}
                    else "non_death_terminal"
                )
                exclusions[reason] += 1
                continue
            if previous.team != current.team:
                exclusions["team_change"] += 1
                continue
            follows_post_revive_gap = any(
                previous.death_time_ms <= revive_time < current.spawn_time_ms
                for revive_time in player_revives
            )
            qualified.append(
                QualifiedSpawn(
                    player_guid=guid,
                    team=current.team,
                    time_ms=int(current.spawn_time_ms),
                    follows_post_revive_gap=follows_post_revive_gap,
                )
            )

    return SpawnQualification(
        spawns=tuple(sorted(qualified, key=lambda spawn: (spawn.team, spawn.time_ms, spawn.player_guid))),
        exclusions=tuple(sorted(exclusions.items())),
    )


def cluster_spawn_landings(
    spawns: Iterable[QualifiedSpawn],
    *,
    jitter_ms: int = LANDING_CLUSTER_JITTER_MS,
) -> LandingClustering:
    """Cluster same-team callbacks without transitive single-linkage bridging."""
    if jitter_ms < 0:
        raise ValueError("jitter_ms must be non-negative")
    by_team: dict[str, list[QualifiedSpawn]] = defaultdict(list)
    for spawn in spawns:
        by_team[spawn.team].append(spawn)

    landings: list[SpawnLanding] = []
    exclusions: Counter[str] = Counter()
    for team, team_spawns in by_team.items():
        ordered = sorted(team_spawns, key=lambda spawn: (spawn.time_ms, spawn.player_guid))
        current: list[QualifiedSpawn] = []
        anchor_ms: int | None = None
        for spawn in ordered:
            if anchor_ms is None or spawn.time_ms - anchor_ms <= jitter_ms:
                current.append(spawn)
                if anchor_ms is None:
                    anchor_ms = spawn.time_ms
                continue
            landing = _make_landing(team, current)
            if landing is not None:
                landings.append(landing)
            else:
                exclusions["duplicate_player_in_landing"] += len(current)
            current = [spawn]
            anchor_ms = spawn.time_ms
        landing = _make_landing(team, current)
        if landing is not None:
            landings.append(landing)
        elif current:
            exclusions["duplicate_player_in_landing"] += len(current)
    return LandingClustering(
        landings=tuple(sorted(landings, key=lambda landing: (landing.team, landing.time_ms))),
        exclusions=tuple(sorted(exclusions.items())),
    )


def validate_clock(
    inference: ClockInference,
    landings: Iterable[SpawnLanding],
) -> ClockValidation:
    """Validate a unanimous inferred clock against independent landing clusters."""
    team_landings = tuple(landing for landing in landings if landing.team == inference.team)
    spawn_count = sum(landing.spawn_count for landing in team_landings)
    post_revive_count = sum(landing.post_revive_spawn_count for landing in team_landings)
    common = {
        "team": inference.team,
        "interval_ms": inference.interval_ms,
        "offset_ms": inference.offset_ms,
        "timing_observation_count": inference.observation_count,
        "landing_count": len(team_landings),
        "spawn_observation_count": spawn_count,
        "post_revive_spawn_count": post_revive_count,
    }
    if inference.status != "internally_consistent_unvalidated":
        return ClockValidation(
            status=inference.status,
            passing_landing_count=0,
            pass_ratio=None,
            residuals_ms=(),
            **common,
        )
    if inference.interval_ms is None or inference.offset_ms is None:
        raise ValueError("internally consistent clock is missing interval or offset")

    residuals = tuple(
        circular_residual_ms(
            landing.time_ms,
            inference.offset_ms,
            inference.interval_ms,
        )
        for landing in team_landings
    )
    passing = sum(
        residual <= VALIDATION_RESIDUAL_TOLERANCE_MS
        for residual in residuals
    )
    pass_ratio = passing / len(residuals) if residuals else None
    if len(residuals) < MIN_VALIDATION_LANDINGS:
        status = "internally_consistent_unvalidated"
    elif passing / len(residuals) >= MIN_VALIDATION_PASS_RATIO:
        status = "validated"
    else:
        status = "validation_failed"
    return ClockValidation(
        status=status,
        passing_landing_count=passing,
        pass_ratio=pass_ratio,
        residuals_ms=residuals,
        **common,
    )


def circular_residual_ms(time_ms: int, offset_ms: int, interval_ms: int) -> int:
    """Distance from ``time_ms`` to the nearest predicted wave landing."""
    if interval_ms <= 0:
        raise ValueError("interval_ms must be positive")
    phase_ms = (int(time_ms) + int(offset_ms)) % int(interval_ms)
    return min(phase_ms, int(interval_ms) - phase_ms)


def validated_clock_tuple(validation: ClockValidation) -> tuple[int, int] | None:
    """Return ``(offset_ms, interval_ms)`` only for independently valid clocks."""
    if (
        validation.status != "validated"
        or validation.offset_ms is None
        or validation.interval_ms is None
    ):
        return None
    return validation.offset_ms, validation.interval_ms


def validate_round_clocks(
    timings: Iterable[TimingObservation],
    lives: Iterable[PlayerLife],
    revives: Iterable[ReviveObservation] = (),
) -> dict[str, ClockValidation]:
    """Apply the complete protocol to every team represented in one round."""
    timing_rows = tuple(timings)
    qualification = qualify_normal_spawns(lives, revives)
    clustering = cluster_spawn_landings(qualification.spawns)
    teams = sorted({observation.team for observation in timing_rows if observation.team})
    return {
        team: validate_clock(infer_clock(team, timing_rows), clustering.landings)
        for team in teams
    }


def _make_landing(team: str, spawns: list[QualifiedSpawn]) -> SpawnLanding | None:
    if not spawns:
        return None
    # A player cannot normally spawn twice in one team wave. Rejecting the
    # whole ambiguous cluster is safer than letting one player overweight it.
    guids = [spawn.player_guid for spawn in spawns]
    if len(guids) != len(set(guids)):
        return None
    times = sorted(spawn.time_ms for spawn in spawns)
    midpoint = len(times) // 2
    if len(times) % 2:
        landing_time = times[midpoint]
    else:
        landing_time = (times[midpoint - 1] + times[midpoint]) // 2
    return SpawnLanding(
        team=team,
        time_ms=landing_time,
        spawn_count=len(spawns),
        post_revive_spawn_count=sum(spawn.follows_post_revive_gap for spawn in spawns),
    )
