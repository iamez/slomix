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

from fastapi import APIRouter, Depends, Query

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _parse_json_field,
    logger,
)
from website.backend.utils.et_constants import strip_et_colors

router = APIRouter()

# 1s proximity-series buckets — matches the lurker-profile downsample so the
# journey's solo segments line up with the session-wide solo_pct metric.
SERIES_BUCKET_MS = 1000
SOLO_RADIUS = 500  # units from nearest teammate = "solo" (lurker convention)


def _downsample_path(path: list, step_ms: int) -> list[dict]:
    """Thin a 200ms path to step_ms, keeping the rich per-point fields."""
    out: list[dict] = []
    last_t = -step_ms
    for p in path or []:
        try:
            t = int(p.get("time", 0))
        except (TypeError, AttributeError):
            continue
        if t - last_t >= step_ms:
            out.append({
                "t": t,
                "x": float(p.get("x", 0)),
                "y": float(p.get("y", 0)),
                "z": float(p.get("z", 0)),
                "health": p.get("health"),
                "speed": p.get("speed"),
                "stance": p.get("stance"),
                "sprint": p.get("sprint"),
                "event": p.get("event"),
            })
            last_t = t
    return out


def _bucket_points(path: list) -> dict[int, tuple[int, float, float]]:
    """Map 1s bucket -> (time, x, y), one representative point per bucket."""
    buckets: dict[int, tuple[int, float, float]] = {}
    for p in path or []:
        try:
            t = int(p.get("time", 0))
            x = float(p.get("x", 0))
            y = float(p.get("y", 0))
        except (TypeError, AttributeError, ValueError):
            continue
        buckets.setdefault(t // SERIES_BUCKET_MS, (t, x, y))
    return buckets


def _nearest_in_buckets(
    bucket: int, x: float, y: float,
    others: list[dict[int, tuple[int, float, float]]],
) -> tuple[float, int]:
    """(nearest distance, count within SOLO_RADIUS) vs other players' buckets.

    Probes the +-1 neighbouring buckets so a 1s sampling phase shift between
    two tracks cannot make a teammate invisible.
    """
    nearest = float("inf")
    within = 0
    for buckets in others:
        best = float("inf")
        for b in (bucket - 1, bucket, bucket + 1):
            pt = buckets.get(b)
            if pt is None:
                continue
            d = ((x - pt[1]) ** 2 + (y - pt[2]) ** 2) ** 0.5
            if d < best:
                best = d
        if best < nearest:
            nearest = best
        if best <= SOLO_RADIUS:
            within += 1
    return nearest, within


def _life_narrative(life: dict, player_name: str) -> str:
    """One human sentence per life, storytelling style."""
    parts: list[str] = []
    dur_s = (life["duration_ms"] or 0) / 1000
    cls = life.get("player_class") or "player"
    parts.append(f"{player_name} spawned as {cls}, lived {dur_s:.0f}s")
    solo = life.get("solo_pct")
    if solo is not None and solo >= 50:
        parts.append(f"mostly alone ({solo:.0f}% solo)")
    elif solo is not None and solo <= 15:
        parts.append("glued to the team")
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
    elif life.get("death_type") == "round_end":
        parts.append("survived to the end of the round")
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
    # All tracks for the round — the subject's lives plus everyone else for
    # the nearest-teammate/enemy series (~80 tracks/round, cheap).
    track_rows = await db.fetch_all(
        f"""
        SELECT player_guid, player_name, team, player_class,
               spawn_time_ms, death_time_ms, duration_ms, path,
               total_distance, sprint_percentage
        FROM player_track
        {where_sql}
        ORDER BY spawn_time_ms
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )

    subject_rows = [r for r in (track_rows or []) if (r[0] or "").upper().startswith(guid)]
    if not subject_rows:
        return {
            "status": "ok", "scope": scope, "player": None, "lives": [],
            "summary": {"lives": 0},
            "message": "No tracks for this player in the selected round.",
        }

    subject_guid = subject_rows[0][0]
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
                "type": "carrier", "time": int(r[0] or 0), "end_time": int(r[1] or 0),
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
                "type": "objective_run", "time": int(r[0] or 0),
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
            {"type": "construction", "time": int(r[0] or 0), "action": r[1], "objective": r[2]}
            for r in (constr_rows or [])
        ]
    except Exception:
        logger.exception("player-journey objective lookup failed (continuing without)")

    # Bucket every OTHER player's path once for the proximity series.
    others: list[dict] = []
    for r in (track_rows or []):
        if r[0] == subject_guid:
            continue
        path = _parse_json_field(r[7]) or []
        if not path:
            continue
        others.append({
            "team": r[2],
            "spawn": int(r[4] or 0),
            "death": int(r[5] or 0) or None,
            "buckets": _bucket_points(path),
        })

    lives = []
    total_kills = 0
    total_deaths = 0
    for idx, r in enumerate(subject_rows, start=1):
        spawn_ms = int(r[4] or 0)
        death_ms = int(r[5] or 0) or None
        end_ms = death_ms if death_ms is not None else float("inf")
        path = _parse_json_field(r[7]) or []

        # Kills/death inside this life window.
        kills = []
        death = None
        for k in (kill_rows or []):
            kt = int(k[0] or 0)
            if not (spawn_ms <= kt <= end_ms):
                continue
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
        total_kills += len(kills)
        if death:
            total_deaths += 1

        # 1s proximity series vs teammates and enemies alive at that moment.
        series = []
        solo_samples = 0
        for bp in _bucket_points(path).values():
            t, x, y = bp
            alive_team = [
                o["buckets"] for o in others
                if o["team"] == subject_team
                and o["spawn"] <= t <= (o["death"] or float("inf"))
            ]
            alive_enemy = [
                o["buckets"] for o in others
                if o["team"] != subject_team
                and o["spawn"] <= t <= (o["death"] or float("inf"))
            ]
            bucket = t // SERIES_BUCKET_MS
            near_tm, tm_500 = _nearest_in_buckets(bucket, x, y, alive_team)
            near_en, en_500 = _nearest_in_buckets(bucket, x, y, alive_enemy)
            if near_tm > SOLO_RADIUS:
                solo_samples += 1
            series.append({
                "t": t,
                "nearest_teammate": round(near_tm, 1) if near_tm != float("inf") else None,
                "nearest_enemy": round(near_en, 1) if near_en != float("inf") else None,
                "teammates_500u": tm_500,
                "enemies_500u": en_500,
            })
        solo_pct = round(solo_samples / len(series) * 100, 1) if series else None

        life_objectives = [
            e for e in objective_events
            if spawn_ms <= e["time"] <= end_ms
        ]

        life = {
            "life_index": idx,
            "player_class": r[3],
            "spawn_time_ms": spawn_ms,
            "death_time_ms": death_ms,
            "duration_ms": int(r[6] or 0),
            "total_distance": float(r[8] or 0),
            "sprint_pct": float(r[9] or 0),
            "death_type": "round_end" if death_ms is None else None,
            "path": _downsample_path(path, downsample_ms),
            "kills": kills,
            "death": death,
            "proximity_series": series,
            "solo_pct": solo_pct,
            "objective_events": life_objectives,
        }
        life["narrative"] = _life_narrative(life, strip_et_colors(player["name"]))
        lives.append(life)

    alive_total_ms = sum(life["duration_ms"] for life in lives)
    return {
        "status": "ok",
        "scope": scope,
        "player": player,
        "lives": lives,
        "summary": {
            "lives": len(lives),
            "kills": total_kills,
            "deaths": total_deaths,
            "avg_life_s": round(alive_total_ms / len(lives) / 1000, 1) if lives else 0,
            "objective_events": len(objective_events),
        },
    }
