"""
Diagnostics, monitoring, and live-status endpoints.

Extracted from api.py to reduce file size and improve maintainability.
"""

import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from shared.services.round_linkage_anomaly_service import assess_round_linkage_anomalies
from website.backend.dependencies import get_db, require_admin_user
from website.backend.env_utils import getenv_int
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    normalize_monitoring_timestamp as _normalize_monitoring_timestamp,
)
from website.backend.services.game_server_query import query_game_server

router = APIRouter()
logger = get_app_logger("api.diagnostics")

# Game server configuration (for direct UDP query)
GAME_SERVER_HOST = os.getenv("SERVER_HOST", "puran.hehe.si")
GAME_SERVER_PORT = getenv_int("SERVER_PORT", 27960)

MONITORING_STALE_THRESHOLD_SECONDS = getenv_int("MONITORING_STALE_THRESHOLD_SECONDS", 300)


@router.get("/status")
async def get_status(db: DatabaseAdapter = Depends(get_db)):
    try:
        await db.fetch_one("SELECT 1")
        return {"status": "online", "service": "Slomix API", "database": "ok"}
    except Exception as exc:
        logger.error("Status check database error: %s", exc)
        return {
            "status": "degraded",
            "service": "Slomix API",
            "database": "error",
            "error": "Database connection failed",
        }


@router.get("/diagnostics")
async def get_diagnostics(
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Run comprehensive diagnostics on the website backend.
    Checks database connectivity, table permissions, and data availability.
    """
    results = {
        "status": "ok",
        "timestamp": None,
        "database": {"status": "unknown", "tests": []},
        "tables": [],
        "issues": [],
        "warnings": [],
        "time": {},
        "monitoring": {},
    }

    results["timestamp"] = datetime.utcnow().isoformat()

    # Tables to check
    tables_to_check = [
        ("rounds", "SELECT COUNT(*) FROM rounds", True),
        (
            "player_comprehensive_stats",
            "SELECT COUNT(*) FROM player_comprehensive_stats",
            True,
        ),
        ("gaming_sessions", "SELECT COUNT(DISTINCT gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL", False),
        ("processed_files", "SELECT COUNT(*) FROM processed_files", True),
        ("lua_round_teams", "SELECT COUNT(*) FROM lua_round_teams", False),
        ("round_correlations", "SELECT COUNT(*) FROM round_correlations", False),
        ("player_skill_ratings", "SELECT COUNT(*) FROM player_skill_ratings", False),
        ("user_player_links", "SELECT COUNT(*) FROM user_player_links", False),
    ]

    # Test database connectivity and tables
    try:
        for table_name, query, required in tables_to_check:
            try:
                count = await db.fetch_val(query)
                results["tables"].append(
                    {
                        "name": table_name,
                        "status": "ok",
                        "row_count": count,
                        "required": required,
                    }
                )
            except Exception as e:
                error_msg = str(e)
                status = "error"
                if "permission denied" in error_msg.lower():
                    status = "permission_denied"
                    results["warnings"].append(f"No permission to read {table_name}")
                elif "does not exist" in error_msg.lower():
                    status = "not_found"
                    if required:
                        results["issues"].append(
                            f"Required table {table_name} not found"
                        )
                    else:
                        results["warnings"].append(
                            f"Optional table {table_name} not found"
                        )
                else:
                    results["issues"].append(
                        f"Error checking {table_name}: {error_msg}"
                    )

                results["tables"].append(
                    {
                        "name": table_name,
                        "status": status,
                        "error": error_msg,
                        "required": required,
                    }
                )

        results["database"]["status"] = "connected"

        # Check for critical data
        rounds_count = next(
            (
                t["row_count"]
                for t in results["tables"]
                if t["name"] == "rounds" and t.get("row_count")
            ),
            0,
        )
        if rounds_count == 0:
            results["warnings"].append("No rounds data in database")

        players_count = next(
            (
                t["row_count"]
                for t in results["tables"]
                if t["name"] == "player_comprehensive_stats" and t.get("row_count")
            ),
            0,
        )
        if players_count == 0:
            results["warnings"].append("No player stats in database")

    except Exception as e:
        results["database"]["status"] = "error"
        results["database"]["error"] = str(e)
        results["issues"].append(f"Database connection error: {str(e)}")

    # Timing metrics (raw Lua vs capped)
    try:
        time_row = await db.fetch_one(
            """
            SELECT
                COALESCE(SUM(COALESCE(time_dead_minutes, 0) * 60), 0) AS raw_dead_seconds,
                COALESCE(SUM(
                    CASE
                        WHEN COALESCE(time_dead_minutes, 0) * 60 > COALESCE(time_played_seconds, 0)
                        THEN COALESCE(time_played_seconds, 0)
                        ELSE COALESCE(time_dead_minutes, 0) * 60
                    END
                ), 0) AS capped_dead_seconds,
                COALESCE(SUM(
                    CASE
                        WHEN COALESCE(time_dead_minutes, 0) * 60 > COALESCE(time_played_seconds, 0)
                        THEN (COALESCE(time_dead_minutes, 0) * 60 - COALESCE(time_played_seconds, 0))
                        ELSE 0
                    END
                ), 0) AS cap_seconds,
                COALESCE(SUM(
                    CASE
                        WHEN COALESCE(time_dead_minutes, 0) * 60 > COALESCE(time_played_seconds, 0)
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS cap_hits,
                COALESCE(SUM(COALESCE(denied_playtime, 0)), 0) AS raw_denied_seconds
            FROM player_comprehensive_stats
            """
        )
        if time_row:
            (
                raw_dead_seconds,
                capped_dead_seconds,
                cap_seconds,
                cap_hits,
                raw_denied_seconds,
            ) = time_row
            results["time"] = {
                "raw_dead_seconds": int(raw_dead_seconds or 0),
                "agg_dead_seconds": int(capped_dead_seconds or 0),
                "cap_seconds": int(cap_seconds or 0),
                "cap_hits": int(cap_hits or 0),
                "raw_denied_seconds": int(raw_denied_seconds or 0),
            }
    except Exception as e:
        results["warnings"].append(f"Time metrics unavailable: {str(e)}")

    # Set overall status
    if results["issues"]:
        results["status"] = "error"
    elif results["warnings"]:
        results["status"] = "warning"

    # Monitoring history quick info (non-fatal)
    _MONITORING_TABLES = {"server_status_history", "voice_status_history"}
    monitoring = {}
    for table, key in (
        ("server_status_history", "server"),
        ("voice_status_history", "voice"),
    ):
        if table not in _MONITORING_TABLES:
            continue
        try:
            count = await db.fetch_val(f"SELECT COUNT(*) FROM {table}")
            last = await db.fetch_val(f"SELECT MAX(recorded_at) FROM {table}")
            monitoring[key] = {
                "count": count or 0,
                "last_recorded_at": last.isoformat() if last else None,
            }
        except Exception as e:
            logger.error("Error querying monitoring table %s: %s", key, e, exc_info=True)
            monitoring[key] = {"count": 0, "last_recorded_at": None, "error": "query failed"}

    results["monitoring"] = monitoring
    return results


@router.get("/diagnostics/lua-webhook")
async def get_lua_webhook_diagnostics(
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Diagnostics for Lua webhook ingestion (lua_round_teams).
    Shows recent captures and whether rows are linked to rounds.
    """
    payload = {
        "status": "ok",
        "counts": {},
        "linkage_health": {},
        "r1_r2_coverage": [],
        "orphans": [],
        "latest": None,
        "recent": [],
        "trends": {
            "lua_rows_by_day": [],
            "rounds_without_lua_by_day": [],
        },
        "errors": [],
    }

    try:
        total = await db.fetch_val("SELECT COUNT(*) FROM lua_round_teams")
        unlinked = await db.fetch_val("SELECT COUNT(*) FROM lua_round_teams WHERE round_id IS NULL")
        payload["counts"]["total"] = int(total or 0)
        payload["counts"]["unlinked_total"] = int(unlinked or 0)
    except Exception as e:
        payload["status"] = "error"
        payload["errors"].append(f"count_failed: {e}")
        return payload

    try:
        recent_24h = await db.fetch_val(
            "SELECT COUNT(*) FROM lua_round_teams WHERE captured_at >= NOW() - INTERVAL '24 hours'"
        )
        unlinked_24h = await db.fetch_val(
            "SELECT COUNT(*) FROM lua_round_teams WHERE round_id IS NULL AND captured_at >= NOW() - INTERVAL '24 hours'"
        )
        payload["counts"]["last_24h"] = int(recent_24h or 0)
        payload["counts"]["unlinked_24h"] = int(unlinked_24h or 0)
    except Exception as e:
        payload["errors"].append(f"count_24h_failed: {e}")

    # --- Linkage health summary ---
    try:
        total_count = payload["counts"].get("total", 0)
        unlinked_count = payload["counts"].get("unlinked_total", 0)
        linked_count = total_count - unlinked_count
        pct = round(100.0 * linked_count / total_count, 1) if total_count else 0.0
        payload["linkage_health"] = {
            "linked": linked_count,
            "orphans": unlinked_count,
            "linkage_pct": pct,
            "status": "healthy" if pct >= 90 else ("degraded" if pct >= 50 else "poor"),
        }
    except Exception as e:
        payload["errors"].append(f"linkage_health_failed: {e}")

    # --- R1/R2 coverage ---
    try:
        coverage_rows = await db.fetch_all(
            """
            SELECT
                r.round_number,
                COUNT(*) AS total_rounds,
                COUNT(l.id) AS with_lua,
                COUNT(*) - COUNT(l.id) AS without_lua,
                ROUND(100.0 * COUNT(l.id) / NULLIF(COUNT(*), 0), 1) AS coverage_pct
            FROM rounds r
            LEFT JOIN lua_round_teams l ON l.round_id = r.id
            WHERE r.round_number IN (1, 2)
            GROUP BY r.round_number
            ORDER BY r.round_number
            """
        )
        for rn, total_r, with_lua, without_lua, cov_pct in coverage_rows:
            payload["r1_r2_coverage"].append({
                "round_number": int(rn),
                "total_rounds": int(total_r or 0),
                "with_lua": int(with_lua or 0),
                "without_lua": int(without_lua or 0),
                "coverage_pct": float(cov_pct or 0),
            })
    except Exception as e:
        payload["errors"].append(f"r1_r2_coverage_failed: {e}")

    # --- Orphan details ---
    try:
        orphan_rows = await db.fetch_all(
            """
            SELECT id, match_id, map_name, round_number, round_start_unix, captured_at
            FROM lua_round_teams
            WHERE round_id IS NULL
            ORDER BY id
            LIMIT 20
            """
        )
        for oid, mid, mname, rnum, rstart, cap_at in orphan_rows:
            payload["orphans"].append({
                "id": int(oid),
                "match_id": mid,
                "map_name": mname,
                "round_number": int(rnum),
                "round_start_unix": int(rstart or 0),
                "captured_at": cap_at.isoformat() if cap_at else None,
            })
    except Exception as e:
        payload["errors"].append(f"orphans_failed: {e}")

    try:
        row = await db.fetch_one(
            """
            SELECT id, map_name, round_number, round_start_unix, round_end_unix,
                   actual_duration_seconds, total_pause_seconds, end_reason,
                   captured_at, round_id, lua_version
            FROM lua_round_teams
            ORDER BY captured_at DESC NULLS LAST, id DESC
            LIMIT 1
            """
        )
        if row:
            (
                id_,
                map_name,
                round_number,
                round_start_unix,
                round_end_unix,
                actual_duration_seconds,
                total_pause_seconds,
                end_reason,
                captured_at,
                round_id,
                lua_version,
            ) = row
            payload["latest"] = {
                "id": id_,
                "map_name": map_name,
                "round_number": round_number,
                "round_start_unix": round_start_unix,
                "round_end_unix": round_end_unix,
                "actual_duration_seconds": actual_duration_seconds,
                "total_pause_seconds": total_pause_seconds,
                "end_reason": end_reason,
                "captured_at": captured_at.isoformat() if captured_at else None,
                "round_id": round_id,
                "lua_version": lua_version,
            }
    except Exception as e:
        payload["errors"].append(f"latest_failed: {e}")

    try:
        rows = await db.fetch_all(
            """
            SELECT id, map_name, round_number, round_end_unix,
                   actual_duration_seconds, total_pause_seconds,
                   end_reason, captured_at, round_id
            FROM lua_round_teams
            ORDER BY captured_at DESC NULLS LAST, id DESC
            LIMIT 5
            """
        )
        for row in rows:
            (
                id_,
                map_name,
                round_number,
                round_end_unix,
                actual_duration_seconds,
                total_pause_seconds,
                end_reason,
                captured_at,
                round_id,
            ) = row
            payload["recent"].append(
                {
                    "id": id_,
                    "map_name": map_name,
                    "round_number": round_number,
                    "round_end_unix": round_end_unix,
                    "actual_duration_seconds": actual_duration_seconds,
                    "total_pause_seconds": total_pause_seconds,
                    "end_reason": end_reason,
                    "captured_at": captured_at.isoformat() if captured_at else None,
                    "round_id": round_id,
                }
            )
    except Exception as e:
        payload["errors"].append(f"recent_failed: {e}")

    try:
        lua_daily_rows = await db.fetch_all(
            """
            SELECT
                DATE(captured_at) AS day,
                COUNT(*) AS lua_rows,
                COUNT(*) FILTER (WHERE round_id IS NULL) AS unlinked_rows
            FROM lua_round_teams
            WHERE captured_at >= NOW() - INTERVAL '14 days'
            GROUP BY 1
            ORDER BY 1 DESC
            """
        )
        for day, lua_rows, unlinked_rows in lua_daily_rows:
            payload["trends"]["lua_rows_by_day"].append(
                {
                    "day": str(day),
                    "lua_rows": int(lua_rows or 0),
                    "unlinked_rows": int(unlinked_rows or 0),
                }
            )

        round_daily_rows = await db.fetch_all(
            """
            SELECT
                r.round_date AS day,
                COUNT(*) AS rounds_total,
                COUNT(*) FILTER (WHERE l.id IS NULL) AS rounds_without_lua
            FROM rounds r
            LEFT JOIN lua_round_teams l ON l.round_id = r.id
            WHERE r.round_number IN (1, 2)
              AND r.round_date >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY 1
            ORDER BY 1 DESC
            """
        )
        for day, rounds_total, rounds_without_lua in round_daily_rows:
            payload["trends"]["rounds_without_lua_by_day"].append(
                {
                    "day": str(day),
                    "rounds_total": int(rounds_total or 0),
                    "rounds_without_lua": int(rounds_without_lua or 0),
                }
            )
    except Exception as e:
        payload["errors"].append(f"trends_failed: {e}")

    if payload["errors"]:
        payload["status"] = "warning"
    return payload


@router.get("/diagnostics/round-linkage")
async def get_round_linkage_diagnostics(
    sample_limit: int = Query(default=20, ge=1, le=200),
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Read-only anomaly checks for round/match linkage consistency.
    Returns thresholded breach list plus sample mismatch rows.
    """
    return await assess_round_linkage_anomalies(db, sample_limit=sample_limit)


@router.get("/diagnostics/time-audit")
async def get_time_audit(
    limit: int = Query(default=250, ge=1, le=1000),
    ratio_diff: float = Query(default=5.0, ge=0.0, le=500.0),
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Audit stored time_dead values against computed ratios for recent rows.
    Returns summary counts and sample mismatches.
    """
    query = """
        SELECT
            round_id,
            round_date,
            map_name,
            round_number,
            player_guid,
            player_name,
            time_played_seconds,
            time_dead_minutes,
            time_dead_ratio,
            denied_playtime
        FROM player_comprehensive_stats
        ORDER BY round_id DESC
        LIMIT $1
    """
    try:
        rows = await db.fetch_all(query, (limit,))
    except Exception as e:
        logger.error("Database error in time_dead audit: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

    summary = {
        "checked": 0,
        "dead_gt_played": 0,
        "ratio_mismatch": 0,
        "negative_dead": 0,
        "ratio_without_played": 0,
        "denied_gt_played": 0,
    }
    samples = []

    for row in rows:
        summary["checked"] += 1
        (
            round_id,
            round_date,
            map_name,
            round_number,
            player_guid,
            player_name,
            time_played_seconds,
            time_dead_minutes,
            time_dead_ratio,
            denied_playtime,
        ) = row

        time_played_seconds = float(time_played_seconds or 0)
        time_dead_minutes = float(time_dead_minutes or 0)
        time_dead_ratio = float(time_dead_ratio or 0)
        denied_playtime = float(denied_playtime or 0)

        dead_seconds = time_dead_minutes * 60.0
        ratio_calc = None
        ratio_diff_val = None
        if time_played_seconds > 0:
            ratio_calc = (dead_seconds / time_played_seconds) * 100.0
            ratio_diff_val = abs(ratio_calc - time_dead_ratio)

        flags = []
        if time_dead_minutes < 0:
            summary["negative_dead"] += 1
            flags.append("negative_dead")
        if time_played_seconds > 0 and dead_seconds > time_played_seconds + 1:
            summary["dead_gt_played"] += 1
            flags.append("dead_gt_played")
        if time_dead_ratio > 0 and time_played_seconds == 0:
            summary["ratio_without_played"] += 1
            flags.append("ratio_without_played")
        if (
            ratio_diff_val is not None
            and time_dead_ratio > 0
            and ratio_diff_val > ratio_diff
        ):
            summary["ratio_mismatch"] += 1
            flags.append("ratio_mismatch")
        if time_played_seconds > 0 and denied_playtime > time_played_seconds + 1:
            summary["denied_gt_played"] += 1
            flags.append("denied_gt_played")

        if flags and len(samples) < 25:
            samples.append(
                {
                    "round_id": round_id,
                    "round_date": str(round_date),
                    "map_name": map_name,
                    "round_number": round_number,
                    "player_guid": player_guid,
                    "player_name": player_name,
                    "time_played_seconds": time_played_seconds,
                    "time_dead_minutes": time_dead_minutes,
                    "time_dead_ratio": time_dead_ratio,
                    "ratio_calc": round(ratio_calc, 2) if ratio_calc is not None else None,
                    "ratio_diff": round(ratio_diff_val, 2) if ratio_diff_val is not None else None,
                    "denied_playtime": denied_playtime,
                    "flags": flags,
                }
            )

    return {
        "limit": limit,
        "ratio_diff_threshold": ratio_diff,
        "summary": summary,
        "samples": samples,
    }

@router.get("/diagnostics/spawn-audit")
async def get_spawn_audit(
    limit: int = Query(default=200, ge=1, le=1000),
    diff_seconds: int = Query(default=30, ge=0, le=3600),
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Audit Lua spawn stats vs player_comprehensive_stats time_dead_minutes.
    Compares per-player dead_seconds from lua_spawn_stats to DB time_dead_minutes.
    """
    query = """
        SELECT
            s.id,
            s.round_id,
            s.match_id,
            s.round_number,
            s.map_name,
            s.player_guid,
            s.player_name,
            s.spawn_count,
            s.death_count,
            s.dead_seconds,
            s.avg_respawn_seconds,
            s.max_respawn_seconds,
            p.time_dead_minutes,
            p.time_played_seconds
        FROM lua_spawn_stats s
        LEFT JOIN player_comprehensive_stats p
            ON p.round_id = s.round_id
           AND p.player_guid = s.player_guid
        ORDER BY s.id DESC
        LIMIT $1
    """

    try:
        rows = await db.fetch_all(query, (limit,))
    except Exception as e:
        logger.error("Database error in round integrity audit: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

    summary = {
        "checked": 0,
        "missing_round_id": 0,
        "missing_player_stats": 0,
        "dead_gt_played": 0,
        "diff_gt_threshold": 0,
    }
    samples = []

    for row in rows:
        summary["checked"] += 1
        (
            _id,
            round_id,
            match_id,
            round_number,
            map_name,
            player_guid,
            player_name,
            spawn_count,
            death_count,
            dead_seconds,
            avg_respawn_seconds,
            max_respawn_seconds,
            time_dead_minutes,
            time_played_seconds,
        ) = row

        if round_id is None:
            summary["missing_round_id"] += 1

        dead_seconds = int(dead_seconds or 0)
        time_played_seconds = float(time_played_seconds or 0)
        time_dead_minutes = float(time_dead_minutes or 0)
        db_dead_seconds = time_dead_minutes * 60.0
        diff = abs(dead_seconds - db_dead_seconds) if time_dead_minutes or dead_seconds else 0

        flags = []
        if time_dead_minutes == 0 and dead_seconds > 0:
            summary["missing_player_stats"] += 1
            flags.append("missing_player_stats")
        if time_played_seconds > 0 and dead_seconds > time_played_seconds + 1:
            summary["dead_gt_played"] += 1
            flags.append("dead_gt_played")
        if diff > diff_seconds:
            summary["diff_gt_threshold"] += 1
            flags.append("diff_gt_threshold")

        if flags and len(samples) < 25:
            samples.append(
                {
                    "round_id": round_id,
                    "match_id": match_id,
                    "round_number": round_number,
                    "map_name": map_name,
                    "player_guid": player_guid,
                    "player_name": player_name,
                    "spawn_count": spawn_count,
                    "death_count": death_count,
                    "dead_seconds_lua": dead_seconds,
                    "time_dead_seconds_db": int(db_dead_seconds),
                    "time_played_seconds": int(time_played_seconds),
                    "avg_respawn_seconds": avg_respawn_seconds,
                    "max_respawn_seconds": max_respawn_seconds,
                    "diff_seconds": int(diff),
                    "flags": flags,
                }
            )

    return {
        "status": "ok",
        "summary": summary,
        "samples": samples,
        "params": {"limit": limit, "diff_seconds": diff_seconds},
    }


@router.get("/monitoring/status")
async def get_monitoring_status(
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Lightweight monitoring status for history tables.
    """
    now = datetime.utcnow()
    payload = {
        "server": {
            "count": 0,
            "last_recorded_at": None,
            "age_seconds": None,
            "is_stale": False,
            "stale_threshold_seconds": MONITORING_STALE_THRESHOLD_SECONDS,
        },
        "voice": {
            "count": 0,
            "last_recorded_at": None,
            "age_seconds": None,
            "is_stale": False,
            "stale_threshold_seconds": MONITORING_STALE_THRESHOLD_SECONDS,
        },
    }

    _MONITORING_STATUS_TABLES = {"server_status_history", "voice_status_history"}
    for table, key in (
        ("server_status_history", "server"),
        ("voice_status_history", "voice"),
    ):
        if table not in _MONITORING_STATUS_TABLES:
            continue
        try:
            count = await db.fetch_val(f"SELECT COUNT(*) FROM {table}")
            last = await db.fetch_val(f"SELECT MAX(recorded_at) FROM {table}")
            normalized_last = _normalize_monitoring_timestamp(last)
            age_seconds = (
                int((now - normalized_last).total_seconds())
                if normalized_last
                else None
            )
            is_stale = (
                age_seconds is not None
                and age_seconds > MONITORING_STALE_THRESHOLD_SECONDS
            )
            payload[key] = {
                "count": count or 0,
                "last_recorded_at": f"{normalized_last.isoformat()}Z"
                if normalized_last
                else None,
                "age_seconds": age_seconds,
                "is_stale": is_stale,
                "stale_threshold_seconds": MONITORING_STALE_THRESHOLD_SECONDS,
            }
        except Exception as e:
            payload[key] = {
                "count": 0,
                "last_recorded_at": None,
                "age_seconds": None,
                "is_stale": False,
                "stale_threshold_seconds": MONITORING_STALE_THRESHOLD_SECONDS,
                "error": "query failed",
            }
            logger.error("Error querying monitoring status %s: %s", key, e, exc_info=True)

    return payload


@router.get("/live-status")
async def get_live_status(
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Get real-time status of voice channels and game server.

    - Voice channel data: from database (updated by Discord bot)
    - Game server data: direct UDP query (real-time)
    """
    # ========== VOICE CHANNEL STATUS (from database) ==========
    voice_result = {
        "members": [],
        "count": 0,
        "channel_name": "Gaming",
        "updated_at": None,
    }

    try:
        query = """
            SELECT status_data, updated_at
            FROM live_status
            WHERE status_type = 'voice_channel'
        """
        row = await db.fetch_one(query)

        if row:
            status_data = row[0]
            updated_at = row[1]

            if isinstance(status_data, str):
                status_data = json.loads(status_data)

            voice_result = {
                **status_data,
                "updated_at": str(updated_at) if updated_at else None,
            }
    except Exception as e:
        logger.error(f"Error fetching voice channel status: {e}")
        voice_result["error"] = True

    # ========== GAME SERVER STATUS (direct UDP query) ==========
    server_status = query_game_server(GAME_SERVER_HOST, GAME_SERVER_PORT)

    game_result = {
        "online": server_status.online,
        "hostname": server_status.clean_hostname,
        "map": server_status.map_name,
        "players": [
            {"name": p.name, "score": p.score, "ping": p.ping}
            for p in server_status.players
        ],
        "player_count": server_status.player_count,
        "max_players": server_status.max_players,
        "ping_ms": server_status.ping_ms,
        "updated_at": datetime.now().isoformat(),
    }

    if server_status.error:
        game_result["error"] = server_status.error

    return {"voice_channel": voice_result, "game_server": game_result}


@router.get("/server-activity/history")
async def get_server_activity_history(
    hours: int = 72,
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Get historical server activity data for charting.

    Args:
        hours: Number of hours of history to fetch (default 72 = 3 days)

    Returns:
        data_points: Array of status records
        summary: Peak, average, uptime stats
    """
    try:
        # Calculate time range
        since = datetime.utcnow() - timedelta(hours=hours)

        # Fetch data points
        query = """
            SELECT
                recorded_at,
                player_count,
                max_players,
                map_name,
                online
            FROM server_status_history
            WHERE recorded_at >= CAST($1 AS TIMESTAMP)
            ORDER BY recorded_at ASC
        """
        rows = await db.fetch_all(query, (since,))

        data_points = []
        total_players = 0
        peak_players = 0
        peak_time = None
        online_count = 0

        for row in rows:
            recorded_at, player_count, max_players, map_name, online = row

            data_points.append(
                {
                    "timestamp": recorded_at.isoformat() if recorded_at else None,
                    "player_count": player_count,
                    "max_players": max_players,
                    "map": map_name,
                    "online": online,
                }
            )

            if online:
                online_count += 1
                total_players += player_count
                if player_count > peak_players:
                    peak_players = player_count
                    peak_time = recorded_at

        total_records = len(rows)
        avg_players = round(total_players / online_count, 1) if online_count > 0 else 0
        uptime_percent = (
            round((online_count / total_records) * 100, 1) if total_records > 0 else 0
        )

        return {
            "data_points": data_points,
            "summary": {
                "peak_players": peak_players,
                "peak_time": peak_time.isoformat() if peak_time else None,
                "avg_players": avg_players,
                "uptime_percent": uptime_percent,
                "total_records": total_records,
            },
        }

    except Exception as e:
        logger.error("Error fetching server activity: %s", e, exc_info=True)
        return {
            "data_points": [],
            "summary": {
                "peak_players": 0,
                "peak_time": None,
                "avg_players": 0,
                "uptime_percent": 0,
                "total_records": 0,
            },
            "error": "Internal server error",
        }


@router.get("/voice-activity/history")
async def get_voice_activity_history(
    hours: int = 720,
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Get historical voice channel activity data for charting.

    Args:
        hours: Number of hours of history to fetch (default 720 = 30 days)

    Returns:
        data_points: Array of voice status records
        summary: Peak, average, session stats
    """
    try:
        # Calculate time range
        since = datetime.utcnow() - timedelta(hours=hours)

        # Fetch data points from voice_status_history
        query = """
            SELECT
                recorded_at,
                member_count,
                channel_name,
                members
            FROM voice_status_history
            WHERE recorded_at >= CAST($1 AS TIMESTAMP)
            ORDER BY recorded_at ASC
        """
        rows = await db.fetch_all(query, (since,))

        data_points = []
        total_members = 0
        peak_members = 0
        peak_time = None
        session_count = 0
        was_empty = True

        for row in rows:
            recorded_at, member_count, channel_name, members = row

            data_points.append(
                {
                    "timestamp": recorded_at.isoformat() if recorded_at else None,
                    "member_count": member_count,
                    "channel_name": channel_name,
                    "members": members if members else [],
                }
            )

            total_members += member_count
            if member_count > peak_members:
                peak_members = member_count
                peak_time = recorded_at

            # Count sessions (transitions from 0 to > 0)
            if was_empty and member_count > 0:
                session_count += 1
            was_empty = member_count == 0

        total_records = len(rows)
        non_empty_records = sum(1 for p in data_points if p["member_count"] > 0)
        avg_members = (
            round(total_members / non_empty_records, 1) if non_empty_records > 0 else 0
        )

        return {
            "data_points": data_points,
            "summary": {
                "peak_members": peak_members,
                "peak_time": peak_time.isoformat() if peak_time else None,
                "avg_members": avg_members,
                "total_sessions": session_count,
                "total_records": total_records,
            },
        }

    except Exception as e:
        logger.error("Error fetching voice activity: %s", e, exc_info=True)
        return {
            "data_points": [],
            "summary": {
                "peak_members": 0,
                "peak_time": None,
                "avg_members": 0,
                "total_sessions": 0,
                "total_records": 0,
            },
            "error": "Internal server error",
        }


@router.get("/voice-activity/current")
async def get_current_voice_activity(
    db: DatabaseAdapter = Depends(get_db),
    _user: dict = Depends(require_admin_user),
):
    """
    Get detailed current voice channel status with join times.

    Returns detailed information about who is in voice and how long.
    """
    try:
        # First try to get from voice_members table (active members)
        query = """
            SELECT
                discord_id,
                member_name,
                channel_id,
                channel_name,
                joined_at
            FROM voice_members
            WHERE left_at IS NULL
            ORDER BY joined_at ASC
        """
        rows = await db.fetch_all(query)

        members = []
        channels = {}

        for row in rows:
            discord_id, member_name, channel_id, channel_name, joined_at = row

            # Calculate time in voice
            if joined_at:
                now = datetime.utcnow()
                if hasattr(joined_at, "replace"):
                    # Make naive if timezone-aware
                    if joined_at.tzinfo is not None:
                        joined_at = joined_at.replace(tzinfo=None)
                duration_seconds = int((now - joined_at).total_seconds())
            else:
                duration_seconds = 0

            member_info = {
                "discord_id": discord_id,
                "name": member_name,
                "channel_id": channel_id,
                "channel_name": channel_name or "Gaming",
                "joined_at": joined_at.isoformat() if joined_at else None,
                "duration_seconds": duration_seconds,
            }
            members.append(member_info)

            # Group by channel
            if channel_id not in channels:
                channels[channel_id] = {
                    "id": channel_id,
                    "name": channel_name or "Gaming",
                    "members": [],
                }
            channels[channel_id]["members"].append(member_info)

        return {
            "total_count": len(members),
            "members": members,
            "channels": list(channels.values()),
        }

    except Exception as e:
        error_text = str(e)
        denied_voice_members = (
            "permission denied" in error_text.lower()
            and "voice_members" in error_text.lower()
        )
        if not denied_voice_members:
            logger.error(f"Error fetching current voice activity: {e}")
        # Fallback to live_status table
        try:
            query = """
                SELECT status_data, updated_at
                FROM live_status
                WHERE status_type = 'voice_channel'
            """
            row = await db.fetch_one(query)

            if row:
                status_data = row[0]
                if isinstance(status_data, str):
                    status_data = json.loads(status_data)

                members = status_data.get("members", [])
                return {
                    "total_count": len(members),
                    "members": [
                        {"name": m.get("name", "Unknown"), "channel_name": "Gaming"}
                        for m in members
                    ],
                    "channels": [],
                }
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError):
            logger.debug("Voice status fallback parse failed")

        return {
            "total_count": 0,
            "members": [],
            "channels": [],
            "error": None if denied_voice_members else "Voice channel query failed",
        }
