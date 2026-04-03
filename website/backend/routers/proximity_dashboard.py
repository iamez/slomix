"""Proximity dashboard endpoints: dashboard, scopes, summary."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.rate_limit import limiter

# Import endpoint functions from sub-routers for dashboard dispatching
from website.backend.routers.proximity_combat import (
    get_proximity_classes,
    get_proximity_engagements,
    get_proximity_hotzones,
)
from website.backend.routers.proximity_events import get_proximity_events
from website.backend.routers.proximity_helpers import (
    DASHBOARD_ALL_SECTIONS,
    DASHBOARD_SECTION_GROUPS,
    _build_proximity_where_clause,
    _compute_scoped_duos,
    _load_scoped_guid_name_map,
    _parse_iso_date,
    _proximity_stub_meta,
    _timed_section,
    logger,
)
from website.backend.routers.proximity_movement import get_proximity_movers, get_proximity_reactions
from website.backend.routers.proximity_objectives import (
    get_proximity_carrier_events,
    get_proximity_carrier_kills,
    get_proximity_carrier_returns,
    get_proximity_construction_events,
    get_proximity_escort_credits,
    get_proximity_vehicle_progress,
)
from website.backend.routers.proximity_positions import (
    get_proximity_hit_regions,
    get_proximity_hit_regions_headshot_rates,
)
from website.backend.routers.proximity_scoring import (
    get_prox_scores,
    get_prox_scores_formula,
    get_proximity_revives,
    get_proximity_weapon_accuracy,
)
from website.backend.routers.proximity_support import get_proximity_movement_stats
from website.backend.routers.proximity_teamplay import (
    get_proximity_cohesion,
    get_proximity_crossfire_angles,
    get_proximity_lua_trades,
    get_proximity_pushes,
    get_proximity_spawn_timing,
    get_proximity_teamplay,
)
from website.backend.routers.proximity_trades import get_proximity_trade_events, get_proximity_trades_summary

router = APIRouter()


@router.get("/proximity/dashboard")
@limiter.limit("10/minute")
async def get_proximity_dashboard(
    request: Request,
    sections: str = "all",
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Composite endpoint: fetches multiple proximity sections in a single request.
    Replaces 29+ individual HTTP calls with one asyncio.gather.

    sections: "all", a group name (critical/combat/teamplay_v5/analytics/objectives/scoring),
              or comma-separated section keys.
    """
    t0_total = time.monotonic()

    # Parse requested sections
    requested = set()
    for part in sections.split(","):
        part = part.strip()
        if part == "all":
            requested = set(DASHBOARD_ALL_SECTIONS)
            break
        elif part in DASHBOARD_SECTION_GROUPS:
            requested.update(DASHBOARD_SECTION_GROUPS[part])
        elif part in DASHBOARD_ALL_SECTIONS:
            requested.add(part)

    if not requested:
        return {"status": "error", "detail": "No valid sections requested"}

    # Pre-parse session_date so all downstream functions receive a date object.
    parsed_date = _parse_iso_date(session_date)

    # Full scope kwargs (for endpoints that accept all 5 scope params)
    full = dict(range_days=range_days, session_date=parsed_date, map_name=map_name,
                round_number=round_number, round_start_unix=round_start_unix)

    # Section dispatchers
    dispatchers = {
        "summary": lambda: get_proximity_summary(**full, db=db),
        "engagements": lambda: get_proximity_engagements(**full, db=db),
        "hotzones": lambda: get_proximity_hotzones(**full, db=db),
        "movers": lambda: get_proximity_movers(**full, db=db),
        "teamplay": lambda: get_proximity_teamplay(**full, limit=6, db=db),
        "classes": lambda: get_proximity_classes(**full, db=db),
        "events": lambda: get_proximity_events(**full, limit=20, db=db),
        "trades_summary": lambda: get_proximity_trades_summary(**full, db=db),
        "trades_events": lambda: get_proximity_trade_events(**full, limit=10, db=db),
        "spawn_timing": lambda: get_proximity_spawn_timing(**full, db=db),
        "cohesion": lambda: get_proximity_cohesion(**full, db=db),
        "crossfire_angles": lambda: get_proximity_crossfire_angles(**full, db=db),
        "pushes": lambda: get_proximity_pushes(**full, db=db),
        "lua_trades": lambda: get_proximity_lua_trades(**full, db=db),
        "kill_outcomes": lambda: get_proximity_kill_outcomes(**full, db=db),
        "hit_regions": lambda: get_proximity_hit_regions(**full, db=db),
        "carrier_events": lambda: get_proximity_carrier_events(**full, db=db),
        "carrier_kills": lambda: get_proximity_carrier_kills(**full, db=db),
        "carrier_returns": lambda: get_proximity_carrier_returns(**full, db=db),
        "vehicle_progress": lambda: get_proximity_vehicle_progress(**full, db=db),
        "escort_credits": lambda: get_proximity_escort_credits(**full, db=db),
        "construction_events": lambda: get_proximity_construction_events(**full, db=db),
        "reactions": lambda: get_proximity_reactions(**full, limit=6, db=db),
        "kill_outcome_stats": lambda: get_proximity_kill_outcomes_player_stats(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "headshot_rates": lambda: get_proximity_hit_regions_headshot_rates(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "movement_stats": lambda: get_proximity_movement_stats(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "revives": lambda: get_proximity_revives(
            range_days=range_days, session_date=parsed_date, map_name=map_name, db=db),
        "weapon_accuracy": lambda: get_proximity_weapon_accuracy(
            range_days=range_days, map_name=map_name, db=db),
        "prox_scores": lambda: get_prox_scores(request=request, range_days=range_days, db=db),
        "prox_formula": get_prox_scores_formula,
    }

    keys = [s for s in DASHBOARD_ALL_SECTIONS if s in requested and s in dispatchers]
    coros = [_timed_section(k, dispatchers[k]()) for k in keys]

    results = await asyncio.gather(*coros, return_exceptions=True)

    sections_dict = {}
    ok_count = 0
    err_count = 0
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            sections_dict[key] = {"_error": str(result), "status": "error"}
            err_count += 1
        elif isinstance(result, dict) and result.get("status") == "error":
            sections_dict[key] = result
            err_count += 1
        else:
            sections_dict[key] = result
            ok_count += 1

    total_ms = round((time.monotonic() - t0_total) * 1000, 1)

    return {
        "status": "ok",
        "sections_requested": len(keys),
        "sections_ok": ok_count,
        "sections_error": err_count,
        "total_ms": total_ms,
        "sections": sections_dict,
    }


@router.get("/proximity/scopes")
async def get_proximity_scopes(
    range_days: int = 60,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Discover session -> map -> round hierarchy from scoped proximity rows.
    """
    payload = _proximity_stub_meta(range_days)
    safe_range = max(1, min(int(range_days or 60), 3650))
    since = datetime.utcnow().date() - timedelta(days=safe_range)

    try:
        rows = await db.fetch_all(
            """
            SELECT session_date, map_name, round_number, round_start_unix, round_end_unix,
                   COUNT(*) AS engagements
            FROM combat_engagement
            WHERE session_date >= $1
            GROUP BY session_date, map_name, round_number, round_start_unix, round_end_unix
            ORDER BY session_date DESC, map_name ASC, round_number ASC, round_start_unix ASC
            """,
            (since,),
        )

        sessions_by_date: dict[str, dict[str, Any]] = {}
        for row in rows:
            session_date_val = row[0]
            map_name_val = str(row[1] or "unknown")
            round_number_val = int(row[2] or 0)
            round_start_val = int(row[3] or 0)
            round_end_val = int(row[4] or 0)
            engagements = int(row[5] or 0)

            session_key = (
                session_date_val.isoformat()
                if hasattr(session_date_val, "isoformat")
                else str(session_date_val)
            )
            session_entry = sessions_by_date.setdefault(
                session_key,
                {
                    "session_date": session_key,
                    "engagements": 0,
                    "_maps": {},
                },
            )
            session_entry["engagements"] += engagements

            map_entry = session_entry["_maps"].setdefault(
                map_name_val,
                {
                    "map_name": map_name_val,
                    "engagements": 0,
                    "rounds": [],
                    "_first_round_start": None,
                },
            )
            map_entry["engagements"] += engagements
            map_entry["rounds"].append(
                {
                    "round_number": round_number_val,
                    "round_start_unix": round_start_val if round_start_val > 0 else None,
                    "round_end_unix": round_end_val if round_end_val > 0 else None,
                    "engagements": engagements,
                }
            )
            if round_start_val > 0:
                first = map_entry["_first_round_start"]
                if first is None or round_start_val < first:
                    map_entry["_first_round_start"] = round_start_val

        sessions: list[dict[str, Any]] = []
        for session in sorted(
            sessions_by_date.values(),
            key=lambda item: item["session_date"],
            reverse=True,
        ):
            maps = []
            for map_item in session["_maps"].values():
                rounds_sorted = sorted(
                    map_item["rounds"],
                    key=lambda r: (
                        r["round_start_unix"] if r["round_start_unix"] is not None else 10**12,
                        r["round_number"],
                    ),
                )
                maps.append(
                    {
                        "map_name": map_item["map_name"],
                        "engagements": map_item["engagements"],
                        "round_count": len(rounds_sorted),
                        "rounds": rounds_sorted,
                        "_first_round_start": map_item["_first_round_start"],
                    }
                )

            maps_sorted = sorted(
                maps,
                key=lambda m: (
                    m["_first_round_start"] if m["_first_round_start"] is not None else 10**12,
                    m["map_name"],
                ),
            )
            for item in maps_sorted:
                item.pop("_first_round_start", None)

            sessions.append(
                {
                    "session_date": session["session_date"],
                    "engagements": session["engagements"],
                    "map_count": len(maps_sorted),
                    "round_count": sum(map_item["round_count"] for map_item in maps_sorted),
                    "maps": maps_sorted,
                }
            )

        default_scope = {
            "session_date": sessions[0]["session_date"] if sessions else None,
            "map_name": None,
            "round_number": None,
            "round_start_unix": None,
        }

        payload.update(
            {
                "status": "ok" if sessions else "prototype",
                "ready": bool(sessions),
                "message": None if sessions else payload["message"],
                "sessions": sessions,
                "scope": default_scope,
            }
        )
    except Exception:
        logger.exception("Proximity scopes query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "sessions": [],
                "scope": {
                    "session_date": None,
                    "map_name": None,
                    "round_number": None,
                    "round_start_unix": None,
                },
            }
        )
    return payload


@router.get("/proximity/summary")
async def get_proximity_summary(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Summary for proximity analytics scoped by session/map/round filters.
    """
    payload = _proximity_stub_meta(range_days)
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )
    query_params = tuple(params)

    try:
        engagement_row = await db.fetch_one(
            "SELECT COUNT(*) AS total_engagements, "
            "AVG(distance_traveled) AS avg_distance, "
            "AVG(duration_ms) AS avg_duration_ms, "
            "AVG(num_attackers) AS avg_attackers, "
            "SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) AS crossfire_events, "
            "SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes, "
            "SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS kills "
            f"FROM combat_engagement {where_sql}",
            query_params,
        )
        total_engagements = engagement_row[0] if engagement_row else 0
        avg_distance = engagement_row[1] if engagement_row else None
        avg_duration = engagement_row[2] if engagement_row else None
        avg_attackers = engagement_row[3] if engagement_row else None
        crossfire_events = engagement_row[4] if engagement_row else 0
        escapes = engagement_row[5] if engagement_row else 0
        kills = engagement_row[6] if engagement_row else 0

        sample_rounds = await db.fetch_val(
            "SELECT COUNT(DISTINCT (session_date, round_number, round_start_unix)) "
            f"FROM combat_engagement {where_sql}",
            query_params,
        )

        hotzones = await db.fetch_val(
            """
            SELECT COUNT(*)
            FROM (
                SELECT FLOOR(COALESCE(end_x, start_x) / 256.0)::int AS grid_x,
                       FLOOR(COALESCE(end_y, start_y) / 256.0)::int AS grid_y
                FROM combat_engagement
            """
            + f" {where_sql} "
            + """
                  AND COALESCE(end_x, start_x) IS NOT NULL
                  AND COALESCE(end_y, start_y) IS NOT NULL
                GROUP BY 1, 2
            ) hz
            """,
            query_params,
        )

        track_row = None
        try:
            track_row = await db.fetch_one(
                "SELECT COUNT(*) AS tracks, "
                "COUNT(DISTINCT player_guid) AS unique_players, "
                "AVG(total_distance) AS avg_track_distance, "
                "AVG(avg_speed) AS avg_speed, "
                "AVG(sprint_percentage) AS avg_sprint_pct, "
                "AVG(CASE WHEN spawn_time_ms >= 0 THEN time_to_first_move_ms END) AS avg_time_to_first_move_ms "
                f"FROM player_track {where_sql}",
                query_params,
            )
        except Exception:
            logger.exception("Failed to fetch player_track stats in summary")
            track_row = None

        duo_rows = await db.fetch_all(
            "SELECT attackers, crossfire_participants, crossfire_delay_ms, outcome "
            f"FROM combat_engagement {where_sql} "
            "AND is_crossfire = TRUE "
            "ORDER BY session_date DESC, round_start_unix DESC, start_time_ms DESC "
            "LIMIT 5000",
            query_params,
        )
        guid_name_map = await _load_scoped_guid_name_map(db, where_sql, query_params)
        top_duos = _compute_scoped_duos(duo_rows, 10, guid_name_map=guid_name_map)

        # v5 teamplay counts
        v5_counts = {}
        for tbl in ['proximity_spawn_timing', 'proximity_team_cohesion',
                     'proximity_crossfire_opportunity', 'proximity_team_push',
                     'proximity_lua_trade_kill']:
            try:
                cnt = await db.fetch_val(
                    f"SELECT COUNT(*) FROM {tbl} {where_sql}", query_params
                )
                v5_counts[tbl] = int(cnt or 0)
            except Exception:
                logger.exception("Failed to count v5 table %s", tbl)
                v5_counts[tbl] = 0

        payload.update(
            {
                "status": "ok" if (total_engagements or 0) > 0 else "prototype",
                "ready": (total_engagements or 0) > 0,
                "message": None if (total_engagements or 0) > 0 else payload["message"],
                "scope": scope,
                "total_engagements": int(total_engagements or 0),
                "avg_distance_m": round(avg_distance, 1) if avg_distance is not None else None,
                "crossfire_events": int(crossfire_events or 0),
                "hotzones": int(hotzones or 0),
                "avg_duration_ms": round(avg_duration, 0) if avg_duration is not None else None,
                "avg_attackers": round(avg_attackers, 2) if avg_attackers is not None else None,
                "escape_rate_pct": round((escapes or 0) * 100 / total_engagements, 1)
                if total_engagements
                else None,
                "kill_rate_pct": round((kills or 0) * 100 / total_engagements, 1)
                if total_engagements
                else None,
                "unique_players": int(track_row[1]) if track_row else None,
                "avg_track_distance_m": round(track_row[2], 1)
                if track_row and track_row[2] is not None
                else None,
                "avg_speed": round(track_row[3], 2)
                if track_row and track_row[3] is not None
                else None,
                "avg_sprint_pct": round(track_row[4], 1)
                if track_row and track_row[4] is not None
                else None,
                "avg_time_to_first_move_ms": round(track_row[5], 0)
                if track_row and track_row[5] is not None
                else None,
                "sample_rounds": int(sample_rounds or 0),
                "top_duos": top_duos,
                "v5_counts": v5_counts,
            }
        )
    except Exception:
        logger.exception("Proximity summary query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "total_engagements": None,
                "avg_distance_m": None,
                "crossfire_events": None,
                "hotzones": None,
                "sample_rounds": 0,
                "top_duos": [],
            }
        )
    return payload


# ===== KILL OUTCOMES (v5.2) =====
# These endpoints are also referenced by the dashboard dispatcher above.


@router.get("/proximity/kill-outcomes")
async def get_proximity_kill_outcomes(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    limit: int = 200,
    db: DatabaseAdapter = Depends(get_db),
):
    """Kill outcome summary and events — gib/revive/tapout breakdown.

    Defined here because the dashboard dispatches to it; the dedicated endpoint
    is registered by proximity_positions but this local version is used
    only for internal dashboard calls.
    """
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
        player_guid=player_guid, player_guid_columns=["victim_guid", "killer_guid"],
    )
    query_params = tuple(params)
    try:
        # Summary by outcome type
        summary_rows = await db.fetch_all(
            f"""
            SELECT outcome, COUNT(*) AS cnt,
                   ROUND(AVG(delta_ms)::numeric, 0) AS avg_delta,
                   ROUND(AVG(effective_denied_ms)::numeric, 0) AS avg_denied
            FROM proximity_kill_outcome {where_sql}
            GROUP BY outcome
            ORDER BY cnt DESC
            """,
            query_params,
        )
        total = sum(int(r[1] or 0) for r in (summary_rows or []))
        outcome_map = {}
        for r in (summary_rows or []):
            outcome_map[r[0]] = {
                "count": int(r[1] or 0),
                "avg_delta_ms": int(r[2] or 0),
                "avg_denied_ms": int(r[3] or 0),
            }
        gibbed = outcome_map.get("gibbed", {}).get("count", 0)
        revived = outcome_map.get("revived", {}).get("count", 0)
        tapped = outcome_map.get("tapped_out", {}).get("count", 0)

        # Recent events
        safe_limit = max(1, min(limit, 500))
        limit_idx = len(params) + 1
        events = await db.fetch_all(
            f"""
            SELECT kill_time, victim_guid, victim_name, killer_guid, killer_name,
                   kill_mod, outcome, delta_ms, effective_denied_ms,
                   gibber_guid, gibber_name, reviver_guid, reviver_name,
                   session_date, map_name, round_number
            FROM proximity_kill_outcome {where_sql}
            ORDER BY session_date DESC, kill_time DESC
            LIMIT ${limit_idx}
            """,
            query_params + (safe_limit,),
        )

        return {
            "status": "ok",
            "scope": scope,
            "summary": {
                "total_kills": total,
                "gibbed": gibbed,
                "revived": revived,
                "tapped_out": tapped,
                "expired": outcome_map.get("expired", {}).get("count", 0),
                "round_end": outcome_map.get("round_end", {}).get("count", 0),
                "gib_rate": round(gibbed * 100.0 / total, 1) if total > 0 else 0,
                "revive_rate": round(revived * 100.0 / total, 1) if total > 0 else 0,
                "avg_delta_ms": outcome_map.get("gibbed", {}).get("avg_delta_ms", 0),
                "avg_denied_ms": outcome_map.get("gibbed", {}).get("avg_denied_ms", 0),
            },
            "outcomes": outcome_map,
            "events": [
                {
                    "kill_time": int(r[0] or 0),
                    "victim_guid": r[1], "victim_name": r[2],
                    "killer_guid": r[3], "killer_name": r[4],
                    "kill_mod": int(r[5] or 0),
                    "outcome": r[6],
                    "delta_ms": int(r[7] or 0),
                    "effective_denied_ms": int(r[8] or 0),
                    "gibber_guid": r[9] or "", "gibber_name": r[10] or "",
                    "reviver_guid": r[11] or "", "reviver_name": r[12] or "",
                    "session_date": r[13].isoformat() if r[13] else None,
                    "map_name": r[14], "round_number": int(r[15] or 0),
                }
                for r in (events or [])
            ],
        }
    except Exception:
        logger.exception("Proximity kill-outcomes error")
        raise HTTPException(status_code=500, detail="Proximity kill-outcomes error")


@router.get("/proximity/kill-outcomes/player-stats")
async def get_proximity_kill_outcomes_player_stats(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    player_guid: str | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player kill outcome stats — Kill Permanence Rate (KPR) and revive rates."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, None, None,
    )
    query_params = tuple(params)
    safe_limit = max(1, min(limit, 50))
    try:
        # As killer: how permanent are their kills?
        killer_rows = await db.fetch_all(
            f"""
            SELECT killer_guid, MAX(killer_name) AS name,
                   COUNT(*) AS total_kills,
                   SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END) AS gibs,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) AS revives,
                   SUM(CASE WHEN outcome = 'tapped_out' THEN 1 ELSE 0 END) AS tapouts,
                   ROUND(AVG(effective_denied_ms)::numeric, 0) AS avg_denied_ms
            FROM proximity_kill_outcome {where_sql}
            AND killer_guid != ''
            GROUP BY killer_guid
            HAVING COUNT(*) >= 3
            ORDER BY (SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END)::float
                     / NULLIF(SUM(CASE WHEN outcome IN ('gibbed','revived') THEN 1 ELSE 0 END), 0)) DESC NULLS LAST
            LIMIT {safe_limit}
            """,
            query_params,
        )
        # As victim: how often are they revived?
        victim_rows = await db.fetch_all(
            f"""
            SELECT victim_guid, MAX(victim_name) AS name,
                   COUNT(*) AS times_killed,
                   SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END) AS times_gibbed,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) AS times_revived,
                   SUM(CASE WHEN outcome = 'tapped_out' THEN 1 ELSE 0 END) AS times_tapped,
                   ROUND(AVG(delta_ms)::numeric, 0) AS avg_wait_ms
            FROM proximity_kill_outcome {where_sql}
            GROUP BY victim_guid
            HAVING COUNT(*) >= 3
            ORDER BY (SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END)::float
                     / NULLIF(COUNT(*), 0)) DESC NULLS LAST
            LIMIT {safe_limit}
            """,
            query_params,
        )

        def _killer_stats(r):
            total = int(r[2] or 0)
            gibs = int(r[3] or 0)
            revs = int(r[4] or 0)
            contested = gibs + revs
            return {
                "guid": r[0], "name": r[1],
                "total_kills": total,
                "gibs": gibs, "revives_against": revs, "tapouts": int(r[5] or 0),
                "kpr": round(gibs / contested, 3) if contested > 0 else 0,
                "avg_denied_ms": int(r[6] or 0),
            }

        def _victim_stats(r):
            total = int(r[2] or 0)
            gibbed = int(r[3] or 0)
            revived = int(r[4] or 0)
            return {
                "guid": r[0], "name": r[1],
                "times_killed": total,
                "times_gibbed": gibbed, "times_revived": revived,
                "times_tapped": int(r[5] or 0),
                "revive_rate": round(revived / total, 3) if total > 0 else 0,
                "gib_rate": round(gibbed / total, 3) if total > 0 else 0,
                "avg_wait_ms": int(r[6] or 0),
            }

        # If specific player requested, filter
        as_killer = [_killer_stats(r) for r in (killer_rows or [])]
        as_victim = [_victim_stats(r) for r in (victim_rows or [])]
        if player_guid and player_guid.strip():
            g = player_guid.strip()
            as_killer = [s for s in as_killer if s["guid"] == g] or as_killer[:1]
            as_victim = [s for s in as_victim if s["guid"] == g] or as_victim[:1]

        return {
            "status": "ok",
            "scope": scope,
            "kill_permanence_leaders": as_killer,
            "revive_rate_leaders": as_victim,
        }
    except Exception:
        logger.exception("Proximity kill-outcomes player-stats error")
        raise HTTPException(status_code=500, detail="Proximity kill-outcomes player-stats error")
