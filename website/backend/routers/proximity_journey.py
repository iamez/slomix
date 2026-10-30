"""Player Journey endpoint: per-life spawn->death traces with full context.

For one player in one round, returns every life (player_track row) enriched
with: the movement path, kills/deaths (proximity_kill_outcome), spawn-timing
usage (proximity_spawn_timing — see docs/PROXIMITY_E2E_AUDIT_2026-06-10.md
section 3 for the field semantics), a 1s nearest-teammate/nearest-enemy
proximity series computed from all players' tracks, overlapping objective
events, and a one-line narrative.

Strictly round-scoped (session_date + map_name + round_number required) to
keep payloads bounded (~100-300 KB for a long round).
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query

from shared.proximity_paths import capture_segments
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _parse_json_field,
    logger,
)
from website.backend.services.track_lifecycle import track_end_sql
from website.backend.utils.et_constants import strip_et_colors

router = APIRouter()

# 1s proximity-series buckets — matches the lurker-profile downsample so the
# journey's solo segments line up with the session-wide solo_pct metric.
SERIES_BUCKET_MS = 1000
SOLO_RADIUS = 500  # units from nearest teammate = "solo" (lurker convention)


def _raw_track_span(start: int | None, end: int | None) -> int | None:
    """Raw source-clock span, NOT pause-adjusted active time; end0 is unknown."""
    if start is None or end is None or start < 0 or end <= 0 or end < start:
        return None
    return end - start


def _event_owner(time: int | None, rows: list) -> tuple[int | None, str | None]:
    """Require one known closed window; no inferred end or boundary tiebreak."""
    if time is None or time < 0:
        return None, "missing_or_negative_timestamp"
    candidates = []
    for index, row in enumerate(rows):
        start, end = row[4], row[5]
        known = _raw_track_span(start, end) is not None
        if start is not None and start >= 0 and time < start:
            continue
        # An invalid/reversed interval supplies no reliable upper bound.
        if known and time > end:
            continue
        candidates.append((index, known))
    if len(candidates) != 1:
        return None, "ambiguous_life_windows" if candidates else "outside_life_windows"
    index, known = candidates[0]
    return (index, None) if known else (None, "unknown_life_bounds")


def _downsample_path(path: list, step_ms: int) -> list[dict]:
    """Thin a 200ms path to step_ms, keeping the rich per-point fields."""
    out: list[dict] = []
    last_t = -step_ms
    segmented = capture_segments(path or [])
    boundary_ids = {id(segment[0]) for segment in segmented[1:]}
    for p in path or []:
        try:
            t = int(p.get("time", 0))
        except (TypeError, AttributeError):
            continue
        boundary = id(p) in boundary_ids or p.get("event") == "capture_resume"
        if boundary or t - last_t >= step_ms:
            out.append({
                "t": t,
                "x": float(p["x"]) if p.get("x") is not None else None,
                "y": float(p["y"]) if p.get("y") is not None else None,
                "z": float(p["z"]) if p.get("z") is not None else None,
                "health": p.get("health"),
                "speed": p.get("speed"),
                "stance": p.get("stance"),
                "sprint": p.get("sprint"),
                "event": p.get("event"),
                "break_before": boundary,
            })
            last_t = t
    return out


def _observations(path: list):
    """Finite source positions only; missing fields are not zero coordinates."""
    for p in path or []:
        if not isinstance(p, dict):
            continue
        t, x, y = p.get("time"), p.get("x"), p.get("y")
        if type(t) is not int or t < 0:
            continue
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)):
            continue
        yield t, float(x), float(y)


def _bucket_points(path: list) -> dict[int, tuple[int, float, float]]:
    """One actual subject observation per second; no fabricated coordinates."""
    buckets: dict[int, tuple[int, float, float]] = {}
    for t, x, y in _observations(path):
        buckets.setdefault(t // SERIES_BUCKET_MS, (t, x, y))
    return buckets


def _simultaneous_neighbours(t: int, x: float, y: float, team: str, observations: dict) -> dict:
    """One unambiguous position per GUID at this exact raw timestamp."""
    friends, enemies = [], []
    ambiguous = 0
    for positions in observations.get(t, {}).values():
        if len(positions) != 1:
            ambiguous += 1
            continue
        other_team, ox, oy = next(iter(positions))
        distance = math.hypot(x - ox, y - oy)
        (friends if other_team == team else enemies).append(distance)
    return {
        "t": t,
        "nearest_teammate": round(min(friends), 1) if friends else None,
        "nearest_enemy": round(min(enemies), 1) if enemies else None,
        "teammates_500u": sum(d <= SOLO_RADIUS for d in friends),
        "enemies_500u": sum(d <= SOLO_RADIUS for d in enemies),
        "observed_teammates": len(friends),
        "observed_enemies": len(enemies),
        "ambiguous_players": ambiguous,
    }


def _life_narrative(life: dict, player_name: str) -> str:
    """One human sentence per life, storytelling style."""
    parts: list[str] = []
    raw_ms = life.get("raw_duration_ms")
    cls = life.get("player_class") or "player"
    elapsed = (f"raw track span {raw_ms / 1000:.0f}s (may include pauses)"
               if raw_ms is not None else "raw track span unavailable")
    parts.append(f"{player_name} spawned as {cls}, {elapsed}")
    solo = life.get("solo_pct")
    if solo is not None and solo >= 50:
        parts.append(f"observed teammates farther than 500u in {solo:.0f}% of covered samples")
    elif solo is not None and solo <= 15:
        parts.append("near observed teammates in most covered samples")
    kills = life.get("kills") or []
    if kills:
        denials = [k["time_to_next_spawn"] for k in kills if k.get("time_to_next_spawn")]
        if denials:
            parts.append(
                f"{len(kills)} kill{'s' if len(kills) != 1 else ''} "
                f"(denied ~{max(denials) / 1000:.0f}s of enemy spawn time)"
            )
        else:
            parts.append(f"{len(kills)} kill{'s' if len(kills) != 1 else ''}")
    death = life.get("death")
    if death:
        outcome = death.get("outcome") or ""
        killer = strip_et_colors(death.get("killer_name") or "")
        if outcome == "revived":
            parts.append(f"downed by {killer or 'the enemy'} but revived")
        elif outcome:
            parts.append(f"died to {killer or 'the world'} ({outcome})")
    elif not life.get("deaths") and life.get("death_type") == "round_end":
        parts.append("survived to the end of the round")
    if life.get("event_assignment_unavailable"):
        parts.append(life["event_assignment_unavailable"])
    return ", ".join(parts) + "."


@router.get("/proximity/player-journey")
async def get_player_journey(
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    map_name: str = Query(..., description="Map name"),
    round_number: int = Query(..., ge=0, description="Round number"),
    player_guid: str = Query(..., min_length=8, max_length=32),
    round_start_unix: int | None = Query(default=None, ge=0),
    downsample_ms: int = Query(default=400, ge=200, le=2000),
    db: DatabaseAdapter = Depends(get_db),
):
    """Every spawn->death life of one player in one round, with context."""
    where_sql, params, scope = _build_proximity_where_clause(
        30, session_date, map_name, round_number, round_start_unix,
    )

    guid = player_guid.strip().upper()
    elapsed_time_quality = {
        "basis": "raw_source_timestamps",
        "active_time_verified": False,
        "reason": "Raw spans may include pauses; active life time is not verified.",
        "excludes": "Missing/negative spawn, missing/zero end sentinel, or reversed end.",
    }
    # All tracks for the round — the subject's lives plus everyone else for
    # the nearest-teammate/enemy series (~80 tracks/round, cheap).
    track_rows = await db.fetch_all(
        f"""
        SELECT player_guid, player_name, team, player_class,
               spawn_time_ms, death_time_ms, duration_ms, path,
               total_distance, sprint_percentage, {track_end_sql()} AS death_type
        FROM player_track
        {where_sql}
        ORDER BY spawn_time_ms
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )

    subject_rows = [r for r in (track_rows or []) if (r[0] or "").upper().startswith(guid)]
    if len({(r[0] or "").upper() for r in subject_rows}) > 1:
        raise HTTPException(status_code=409, detail="Ambiguous player GUID prefix; use a full GUID.")
    if not subject_rows:
        return {
            "status": "ok", "scope": scope, "player": None, "lives": [],
            "summary": {"lives": 0, "avg_life_s": None,
                        "avg_raw_span_s": None, "raw_span_samples": 0},
            "elapsed_time_quality": elapsed_time_quality,
            "event_assignment": {"status": "unavailable", "reason": "No matching tracks; event lookups not performed."},
            "unassigned_events": [],
            "message": "No tracks for this player in the selected round.",
        }

    subject_guid = subject_rows[0][0]
    # Interim conservative scope gate: neighbouring bucket probes do not yet
    # carry per-segment coverage, so any declared gap invalidates this series.
    proximity_unavailable = (
        "Proximity unavailable: capture interruption in the selected round; "
        "segment-aware neighbour coverage is not yet available."
        if any(
            p.get("event") == "capture_resume"
            for row in (track_rows or [])
            for p in (_parse_json_field(row[7]) or [])
        ) else None
    )
    subject_team = subject_rows[0][2]
    player = {
        "guid": subject_guid,
        "name": subject_rows[0][1],
        "team": subject_team,
    }

    # Kills/deaths involving the player.
    guid_params = list(params)
    guid_params.append(subject_guid)
    gp = len(guid_params)
    kill_rows = await db.fetch_all(
        f"""
        SELECT kill_time, killer_guid, killer_name, victim_guid, victim_name,
               outcome, effective_denied_ms, reviver_name, gibber_name
        FROM proximity_kill_outcome
        {where_sql} AND (killer_guid = ${gp} OR victim_guid = ${gp})
        ORDER BY kill_time
        """,  # nosec B608 - where_sql/gp are $N-parameterized; no user data interpolated
        tuple(guid_params),
    )
    st_rows = await db.fetch_all(
        f"""
        SELECT kill_time, killer_guid, victim_guid, enemy_spawn_interval,
               time_to_next_spawn, spawn_timing_score
        FROM proximity_spawn_timing
        {where_sql} AND (killer_guid = ${gp} OR victim_guid = ${gp})
        ORDER BY kill_time
        """,  # nosec B608 - where_sql/gp are $N-parameterized; no user data interpolated
        tuple(guid_params),
    )
    st_by_kill = {(int(r[0]), r[1], r[2]): r for r in (st_rows or [])}

    # Objective involvement (carrier runs, objective runs, constructions).
    objective_events: list[dict] = []
    objective_events_unavailable: str | None = None
    try:
        carrier_rows = await db.fetch_all(
            f"""
            SELECT pickup_time, drop_time, outcome, carry_distance, flag_team
            FROM proximity_carrier_event
            {where_sql} AND carrier_guid = ${gp}
            ORDER BY pickup_time
            """,  # nosec B608 - where_sql/gp are $N-parameterized; no user data interpolated
            tuple(guid_params),
        )
        objective_events += [
            {
                "type": "carrier", "time": int(r[0]) if r[0] is not None else None, "end_time": int(r[1] or 0),
                "outcome": r[2], "carry_distance": float(r[3] or 0), "flag_team": r[4],
            }
            for r in (carrier_rows or [])
        ]
        run_rows = await db.fetch_all(
            f"""
            SELECT action_time, action_type, track_name, run_type
            FROM proximity_objective_run
            {where_sql} AND engineer_guid = ${gp}
            ORDER BY action_time
            """,  # nosec B608 - where_sql/gp are $N-parameterized; no user data interpolated
            tuple(guid_params),
        )
        objective_events += [
            {
                "type": "objective_run", "time": int(r[0]) if r[0] is not None else None,
                "action": r[1], "objective": r[2], "run_type": r[3],
            }
            for r in (run_rows or [])
        ]
        constr_rows = await db.fetch_all(
            f"""
            SELECT event_time, event_type, track_name
            FROM proximity_construction_event
            {where_sql} AND player_guid = ${gp}
            ORDER BY event_time
            """,  # nosec B608 - where_sql/gp are $N-parameterized; no user data interpolated
            tuple(guid_params),
        )
        objective_events += [
            {"type": "construction", "time": int(r[0]) if r[0] is not None else None,
             "action": r[1], "objective": r[2]}
            for r in (constr_rows or [])
        ]
    except Exception as exc:
        logger.exception("player-journey objective lookup failed (continuing without)")
        # Named, not zeroed — and not partial either: a failure after the first
        # query would otherwise leave the carrier rows in the lives while the
        # summary says unavailable (Codex on #1009, twice).
        objective_events_unavailable = f"objective lookup failed: {type(exc).__name__}"
        objective_events = []

    kill_owners = [_event_owner(k[0], subject_rows) for k in (kill_rows or [])]
    objective_owners = [_event_owner(e["time"], subject_rows) for e in objective_events]
    unassigned_events = [
        {"kind": "combat", "time": k[0], "killer_guid": k[1], "victim_guid": k[3],
         "outcome": k[5], "reason": owner[1]}
        for k, owner in zip(kill_rows or [], kill_owners) if owner[0] is None
    ] + [
        {**e, "kind": "objective", "reason": owner[1]}
        for e, owner in zip(objective_events, objective_owners) if owner[0] is None
    ]
    event_assignment_unavailable = (
        f"event attribution incomplete: {len(unassigned_events)} source events have no unique known life"
        if unassigned_events else None
    )

    # Index all observations once: subject downsampling must not discard the
    # simultaneous neighbour point. A repeated GUID never adds a second player.
    observations: dict = {}
    for r in (track_rows or []):
        other_guid = (r[0] or "").upper()
        if not other_guid or other_guid == subject_guid.upper():
            continue
        if r[2] not in ("AXIS", "ALLIES"):
            continue  # Unknown/spectator allegiance is not an observed enemy.
        path = _parse_json_field(r[7]) or []
        for t, x, y in _observations(path):
            if r[4] is not None and r[4] >= 0 and t < r[4]:
                continue
            if r[5] is not None and r[5] > 0 and t > r[5]:
                continue
            observations.setdefault(t, {}).setdefault(other_guid, set()).add((r[2], x, y))

    lives = []
    total_kills = 0
    total_deaths = 0
    for idx, r in enumerate(subject_rows, start=1):
        life_team = r[2]
        life_proximity_unavailable = proximity_unavailable
        if life_team not in ("AXIS", "ALLIES"):
            life_proximity_unavailable = "Proximity unavailable: this track has no known playing team."
        spawn_ms = int(r[4] or 0)
        death_ms = int(r[5] or 0) or None
        path = _parse_json_field(r[7]) or []

        # Kills/death inside this life window.
        kills = []
        death = None
        deaths = []
        for k, owner in zip(kill_rows or [], kill_owners):
            if owner[0] != idx - 1:
                continue
            kt = int(k[0])
            st = st_by_kill.get((kt, k[1], k[3]))
            if k[1] == subject_guid:
                kills.append({
                    "time": kt,
                    "victim_name": k[4],
                    "outcome": k[5],
                    "denied_ms": int(k[6] or 0),
                    "spawn_timing_score": float(st[5]) if st else None,
                    "time_to_next_spawn": int(st[4]) if st else None,
                })
            if k[3] == subject_guid:
                death = {
                    "time": kt,
                    "killer_name": k[2],
                    "outcome": k[5],
                    "reviver_name": k[7] or None,
                    "gibber_name": k[8] or None,
                    # victim-side wait the death cost (seconds to next wave)
                    "victim_wait_ms": int(st[4]) if st else None,
                }
                deaths.append(death)
        # The legacy singular slot cannot represent multiple source outcomes.
        # Keep every record, but do not silently pick the last as definitive.
        if len(deaths) > 1:
            death = None
        total_kills += len(kills)
        total_deaths += len(deaths)

        # Sampled proximity vs simultaneous positions, not a full alive roster.
        series = []
        solo_samples = 0
        observed_team_samples = 0
        for bp in ([] if life_proximity_unavailable else _bucket_points(path).values()):
            t, x, y = bp
            sample = _simultaneous_neighbours(t, x, y, life_team, observations)
            if sample["nearest_teammate"] is not None:
                observed_team_samples += 1
                if sample["teammates_500u"] == 0:
                    solo_samples += 1
            series.append(sample)
        solo_pct = (
            round(solo_samples / observed_team_samples * 100, 1)
            if observed_team_samples else None
        )

        life_objectives = [
            e for e, owner in zip(objective_events, objective_owners)
            if owner[0] == idx - 1
        ]

        life = {
            "life_index": idx,
            "team": life_team,
            "player_class": r[3],
            "spawn_time_ms": spawn_ms,
            "death_time_ms": death_ms,
            "duration_ms": int(r[6] or 0),
            # Legacy stored duration above is retained, not certified/repaired.
            "raw_duration_ms": _raw_track_span(r[4], r[5]),
            "total_distance": float(r[8] or 0),
            "sprint_pct": float(r[9] or 0),
            # No death-time sentinel or positional gap can establish a cause.
            "death_type": r[10],
            "path": _downsample_path(path, downsample_ms),
            "kills": kills,
            "death": death,
            "deaths": deaths,
            "proximity_series": series,
            "proximity_unavailable": life_proximity_unavailable,
            "solo_basis": "Simultaneous raw-time observations; missing times, conflicting GUID positions and unknown/nonplaying teams excluded, not proof of solitude or a complete alive roster.",
            "proximity_coverage": {"subject_samples": len(series),
                                   "samples_with_observed_teammate": observed_team_samples},
            "solo_pct": solo_pct,
            "objective_events": life_objectives,
            "event_assignment_unavailable": (
                "; ".join(filter(None, [event_assignment_unavailable,
                    "multiple death outcomes in this track; singular death unavailable" if len(deaths) > 1 else None]))
                or None
            ),
        }
        life["narrative"] = _life_narrative(life, strip_et_colors(player["name"]))
        lives.append(life)

    raw_spans = [life["raw_duration_ms"] for life in lives if life["raw_duration_ms"] is not None]
    return {
        "status": "ok",
        "scope": scope,
        "player": player,
        "lives": lives,
        "elapsed_time_quality": elapsed_time_quality,
        "event_assignment": {
            "status": "partial" if unassigned_events or objective_events_unavailable else "assigned",
            "basis": "Unique known closed source window; shared endpoints are ambiguous.",
            "scope": "Retrieved combat and objective records only; not evidence of complete capture.",
            "objective_lookup_unavailable": objective_events_unavailable,
            "source_events": len(kill_owners) + len(objective_owners),
            "assigned": len(kill_owners) + len(objective_owners) - len(unassigned_events),
            "unassigned": len(unassigned_events),
            "excludes": "Unknown/overlapping life bounds, missing/negative times and events outside lives.",
        },
        "unassigned_events": unassigned_events,
        "summary": {
            "lives": len(lives),
            "kills": total_kills,
            "deaths": total_deaths,
            "avg_life_s": None,  # Deprecated: raw spans never certify active life.
            "avg_raw_span_s": round(sum(raw_spans) / len(raw_spans) / 1000, 1) if raw_spans else None,
            "raw_span_samples": len(raw_spans),
            "objective_events": None if objective_events_unavailable else len(objective_events),
            "objective_events_unavailable": objective_events_unavailable,
        },
    }
