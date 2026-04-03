"""Proximity support endpoints: support-summary, movement-stats."""

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _parse_iso_date,
    _table_column_exists,
    logger,
)

router = APIRouter()


@router.get("/proximity/support-summary")
async def get_proximity_support_summary(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Support summary — medic support uptime per round."""
    try:
        if not await _table_column_exists(db, 'proximity_support_summary', 'support_uptime_pct'):
            return {"status": "ok", "summary": {}, "rounds": [], "by_map": []}

        where_parts: list = []
        params: list = []
        if session_date:
            params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
            where_parts.append(f"session_date = ${len(params)}")
        else:
            params.append(range_days)
            where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
        if map_name:
            params.append(map_name)
            where_parts.append(f"map_name = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*) AS total_rounds,
                   ROUND(AVG(support_uptime_pct)::numeric, 1) AS avg_uptime_pct,
                   ROUND(MAX(support_uptime_pct)::numeric, 1) AS max_uptime_pct,
                   ROUND(AVG(CASE WHEN total_samples > 0
                        THEN support_samples::numeric / total_samples * 100 ELSE 0 END), 1) AS avg_coverage_pct
            FROM proximity_support_summary {where_sql}
            """,
            tuple(params),
        )
        summary = {
            "total_rounds": int(summary_row[0] or 0) if summary_row else 0,
            "avg_uptime_pct": float(summary_row[1] or 0) if summary_row else 0,
            "max_uptime_pct": float(summary_row[2] or 0) if summary_row else 0,
            "avg_coverage_pct": float(summary_row[3] or 0) if summary_row else 0,
        }

        # Per-map breakdown
        map_rows = await db.fetch_all(
            f"""
            SELECT map_name,
                   COUNT(*) AS rounds,
                   ROUND(AVG(support_uptime_pct)::numeric, 1) AS avg_uptime_pct,
                   ROUND(MAX(support_uptime_pct)::numeric, 1) AS max_uptime_pct,
                   SUM(support_samples) AS total_support_samples,
                   SUM(total_samples) AS total_samples
            FROM proximity_support_summary {where_sql}
            GROUP BY map_name
            ORDER BY AVG(support_uptime_pct) DESC
            """,
            tuple(params),
        )
        by_map = [dict(r) for r in (map_rows or [])]

        # Recent rounds
        recent_rows = await db.fetch_all(
            f"""
            SELECT map_name, round_number, support_uptime_pct,
                   support_samples, total_samples, session_date
            FROM proximity_support_summary {where_sql}
            ORDER BY session_date DESC, round_start_unix DESC
            LIMIT 15
            """,
            tuple(params),
        )
        rounds = [dict(r) for r in (recent_rows or [])]

        return {"status": "ok", "summary": summary, "by_map": by_map, "rounds": rounds}
    except Exception:
        logger.exception("support-summary error")
        raise HTTPException(status_code=500, detail="support-summary error")


@router.get("/proximity/movement-stats")
async def get_proximity_movement_stats(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    player_guid: str | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player aggregated movement analytics from path samples."""
    where_parts = ["peak_speed IS NOT NULL"]
    params: list = []

    if session_date:
        params.append(_parse_iso_date(session_date) if isinstance(session_date, str) else session_date)
        where_parts.append(f"session_date = ${len(params)}")
    else:
        params.append(range_days)
        where_parts.append(f"session_date >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")
    if map_name:
        params.append(map_name)
        where_parts.append(f"map_name = ${len(params)}")
    if player_guid:
        params.append(player_guid)
        where_parts.append(f"player_guid = ${len(params)}")

    where_sql = "WHERE " + " AND ".join(where_parts)
    safe_limit = max(1, min(limit, 50))
    scope = {"session_date": session_date, "map_name": map_name, "player_guid": player_guid}

    try:
        rows = await db.fetch_all(
            f"""
            SELECT player_guid, MAX(player_name) AS name,
                   COUNT(*) AS tracks,
                   ROUND(SUM(duration_ms)::numeric / 1000, 1) AS alive_sec,
                   ROUND(AVG(peak_speed)::numeric, 1) AS avg_peak_speed,
                   ROUND(MAX(peak_speed)::numeric, 1) AS max_peak_speed,
                   ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
                   ROUND(SUM(total_distance)::numeric, 0) AS total_distance,
                   ROUND(SUM(stance_standing_sec)::numeric, 1) AS standing_sec,
                   ROUND(SUM(stance_crouching_sec)::numeric, 1) AS crouching_sec,
                   ROUND(SUM(stance_prone_sec)::numeric, 1) AS prone_sec,
                   ROUND(SUM(sprint_sec)::numeric, 1) AS sprint_sec,
                   ROUND(AVG(sprint_percentage)::numeric, 1) AS avg_sprint_pct,
                   ROUND(AVG(post_spawn_distance)::numeric, 0) AS avg_post_spawn_dist,
                   ROUND(AVG(CASE WHEN duration_ms > 0 THEN total_distance / (duration_ms::real / 1000) ELSE 0 END)::numeric, 1) AS avg_distance_per_sec
            FROM player_track {where_sql}
            GROUP BY player_guid
            HAVING COUNT(*) >= 3
            ORDER BY SUM(total_distance) DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )

        players = []
        for r in (rows or []):
            alive = float(r[3] or 0)
            standing = float(r[8] or 0)
            crouching = float(r[9] or 0)
            prone = float(r[10] or 0)
            stance_total = standing + crouching + prone
            players.append({
                "guid": r[0],
                "name": r[1],
                "tracks": int(r[2] or 0),
                "alive_sec": alive,
                "avg_peak_speed": float(r[4] or 0),
                "max_peak_speed": float(r[5] or 0),
                "avg_speed": float(r[6] or 0),
                "total_distance": float(r[7] or 0),
                "standing_sec": standing,
                "crouching_sec": crouching,
                "prone_sec": prone,
                "standing_pct": round(standing * 100 / stance_total, 1) if stance_total > 0 else 0,
                "crouching_pct": round(crouching * 100 / stance_total, 1) if stance_total > 0 else 0,
                "prone_pct": round(prone * 100 / stance_total, 1) if stance_total > 0 else 0,
                "sprint_sec": float(r[11] or 0),
                "avg_sprint_pct": float(r[12] or 0),
                "avg_post_spawn_dist": float(r[13] or 0),
                "avg_distance_per_sec": float(r[14] or 0),
            })

        return {
            "status": "ok",
            "scope": scope,
            "players": players,
        }
    except Exception:
        logger.exception("Proximity movement-stats error")
        raise HTTPException(status_code=500, detail="Proximity movement-stats error")
