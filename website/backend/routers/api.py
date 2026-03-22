import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import math
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from bot.core.season_manager import SeasonManager
from bot.core.utils import (
    escape_like_pattern,
)  # SQL injection protection for LIKE queries
from bot.config import load_config
from website.backend.services.website_session_data_service import (
    WebsiteSessionDataService as SessionDataService,
)
from website.backend.services.game_server_query import query_game_server
from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.stopwatch_scoring_service import StopwatchScoringService
from bot.services.round_linkage_anomaly_service import assess_round_linkage_anomalies
from website.backend.logging_config import get_app_logger
from website.backend.env_utils import getenv_int

router = APIRouter()
logger = get_app_logger("api")

# Game server configuration (for direct UDP query)
GAME_SERVER_HOST = os.getenv("SERVER_HOST", "puran.hehe.si")
GAME_SERVER_PORT = getenv_int("SERVER_PORT", 27960)

MONITORING_STALE_THRESHOLD_SECONDS = getenv_int("MONITORING_STALE_THRESHOLD_SECONDS", 300)


# Shared helpers — extracted to api_helpers.py for reuse across routers.
# Local aliases preserve the underscore-prefixed names used by endpoints below.
from website.backend.routers.api_helpers import (  # noqa: E402
    normalize_monitoring_timestamp as _normalize_monitoring_timestamp,
    normalize_weapon_key as _normalize_weapon_key,
    clean_weapon_name as _clean_weapon_name,
    normalize_map_name as _normalize_map_name,
    calculate_player_achievements,
    resolve_player_guid,
    resolve_display_name,
    batch_resolve_display_names,
    resolve_alias_guid_map,
    resolve_name_guid_map,
)


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
async def get_diagnostics(db: DatabaseAdapter = Depends(get_db)):
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
        ("sessions", "SELECT COUNT(*) FROM sessions", False),
        ("players", "SELECT COUNT(*) FROM players", False),
        ("lua_spawn_stats", "SELECT COUNT(*) FROM lua_spawn_stats", False),
        ("server_status_history", "SELECT COUNT(*) FROM server_status_history", False),
        ("voice_status_history", "SELECT COUNT(*) FROM voice_status_history", False),
        ("discord_users", "SELECT COUNT(*) FROM discord_users", False),
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
async def get_lua_webhook_diagnostics(db: DatabaseAdapter = Depends(get_db)):
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
async def get_monitoring_status(db: DatabaseAdapter = Depends(get_db)):
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
async def get_live_status(db: DatabaseAdapter = Depends(get_db)):
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
        print(f"Error fetching voice channel status: {e}")
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
    hours: int = 72, db: DatabaseAdapter = Depends(get_db)
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
    hours: int = 720, db: DatabaseAdapter = Depends(get_db)
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
async def get_current_voice_activity(db: DatabaseAdapter = Depends(get_db)):
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
            print(f"Error fetching current voice activity: {e}")
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


@router.get("/stats/overview")
async def get_stats_overview(db: DatabaseAdapter = Depends(get_db)):
    """Get homepage overview statistics"""
    lookback_days = 14
    start_date_str = (
        (datetime.now() - timedelta(days=lookback_days))
        .date()
        .strftime("%Y-%m-%d")
    )

    async def safe_val(query: str, params: Optional[tuple] = None, default=0):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            logger.warning("[overview] query failed: %s", e)
            return default

    async def safe_one(query: str, params: Optional[tuple] = None):
        try:
            return await db.fetch_one(query, params)
        except Exception as e:
            logger.warning("[overview] query failed: %s", e)
            return None

    # Use only legal rounds (completed or pre-status rows) and only R1/R2
    round_filter = """
        WHERE round_number IN (1, 2)
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
    """
    round_filter_fallback = """
        WHERE round_number IN (1, 2)
    """

    rounds_table_exists = await safe_val(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'rounds'
        )
        """,
        default=False,
    )
    sessions_table_exists = await safe_val(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'sessions'
        )
        """,
        default=False,
    )

    if rounds_table_exists:
        # Round-based metrics (try with round_status first, fallback without)
        try:
            rounds_count = await db.fetch_val(
                f"SELECT COUNT(*) FROM rounds {round_filter}"
            )
            rounds_first = await db.fetch_val(
                f"SELECT MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter}"
            )
            rounds_latest = await db.fetch_val(
                f"SELECT MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter}"
            )
            rounds_recent = await db.fetch_val(
                f"""
                SELECT COUNT(*)
                FROM rounds
                {round_filter}
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
            sessions_count = await db.fetch_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter}
                  AND gaming_session_id IS NOT NULL
                """
            )
            sessions_recent = await db.fetch_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter}
                  AND gaming_session_id IS NOT NULL
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
        except Exception as e:
            logger.warning("round_status filter failed, retrying fallback: %s", e)
            rounds_count = await safe_val(
                f"SELECT COUNT(*) FROM rounds {round_filter_fallback}"
            )
            rounds_first = await safe_val(
                f"SELECT MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter_fallback}",
                default=None,
            )
            rounds_latest = await safe_val(
                f"SELECT MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter_fallback}",
                default=None,
            )
            rounds_recent = await safe_val(
                f"""
                SELECT COUNT(*)
                FROM rounds
                {round_filter_fallback}
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
            sessions_count = await safe_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter_fallback}
                  AND gaming_session_id IS NOT NULL
                """
            )
            sessions_recent = await safe_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter_fallback}
                  AND gaming_session_id IS NOT NULL
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
    if (rounds_count or 0) == 0 and sessions_table_exists:
        # If rounds table exists but is empty, fall back to sessions table
        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
            """
        )
        rounds_first = await safe_val(
            """
            SELECT MIN(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_latest = await safe_val(
            """
            SELECT MAX(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_recent = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
        try:
            sessions_count = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                """
            )
        except Exception:
            sessions_count = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                """
            )
        try:
            sessions_recent = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
        except Exception:
            sessions_recent = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
    elif not rounds_table_exists:
        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
            """
        )
        rounds_first = await safe_val(
            """
            SELECT MIN(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_latest = await safe_val(
            """
            SELECT MAX(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_recent = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
        try:
            sessions_count = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                """
            )
        except Exception:
            sessions_count = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                """
            )
        try:
            sessions_recent = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
        except Exception:
            sessions_recent = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )

    # Player + kill metrics from stats table
    players_all_time = await safe_val(
        """
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
        """
    )
    try:
        players_recent = await db.fetch_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    except Exception:
        players_recent = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    if players_recent == 0:
        players_recent = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    total_kills = await safe_val(
        """
        SELECT COALESCE(SUM(kills), 0)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
        """
    )
    try:
        total_kills_recent = await db.fetch_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    except Exception:
        total_kills_recent = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    if total_kills_recent == 0:
        total_kills_recent = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )

    # Most active players (by rounds played)
    active_overall = await safe_one(
        """
        SELECT player_guid,
               MAX(player_name) as player_name,
               COUNT(DISTINCT round_id) as rounds_played
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
        GROUP BY player_guid
        ORDER BY rounds_played DESC
        LIMIT 1
        """
    )
    if active_overall is None:
        active_overall = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """
        )

    try:
        active_recent = await db.fetch_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(DISTINCT round_id) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    except Exception:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(DISTINCT round_id) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    if active_recent is None:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    if active_recent is None:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    if active_recent is None:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )

    active_overall_payload = None
    if active_overall:
        active_overall_payload = {
            "name": await resolve_display_name(db, active_overall[0], active_overall[1] or "Unknown"),
            "rounds": active_overall[2],
        }
    active_recent_payload = None
    if active_recent:
        active_recent_payload = {
            "name": await resolve_display_name(db, active_recent[0], active_recent[1] or "Unknown"),
            "rounds": active_recent[2],
        }

    return {
        "rounds": rounds_count or 0,
        "players": players_recent or 0,
        "sessions": sessions_count or 0,
        "total_kills": total_kills or 0,
        "rounds_since": rounds_first,
        "rounds_latest": rounds_latest,
        "rounds_14d": rounds_recent or 0,
        "players_all_time": players_all_time or 0,
        "players_14d": players_recent or 0,
        "sessions_14d": sessions_recent or 0,
        "total_kills_14d": total_kills_recent or 0,
        "most_active_overall": active_overall_payload,
        "most_active_14d": active_recent_payload,
        "window_days": lookback_days,
    }


async def build_session_scoring(
    session_date: str,
    session_ids: Optional[list],
    data_service: SessionDataService,
    scoring_service: StopwatchScoringService,
):
    """
    Build scoring payload with debug info and warnings.
    """
    scoring_payload = {
        "available": False,
        "reason": "No hardcoded teams available",
    }
    warnings = []
    debug = []

    if not session_ids:
        return scoring_payload, warnings, None

    hardcoded_teams = await data_service.get_hardcoded_teams(session_ids)
    if not hardcoded_teams or len(hardcoded_teams) < 2:
        return scoring_payload, warnings, hardcoded_teams

    team_rosters = {}
    for team_name, players in hardcoded_teams.items():
        if isinstance(players, dict):
            guids = players.get("guids", [])
        else:
            guids = []
            for p in players:
                if isinstance(p, dict) and "guid" in p:
                    guids.append(p["guid"])
                elif isinstance(p, str):
                    guids.append(p)
        team_rosters[team_name] = guids

    if len(team_rosters) < 2:
        return scoring_payload, warnings, hardcoded_teams

    scoring_result = await scoring_service.calculate_session_scores_with_teams(
        session_date, session_ids, team_rosters
    )
    if not scoring_result:
        scoring_payload = {
            "available": False,
            "reason": "Scoring not available for this session",
        }
        return scoring_payload, warnings, hardcoded_teams

    maps = scoring_result.get("maps", []) or []
    fallback_maps = []
    incomplete_maps = []
    for m in maps:
        source = m.get("scoring_source")
        if source == "time":
            fallback_maps.append(m.get("map"))
        if source in ("incomplete", "ambiguous"):
            incomplete_maps.append(m.get("map"))
        debug.append(
            {
                "map": m.get("map"),
                "winner_side": m.get("winner_side"),
                "r1_defender_side": m.get("r1_defender_side"),
                "team_a_r1_side": m.get("team_a_r1_side"),
                "team_a_r2_side": m.get("team_a_r2_side"),
                "scoring_source": source,
                "counted": m.get("counted", True),
                "note": m.get("note"),
            }
        )

    if fallback_maps:
        warnings.append(
            "Lua header winner missing: used time fallback for "
            + ", ".join([m for m in fallback_maps if m])
        )
    if incomplete_maps:
        warnings.append(
            "Incomplete maps (R1 only / ambiguous): "
            + ", ".join([m for m in incomplete_maps if m])
        )

    scoring_payload = {
        "available": True,
        "team_a_name": scoring_result.get("team_a_name", "Team A"),
        "team_b_name": scoring_result.get("team_b_name", "Team B"),
        "team_a_score": scoring_result.get("team_a_maps", 0),
        "team_b_score": scoring_result.get("team_b_maps", 0),
        "maps": maps,
        "total_maps": scoring_result.get("total_maps", 0),
        "debug": debug,
    }

    return scoring_payload, warnings, hardcoded_teams


@router.get("/stats/activity-calendar")
async def get_activity_calendar(
    days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Return a simple activity calendar (rounds per day) for the last N days.
    """
    lookback_days = max(1, min(days, 365))
    start_date = (datetime.now() - timedelta(days=lookback_days)).date().strftime(
        "%Y-%m-%d"
    )

    query = """
        SELECT SUBSTR(CAST(round_date AS TEXT), 1, 10) as day, COUNT(*) as rounds
        FROM rounds
        WHERE round_number IN (1, 2)
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        GROUP BY SUBSTR(CAST(round_date AS TEXT), 1, 10)
        ORDER BY day
    """

    try:
        rows = await db.fetch_all(query, (start_date,))
    except Exception:
        rows = []

    if not rows:
        # Fallback for legacy SQLite schema (sessions table)
        fallback = """
            SELECT SUBSTR(CAST(session_date AS TEXT), 1, 10) as day, COUNT(*) as rounds
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY SUBSTR(CAST(session_date AS TEXT), 1, 10)
            ORDER BY day
        """
        try:
            rows = await db.fetch_all(fallback, (start_date,))
        except Exception:
            # If legacy table doesn't exist, return empty activity
            return {"days": lookback_days, "activity": {}}

    activity = {str(row[0]): int(row[1]) for row in rows}
    return {"days": lookback_days, "activity": activity}


@router.get("/seasons/current")
async def get_current_season():
    sm = SeasonManager()
    current_id = sm.get_current_season()
    start_date, end_date = sm.get_season_dates(current_id)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    year, quarter = current_id.split("-Q")
    quarter = int(quarter)
    next_quarter = quarter + 1
    next_year = int(year)
    if next_quarter > 4:
        next_quarter = 1
        next_year += 1
    next_id = f"{next_year}-Q{next_quarter}"
    next_start, _ = sm.get_season_dates(next_id)
    return {
        "id": current_id,
        "name": sm.get_season_name(current_id),
        "days_left": sm.get_days_until_season_end(),
        "start_date": start_str,
        "end_date": end_str,
        "next_season_id": next_id,
        "next_season_name": sm.get_season_name(next_id),
        "next_season_start": next_start.strftime("%Y-%m-%d"),
    }


@router.get("/seasons/current/summary")
async def get_current_season_summary(db: DatabaseAdapter = Depends(get_db)):
    """
    Summary stats for the current season (totals + activity).
    """
    sm = SeasonManager()
    current_id = sm.get_current_season()
    start_date, end_date = sm.get_season_dates(current_id)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    async def safe_val(query: str, params: Optional[tuple] = None, default=0):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            print(f"[season_summary] query failed: {e}")
            return default

    async def safe_one(query: str, params: Optional[tuple] = None):
        try:
            return await db.fetch_one(query, params)
        except Exception as e:
            print(f"[season_summary] query failed: {e}")
            return None

    round_status_clause = "AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)"

    try:
        rounds_count = await db.fetch_val(
            f"""
            SELECT COUNT(*)
            FROM rounds
            WHERE round_number IN (1, 2)
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        players_count = await db.fetch_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        sessions_count = await db.fetch_val(
            f"""
            SELECT COUNT(DISTINCT gaming_session_id)
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        maps_count = await db.fetch_val(
            f"""
            SELECT COUNT(DISTINCT map_name)
            FROM rounds
            WHERE map_name IS NOT NULL
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        kills_total = await db.fetch_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        active_days = await db.fetch_val(
            f"""
            SELECT COUNT(DISTINCT SUBSTR(CAST(round_date AS TEXT), 1, 10))
            FROM rounds
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
              {round_status_clause}
            """,
            (start_str, end_str),
        )
        top_map_row = await db.fetch_one(
            f"""
            SELECT map_name, COUNT(*) as plays
            FROM rounds
            WHERE map_name IS NOT NULL
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            GROUP BY map_name
            ORDER BY plays DESC
            LIMIT 1
            """,
            (start_str, end_str),
        )
    except Exception as e:
        print(f"[season_summary] round_status filter failed, retrying fallback: {e}")

        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM rounds
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
        )
        sessions_count = await safe_val(
            """
            SELECT COUNT(DISTINCT gaming_session_id)
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
        )
        maps_count = await safe_val(
            """
            SELECT COUNT(DISTINCT map_name)
            FROM rounds
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
        )
        active_days = await safe_val(
            """
            SELECT COUNT(DISTINCT SUBSTR(CAST(round_date AS TEXT), 1, 10))
            FROM rounds
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
        )
        top_map_row = await safe_one(
            """
            SELECT map_name, COUNT(*) as plays
            FROM rounds
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            GROUP BY map_name
            ORDER BY plays DESC
            LIMIT 1
            """,
            (start_str, end_str),
        )
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )

        if rounds_count is None and sessions_count is None:
            # Fallback for legacy SQLite schema (sessions table)
            rounds_count = await safe_val(
                """
                SELECT COUNT(*)
                FROM sessions
                WHERE round_number IN (1, 2)
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            players_count = await safe_val(
                """
                SELECT COUNT(DISTINCT player_guid)
                FROM player_comprehensive_stats
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            sessions_count = await safe_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            maps_count = await safe_val(
                """
                SELECT COUNT(DISTINCT map_name)
                FROM sessions
                WHERE map_name IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            kills_total = await safe_val(
                """
                SELECT COALESCE(SUM(kills), 0)
                FROM player_comprehensive_stats
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            active_days = await safe_val(
                """
                SELECT COUNT(DISTINCT SUBSTR(CAST(session_date AS TEXT), 1, 10))
                FROM sessions
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            top_map_row = await safe_one(
                """
                SELECT map_name, COUNT(*) as plays
                FROM sessions
                WHERE map_name IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                GROUP BY map_name
                ORDER BY plays DESC
                LIMIT 1
                """,
                (start_str, end_str),
            )

    # If rounds exist but player stats use session_date, retry with session_date
    if rounds_count and (players_count is None or players_count == 0):
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )

    if rounds_count and (kills_total is None or kills_total == 0):
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )

    # If rounds data is empty, try sessions table as a last resort
    if (rounds_count or 0) == 0 and (sessions_count or 0) == 0:
        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        sessions_count = await safe_val(
            """
            SELECT COUNT(DISTINCT session_id)
            FROM sessions
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        maps_count = await safe_val(
            """
            SELECT COUNT(DISTINCT map_name)
            FROM sessions
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        active_days = await safe_val(
            """
            SELECT COUNT(DISTINCT SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        top_map_row = await safe_one(
            """
            SELECT map_name, COUNT(*) as plays
            FROM sessions
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            GROUP BY map_name
            ORDER BY plays DESC
            LIMIT 1
            """,
            (start_str, end_str),
        )

    active_days = active_days or 0
    rounds_count = rounds_count or 0
    avg_rounds = round(rounds_count / active_days, 1) if active_days else 0
    top_map = top_map_row[0] if top_map_row else None
    top_map_plays = top_map_row[1] if top_map_row else 0

    return {
        "season_id": current_id,
        "start_date": start_str,
        "end_date": end_str,
        "totals": {
            "rounds": rounds_count,
            "players": players_count or 0,
            "sessions": sessions_count or 0,
            "maps": maps_count or 0,
            "kills": kills_total or 0,
            "active_days": active_days,
            "avg_rounds_per_day": avg_rounds,
        },
        "top_map": {"name": top_map, "plays": top_map_plays},
    }


@router.get("/stats/last-session")
async def get_last_session(db: DatabaseAdapter = Depends(get_db)):
    """Get the latest session data (similar to !last_session)"""
    config = load_config()
    db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
    service = SessionDataService(db, db_path)
    scoring_service = StopwatchScoringService(db)

    latest_date = await service.get_latest_session_date()
    if not latest_date:
        raise HTTPException(status_code=404, detail="No sessions found")

    sessions, session_ids, session_ids_str, player_count = await service.fetch_session_data(
        latest_date
    )
    stats_service = SessionStatsAggregator(db)

    gaming_session_id = None
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        gaming_row = await db.fetch_one(
            f"""
            SELECT DISTINCT gaming_session_id
            FROM rounds
            WHERE id IN ({placeholders})
            LIMIT 1
            """,
            tuple(session_ids),
        )
        if gaming_row:
            gaming_session_id = gaming_row[0]

    # Calculate map counts
    map_counts = {}
    for _, map_name, _, _ in sessions:
        map_counts[map_name] = map_counts.get(map_name, 0) + 1

    # Since each map usually has 2 rounds, divide by 2 for
    # "matches" count, or just list unique maps
    unique_maps = list(map_counts.keys())

    # Get detailed matches for this session
    matches = await service.get_session_matches_by_round_ids(session_ids)

    scoring_payload, scoring_warnings, hardcoded_teams = await build_session_scoring(
        latest_date, session_ids, service, scoring_service
    )

    # Build team rosters with aggregated player stats for UI grouping
    teams_payload = []
    unassigned_players = []
    stats_checks = []
    if session_ids and session_ids_str:
        raw_dead_map = {}
        try:
            placeholders = ",".join("?" * len(session_ids))
            raw_rows = await db.fetch_all(
                f"""
                SELECT player_guid,
                       SUM(COALESCE(time_dead_minutes, 0) * 60) as raw_dead_seconds
                FROM player_comprehensive_stats
                WHERE round_id IN ({placeholders})
                GROUP BY player_guid
                """,
                tuple(session_ids),
            )
            raw_dead_map = {
                row[0]: int(row[1] or 0) for row in raw_rows if row and row[0]
            }
        except Exception:
            raw_dead_map = {}

        try:
            player_rows = await stats_service.aggregate_all_player_stats(
                session_ids, session_ids_str
            )
        except Exception:
            player_rows = []

        guid_to_team = {}
        if hardcoded_teams:
            for team_name, team_data in hardcoded_teams.items():
                for guid in team_data.get("guids", []):
                    guid_to_team[guid] = team_name

        team_1_name = "Team A"
        team_2_name = "Team B"
        name_to_team = {}
        if hardcoded_teams and len(hardcoded_teams) >= 2:
            (
                team_1_name,
                team_2_name,
                _,
                _,
                name_to_team,
            ) = await service.build_team_mappings(
                session_ids, session_ids_str, hardcoded_teams
            )

        team_lookup = {
            team_1_name: [],
            team_2_name: [],
        }

        total_kills = 0
        total_deaths = 0

        for row in player_rows:
            (
                player_name,
                player_guid,
                kills,
                deaths,
                weighted_dpm,
                _total_hits,
                _total_shots,
                _total_headshots,
                headshot_kills,
                total_seconds,
                total_time_dead,
                total_denied,
                total_gibs,
                total_revives_given,
                total_times_revived,
                total_damage_received,
                total_damage_given,
                total_useful_kills,
                total_double_kills,
                total_triple_kills,
                total_quad_kills,
                total_multi_kills,
                total_mega_kills,
                total_self_kills,
                total_full_selfkills,
                *optional_tail,
            ) = row
            total_kill_assists = optional_tail[0] if optional_tail else 0

            total_kills += int(kills or 0)
            total_deaths += int(deaths or 0)

            kd = (kills / deaths) if deaths else float(kills or 0)
            team_name = name_to_team.get(player_name) or guid_to_team.get(player_guid)

            player_payload = {
                "name": player_name,
                "guid": player_guid,
                "kills": int(kills or 0),
                "deaths": int(deaths or 0),
                "kd": round(kd, 2),
                "dpm": int(weighted_dpm or 0),
                "headshot_kills": int(headshot_kills or 0),
                "time_played_seconds": int(total_seconds or 0),
                "time_dead_seconds": int(total_time_dead or 0),
                "time_dead_seconds_raw": int(raw_dead_map.get(player_guid, total_time_dead or 0)),
                "denied_playtime": int(total_denied or 0),
                "gibs": int(total_gibs or 0),
                "revives_given": int(total_revives_given or 0),
                "times_revived": int(total_times_revived or 0),
                "damage_given": int(total_damage_given or 0),
                "damage_received": int(total_damage_received or 0),
                "useful_kills": int(total_useful_kills or 0),
                "double_kills": int(total_double_kills or 0),
                "triple_kills": int(total_triple_kills or 0),
                "quad_kills": int(total_quad_kills or 0),
                "multi_kills": int(total_multi_kills or 0),
                "mega_kills": int(total_mega_kills or 0),
                "self_kills": int(total_self_kills or 0),
                "full_selfkills": int(total_full_selfkills or 0),
                "kill_assists": int(total_kill_assists or 0),
            }

            if team_name and team_name in team_lookup:
                team_lookup[team_name].append(player_payload)
            else:
                unassigned_players.append(player_payload)

        for team_name, players in team_lookup.items():
            players_sorted = sorted(players, key=lambda p: (-p["kills"], -p["dpm"]))
            teams_payload.append({"name": team_name, "players": players_sorted})

        if total_kills != total_deaths:
            stats_checks.append(
                f"Kill/death mismatch: {total_kills} kills vs {total_deaths} deaths"
            )
        if unassigned_players:
            stats_checks.append(
                f"Unassigned players: {', '.join(p['name'] for p in unassigned_players)}"
            )

    return {
        "date": latest_date,
        "player_count": player_count,
        "rounds": len(sessions),
        "maps": unique_maps,
        "map_counts": map_counts,
        "matches": matches,
        "scoring": scoring_payload,
        "warnings": scoring_warnings,
        "teams": teams_payload,
        "unassigned_players": unassigned_players,
        "stats_checks": stats_checks,
        "gaming_session_id": gaming_session_id,
    }


@router.get("/stats/session-leaderboard")
async def get_session_leaderboard(
    limit: int = 5,
    session_id: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get the leaderboard for a specific session (or latest if not specified)"""
    data_service = SessionDataService(db, None)
    stats_service = SessionStatsAggregator(db)

    if session_id is not None:
        # Fetch rounds for the specified gaming_session_id
        rounds = await db.fetch_all(
            """
            SELECT id FROM rounds
            WHERE gaming_session_id = $1
              AND round_number IN (1, 2)
              AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
            """,
            (session_id,),
        )
        if not rounds:
            return []
        session_ids = [r[0] for r in rounds]
        session_ids_str = ", ".join("?" * len(session_ids))
    else:
        latest_date = await data_service.get_latest_session_date()
        if not latest_date:
            return []
        sessions, session_ids, session_ids_str, _ = await data_service.fetch_session_data(
            latest_date
        )
        if not session_ids:
            return []

    leaderboard = await stats_service.get_dpm_leaderboard(
        session_ids, session_ids_str, limit
    )

    # Format for frontend
    result = []
    for i, (name, dpm, kills, deaths) in enumerate(leaderboard, 1):
        result.append(
            {"rank": i, "name": name, "dpm": int(dpm), "kills": kills, "deaths": deaths}
        )

    return result


@router.get("/stats/session-score/{date}")
async def get_session_score(date: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get stopwatch scoring payload for a specific session date.
    """
    config = load_config()
    db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
    service = SessionDataService(db, db_path)
    scoring_service = StopwatchScoringService(db)

    sessions, session_ids, session_ids_str, player_count = await service.fetch_session_data_by_date(
        date
    )
    if not session_ids:
        raise HTTPException(status_code=404, detail="Session not found")

    scoring_payload, warnings, hardcoded_teams = await build_session_scoring(
        date, session_ids, service, scoring_service
    )

    teams_payload = []
    if hardcoded_teams and len(hardcoded_teams) >= 2:
        for team_name, team_data in hardcoded_teams.items():
            teams_payload.append(
                {
                    "name": team_name,
                    "guids": team_data.get("guids", []),
                    "names": team_data.get("names", []),
                }
            )
    elif session_ids and session_ids_str:
        try:
            (
                team_1_name,
                team_2_name,
                team_1_players,
                team_2_players,
                _,
            ) = await service.build_team_mappings(session_ids, session_ids_str, None)
            teams_payload = [
                {"name": team_1_name, "names": team_1_players, "guids": []},
                {"name": team_2_name, "names": team_2_players, "guids": []},
            ]
        except Exception:
            teams_payload = []

    return {
        "date": date,
        "player_count": player_count,
        "rounds": len(sessions or []),
        "scoring": scoring_payload,
        "warnings": warnings,
        "teams": teams_payload,
    }


@router.get("/stats/matches")
async def get_matches(limit: int = 5, db: DatabaseAdapter = Depends(get_db)):
    """Get recent matches"""
    data_service = SessionDataService(db, None)
    return await data_service.get_recent_matches(limit)


@router.get("/sessions")
async def get_sessions_list(
    limit: int = 20, offset: int = 0, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get list of all gaming sessions (like !sessions command).
    Returns sessions grouped by gaming_session_id to handle midnight-spanning sessions.
    """
    query = """
        WITH session_rounds AS (
            SELECT
                r.gaming_session_id,
                MIN(SUBSTR(CAST(r.round_date AS TEXT), 1, 10)) as session_date,
                COUNT(r.id) as round_count,
                COUNT(DISTINCT r.map_name) as map_count,
                STRING_AGG(DISTINCT r.map_name, ', ' ORDER BY r.map_name) as maps_played,
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 1 THEN 1 END) as allies_wins,
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 2 THEN 1 END) as axis_wins,
                COUNT(CASE WHEN r.round_number = 1 AND (r.winner_team NOT IN (1, 2) OR r.winner_team IS NULL) THEN 1 END) as draws
            FROM rounds r
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_players AS (
            SELECT
                r.gaming_session_id,
                COUNT(DISTINCT p.player_guid) as player_count,
                COALESCE(SUM(p.kills), 0) as total_kills
            FROM rounds r
            INNER JOIN player_comprehensive_stats p
                ON p.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        )
        SELECT
            sr.session_date,
            sr.gaming_session_id,
            sr.round_count,
            sr.map_count,
            COALESCE(sp.player_count, 0) as player_count,
            COALESCE(sp.total_kills, 0) as total_kills,
            sr.maps_played,
            sr.allies_wins,
            sr.axis_wins,
            sr.draws
        FROM session_rounds sr
        LEFT JOIN session_players sp ON sr.gaming_session_id = sp.gaming_session_id
        ORDER BY sr.session_date DESC
        LIMIT $1 OFFSET $2
    """

    try:
        rows = await db.fetch_all(query, (limit, offset))
    except Exception as e:
        print(f"Error fetching sessions list: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    sessions = []
    for row in rows:
        round_date = row[0]
        # Format time_ago
        if isinstance(round_date, str):
            round_date = round_date[:10]
            dt = datetime.strptime(round_date, "%Y-%m-%d")
        else:
            dt = datetime.combine(round_date, datetime.min.time())

        now = datetime.now()
        diff = now - dt
        days = diff.days

        if days == 0:
            time_ago = "Today"
        elif days == 1:
            time_ago = "Yesterday"
        elif days < 7:
            time_ago = f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            time_ago = f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            time_ago = dt.strftime("%b %d, %Y")

        sessions.append(
            {
                "date": str(round_date),
                "session_id": row[1],
                "rounds": row[2],
                "maps": row[3],
                "players": row[4],
                "total_kills": row[5],
                "maps_played": row[6].split(", ") if row[6] else [],
                "allies_wins": row[7],
                "axis_wins": row[8],
                "draws": row[9],
                "time_ago": time_ago,
                "formatted_date": dt.strftime("%A, %B %d, %Y"),
            }
        )

    return sessions


@router.get("/sessions/{date}")
async def get_session_details(date: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get detailed info for a specific session by date.
    Returns matches/rounds within the session and top players.
    """
    data_service = SessionDataService(db, None)
    stats_service = SessionStatsAggregator(db)

    # Get session data (supports multiple sessions on the same date)
    sessions, session_ids, session_ids_str, player_count = (
        await data_service.fetch_session_data_by_date(date)
    )

    if not sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get matches for this session
    matches = await data_service.get_session_matches_by_round_ids(session_ids)

    # Get leaderboard (top players by DPM)
    leaderboard = []
    if session_ids:
        try:
            lb_data = await stats_service.get_dpm_leaderboard(
                session_ids, session_ids_str, 10
            )
            for i, (name, dpm, kills, deaths) in enumerate(lb_data, 1):
                kd = kills / deaths if deaths > 0 else kills
                leaderboard.append(
                    {
                        "rank": i,
                        "name": name,
                        "dpm": int(dpm),
                        "kills": kills,
                        "deaths": deaths,
                        "kd": round(kd, 2),
                    }
                )
        except Exception as e:
            print(f"Error fetching session leaderboard: {e}")

    # Scoring + team rosters
    scoring_service = StopwatchScoringService(db)
    scoring_payload, warnings, hardcoded_teams = await build_session_scoring(
        date, session_ids, data_service, scoring_service
    )

    teams_payload = []
    if hardcoded_teams and len(hardcoded_teams) >= 2:
        for team_name, team_data in hardcoded_teams.items():
            teams_payload.append(
                {
                    "name": team_name,
                    "guids": team_data.get("guids", []),
                    "names": team_data.get("names", []),
                }
            )
    elif session_ids and session_ids_str:
        try:
            (
                team_1_name,
                team_2_name,
                team_1_players,
                team_2_players,
                _,
            ) = await data_service.build_team_mappings(
                session_ids, session_ids_str, None
            )
            teams_payload = [
                {"name": team_1_name, "names": team_1_players, "guids": []},
                {"name": team_2_name, "names": team_2_players, "guids": []},
            ]
        except Exception:
            teams_payload = []

    # Calculate map summary
    map_counts = {}
    for _, map_name, _, _ in sessions:
        map_counts[map_name] = map_counts.get(map_name, 0) + 1

    # Group matches by map (R1 + R2 = 1 map match)
    map_matches = {}
    for match in matches:
        map_name = match["map_name"]
        if map_name not in map_matches:
            map_matches[map_name] = {"rounds": [], "map_name": map_name}
        map_matches[map_name]["rounds"].append(match)

    return {
        "date": date,
        "player_count": player_count,
        "total_rounds": len(sessions),
        "maps_played": list(map_counts.keys()),
        "map_counts": map_counts,
        "matches": list(map_matches.values()),
        "leaderboard": leaderboard,
        "scoring": scoring_payload,
        "warnings": warnings,
        "teams": teams_payload,
    }


class LinkPlayerRequest(BaseModel):
    player_name: str


def _require_ajax_csrf_header(request: Request) -> None:
    if request.headers.get("x-requested-with", "").lower() != "xmlhttprequest":
        raise HTTPException(status_code=403, detail="Missing required CSRF header")


@router.get("/player/search")
async def search_player(query: str, db: DatabaseAdapter = Depends(get_db)):
    """Search for player aliases"""
    if len(query) < 2:
        return []

    # Escape LIKE wildcards (%, _) in user input to prevent SQL injection
    safe_query = escape_like_pattern(query)

    # Case-insensitive search (ILIKE is Postgres specific)
    sql = """
        SELECT player_guid, MAX(player_name) as player_name
        FROM player_comprehensive_stats
        WHERE player_name ILIKE ?
        GROUP BY player_guid
        ORDER BY MAX(player_name)
        LIMIT 10
    """
    rows = await db.fetch_all(sql, (f"%{safe_query}%",))
    name_map = await batch_resolve_display_names(
        db, [(guid, player_name or "Unknown") for guid, player_name in rows]
    )
    return [name_map.get(guid, player_name or "Unknown") for guid, player_name in rows]


@router.post("/player/link")
async def link_player(
    request: Request, payload: LinkPlayerRequest, db: DatabaseAdapter = Depends(get_db)
):
    """Link Discord account to player alias"""
    _require_ajax_csrf_header(request)
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    discord_id = int(user["id"])

    # Check if already linked
    existing = await db.fetch_one(
        "SELECT player_name FROM player_links WHERE discord_id = ?", (discord_id,)
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Already linked to {existing[0]}")

    # Verify player exists in stats
    stats = await db.fetch_one(
        "SELECT 1 FROM player_comprehensive_stats WHERE player_name = ? LIMIT 1",
        (payload.player_name,),
    )
    if not stats:
        raise HTTPException(status_code=404, detail="Player alias not found in stats")

    # Insert link
    await db.execute(
        "INSERT INTO player_links (discord_id, player_name, linked_at) VALUES (?, ?, NOW())",
        (discord_id, payload.player_name),
    )

    # Update session
    user["linked_player"] = payload.player_name
    request.session["user"] = user

    return {"status": "success", "linked_player": payload.player_name}


@router.get("/stats/live-session")
async def get_live_session(db: DatabaseAdapter = Depends(get_db)):
    """
    Get current live session status.
    """
    # Check if session is active (last activity within 30 minutes)
    # Postgres specific query
    query = """
        SELECT
            MAX(round_date) as last_round,
            COUNT(DISTINCT round_date) as rounds,
            COUNT(DISTINCT player_guid) as players
        FROM player_comprehensive_stats
        WHERE round_date::timestamp >= CURRENT_DATE
            AND round_date::timestamp >= NOW() - INTERVAL '30 minutes'
    """
    try:
        result = await db.fetch_one(query)
    except Exception as e:
        logger.error("Database error in get_live_session: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

    if not result or not result[0]:
        return {"active": False}

    # Get latest round details (actual_duration_seconds lives on rounds table)
    latest_query = """
        SELECT DISTINCT ON (p.round_date)
            p.map_name,
            p.round_date,
            r.actual_duration_seconds
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.round_date::timestamp >= CURRENT_DATE
        ORDER BY p.round_date DESC
        LIMIT 1
    """
    try:
        latest = await db.fetch_one(latest_query)
    except Exception as e:
        logger.error("Failed to fetch latest round details: %s", e)
        latest = None

    def format_stopwatch_time(seconds: int) -> str:
        if not seconds:
            return "0:00"
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    return {
        "active": True,
        "rounds_completed": result[1],
        "current_players": result[2],
        "current_map": latest[0] if latest else "Unknown",
        "last_round_time": format_stopwatch_time(latest[2]) if latest else None,
        "last_update": str(result[0]),
    }


@router.get("/stats/player/{player_name}")
async def get_player_stats(player_name: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get aggregated statistics for a specific player.
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name
    display_name = (
        await resolve_display_name(db, player_guid, player_name) if use_guid else player_name
    )

    # Postgres query
    # We join with rounds to get win/loss data
    # We assume round_id exists in player_comprehensive_stats as per bot code
    query = """
        SELECT
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_seconds) as total_time,
            COUNT(p.round_id) as total_games,
            SUM(p.xp) as total_xp,
            SUM(CASE WHEN p.team = r.winner_team THEN 1 ELSE 0 END) as total_wins,
            MAX(p.round_date) as last_seen
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1
          AND p.round_number IN (1, 2)
    """
    if not use_guid:
        query = query.replace("p.player_guid = $1", "p.player_name ILIKE $1")

    try:
        row = await db.fetch_one(query, (identifier,))
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not row or not row[0]:  # No kills usually means no stats found
        raise HTTPException(status_code=404, detail="Player not found")

    (kills, deaths, damage, time, games, xp, wins, last_seen) = row

    # Handle None values
    kills = kills or 0
    deaths = deaths or 0
    damage = damage or 0
    time = time or 0
    games = games or 0
    xp = xp or 0
    wins = wins or 0

    kd = kills / deaths if deaths > 0 else kills
    dpm = (damage / (time / 60)) if time > 0 else 0
    win_rate = (wins / games * 100) if games > 0 else 0

    # Calculate achievements based on stats
    achievements = calculate_player_achievements(int(kills), int(games), kd)

    # Get favorite weapon (most kills) from weapon_comprehensive_stats
    weapon_query = """
        SELECT weapon_name, SUM(kills) as total_kills
        FROM weapon_comprehensive_stats
        WHERE player_guid = $1
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT 1
    """
    if not use_guid:
        weapon_query = weapon_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        weapon_row = await db.fetch_one(weapon_query, (identifier,))
        if weapon_row and weapon_row[0]:
            clean_name = weapon_row[0]
            if clean_name.lower().startswith("ws ") or clean_name.lower().startswith(
                "ws_"
            ):
                clean_name = clean_name[3:]
            favorite_weapon = clean_name.replace("_", " ").title()
        else:
            favorite_weapon = None
    except Exception as e:
        print(f"Error fetching favorite weapon for {player_name}: {e}")
        favorite_weapon = None

    # Get favorite map (most played)
    map_query = """
        SELECT map_name, COUNT(*) as play_count
        FROM player_comprehensive_stats
        WHERE player_guid = $1
        GROUP BY map_name
        ORDER BY play_count DESC
        LIMIT 1
    """
    if not use_guid:
        map_query = map_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        map_row = await db.fetch_one(map_query, (identifier,))
        favorite_map = map_row[0] if map_row else None
    except Exception as e:
        print(f"Error fetching favorite map for {player_name}: {e}")
        favorite_map = None

    # Get highest and lowest DPM (single round)
    dpm_query = """
        SELECT
            MAX(CASE WHEN time_played_seconds > 60 THEN damage_given * 60.0 / time_played_seconds END) as max_dpm,
            MIN(CASE WHEN time_played_seconds > 60 THEN damage_given * 60.0 / time_played_seconds END) as min_dpm
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND time_played_seconds > 60
    """
    if not use_guid:
        dpm_query = dpm_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        dpm_row = await db.fetch_one(dpm_query, (identifier,))
        highest_dpm = int(dpm_row[0]) if dpm_row and dpm_row[0] else None
        lowest_dpm = int(dpm_row[1]) if dpm_row and dpm_row[1] else None
    except Exception as e:
        print(f"Error fetching DPM records for {player_name}: {e}")
        highest_dpm = None
        lowest_dpm = None

    # Get player aliases (other names used by same GUID)
    alias_query = """
        SELECT DISTINCT player_name
        FROM player_comprehensive_stats
        WHERE player_guid = $1
        AND player_name NOT ILIKE $2
        ORDER BY player_name
        LIMIT 5
    """
    try:
        if use_guid:
            alias_rows = await db.fetch_all(alias_query, (player_guid, display_name))
        else:
            alias_rows = []
        aliases = [row[0] for row in alias_rows] if alias_rows else []
    except Exception as e:
        print(f"Error fetching aliases for {player_name}: {e}")
        aliases = []

    # Check Discord link status
    discord_query = """
        SELECT discord_id FROM player_links WHERE player_guid = $1 LIMIT 1
    """
    if not use_guid:
        discord_query = discord_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        discord_row = await db.fetch_one(discord_query, (identifier,))
        discord_linked = discord_row is not None
    except Exception as e:
        print(f"Error checking Discord link for {player_name}: {e}")
        discord_linked = False

    return {
        "name": display_name,
        "guid": player_guid,
        "stats": {
            "kills": int(kills),
            "deaths": int(deaths),
            "damage": int(damage),
            "games": int(games),
            "wins": int(wins),
            "losses": int(games - wins),
            "win_rate": round(win_rate, 1),
            "kd": round(kd, 2),
            "dpm": int(dpm),
            "total_xp": int(xp),
            "playtime_hours": round(time / 3600, 1),
            "last_seen": last_seen,
            "favorite_weapon": favorite_weapon,
            "favorite_map": favorite_map,
            "highest_dpm": highest_dpm,
            "lowest_dpm": lowest_dpm,
        },
        "aliases": aliases,
        "discord_linked": discord_linked,
        "achievements": achievements,
    }


@router.get("/stats/compare")
async def compare_players(
    player1: str, player2: str, db: DatabaseAdapter = Depends(get_db)
):
    """
    Compare two players side-by-side with radar chart data.
    Returns normalized stats (0-100 scale) for fair comparison.
    """
    guid1 = await resolve_player_guid(db, player1)
    guid2 = await resolve_player_guid(db, player2)

    if guid1 and guid2 and guid1 == guid2:
        raise HTTPException(status_code=400, detail="Both identifiers resolve to the same player")

    params = []
    clauses = []
    if guid1:
        clauses.append(f"player_guid = ${len(params) + 1}")
        params.append(guid1)
    else:
        clauses.append(f"player_name ILIKE ${len(params) + 1}")
        params.append(player1)

    if guid2:
        clauses.append(f"player_guid = ${len(params) + 1}")
        params.append(guid2)
    else:
        clauses.append(f"player_name ILIKE ${len(params) + 1}")
        params.append(player2)

    where_clause = " OR ".join(clauses)

    query = f"""
        SELECT
            player_guid,
            MAX(player_name) as player_name,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage_given) as total_damage,
            SUM(time_played_seconds) as total_time,
            COUNT(*) as total_games,
            SUM(revives_given) as total_revives,
            SUM(headshots) as total_headshots,
            AVG(accuracy) as avg_accuracy,
            SUM(gibs) as total_gibs,
            SUM(xp) as total_xp
        FROM player_comprehensive_stats
        WHERE ({where_clause})
          AND round_number IN (1, 2)
        GROUP BY player_guid
    """

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        print(f"Error comparing players: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if len(rows) < 2:
        raise HTTPException(status_code=404, detail="One or both players not found")

    # Process both players
    players = []
    row_map = {row[0]: row for row in rows}
    ordered_guids = []
    if guid1:
        ordered_guids.append(guid1)
    if guid2 and guid2 not in ordered_guids:
        ordered_guids.append(guid2)

    if ordered_guids:
        ordered_rows = [row_map.get(g) for g in ordered_guids if row_map.get(g)]
        ordered_rows += [r for r in rows if r not in ordered_rows]
    else:
        ordered_rows = rows

    for row in ordered_rows:
        guid = row[0]
        name = (
            await resolve_display_name(db, guid, row[1] or "Unknown")
            if guid
            else (row[1] or "Unknown")
        )
        kills = row[2] or 0
        deaths = row[3] or 0
        damage = row[4] or 0
        time_played = row[5] or 0
        games = row[6] or 0
        revives = row[7] or 0
        headshots = row[8] or 0
        accuracy = row[9] or 0
        gibs = row[10] or 0
        xp = row[11] or 0

        time_minutes = time_played / 60 if time_played > 0 else 1
        kd = kills / deaths if deaths > 0 else kills
        dpm = damage / time_minutes

        players.append(
            {
                "name": name,
                "guid": guid,
                "raw": {
                    "kills": int(kills),
                    "deaths": int(deaths),
                    "damage": int(damage),
                    "games": int(games),
                    "kd": round(kd, 2),
                    "dpm": round(dpm, 1),
                    "revives": int(revives),
                    "headshots": int(headshots),
                    "accuracy": round(accuracy, 1),
                    "gibs": int(gibs),
                    "xp": int(xp),
                },
            }
        )

    # Calculate normalized stats for radar chart (0-100 scale)
    # Compare each stat relative to the max between the two players
    radar_labels = ["K/D", "DPM", "Accuracy", "Revives", "Headshots", "Gibs"]
    p1, p2 = players[0], players[1]

    def normalize(val1, val2):
        """Normalize two values to 0-100 scale based on max."""
        max_val = max(val1, val2)
        if max_val == 0:
            return 50, 50
        return round(val1 / max_val * 100, 1), round(val2 / max_val * 100, 1)

    p1_kd, p2_kd = normalize(p1["raw"]["kd"], p2["raw"]["kd"])
    p1_dpm, p2_dpm = normalize(p1["raw"]["dpm"], p2["raw"]["dpm"])
    p1_acc, p2_acc = normalize(p1["raw"]["accuracy"], p2["raw"]["accuracy"])
    p1_rev, p2_rev = normalize(p1["raw"]["revives"], p2["raw"]["revives"])
    p1_hs, p2_hs = normalize(p1["raw"]["headshots"], p2["raw"]["headshots"])
    p1_gibs, p2_gibs = normalize(p1["raw"]["gibs"], p2["raw"]["gibs"])

    return {
        "player1": {**p1, "radar": [p1_kd, p1_dpm, p1_acc, p1_rev, p1_hs, p1_gibs]},
        "player2": {**p2, "radar": [p2_kd, p2_dpm, p2_acc, p2_rev, p2_hs, p2_gibs]},
        "radar_labels": radar_labels,
    }


@router.get("/stats/leaderboard")
async def get_leaderboard(
    stat: str = "dpm",
    period: str = "30d",
    min_games: int = 3,
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    # Calculate start date
    if period == "7d":
        start_date_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "30d":
        start_date_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == "season":
        sm = SeasonManager()
        start_date_str = sm.get_season_dates()[0].strftime("%Y-%m-%d")
    else:
        start_date_str = datetime(2020, 1, 1).strftime("%Y-%m-%d")

    # Base query parts
    # nosec B608 - These clauses are static strings, not user-controlled input
    where_clause = "WHERE round_number IN (1, 2) AND time_played_seconds > 0 AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)"
    name_select = "MAX(player_name) as player_name"
    guid_select = "player_guid"
    group_by = "GROUP BY player_guid"
    # Removed session count filter - table doesn't track sessions, only rounds/dates
    having = ""  # No HAVING clause needed for basic leaderboard

    if stat == "dpm":
        # nosec B608 - where_clause, group_by, having are static strings
        query = f"""
            WITH player_stats AS (
                SELECT
                    {guid_select} as player_guid,
                    {name_select},
                    COUNT(*) as rounds_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    SUM(time_played_seconds) as total_time,
                    ROUND((SUM(damage_given)::numeric / NULLIF(SUM(time_played_seconds), 0) * 60), 2) as value,
                    CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
                FROM player_comprehensive_stats
                {where_clause}
                {group_by}
                {having}
            )
            SELECT
                player_guid,
                player_name,
                value,
                rounds_played,
                total_kills,
                total_deaths,
                kd_ratio
            FROM player_stats
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "kills":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(kills) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "kd":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 0)), 2) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "headshots":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(headshots) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "revives":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(revives_given) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "accuracy":
        # Accuracy requires minimum bullets fired to be meaningful
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                ROUND(AVG(accuracy)::numeric, 1) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause} AND bullets_fired > 100
            {group_by}
            HAVING COUNT(*) >= 3
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "gibs":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(gibs) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "games":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                COUNT(*) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "damage":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(damage_given) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    else:
        return []

    try:
        rows = await db.fetch_all(query, (start_date_str, limit))
    except Exception as e:

        logger.error("Leaderboard query error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")

    name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in rows]
    )
    leaderboard = []
    for i, row in enumerate(rows):
        leaderboard.append(
            {
                "rank": i + 1,
                "guid": row[0],
                "name": name_map.get(row[0], row[1] or "Unknown"),
                "value": float(row[2]) if row[2] is not None else 0,
                "rounds": row[3],  # Changed from sessions to rounds
                "kills": row[4],
                "deaths": row[5],
                "kd": float(row[6]) if row[6] is not None else 0,
            }
        )
    return leaderboard

@router.get("/stats/quick-leaders")
async def get_quick_leaders(
    limit: int = 5,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Quick leaders for homepage:
    - Top XP in last 7 days
    - Top DPM per session in last 7 days
    """
    start_date = (datetime.now() - timedelta(days=7)).date()

    xp_query = """
        SELECT
            p.player_guid,
            MAX(p.player_name) as player_name,
            SUM(p.xp) as total_xp,
            COUNT(DISTINCT p.round_id) as rounds_played
        FROM player_comprehensive_stats p
        WHERE p.round_number IN (1, 2)
          AND p.time_played_seconds > 0
          AND CAST(SUBSTR(CAST(p.round_date AS TEXT), 1, 10) AS DATE) >= $1
        GROUP BY p.player_guid
        ORDER BY total_xp DESC
        LIMIT $2
    """
    errors = []
    xp_rows = []
    try:
        xp_rows = await db.fetch_all(xp_query, (start_date, limit))
    except Exception:
        xp_rows = []

    if not xp_rows:
        # Fallback for schemas using session_date
        fallback_xp = """
            SELECT
                p.player_guid,
                MAX(p.player_name) as player_name,
                SUM(p.xp) as total_xp,
                COUNT(*) as rounds_played
            FROM player_comprehensive_stats p
            WHERE p.round_number IN (1, 2)
              AND p.time_played_seconds > 0
              AND CAST(SUBSTR(CAST(p.session_date AS TEXT), 1, 10) AS DATE) >= $1
            GROUP BY p.player_guid
            ORDER BY total_xp DESC
            LIMIT $2
        """
        try:
            xp_rows = await db.fetch_all(fallback_xp, (start_date, limit))
        except Exception as e:
            errors.append(f"xp_query_failed: {e}")
            xp_rows = []
    xp_name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in xp_rows]
    )
    xp_leaders = []
    for i, row in enumerate(xp_rows):
        xp_leaders.append(
            {
                "rank": i + 1,
                "guid": row[0],
                "name": xp_name_map.get(row[0], row[1] or "Unknown"),
                "value": row[2] or 0,
                "rounds": row[3] or 0,
                "label": "XP",
            }
        )

    dpm_query = """
        WITH session_player AS (
            SELECT
                r.gaming_session_id,
                p.player_guid,
                MAX(p.player_name) as player_name,
                SUM(p.damage_given) as total_damage,
                SUM(p.time_played_seconds) as total_time
            FROM player_comprehensive_stats p
            INNER JOIN rounds r ON r.id = p.round_id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
              AND p.time_played_seconds > 0
              AND CAST(SUBSTR(CAST(r.round_date AS TEXT), 1, 10) AS DATE) >= $1
            GROUP BY r.gaming_session_id, p.player_guid
        ),
        session_dpm AS (
            SELECT
                player_guid,
                MAX(player_name) as player_name,
                AVG(CASE WHEN total_time > 0 THEN (total_damage::numeric / total_time * 60) ELSE 0 END) as value,
                COUNT(*) as sessions_played
            FROM session_player
            GROUP BY player_guid
        )
        SELECT player_guid, player_name, value, sessions_played
        FROM session_dpm
        ORDER BY value DESC
        LIMIT $2
    """
    dpm_rows = []
    try:
        dpm_rows = await db.fetch_all(dpm_query, (start_date, limit))
    except Exception:
        dpm_rows = []

    if not dpm_rows:
        fallback_dpm = """
            WITH session_player AS (
                SELECT
                    r.gaming_session_id,
                    p.player_guid,
                    MAX(p.player_name) as player_name,
                    SUM(p.damage_given) as total_damage,
                    SUM(p.time_played_seconds) as total_time
                FROM player_comprehensive_stats p
                INNER JOIN rounds r
                    ON r.round_date = p.round_date
                    AND r.map_name = p.map_name
                    AND r.round_number = p.round_number
                WHERE r.gaming_session_id IS NOT NULL
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                  AND p.time_played_seconds > 0
                  AND CAST(SUBSTR(CAST(r.round_date AS TEXT), 1, 10) AS DATE) >= $1
                GROUP BY r.gaming_session_id, p.player_guid
            ),
            session_dpm AS (
                SELECT
                    player_guid,
                    MAX(player_name) as player_name,
                    AVG(CASE WHEN total_time > 0 THEN (total_damage::numeric / total_time * 60) ELSE 0 END) as value,
                    COUNT(*) as sessions_played
                FROM session_player
                GROUP BY player_guid
            )
            SELECT player_guid, player_name, value, sessions_played
            FROM session_dpm
            ORDER BY value DESC
            LIMIT $2
        """
        try:
            dpm_rows = await db.fetch_all(fallback_dpm, (start_date, limit))
        except Exception:
            fallback_session_dpm = """
                WITH session_player AS (
                    SELECT
                        p.session_id,
                        p.player_guid,
                        MAX(p.player_name) as player_name,
                        SUM(p.damage_given) as total_damage,
                        SUM(p.time_played_seconds) as total_time
                    FROM player_comprehensive_stats p
                    WHERE p.session_id IS NOT NULL
                      AND p.round_number IN (1, 2)
                      AND p.time_played_seconds > 0
                      AND CAST(SUBSTR(CAST(p.session_date AS TEXT), 1, 10) AS DATE) >= $1
                    GROUP BY p.session_id, p.player_guid
                ),
                session_dpm AS (
                    SELECT
                        player_guid,
                        MAX(player_name) as player_name,
                        AVG(CASE WHEN total_time > 0 THEN (total_damage::numeric / total_time * 60) ELSE 0 END) as value,
                        COUNT(*) as sessions_played
                    FROM session_player
                    GROUP BY player_guid
                )
                SELECT player_guid, player_name, value, sessions_played
                FROM session_dpm
                ORDER BY value DESC
                LIMIT $2
            """
            try:
                dpm_rows = await db.fetch_all(
                    fallback_session_dpm, (start_date, limit)
                )
            except Exception as e:
                errors.append(f"dpm_query_failed: {e}")
                dpm_rows = []
    dpm_leaders = []
    for i, row in enumerate(dpm_rows):
        display_name = await resolve_display_name(db, row[0], row[1] or "Unknown")
        dpm_leaders.append(
            {
                "rank": i + 1,
                "guid": row[0],
                "name": display_name,
                "value": float(row[2] or 0),
                "sessions": row[3] or 0,
                "label": "DPM/session",
            }
        )

    return {
        "window_days": 7,
        "xp": xp_leaders,
        "dpm_sessions": dpm_leaders,
        "errors": errors,
    }


@router.get("/stats/maps")
async def get_maps(db: DatabaseAdapter = Depends(get_db)):
    """
    Get comprehensive statistics for all maps.
    Returns times played, win rates, kill stats, etc.
    Note: In stopwatch mode, 2 rounds = 1 match.
    """
    query = """
        WITH map_stats AS (
            SELECT
                r.map_name,
                COUNT(*) as total_rounds,
                COUNT(*) / 2 as matches_played,
                SUM(CASE WHEN r.winner_team = 1 THEN 1 ELSE 0 END) as allies_wins,
                SUM(CASE WHEN r.winner_team = 2 THEN 1 ELSE 0 END) as axis_wins,
                MAX(SUBSTR(CAST(r.round_date AS TEXT), 1, 10)) as last_played,
                -- Parse M:SS format to seconds, then avg/min/max
                AVG(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as avg_duration,
                MIN(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as min_duration,
                MAX(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as max_duration
            FROM rounds r
            WHERE r.map_name IS NOT NULL
              AND r.round_number IN (1, 2)
            GROUP BY r.map_name
        ),
        player_stats AS (
            SELECT
                p.map_name,
                SUM(p.kills) as total_kills,
                SUM(p.deaths) as total_deaths,
                AVG(p.dpm) as avg_dpm,
                COUNT(DISTINCT p.player_guid) as unique_players
            FROM player_comprehensive_stats p
            WHERE p.map_name IS NOT NULL AND p.time_played_seconds > 0
              AND p.round_number IN (1, 2)
            GROUP BY p.map_name
        ),
        weapon_stats AS (
            SELECT
                w.map_name,
                SUM(CASE WHEN LOWER(w.weapon_name) LIKE '%grenade%' AND LOWER(w.weapon_name) NOT LIKE '%smoke%' THEN w.kills ELSE 0 END) as grenade_kills,
                SUM(CASE WHEN LOWER(w.weapon_name) LIKE '%panzer%' THEN w.kills ELSE 0 END) as panzer_kills,
                SUM(CASE WHEN LOWER(w.weapon_name) LIKE '%mortar%' THEN w.kills ELSE 0 END) as mortar_kills
            FROM weapon_comprehensive_stats w
            WHERE w.map_name IS NOT NULL
              AND w.round_number IN (1, 2)
            GROUP BY w.map_name
        )
        SELECT
            m.map_name,
            m.total_rounds,
            m.matches_played,
            m.allies_wins,
            m.axis_wins,
            m.avg_duration,
            m.min_duration,
            m.max_duration,
            m.last_played,
            p.total_kills,
            p.total_deaths,
            p.avg_dpm,
            p.unique_players,
            w.grenade_kills,
            w.panzer_kills,
            w.mortar_kills
        FROM map_stats m
        LEFT JOIN player_stats p ON m.map_name = p.map_name
        LEFT JOIN weapon_stats w ON m.map_name = w.map_name
        ORDER BY m.matches_played DESC
    """
    try:
        rows = await db.fetch_all(query)

        maps = []
        for row in rows:
            total_rounds = row[1] or 0
            allies_wins = row[3] or 0
            axis_wins = row[4] or 0
            total_games = allies_wins + axis_wins

            allies_win_rate = (
                round((allies_wins / total_games * 100), 1) if total_games > 0 else 50
            )
            axis_win_rate = (
                round((axis_wins / total_games * 100), 1) if total_games > 0 else 50
            )

            maps.append(
                {
                    "name": row[0],
                    "total_rounds": total_rounds,
                    "matches_played": row[2] or total_rounds // 2,
                    "allies_wins": allies_wins,
                    "axis_wins": axis_wins,
                    "allies_win_rate": allies_win_rate,
                    "axis_win_rate": axis_win_rate,
                    "avg_duration": int(row[5]) if row[5] else 0,
                    "min_duration": int(row[6]) if row[6] else 0,
                    "max_duration": int(row[7]) if row[7] else 0,
                    "last_played": row[8],
                    "total_kills": row[9] or 0,
                    "total_deaths": row[10] or 0,
                    "avg_dpm": round(row[11], 1) if row[11] else 0,
                    "unique_players": row[12] or 0,
                    "grenade_kills": row[13] or 0,
                    "panzer_kills": row[14] or 0,
                    "mortar_kills": row[15] or 0,
                }
            )

        return maps
    except Exception as e:
        print(f"Error fetching map stats: {e}")
        return []


@router.get("/stats/weapons")
async def get_weapon_stats(
    period: str = "all",
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get aggregated weapon statistics across all players.
    Returns weapon usage, kills, and accuracy data from weapon_comprehensive_stats table.
    """
    # Calculate start date based on period
    where_clause = "WHERE 1=1"
    params = []
    param_idx = 1

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    # else: all time, no date filter

    query = f"""
        SELECT
            weapon_name,
            SUM(kills) as total_kills,
            SUM(headshots) as total_headshots,
            SUM(shots) as total_shots,
            SUM(hits) as total_hits,
            AVG(accuracy) as avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT ${param_idx}
    """
    params.append(limit)

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        print(f"Error fetching weapon stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return []

    weapons = []
    for row in rows:
        weapon_name = row[0] or "Unknown"
        total_kills = row[1] or 0
        total_headshots = row[2] or 0
        total_hits = row[4] or 0
        avg_accuracy = row[5] or 0

        if total_kills <= 0:
            continue

        # Weapon-level headshot accuracy: headshots / hits * 100
        # headshots in weapon_comprehensive_stats are headshot HITS, not kills.
        hs_rate = min(100, round((total_headshots / total_hits * 100), 1)) if total_hits > 0 else 0.0
        weapons.append(
            {
                "name": _clean_weapon_name(weapon_name),
                "weapon_key": _normalize_weapon_key(weapon_name),
                "kills": int(total_kills),
                "headshots": int(total_headshots),
                "hs_rate": hs_rate,
                "accuracy": round(avg_accuracy, 1),
            }
        )

    return weapons


@router.get("/stats/weapons/hall-of-fame")
async def get_weapon_hall_of_fame(
    period: str = "all", db: DatabaseAdapter = Depends(get_db)
):
    """
    Get top player per weapon for Hall of Fame.
    Focuses on iconic weapons (pistols, smgs, rifles, heavy, explosives).
    """
    hall_weapons = [
        "luger",
        "colt",
        "mp40",
        "thompson",
        "sten",
        "fg42",
        "garand",
        "k43",
        "kar98",
        "panzerfaust",
        "mortar",
        "grenade",
    ]

    weapon_key_expr = "REPLACE(REPLACE(LOWER(weapon_name), 'ws_', ''), ' ', '')"
    where_clause = "WHERE weapon_name IS NOT NULL"
    params = []
    param_idx = 1

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1

    weapon_placeholders = ",".join(
        f"${i}" for i in range(param_idx, param_idx + len(hall_weapons))
    )
    where_clause += f" AND {weapon_key_expr} IN ({weapon_placeholders})"
    params.extend(hall_weapons)

    query = f"""
        SELECT
            {weapon_key_expr} as weapon_key,
            MAX(weapon_name) as weapon_name,
            player_guid,
            MAX(player_name) as player_name,
            SUM(kills) as kills,
            SUM(headshots) as headshots,
            SUM(shots) as shots,
            SUM(hits) as hits,
            AVG(accuracy) as avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY weapon_key, player_guid
    """

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        print(f"Error fetching weapon hall of fame: {e}")
        return {"period": period, "leaders": {}}

    leaders = {}
    for row in rows:
        weapon_key = row[0]
        weapon_name = row[1] or weapon_key
        player_guid = row[2]
        fallback_name = row[3] or "Unknown"
        player_name = await resolve_display_name(db, player_guid, fallback_name)
        kills = row[4] or 0
        headshots = row[5] or 0
        shots = row[6] or 0
        hits = row[7] or 0
        accuracy = (hits / shots * 100) if shots else (row[8] or 0)

        current = leaders.get(weapon_key)
        if not current or kills > current["kills"]:
            leaders[weapon_key] = {
                "weapon": _clean_weapon_name(weapon_name),
                "weapon_key": weapon_key,
                "player_guid": player_guid,
                "player_name": player_name,
                "kills": kills,
                "headshots": headshots,
                "accuracy": round(accuracy, 1),
            }

    return {"period": period, "leaders": leaders}


@router.get("/stats/weapons/by-player")
@router.get("/stats/weapons/by_player")
async def get_weapon_stats_by_player(
    period: str = "all",
    player_limit: int = 25,
    weapon_limit: int = 5,
    player_guid: Optional[str] = None,
    gaming_session_id: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Return per-player weapon stats keyed by player GUID.
    Useful for comprehensive weapon mastery views.
    """
    where_clause = "WHERE weapon_name IS NOT NULL"
    params: List[Any] = []
    param_idx = 1

    # Session-scoped: filter to rounds in the given gaming session
    if gaming_session_id is not None:
        where_clause += (
            f" AND round_id IN ("
            f"SELECT id FROM rounds WHERE gaming_session_id = ${param_idx}"
            f" AND round_number IN (1, 2))"
        )
        params.append(gaming_session_id)
        param_idx += 1
    elif period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1

    if player_guid:
        where_clause += f" AND player_guid = ${param_idx}"
        params.append(player_guid)
        param_idx += 1

    query = f"""
        SELECT
            player_guid,
            MAX(player_name) AS player_name,
            weapon_name,
            SUM(kills) AS total_kills,
            SUM(headshots) AS total_headshots,
            SUM(shots) AS total_shots,
            SUM(hits) AS total_hits,
            AVG(accuracy) AS avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY player_guid, weapon_name
        HAVING SUM(kills) > 0 OR SUM(hits) > 0
        ORDER BY player_guid, total_kills DESC, total_hits DESC
    """

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        print(f"Error fetching weapon stats by player: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    players: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        guid = row[0]
        if not guid:
            continue
        if guid not in players:
            players[guid] = {
                "player_guid": guid,
                "player_name": row[1] or "Unknown",
                "total_kills": 0,
                "weapons": [],
            }

        kills = int(row[3] or 0)
        headshots = int(row[4] or 0)
        shots = int(row[5] or 0)
        hits = int(row[6] or 0)
        avg_accuracy = float(row[7] or 0)
        # Player-level headshot accuracy: headshots / hits * 100
        # headshots in weapon_comprehensive_stats are headshot HITS, not kills.
        hs_rate = round((headshots / hits) * 100, 1) if hits > 0 else 0.0

        players[guid]["total_kills"] += kills
        players[guid]["weapons"].append(
            {
                "name": _clean_weapon_name(row[2]),
                "weapon_key": _normalize_weapon_key(row[2]),
                "kills": kills,
                "headshots": headshots,
                "hs_rate": min(100.0, hs_rate),
                "shots": shots,
                "hits": hits,
                "accuracy": round(avg_accuracy, 1),
            }
        )

    ranked_players = sorted(
        players.values(),
        key=lambda p: p["total_kills"],
        reverse=True,
    )

    if player_limit > 0:
        ranked_players = ranked_players[:player_limit]
    for player in ranked_players:
        player["weapons"] = player["weapons"][: max(1, weapon_limit)]

    return {
        "period": period,
        "player_count": len(ranked_players),
        "players": ranked_players,
    }


@router.get("/stats/matches/{match_id}")
async def get_match_details(match_id: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get detailed stats for a specific match/round.
    match_id can be: round ID (numeric) or round_date string
    """
    # First, get the round info
    if match_id.isdigit():
        # It's a round ID
        round_query = """
            SELECT id, map_name, round_number, round_date, winner_team,
                   actual_time, round_outcome, gaming_session_id, time_limit
            FROM rounds
            WHERE id = $1
        """
        round_row = await db.fetch_one(round_query, (int(match_id),))
    else:
        # It's a date - get latest round for that date
        round_query = """
            SELECT id, map_name, round_number, round_date, winner_team,
                   actual_time, round_outcome, gaming_session_id, time_limit
            FROM rounds
            WHERE round_date = $1
            ORDER BY CAST(REPLACE(round_time, ':', '') AS INTEGER) DESC
            LIMIT 1
        """
        round_row = await db.fetch_one(round_query, (match_id,))

    if not round_row:
        raise HTTPException(status_code=404, detail="Match not found")

    round_id = round_row[0]
    map_name = round_row[1]
    round_number = round_row[2]
    round_date = round_row[3]
    winner_team = round_row[4]
    actual_time = round_row[5]
    round_outcome = round_row[6]
    gaming_session_id = round_row[7]
    time_limit = round_row[8] if len(round_row) > 8 else None

    # Convert winner_team int to string
    winner = "Allies" if winner_team == 1 else "Axis" if winner_team == 2 else "Draw"

    # Get player stats for this specific round
    # Use DISTINCT ON to deduplicate players (in case of multiple entries per player)
    # Picks the row with highest damage_given per player, then orders by team
    query = """
        SELECT * FROM (
            SELECT DISTINCT ON (player_name)
                player_name,
                kills,
                deaths,
                damage_given,
                damage_received,
                time_played_seconds,
                team,
                xp,
                headshots,
                revives_given,
                accuracy,
                gibs,
                self_kills,
                team_kills,
                times_revived,
                most_useful_kills,
                bullets_fired,
                time_dead_minutes,
                denied_playtime,
                double_kills,
                triple_kills,
                quad_kills,
                multi_kills,
                mega_kills,
                player_guid
            FROM player_comprehensive_stats
            WHERE round_date = $1
              AND map_name = $2
              AND round_number = $3
            ORDER BY player_name, damage_given DESC
        ) AS deduplicated
        ORDER BY team, damage_given DESC
    """

    try:
        rows = await db.fetch_all(query, (round_date, map_name, round_number))
    except Exception as e:
        print(f"Error fetching match details: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        raise HTTPException(status_code=404, detail="No player stats found")

    # Group players by team
    team1_players = []
    team2_players = []

    for row in rows:
        time_played = row[5] or 0
        dpm = (row[3] / (time_played / 60)) if time_played > 0 else 0
        kd = row[1] / row[2] if row[2] > 0 else float(row[1])

        # Calculate hits from accuracy and bullets_fired
        bullets_fired = row[16] or 0
        accuracy_pct = row[10] or 0
        hits = round(bullets_fired * accuracy_pct / 100) if accuracy_pct > 0 else 0

        player = {
            "name": row[0],
            "kills": row[1] or 0,
            "deaths": row[2] or 0,
            "damage_given": row[3] or 0,
            "damage_received": row[4] or 0,
            "time_played": time_played,
            "team": row[6],
            "xp": row[7] or 0,
            "headshots": row[8] or 0,
            "revives_given": row[9] or 0,
            "accuracy": round(accuracy_pct, 1),
            "gibs": row[11] or 0,
            "selfkills": row[12] or 0,
            "teamkills": row[13] or 0,
            "times_revived": row[14] or 0,
            "useful_kills": row[15] or 0,
            "shots": bullets_fired,
            "hits": hits,
            "time_dead": round((row[17] or 0) * 60),  # Convert minutes to seconds
            "time_denied": row[18] or 0,
            "double_kills": row[19] or 0,
            "triple_kills": row[20] or 0,
            "quad_kills": row[21] or 0,
            "multi_kills": row[22] or 0,
            "mega_kills": row[23] or 0,
            "player_guid": row[24],
            "dpm": round(dpm, 1),
            "kd": round(kd, 2),
        }

        if row[6] == 1:
            team1_players.append(player)
        else:
            team2_players.append(player)

    # Check if teams are imbalanced (difference > 2 players)
    team_diff = abs(len(team1_players) - len(team2_players))
    if team_diff > 2 and len(team1_players) + len(team2_players) >= 4:
        # Teams are imbalanced - redistribute evenly
        # This happens when team detection failed
        all_players = team1_players + team2_players
        # Sort by damage to keep best players distributed
        all_players.sort(key=lambda p: p["damage_given"], reverse=True)
        mid_point = len(all_players) // 2
        team1_players = all_players[:mid_point]
        team2_players = all_players[mid_point:]

    # Calculate team totals
    def team_totals(players):
        return {
            "kills": sum(p["kills"] for p in players),
            "deaths": sum(p["deaths"] for p in players),
            "damage": sum(p["damage_given"] for p in players),
        }

    return {
        "match": {
            "id": round_id,
            "map_name": map_name,
            "round_number": round_number,
            "round_date": str(round_date),
            "winner": winner,
            "duration": actual_time,
            "outcome": round_outcome,
            "time_limit": time_limit,
            "gaming_session_id": gaming_session_id,
        },
        "team1": {
            "name": "Allies",
            "players": team1_players,
            "totals": team_totals(team1_players),
            "is_winner": winner_team == 1,
        },
        "team2": {
            "name": "Axis",
            "players": team2_players,
            "totals": team_totals(team2_players),
            "is_winner": winner_team == 2,
        },
        "player_count": len(rows),
    }


@router.get("/player/{player_name}/matches")
async def get_player_matches(
    player_name: str,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get recent match history for a specific player.
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name

    query = """
        SELECT
            round_id,
            round_date,
            map_name,
            round_number,
            kills,
            deaths,
            damage_given,
            time_played_seconds,
            team,
            xp,
            accuracy
        FROM player_comprehensive_stats
        WHERE player_guid = $1
        ORDER BY round_date DESC, round_number DESC
        LIMIT $2
    """
    if not use_guid:
        query = query.replace("player_guid = $1", "player_name ILIKE $1")

    try:
        rows = await db.fetch_all(query, (identifier, limit))
    except Exception as e:
        print(f"Error fetching player matches: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return []

    matches = []
    for row in rows:
        time_played = row[7] or 0
        dpm = (row[6] / (time_played / 60)) if time_played > 0 else 0
        kd = row[4] / row[5] if row[5] > 0 else row[4]

        matches.append(
            {
                "round_id": row[0],
                "round_date": row[1],
                "map_name": row[2],
                "round_number": row[3],
                "kills": row[4],
                "deaths": row[5],
                "damage": row[6],
                "time_played": time_played,
                "team": row[8],
                "xp": row[9],
                "accuracy": row[10],
                "dpm": round(dpm, 1),
                "kd": round(kd, 2),
            }
        )

    return matches


@router.get("/stats/player/{player_name}/form")
async def get_player_form(
    player_name: str,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get player's recent form - session DPM (aggregated per gaming session).
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name

    query = """
        SELECT
            r.gaming_session_id,
            MIN(p.round_date) as session_date,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_seconds) as total_time,
            COUNT(*) as rounds_played,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE p.player_guid = $1
        AND p.time_played_seconds > 0
        AND r.gaming_session_id IS NOT NULL
        GROUP BY r.gaming_session_id
        HAVING SUM(p.time_played_seconds) > 120
        ORDER BY MIN(p.round_date) DESC
        LIMIT $2
    """
    if not use_guid:
        query = query.replace("p.player_guid = $1", "p.player_name ILIKE $1")

    try:
        rows = await db.fetch_all(query, (identifier, limit))
    except Exception as e:
        print(f"Error fetching player form: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return {"sessions": [], "avg_dpm": 0, "trend": "insufficient_data"}

    sessions = []
    for row in reversed(rows):
        total_time = row[3] or 0
        time_min = total_time / 60 if total_time > 0 else 1
        dpm = round((row[2] or 0) / time_min, 1)
        kills = row[5] or 0
        deaths = row[6] or 0
        kd = round(kills / deaths, 2) if deaths > 0 else kills

        date_obj = row[1]
        if isinstance(date_obj, str):
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
        label = date_obj.strftime("%b %d")

        sessions.append(
            {
                "label": label,
                "date": str(row[1]),
                "dpm": dpm,
                "rounds": row[4],
                "kd": kd,
            }
        )

    dpms = [s["dpm"] for s in sessions]
    avg_dpm = round(sum(dpms) / len(dpms), 1)

    if len(dpms) >= 6:
        early_avg = sum(dpms[:3]) / 3
        recent_avg = sum(dpms[-3:]) / 3
        if recent_avg > early_avg * 1.1:
            trend = "improving"
        elif recent_avg < early_avg * 0.9:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {"sessions": sessions, "avg_dpm": avg_dpm, "trend": trend}


@router.get("/stats/player/{player_name}/rounds")
async def get_player_rounds(
    player_name: str,
    limit: int = 30,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get player's recent per-round DPM (individual maps).
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name

    query = """
        SELECT
            p.round_date,
            p.map_name,
            p.damage_given,
            p.time_played_seconds
        FROM player_comprehensive_stats p
        WHERE p.player_guid = $1
        AND p.time_played_seconds > 60
        ORDER BY p.round_date DESC, p.round_id DESC
        LIMIT $2
    """
    if not use_guid:
        query = query.replace("p.player_guid = $1", "p.player_name ILIKE $1")

    try:
        rows = await db.fetch_all(query, (identifier, limit))
    except Exception as e:
        print(f"Error fetching player rounds: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return {"rounds": [], "avg_dpm": 0}

    rounds = []
    for row in reversed(rows):
        time_min = row[3] / 60 if row[3] > 0 else 1
        dpm = round(row[2] / time_min, 1)
        raw_map = row[1] or "Unknown"
        short_map = (
            raw_map
            .replace("maps/", "")
            .replace("maps\\", "")
        )
        if short_map.lower().endswith((".bsp", ".pk3", ".arena")):
            short_map = short_map.rsplit(".", 1)[0]
        if len(short_map) > 12:
            short_map = short_map[:12]

        date_obj = row[0]
        if isinstance(date_obj, str):
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d")

        rounds.append(
            {
                "label": short_map,
                "date": str(row[0]),
                "dpm": dpm,
            }
        )

    dpms = [r["dpm"] for r in rounds]
    avg_dpm = round(sum(dpms) / len(dpms), 1)

    return {"rounds": rounds, "avg_dpm": avg_dpm}


@router.get("/sessions/{date}/graphs")
async def get_session_graph_stats(
    date: str,
    gaming_session_id: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get aggregated session stats formatted for graph rendering.
    Returns data for:
    - Combat Stats (Offense): kills, deaths, damage, K/D, DPM
    - Combat Stats (Defense/Support): revives, gibs, headshots, time alive/dead
    - Advanced Metrics: FragPotential, Damage Efficiency, Time Denied, Survival Rate
    - Playstyle Analysis: Classification based on stats patterns
    - DPM Timeline: Per-round DPM values for each player
    """
    # Get all player stats for this session date
    # Use DISTINCT to avoid duplicates from the rounds join
    if gaming_session_id is not None:
        where_clause = "r.gaming_session_id = $1"
        params = (gaming_session_id,)
    else:
        where_clause = "SUBSTRING(p.round_date, 1, 10) = $1"
        params = (date,)

    query = f"""
        SELECT DISTINCT
            p.player_name,
            p.round_number,
            p.kills,
            p.deaths,
            p.damage_given,
            p.damage_received,
            p.time_played_seconds,
            p.revives_given,
            p.kill_assists,
            p.gibs,
            p.headshots,
            p.accuracy,
            p.team_kills,
            p.self_kills,
            p.times_revived,
            p.time_dead_minutes,
            p.denied_playtime,
            p.most_useful_kills,
            p.map_name,
            r.id as round_id,
            p.constructions,
            p.objectives_stolen,
            p.dynamites_planted,
            p.dynamites_defused,
            p.useless_kills,
            p.double_kills,
            p.triple_kills,
            p.quad_kills,
            p.mega_kills,
            p.bullets_fired,
            p.time_played_percent
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE {where_clause}
          AND r.round_number IN (1, 2)
          AND (r.round_status IN ('completed', 'cancelled', 'substitution') OR r.round_status IS NULL)
        ORDER BY p.player_name, r.id
    """

    try:
        rows = await db.fetch_all(query, params)
    except Exception as e:
        print(f"Error fetching session graph stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        raise HTTPException(status_code=404, detail="No stats found for this session")

    # Aggregate stats per player
    player_stats = {}
    dpm_timeline = {}  # player -> list of (map_round, dpm)

    for row in rows:
        name = row[0]
        round_num = row[1]
        kills = row[2] or 0
        deaths = row[3] or 0
        damage_given = row[4] or 0
        damage_received = row[5] or 0
        time_played = row[6] or 0
        revives = row[7] or 0
        kill_assists = row[8] or 0
        gibs = row[9] or 0
        headshots = row[10] or 0
        accuracy = row[11] or 0
        team_kills = row[12] or 0
        self_kills = row[13] or 0
        times_revived = row[14] or 0
        time_dead_minutes = row[15] or 0
        denied_playtime = row[16] or 0
        useful_kills = row[17] or 0
        map_name = row[18]
        round_id = row[19]  # unique identifier for deduplication
        constructions = row[20] or 0
        objectives_stolen = row[21] or 0
        dynamites_planted = row[22] or 0
        dynamites_defused = row[23] or 0
        useless_kills = row[24] or 0
        double_kills = row[25] or 0
        triple_kills = row[26] or 0
        quad_kills = row[27] or 0
        mega_kills = row[28] or 0
        bullets_fired = row[29] or 0
        time_played_percent = float(row[30]) if row[30] else 0.0

        if name not in player_stats:
            player_stats[name] = {
                "kills": 0,
                "deaths": 0,
                "damage_given": 0,
                "damage_received": 0,
                "time_played": 0,
                "revives": 0,
                "kill_assists": 0,
                "gibs": 0,
                "headshots": 0,
                "accuracy_sum": 0,
                "accuracy_count": 0,
                "tpp_weighted_sum": 0,
                "tpp_weight": 0,
                "team_kills": 0,
                "self_kills": 0,
                "times_revived": 0,
                "time_dead_minutes": 0,
                "denied_playtime": 0,
                "useful_kills": 0,
                "rounds_played": 0,
                "seen_rounds": set(),  # Track unique round_ids
                "constructions": 0,
                "objectives_stolen": 0,
                "dynamites_planted": 0,
                "dynamites_defused": 0,
                "useless_kills": 0,
                "double_kills": 0,
                "triple_kills": 0,
                "quad_kills": 0,
                "mega_kills": 0,
            }
            dpm_timeline[name] = []

        # Skip if we've already processed this round for this player
        if round_id in player_stats[name]["seen_rounds"]:
            continue
        player_stats[name]["seen_rounds"].add(round_id)

        ps = player_stats[name]
        ps["kills"] += kills
        ps["deaths"] += deaths
        ps["damage_given"] += damage_given
        ps["damage_received"] += damage_received
        ps["time_played"] += time_played
        ps["revives"] += revives
        ps["kill_assists"] += kill_assists
        ps["gibs"] += gibs
        ps["headshots"] += headshots
        ps["accuracy_sum"] += accuracy
        ps["accuracy_count"] += 1
        if time_played_percent > 0:
            ps["tpp_weighted_sum"] += time_played_percent * time_played
            ps["tpp_weight"] += time_played
        ps["team_kills"] += team_kills
        ps["self_kills"] += self_kills
        ps["times_revived"] += times_revived
        ps["time_dead_minutes"] += time_dead_minutes
        ps["denied_playtime"] += denied_playtime
        ps["useful_kills"] += useful_kills
        ps["constructions"] += constructions
        ps["objectives_stolen"] += objectives_stolen
        ps["dynamites_planted"] += dynamites_planted
        ps["dynamites_defused"] += dynamites_defused
        ps["useless_kills"] += useless_kills
        ps["double_kills"] += double_kills
        ps["triple_kills"] += triple_kills
        ps["quad_kills"] += quad_kills
        ps["mega_kills"] += mega_kills
        ps["rounds_played"] += 1

        # DPM for this round
        round_dpm = (damage_given / (time_played / 60)) if time_played > 0 else 0
        # Use shorter map name format for timeline
        short_map = map_name.split("_")[-1][:8] if "_" in map_name else map_name[:8]
        dpm_timeline[name].append(
            {"label": f"{short_map} R{round_num}", "dpm": round(round_dpm, 1)}
        )

    # Calculate derived metrics and build response
    players_data = []
    for name, stats in player_stats.items():
        time_minutes = stats["time_played"] / 60 if stats["time_played"] > 0 else 1

        # Basic ratios
        kd = stats["kills"] / stats["deaths"] if stats["deaths"] > 0 else stats["kills"]
        dpm = stats["damage_given"] / time_minutes

        # Damage Efficiency: ratio of damage given to received (>1 is good)
        damage_efficiency = stats["damage_given"] / max(1, stats["damage_received"])

        # Survival Rate: prefer engine alive% (TAB[8]), fallback to computed
        tpp_wsum = stats.get("tpp_weighted_sum", 0)
        tpp_w = stats.get("tpp_weight", 0)
        survival_rate_engine = round(tpp_wsum / tpp_w, 1) if tpp_w > 0 else None
        time_dead_min = stats.get("time_dead_minutes", 0)
        time_played_min = max(0.01, time_minutes)
        survival_rate_computed = max(0, 100 - (time_dead_min / time_played_min * 100))
        survival_rate = survival_rate_engine if survival_rate_engine is not None else survival_rate_computed

        # Time Denied (use Lua denied_playtime when available; normalize per minute)
        time_denied_raw = stats.get("denied_playtime", 0)
        time_denied = (time_denied_raw / time_minutes) if time_minutes > 0 else 0
        time_dead_raw_seconds = stats.get("time_dead_minutes", 0) * 60

        # Simple average accuracy per round
        avg_accuracy = (
            stats["accuracy_sum"] / stats["accuracy_count"]
            if stats["accuracy_count"] > 0
            else 0
        )

        # Playstyle classification (8 categories like Discord bot)
        playstyle = classify_playstyle(stats, dpm, kd, avg_accuracy, survival_rate)
        rounds_played = max(1, stats["rounds_played"])

        players_data.append(
            {
                "name": name,
                "combat_offense": {
                    "kills": stats["kills"],
                    "deaths": stats["deaths"],
                    "damage_given": stats["damage_given"],
                    "kd": round(kd, 2),
                    "dpm": round(dpm, 1),
                },
                "combat_defense": {
                    "revives": stats["revives"],
                    "kill_assists": stats["kill_assists"],
                    "gibs": stats["gibs"],
                    "headshots": stats["headshots"],
                    "useful_kills": stats["useful_kills"],
                    "times_revived": stats["times_revived"],
                    "team_kills": stats["team_kills"],
                    "self_kills": stats["self_kills"],
                },
                "advanced_metrics": {
                    "frag_potential": round((stats["damage_given"] / max(1, stats["time_played"] - stats.get("time_dead_minutes", 0) * 60)) * 60, 1),
                    "damage_efficiency": round(damage_efficiency, 1),
                    "survival_rate": round(survival_rate, 1),
                    "time_denied": round(time_denied, 1),
                    "time_denied_raw_seconds": int(time_denied_raw or 0),
                    "time_dead_raw_seconds": int(time_dead_raw_seconds or 0),
                    "useful_kills_per_round": round(
                        stats["useful_kills"] / rounds_played, 2
                    ),
                    "deaths_per_round": round(stats["deaths"] / rounds_played, 2),
                    "rounds_played": rounds_played,
                },
                "playstyle": playstyle,
                "dpm_timeline": dpm_timeline[name],
            }
        )

    _apply_session_aggression_model(players_data)

    # Sort by DPM for consistent ordering
    players_data.sort(key=lambda x: x["combat_offense"]["dpm"], reverse=True)

    return {"date": date, "player_count": len(players_data), "players": players_data}


def _clamp_percentage(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(100.0, float(value))), 1)


def _score_relative_metric(
    value: Any, values: List[Any], invert: bool = False, neutral: float = 50.0
) -> float:
    """Score a value relative to a set using percentile rank.

    Percentile rank is outlier-resistant: one extreme value cannot
    compress all others toward 50. Each player's score reflects how
    many session-mates they beat, not their distance from min/max.
    """
    numeric_values: list[float] = []
    for item in values:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            numeric_values.append(number)

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return neutral

    if not math.isfinite(numeric_value) or not numeric_values:
        return neutral

    n = len(numeric_values)
    if n <= 1:
        return neutral

    count_below = sum(1 for v in numeric_values if v < numeric_value)
    scaled = (count_below / (n - 1)) * 100.0
    if invert:
        scaled = 100.0 - scaled
    return _clamp_percentage(scaled) or neutral


def _apply_session_aggression_model(players_data: List[Dict[str, Any]]) -> None:
    if not players_data:
        return

    frag_values = []
    denied_values = []
    useful_values = []
    death_values = []
    dead_share_values = []
    efficiency_values = []
    survival_values = []

    for player in players_data:
        adv = player.get("advanced_metrics") or {}
        frag_values.append(float(adv.get("frag_potential") or 0.0))
        denied_values.append(float(adv.get("time_denied") or 0.0))
        useful_values.append(float(adv.get("useful_kills_per_round") or 0.0))
        death_values.append(float(adv.get("deaths_per_round") or 0.0))
        survival_rate = float(adv.get("survival_rate") or 0.0)
        dead_share_values.append(max(0.0, 100.0 - survival_rate))
        efficiency_values.append(float(adv.get("damage_efficiency") or 0.0))
        survival_values.append(survival_rate)

    for player in players_data:
        adv = player.get("advanced_metrics") or {}
        playstyle = player.setdefault("playstyle", {})

        survival_rate = float(adv.get("survival_rate") or 0.0)
        dead_time_share = max(0.0, 100.0 - survival_rate)

        frag_score = _score_relative_metric(
            adv.get("frag_potential"), frag_values, neutral=50.0
        )
        denied_score = _score_relative_metric(
            adv.get("time_denied"), denied_values, neutral=50.0
        )
        useful_score = _score_relative_metric(
            adv.get("useful_kills_per_round"), useful_values, neutral=50.0
        )
        death_score = _score_relative_metric(
            adv.get("deaths_per_round"), death_values, neutral=50.0
        )
        dead_share_score = _score_relative_metric(
            dead_time_share, dead_share_values, neutral=50.0
        )
        efficiency_score = _score_relative_metric(
            adv.get("damage_efficiency"), efficiency_values, neutral=50.0
        )
        survival_score = _score_relative_metric(
            survival_rate, survival_values, neutral=50.0
        )

        pressure_score = (frag_score * 0.50) + (denied_score * 0.25) + (
            useful_score * 0.25
        )
        risk_load = (death_score * 0.60) + (dead_share_score * 0.40)
        productivity = (pressure_score * 0.65) + (efficiency_score * 0.35)
        empty_death_burden = max(0.0, risk_load - productivity)

        aggression_score = _clamp_percentage(
            (pressure_score * 0.80)
            + (risk_load * 0.20)
            - (empty_death_burden * 0.50)
        ) or 0.0
        discipline_score = _clamp_percentage(
            (survival_score * 0.45)
            + (efficiency_score * 0.35)
            + ((100.0 - empty_death_burden) * 0.20)
        ) or 0.0

        playstyle["aggression"] = aggression_score
        adv["aggression_score"] = aggression_score
        adv["pressure_score"] = round(pressure_score, 1)
        adv["risk_load"] = round(risk_load, 1)
        adv["empty_death_burden"] = round(empty_death_burden, 1)
        adv["discipline_score"] = discipline_score
        adv["dead_time_share"] = round(dead_time_share, 1)


def classify_playstyle(
    stats: dict,
    dpm: float,
    kd: float,
    accuracy: float,
    survival_rate: float,
) -> dict:
    """
    Classify player playstyle into 8 categories (0-100 scale).
    Based on Discord bot's SessionGraphGenerator logic.
    """
    rounds = stats["rounds_played"] or 1

    # Normalize stats per round for fair comparison
    revives_pr = stats["revives"] / rounds
    assists_pr = stats.get("kill_assists", 0) / rounds
    constructions_pr = stats.get("constructions", 0) / rounds
    obj_actions_pr = (
        stats.get("objectives_stolen", 0)
        + stats.get("dynamites_planted", 0)
        + stats.get("dynamites_defused", 0)
    ) / rounds

    # Calculate each playstyle dimension (0-100)
    precision = min(100, accuracy * 2)
    survivability = min(100, max(0, survival_rate))
    # ET:Legacy support = medic (revives) + teamwork (assists) +
    # engineer/fieldops (constructions, objectives, dynamites).
    # Weighted: revives 40%, assists 30%, constructions+objectives 30%
    support = min(100, (
        min(100, revives_pr * 20) * 0.40        # medic: caps at 5 rev/round
        + min(100, assists_pr * 15) * 0.30       # teamwork: caps at 6.7 assists/round
        + min(100, (constructions_pr + obj_actions_pr) * 30) * 0.30  # engi/obj: caps at 3.3/round
    ))
    lethality = min(100, kd * 30)

    # Brutality = smart elimination power (industry-first composite):
    # - denied_playtime: man-advantage time created (hockey power-play model)
    # - gib_efficiency: finish rate, kills you complete (Apex "thirst" model)
    # - useful_kill_ratio: impactful kills (HLTV Round Swing model)
    # - multi_kill_bonus: domination moments (Quake "Excellent" model)
    # - useless_kill_penalty: wasted frags (PandaSkill "Worthless Death" model)
    denied_pr = stats["denied_playtime"] / rounds  # seconds of man-advantage per round
    total_kills = max(1, stats["kills"])
    gib_eff = (stats["gibs"] / total_kills) * 100  # % of kills finished
    useful = stats["useful_kills"]
    useless = stats.get("useless_kills", 0)
    useful_ratio = (useful / max(1, useful + useless)) * 100 if (useful + useless) > 0 else 50
    multi_raw = (
        stats.get("double_kills", 0)
        + stats.get("triple_kills", 0) * 2
        + stats.get("quad_kills", 0) * 3
        + stats.get("mega_kills", 0) * 4
    ) / rounds
    useless_ratio = (useless / total_kills) * 100

    brutality = min(100, max(0, (
        min(100, denied_pr * 2.5) * 0.35        # ~40s denied/round = 100 (one full spawn wave)
        + min(100, gib_eff) * 0.25               # 100% gib rate = 100
        + min(100, useful_ratio) * 0.20           # useful kill ratio
        + min(100, multi_raw * 25) * 0.10         # ~4 multi events/round = 100
        - min(100, useless_ratio) * 0.10          # penalty for wasted frags
    )))

    efficiency = min(
        100, (stats["damage_given"] / max(1, stats["damage_received"])) * 25
    )

    # Consistency = well-roundedness across dimensions.
    # Low deviation across axes → high consistency. Replaces the old
    # `rounds * 10` formula which capped at 10 rounds and was always
    # 100 in any BO6+ session.
    dims = [precision, survivability, support, lethality, brutality, efficiency]
    dim_mean = sum(dims) / len(dims)
    dim_dev = (sum((d - dim_mean) ** 2 for d in dims) / len(dims)) ** 0.5
    consistency = min(100, max(0, 100 - dim_dev * 2))

    return {
        # Aggression is session-normalized later using productive pressure
        # signals. Keep the base classifier neutral on its own.
        "aggression": 50.0,
        "precision": precision,
        "survivability": survivability,
        "support": support,
        "lethality": lethality,
        "brutality": brutality,
        "consistency": consistency,
        "efficiency": efficiency,
    }


@router.get("/stats/records")
async def get_records(
    map_name: str = None, limit: int = 1, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get all-time records (Hall of Fame).
    If map_name is provided, returns records for that map only.
    """
    # Categories to fetch
    categories = {
        "kills": {"col": "kills", "label": "Most Kills"},
        "damage": {"col": "damage_given", "label": "Most Damage"},
        "revives": {"col": "revives_given", "label": "Most Revives"},
        "gibs": {"col": "gibs", "label": "Most Gibs"},
        "headshots": {"col": "headshots", "label": "Most Headshots"},
        "xp": {"col": "xp", "label": "Most XP"},
        "accuracy": {
            "col": "accuracy",
            "label": "Best Accuracy",
            "filter": "bullets_fired > 50",
        },
        "revived": {"col": "times_revived", "label": "Most Times Revived"},
        "useful_kills": {"col": "most_useful_kills", "label": "Most Useful Kills"},
        "obj_stolen": {"col": "objectives_stolen", "label": "Objectives Stolen"},
        "obj_returned": {"col": "objectives_returned", "label": "Objectives Returned"},
        "dyna_planted": {"col": "dynamites_planted", "label": "Dynamites Planted"},
        "dyna_defused": {"col": "dynamites_defused", "label": "Dynamites Defused"},
    }

    results = {}

    base_where = "WHERE round_number IN (1, 2) AND time_played_seconds > 0"
    params = []

    if map_name:
        base_where += " AND map_name = $1"
        params.append(map_name)

    for key, config in categories.items():
        col = config["col"]
        extra_filter = f" AND {config['filter']}" if "filter" in config else ""

        query = f"""
            SELECT
                player_name,
                {col} as value,
                map_name,
                round_date
            FROM player_comprehensive_stats
            {base_where} {extra_filter}
            ORDER BY {col} DESC
            LIMIT $2
        """

        # Adjust param index for limit
        if map_name:
            q_params = (map_name, limit)
            query = query.replace("$2", "$2")
        else:
            q_params = (limit,)
            query = query.replace("$2", "$1")

        try:
            rows = await db.fetch_all(query, q_params)
            if rows:
                results[key] = [
                    {"player": row[0], "value": row[1], "map": row[2], "date": row[3]}
                    for row in rows
                ]
        except Exception as e:
            print(f"Error fetching record for {key}: {e}")
            results[key] = []

    return results


# ========================================
# ENDSTATS / AWARDS ENDPOINTS
# ========================================

# Award categories for display (mirrors bot/endstats_parser.py)
AWARD_CATEGORIES = {
    "combat": {
        "emoji": "⚔️",
        "name": "Combat",
        "awards": [
            "Most damage given",
            "Most damage received",
            "Most kills per minute",
            "Most damage per minute",
            "Best K/D ratio",
            "Tank/Meatshield (Refuses to die)",
        ],
    },
    "deaths": {
        "emoji": "💀",
        "name": "Deaths & Mayhem",
        "awards": [
            "Most deaths",
            "Most selfkills",
            "Most teamkills",
            "Longest death spree",
            "Most panzer deaths",
            "Most mortar deaths",
            "Most MG42 deaths",
            "Mortarmagnet",
        ],
    },
    "skills": {
        "emoji": "🎯",
        "name": "Skills",
        "awards": [
            "Most headshot kills",
            "Most headshots",
            "Highest light weapons accuracy",
            "Highest headshot accuracy",
            "Most light weapon kills",
            "Most pistol kills",
            "Most rifle kills",
            "Most sniper kills",
            "Most knife kills",
            "Longest killing spree",
            "Most multikills",
            "Most doublekills",
            "Quickest multikill w/ light weapons",
            "Most bullets fired",
        ],
    },
    "weapons": {
        "emoji": "🔫",
        "name": "Weapons",
        "awards": [
            "Most grenade kills",
            "Most panzer kills",
            "Most mortar kills",
            "Most mine kills",
            "Most air support kills",
            "Most riflenade kills",
            "Farthest riflenade kill",
            "Most MG42 kills",
        ],
    },
    "teamwork": {
        "emoji": "🤝",
        "name": "Teamwork",
        "awards": [
            "Most revives",
            "Most revived",
            "Most kill assists",
            "Most killsteals",
            "Most team damage given",
            "Most team damage received",
        ],
    },
    "objectives": {
        "emoji": "🎯",
        "name": "Objectives",
        "awards": [
            "Most dynamites planted",
            "Most dynamites defused",
            "Most objectives stolen",
            "Most objectives returned",
            "Most corpse gibs",
        ],
    },
    "timing": {
        "emoji": "⏱️",
        "name": "Timing",
        "awards": [
            "Most useful kills (>Half respawn time left)",
            "Most useless kills",
            "Full respawn king",
            "Most playtime denied",
            "Least time dead (What spawn?)",
        ],
    },
}


def categorize_award(award_name: str) -> tuple:
    """Return (category_key, emoji, category_name) for an award."""
    for cat_key, cat_data in AWARD_CATEGORIES.items():
        if award_name in cat_data["awards"]:
            return (cat_key, cat_data["emoji"], cat_data["name"])
    return ("other", "📋", "Other")


@router.get("/rounds/{round_id}/awards")
async def get_round_awards(round_id: int, db: DatabaseAdapter = Depends(get_db)):
    """
    Get awards for a specific round, grouped by category.
    """
    # Get round info
    round_query = "SELECT map_name, round_number, round_date FROM rounds WHERE id = $1"
    round_row = await db.fetch_one(round_query, (round_id,))

    if not round_row:
        raise HTTPException(status_code=404, detail="Round not found")

    # Get awards
    awards_query = """
        SELECT award_name, player_name, player_guid, award_value, award_value_numeric
        FROM round_awards
        WHERE round_id = $1
        ORDER BY id
    """
    awards_rows = await db.fetch_all(awards_query, (round_id,))

    unknown_names = [row[1] for row in awards_rows if row[2] is None and row[1]]
    alias_map = await resolve_alias_guid_map(db, unknown_names)
    name_map = await resolve_name_guid_map(db, unknown_names)

    # Group by category
    categories = {}
    for row in awards_rows:
        award_name, player, player_guid, value, numeric = row
        effective_guid = (
            player_guid
            or alias_map.get(player.lower() if player else "")
            or name_map.get(player.lower() if player else "")
        )
        cat_key, emoji, cat_name = categorize_award(award_name)

        if cat_key not in categories:
            categories[cat_key] = {"emoji": emoji, "name": cat_name, "awards": []}

        display_name = (
            await resolve_display_name(db, effective_guid, player or "Unknown")
            if effective_guid
            else (player or "Unknown")
        )
        categories[cat_key]["awards"].append(
            {
                "award": award_name,
                "player": display_name,
                "guid": effective_guid,
                "value": value,
                "numeric": numeric,
            }
        )

    return {
        "round_id": round_id,
        "map_name": round_row[0],
        "round_number": round_row[1],
        "round_date": round_row[2],
        "categories": categories,
    }


@router.get("/rounds/{round_id}/vs-stats")
async def get_round_vs_stats(round_id: int, db: DatabaseAdapter = Depends(get_db)):
    """
    Get VS stats (player K/D) for a specific round.
    """
    query = """
        SELECT player_name, player_guid, kills, deaths
        FROM round_vs_stats
        WHERE round_id = $1
        ORDER BY kills DESC, deaths ASC
    """
    rows = await db.fetch_all(query, (round_id,))

    unknown_names = [row[0] for row in rows if row[1] is None and row[0]]
    alias_map = await resolve_alias_guid_map(db, unknown_names)
    name_map = await resolve_name_guid_map(db, unknown_names)

    return {
        "round_id": round_id,
        "stats": [
            {
                "player": (
                    await resolve_display_name(
                        db,
                        row[1]
                        or alias_map.get(row[0].lower() if row[0] else "")
                        or name_map.get(row[0].lower() if row[0] else ""),
                        row[0] or "Unknown",
                    )
                    if (
                        row[1]
                        or alias_map.get(row[0].lower() if row[0] else "")
                        or name_map.get(row[0].lower() if row[0] else "")
                    )
                    else (row[0] or "Unknown")
                ),
                "guid": row[1] or alias_map.get(row[0].lower() if row[0] else "") or name_map.get(row[0].lower() if row[0] else ""),
                "kills": row[2],
                "deaths": row[3],
            }
            for row in rows
        ],
    }


@router.get("/player/{guid}/vs-stats")
async def get_player_vs_stats(
    guid: str,
    scope: str = "all",
    round_id: Optional[int] = None,
    session_id: Optional[int] = None,
    limit: int = Query(default=10, le=50),
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Player vs player stats — Easiest Preys and Worst Enemies.
    Scope: 'round' (single round), 'session' (gaming session), 'all' (all-time).
    """
    safe_limit = max(1, min(limit, 50))

    # Build round filter based on scope
    if scope == "round" and round_id:
        round_filter = "AND v.round_id = $2"
        params_base: tuple = (guid, round_id)
    elif scope == "session" and session_id:
        round_filter = "AND v.round_id IN (SELECT id FROM rounds WHERE gaming_session_id = $2)"
        params_base = (guid, session_id)
    else:
        round_filter = ""
        params_base = (guid,)

    limit_param = f"${len(params_base) + 1}"

    # Easiest Preys — opponents this player killed most
    preys_query = f"""
        SELECT
            COALESCE(v.player_guid, v.player_name) AS opponent_key,
            MAX(v.player_name) AS opponent_name,
            v.player_guid AS opponent_guid,
            SUM(v.kills) AS total_kills,
            SUM(v.deaths) AS total_deaths
        FROM round_vs_stats v
        WHERE v.subject_guid = $1 {round_filter}
          AND v.subject_guid IS NOT NULL
        GROUP BY opponent_key, v.player_guid
        ORDER BY total_kills DESC, total_deaths ASC
        LIMIT {limit_param}
    """
    preys_rows = await db.fetch_all(preys_query, params_base + (safe_limit,))

    # Worst Enemies — opponents who killed this player most
    enemies_query = f"""
        SELECT
            COALESCE(v.player_guid, v.player_name) AS opponent_key,
            MAX(v.player_name) AS opponent_name,
            v.player_guid AS opponent_guid,
            SUM(v.kills) AS total_kills,
            SUM(v.deaths) AS total_deaths
        FROM round_vs_stats v
        WHERE v.subject_guid = $1 {round_filter}
          AND v.subject_guid IS NOT NULL
        GROUP BY opponent_key, v.player_guid
        ORDER BY total_deaths DESC, total_kills ASC
        LIMIT {limit_param}
    """
    enemies_rows = await db.fetch_all(enemies_query, params_base + (safe_limit,))

    def build_entry(row):
        kills = int(row[3] or 0)
        deaths = int(row[4] or 0)
        return {
            "opponent_name": row[1],
            "opponent_guid": row[2],
            "kills": kills,
            "deaths": deaths,
            "kd": round(kills / max(deaths, 1), 2),
        }

    return {
        "guid": guid,
        "scope": scope,
        "round_id": round_id if scope == "round" else None,
        "session_id": session_id if scope == "session" else None,
        "easiest_preys": [build_entry(r) for r in (preys_rows or [])],
        "worst_enemies": [build_entry(r) for r in (enemies_rows or [])],
    }


@router.get("/awards/leaderboard")
async def get_awards_leaderboard(
    limit: int = 20,
    days: int = 0,
    award_type: str = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get leaderboard of players by total awards won.

    Args:
        limit: Number of players to return
        days: Filter to last N days (0 = all time)
        award_type: Filter to specific award type
    """
    params = []
    where_clauses = []
    param_idx = 1

    if days > 0:
        where_clauses.append(
            f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')"
        )
        params.append(days)
        param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get player award counts with their most won award (GUID-aware)
    query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        ),
        player_counts AS (
            SELECT
                COALESCE(ra.player_guid, am.guid, nm.player_guid, ra.player_name) as player_key,
                COALESCE(ra.player_guid, am.guid, nm.player_guid) as player_guid,
                MAX(ra.player_name) as player_name,
                ra.award_name,
                COUNT(*) as award_specific_count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            {where_sql}
            GROUP BY player_key, player_guid, ra.award_name
        ),
        player_totals AS (
            SELECT
                player_key,
                MAX(player_guid) as player_guid,
                MAX(player_name) as player_name,
                SUM(award_specific_count) as total_awards
            FROM player_counts
            GROUP BY player_key
        ),
        top_awards AS (
            SELECT DISTINCT ON (player_key)
                player_key,
                award_name as top_award,
                award_specific_count as top_award_count
            FROM player_counts
            ORDER BY player_key, award_specific_count DESC
        )
        SELECT
            pt.player_guid,
            pt.player_name,
            pt.total_awards,
            ta.top_award,
            ta.top_award_count
        FROM player_totals pt
        JOIN top_awards ta ON pt.player_key = ta.player_key
        ORDER BY pt.total_awards DESC
        LIMIT ${param_idx}
    """
    params.append(limit)

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception:
        fallback_query = f"""
            WITH player_counts AS (
                SELECT
                    player_name,
                    COUNT(*) as award_count,
                    award_name,
                    COUNT(*) as award_specific_count
                FROM round_awards ra
                {where_sql}
                GROUP BY player_name, award_name
            ),
            player_totals AS (
                SELECT
                    player_name,
                    SUM(award_specific_count) as total_awards
                FROM player_counts
                GROUP BY player_name
            ),
            top_awards AS (
                SELECT DISTINCT ON (player_name)
                    player_name,
                    award_name as top_award,
                    award_specific_count as top_award_count
                FROM player_counts
                ORDER BY player_name, award_specific_count DESC
            )
            SELECT
                pt.player_name,
                pt.total_awards,
                ta.top_award,
                ta.top_award_count
            FROM player_totals pt
            JOIN top_awards ta ON pt.player_name = ta.player_name
            ORDER BY pt.total_awards DESC
            LIMIT ${param_idx}
        """
        rows = await db.fetch_all(fallback_query, tuple(params))

    # Build GUID enrichment map for any name-only rows
    name_pool = []
    for row in rows:
        if len(row) == 4:
            name_pool.append(row[0])
        else:
            name_pool.append(row[1])
    alias_map = await resolve_alias_guid_map(db, name_pool)
    name_map = await resolve_name_guid_map(db, name_pool)

    leaderboard = []
    for idx, row in enumerate(rows):
        if len(row) == 4:
            player_guid = None
            player_name, total_awards, top_award, top_award_count = row
        else:
            player_guid, player_name, total_awards, top_award, top_award_count = row
        if not player_guid and player_name:
            key = player_name.lower()
            player_guid = alias_map.get(key) or name_map.get(key)
        display_name = (
            await resolve_display_name(db, player_guid, player_name or "Unknown")
            if player_guid
            else (player_name or "Unknown")
        )
        leaderboard.append(
            {
                "rank": idx + 1,
                "player": display_name,
                "guid": player_guid,
                "award_count": total_awards,
                "top_award": top_award,
                "top_award_count": top_award_count,
            }
        )

    return {
        "leaderboard": leaderboard,
        "filters": {"days": days, "award_type": award_type},
    }


@router.get("/players/{identifier}/awards")
async def get_player_awards(
    identifier: str, limit: int = 10, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get awards won by a specific player.

    Args:
        identifier: Player name or GUID
        limit: Number of recent awards to return
    """
    resolved_guid = await resolve_player_guid(db, identifier)
    display_name = (
        await resolve_display_name(db, resolved_guid, identifier)
        if resolved_guid
        else identifier
    )

    if resolved_guid:
        count_query = """
            WITH alias_map AS (
                SELECT DISTINCT ON (alias) alias, guid
                FROM player_aliases
                ORDER BY alias, last_seen DESC
            ),
            name_map AS (
                SELECT DISTINCT ON (LOWER(player_name))
                    LOWER(player_name) as name_key,
                    player_guid
                FROM player_comprehensive_stats
                ORDER BY LOWER(player_name), round_date DESC
            )
            SELECT ra.award_name, COUNT(*) as count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            WHERE COALESCE(ra.player_guid, am.guid, nm.player_guid) = $1
            GROUP BY ra.award_name
            ORDER BY count DESC
        """
        recent_query = """
            WITH alias_map AS (
                SELECT DISTINCT ON (alias) alias, guid
                FROM player_aliases
                ORDER BY alias, last_seen DESC
            ),
            name_map AS (
                SELECT DISTINCT ON (LOWER(player_name))
                    LOWER(player_name) as name_key,
                    player_guid
                FROM player_comprehensive_stats
                ORDER BY LOWER(player_name), round_date DESC
            )
            SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            WHERE COALESCE(ra.player_guid, am.guid, nm.player_guid) = $1
            ORDER BY ra.created_at DESC
            LIMIT $2
        """
        try:
            count_rows = await db.fetch_all(count_query, (resolved_guid,))
            recent_rows = await db.fetch_all(recent_query, (resolved_guid, limit))
        except Exception:
            fallback_count = """
                SELECT award_name, COUNT(*) as count
                FROM round_awards
                WHERE player_guid = $1
                GROUP BY award_name
                ORDER BY count DESC
            """
            fallback_recent = """
                SELECT award_name, award_value, round_date, map_name, round_number
                FROM round_awards
                WHERE player_guid = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            count_rows = await db.fetch_all(fallback_count, (resolved_guid,))
            recent_rows = await db.fetch_all(fallback_recent, (resolved_guid, limit))
    else:
        # Fallback: name-based lookup
        count_query = """
            SELECT award_name, COUNT(*) as count
            FROM round_awards
            WHERE player_name ILIKE $1
            GROUP BY award_name
            ORDER BY count DESC
        """
        recent_query = """
            SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
            FROM round_awards ra
            WHERE ra.player_name ILIKE $1
            ORDER BY ra.created_at DESC
            LIMIT $2
        """
        count_rows = await db.fetch_all(count_query, (identifier,))
        recent_rows = await db.fetch_all(recent_query, (identifier, limit))

    total = sum(row[1] for row in count_rows)

    return {
        "player": display_name,
        "guid": resolved_guid,
        "total_awards": total,
        "by_type": {row[0]: row[1] for row in count_rows},
        "recent": [
            {
                "award": row[0],
                "value": row[1],
                "date": row[2],
                "map": row[3],
                "round": row[4],
            }
            for row in recent_rows
        ],
    }


@router.get("/awards")
async def list_awards(
    limit: int = 50,
    offset: int = 0,
    player: str = None,
    award_type: str = None,
    days: int = 0,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    List all awards with pagination and filters.

    Args:
        limit: Number of awards per page
        offset: Pagination offset
        player: Filter by player name
        award_type: Filter by award type
        days: Filter to last N days
    """
    params = []
    where_clauses = []
    param_idx = 1

    resolved_player_guid = None
    if player:
        resolved_player_guid = await resolve_player_guid(db, player)
        if resolved_player_guid:
            where_clauses.append(
                f"COALESCE(ra.player_guid, am.guid) = ${param_idx}"
            )
            params.append(resolved_player_guid)
            param_idx += 1
        else:
            where_clauses.append(f"ra.player_name ILIKE ${param_idx}")
            params.append(f"%{player}%")
            param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    if days > 0:
        where_clauses.append(f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')")
        params.append(days)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get total count + awards (GUID-aware)
    count_query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        )
        SELECT COUNT(*)
        FROM round_awards ra
        LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
        LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
        {where_sql}
    """
    query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        )
        SELECT ra.award_name,
               ra.player_name,
               COALESCE(ra.player_guid, am.guid, nm.player_guid) as player_guid,
               ra.award_value,
               ra.round_date,
               ra.map_name,
               ra.round_number,
               ra.round_id
        FROM round_awards ra
        LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
        LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
        {where_sql}
        ORDER BY ra.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    try:
        count_row = await db.fetch_one(count_query, tuple(params[:-2]))
        total = count_row[0] if count_row else 0
        rows = await db.fetch_all(query, tuple(params))
    except Exception:
        # Fallback if alias table missing
        fallback_where_sql = where_sql.replace("COALESCE(ra.player_guid, am.guid, nm.player_guid)", "ra.player_guid")
        fallback_where_sql = fallback_where_sql.replace("COALESCE(ra.player_guid, am.guid)", "ra.player_guid")
        fallback_count = f"SELECT COUNT(*) FROM round_awards ra {fallback_where_sql}"
        count_row = await db.fetch_one(fallback_count, tuple(params[:-2]))
        total = count_row[0] if count_row else 0
        fallback_query = f"""
            SELECT ra.award_name, ra.player_name, ra.player_guid, ra.award_value,
                   ra.round_date, ra.map_name, ra.round_number, ra.round_id
            FROM round_awards ra
            {fallback_where_sql}
            ORDER BY ra.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        rows = await db.fetch_all(fallback_query, tuple(params))

    return {
        "awards": [
            {
                "award": row[0],
                "player": (
                    await resolve_display_name(db, row[2], row[1] or "Unknown")
                    if row[2]
                    else (row[1] or "Unknown")
                ),
                "guid": row[2],
                "value": row[3],
                "date": row[4],
                "map": row[5],
                "round_number": row[6],
                "round_id": row[7],
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {"player": player, "award_type": award_type, "days": days},
    }

@router.get("/seasons/current/leaders")
async def get_season_leaders(db: DatabaseAdapter = Depends(get_db)):
    """
    Get season leaders for various categories.
    Returns top player in each category for the current season.
    """
    # Get current season date range from SeasonManager
    sm = SeasonManager()
    start_date, end_date = sm.get_season_dates()
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    dmg_given_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(damage_given) as total_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_damage DESC
        LIMIT 1
    """
    dmg_recv_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(damage_received) as total_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_damage DESC
        LIMIT 1
    """
    team_dmg_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(team_damage_given) as total_team_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_team_damage DESC
        LIMIT 1
    """
    fallback_team_dmg = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(team_damage) as total_team_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_team_damage DESC
        LIMIT 1
    """
    revives_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(revives_given) as total_revives
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_revives DESC
        LIMIT 1
    """
    deaths_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(deaths) as total_deaths
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_deaths DESC
        LIMIT 1
    """
    gibs_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(gibs) as total_gibs
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_gibs DESC
        LIMIT 1
    """
    objectives_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(
                    COALESCE(objectives_completed, 0) +
                    COALESCE(objectives_destroyed, 0) +
                    COALESCE(objectives_stolen, 0) +
                    COALESCE(objectives_returned, 0) +
                    COALESCE(dynamites_planted, 0) +
                    COALESCE(dynamites_defused, 0)
               ) as total_objectives
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_objectives DESC
        LIMIT 1
    """
    xp_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(xp) as total_xp
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_xp DESC
        LIMIT 1
    """
    kills_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(kills) as total_kills
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_kills DESC
        LIMIT 1
    """
    dpm_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               ROUND((SUM(damage_given)::numeric / NULLIF(SUM(time_played_seconds), 0) * 60), 1) as dpm
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        HAVING SUM(time_played_seconds) > 600
        ORDER BY dpm DESC
        LIMIT 1
    """
    time_alive_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(time_played_seconds) - SUM(COALESCE(time_dead_minutes, 0) * 60) as time_alive_seconds
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_alive_seconds DESC
        LIMIT 1
    """
    fallback_time_alive = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(time_played_seconds) as time_alive_seconds
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_alive_seconds DESC
        LIMIT 1
    """
    time_dead_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(COALESCE(time_dead_minutes, 0)) as time_dead_minutes
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_dead_minutes DESC
        LIMIT 1
    """
    fallback_time_dead = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(COALESCE(time_dead_minutes, 0)) as time_dead_minutes
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_dead_minutes DESC
        LIMIT 1
    """
    session_query = """
        SELECT gaming_session_id, COUNT(*) as round_count, MIN(round_date) as session_date
        FROM rounds
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY gaming_session_id
        ORDER BY round_count DESC
        LIMIT 1
    """

    def _swap_date_field(query: str, date_field: str) -> str:
        return query.replace("round_date", date_field)

    async def _fetch_one_with_field(query: str, date_field: str):
        try:
            return await db.fetch_one(
                _swap_date_field(query, date_field),
                (start_date_str, end_date_str),
            )
        except Exception:
            return None

    async def _fetch_one_with_fallback(query: str):
        row = await _fetch_one_with_field(query, "round_date")
        if row is None:
            row = await _fetch_one_with_field(query, "session_date")
        return row

    async def fetch_leaders():
        dmg_given = await _fetch_one_with_fallback(dmg_given_query)
        dmg_recv = await _fetch_one_with_fallback(dmg_recv_query)
        team_dmg = await _fetch_one_with_fallback(team_dmg_query)
        if team_dmg is None:
            team_dmg = await _fetch_one_with_fallback(fallback_team_dmg)
        revives = await _fetch_one_with_fallback(revives_query)
        deaths = await _fetch_one_with_fallback(deaths_query)
        gibs = await _fetch_one_with_fallback(gibs_query)
        objectives = await _fetch_one_with_fallback(objectives_query)
        xp = await _fetch_one_with_fallback(xp_query)
        kills = await _fetch_one_with_fallback(kills_query)
        dpm = await _fetch_one_with_fallback(dpm_query)
        time_alive = await _fetch_one_with_fallback(time_alive_query)
        if time_alive is None:
            time_alive = await _fetch_one_with_fallback(fallback_time_alive)
        time_dead = await _fetch_one_with_fallback(time_dead_query)
        if time_dead is None:
            time_dead = await _fetch_one_with_fallback(fallback_time_dead)
        session = await _fetch_one_with_field(session_query, "round_date")
        return {
            "damage_given": dmg_given,
            "damage_received": dmg_recv,
            "team_damage": team_dmg,
            "revives": revives,
            "deaths": deaths,
            "gibs": gibs,
            "objectives": objectives,
            "xp": xp,
            "kills": kills,
            "dpm": dpm,
            "time_alive": time_alive,
            "time_dead": time_dead,
            "session": session,
        }

    leaders_rows = await fetch_leaders()

    dmg_given = leaders_rows["damage_given"]
    dmg_recv = leaders_rows["damage_received"]
    team_dmg = leaders_rows["team_damage"]
    revives = leaders_rows["revives"]
    deaths = leaders_rows["deaths"]
    gibs = leaders_rows["gibs"]
    objectives = leaders_rows["objectives"]
    xp = leaders_rows["xp"]
    kills = leaders_rows["kills"]
    dpm = leaders_rows["dpm"]
    time_alive = leaders_rows["time_alive"]
    time_dead = leaders_rows["time_dead"]
    session = leaders_rows["session"]

    async def leader_payload(row, cast_fn):
        if not row:
            return None
        display_name = await resolve_display_name(db, row[0], row[1] or "Unknown")
        return {"player": display_name, "value": cast_fn(row[2])}

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "leaders": {
            "damage_given": await leader_payload(dmg_given, int),
            "damage_received": await leader_payload(dmg_recv, int),
            "team_damage": await leader_payload(team_dmg, int),
            "revives": await leader_payload(revives, int),
            "deaths": await leader_payload(deaths, int),
            "gibs": await leader_payload(gibs, int),
            "objectives": await leader_payload(objectives, int),
            "xp": await leader_payload(xp, int),
            "kills": await leader_payload(kills, int),
            "dpm": await leader_payload(dpm, float),
            "time_alive": await leader_payload(time_alive, int),
            "time_dead": await leader_payload(time_dead, float),
            "longest_session": {
                "rounds": int(session[1]) if session else 0,
                "date": str(session[2]) if session else None
            } if session else None
        }
    }

@router.get("/rounds/{round_id}/player/{player_guid}/details")
async def get_player_round_details(
    round_id: int,
    player_guid: str,
    db: DatabaseAdapter = Depends(get_db)
):
    """
    Get detailed breakdown for a specific player in a specific round.
    Includes weapon stats, objectives, support stats, and sprees.
    """
    # Get round info
    round_query = "SELECT map_name, round_number, round_date FROM rounds WHERE id = $1"
    round_row = await db.fetch_one(round_query, (round_id,))

    if not round_row:
        raise HTTPException(status_code=404, detail="Round not found")

    map_name, round_number, round_date = round_row

    # Get comprehensive player stats
    stats_query = """
        SELECT
            player_name, kills, deaths, damage_given, damage_received,
            time_played_seconds, headshot_kills, headshots, gibs, revives_given, times_revived,
            accuracy, bullets_fired, team_kills, self_kills,
            most_useful_kills, useless_kills, denied_playtime,
            objectives_stolen, objectives_returned, dynamites_planted, dynamites_defused,
            double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
            time_dead_minutes, xp, kill_assists
        FROM player_comprehensive_stats
        WHERE round_date = $1
          AND map_name = $2
          AND round_number = $3
          AND player_guid = $4
        LIMIT 1
    """
    stats = await db.fetch_one(stats_query, (round_date, map_name, round_number, player_guid))

    if not stats:
        raise HTTPException(status_code=404, detail="Player stats not found")

    # Get weapon stats
    weapon_query = """
        SELECT weapon_name, kills, deaths, headshots, hits, shots, accuracy
        FROM weapon_comprehensive_stats
        WHERE round_date = $1
          AND map_name = $2
          AND round_number = $3
          AND player_guid = $4
        ORDER BY kills DESC
    """
    weapons = await db.fetch_all(weapon_query, (round_date, map_name, round_number, player_guid))
    total_hits = sum((w[4] or 0) for w in weapons)

    (
        player_name,
        kills,
        deaths,
        damage_given,
        damage_received,
        time_played_seconds,
        headshot_kills,
        headshots,
        gibs,
        revives_given,
        times_revived,
        accuracy,
        bullets_fired,
        team_kills,
        self_kills,
        useful_kills,
        useless_kills,
        denied_playtime,
        objectives_stolen,
        objectives_returned,
        dynamites_planted,
        dynamites_defused,
        double_kills,
        triple_kills,
        quad_kills,
        multi_kills,
        mega_kills,
        time_dead_minutes,
        xp,
        kill_assists,
    ) = stats

    # Format response
    return {
        "player_name": player_name,
        "round": {
            "id": round_id,
            "map_name": map_name,
            "round_number": round_number,
            "round_date": str(round_date)
        },
        "combat": {
            "kills": kills or 0,
            "deaths": deaths or 0,
            "damage_given": damage_given or 0,
            "damage_received": damage_received or 0,
            "headshot_kills": headshot_kills or 0,
            "headshots": headshots or 0,
            "gibs": gibs or 0,
            "accuracy": round(accuracy or 0, 1),
            "shots": bullets_fired or 0,
            "hits": total_hits,
        },
        "support": {
            "revives_given": revives_given or 0,
            "times_revived": times_revived or 0,
            "useful_kills": useful_kills or 0,
            "useless_kills": useless_kills or 0,
            "kill_assists": kill_assists or 0,
        },
        "objectives": {
            "stolen": objectives_stolen or 0,
            "returned": objectives_returned or 0,
            "dynamites_planted": dynamites_planted or 0,
            "dynamites_defused": dynamites_defused or 0,
        },
        "sprees": {
            "double_kills": double_kills or 0,
            "triple_kills": triple_kills or 0,
            "quad_kills": quad_kills or 0,
            "multi_kills": multi_kills or 0,
            "mega_kills": mega_kills or 0,
        },
        "time": {
            "played_seconds": time_played_seconds or 0,
            "dead_minutes": time_dead_minutes or 0,
            "denied_playtime": denied_playtime or 0,
        },
        "misc": {
            "xp": xp or 0,
            "team_kills": team_kills or 0,
            "self_kills": self_kills or 0,
        },
        "weapons": [
            {
                "name": w[0],
                "kills": w[1] or 0,
                "deaths": w[2] or 0,
                "headshots": w[3] or 0,
                "hits": w[4] or 0,
                "shots": w[5] or 0,
                "accuracy": round(w[6] or 0, 1)
            }
            for w in weapons
        ]
    }


# ========================================
# HALL OF FAME
# ========================================


@router.get("/hall-of-fame")
async def get_hall_of_fame(
    period: str = "all_time",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    season_id: Optional[int] = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Hall of Fame: top players across multiple stat categories."""
    limit = max(1, min(limit, 100))

    # Build date filter
    date_filter = ""
    params: list = []
    param_idx = 1

    if period == "season" or season_id is not None:
        sm = SeasonManager()
        season_start, season_end = sm.get_season_dates(season_id)
        date_filter = f"AND pcs.round_date >= ${param_idx} AND pcs.round_date <= ${param_idx + 1}"
        params.extend([season_start.strftime("%Y-%m-%d"), season_end.strftime("%Y-%m-%d")])
        param_idx += 2
    elif period == "custom" and start_date and end_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        date_filter = f"AND pcs.round_date >= ${param_idx} AND pcs.round_date <= ${param_idx + 1}"
        params.extend([start_date, end_date])
        param_idx += 2
    elif period == "7d":
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "14d":
        cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "30d":
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "90d":
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    # else: all_time - no date filter

    limit_param = f"${param_idx}"
    params.append(limit)

    try:
        categories = {}

        # --- Simple aggregation categories ---
        simple_cats = {
            "most_active": ("COUNT(*)", "rounds"),
            "most_damage": ("SUM(pcs.damage_given)", "damage"),
            "most_kills": ("SUM(pcs.kills)", "kills"),
            "most_revives": ("SUM(pcs.revives_given)", "revives"),
            "most_xp": ("SUM(pcs.xp)", "xp"),
            "most_assists": ("SUM(pcs.kill_assists)", "assists"),
            "most_deaths": ("SUM(pcs.deaths)", "deaths"),
            "most_selfkills": ("SUM(pcs.self_kills)", "selfkills"),
            "most_full_selfkills": ("SUM(pcs.full_selfkills)", "full_selfkills"),
        }

        for cat_name, (agg_expr, unit) in simple_cats.items():
            # nosec B608 - agg_expr and date_filter are static/controlled strings
            query = f"""
                SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                       {agg_expr} as value
                FROM player_comprehensive_stats pcs
                WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0 {date_filter}
                GROUP BY pcs.player_guid
                ORDER BY value DESC
                LIMIT {limit_param}
            """
            rows = await db.fetch_all(query, tuple(params))
            entries = []
            for rank, row in enumerate(rows, 1):
                name = await resolve_display_name(db, row[0], row[1] or "Unknown")
                entries.append({
                    "rank": rank,
                    "player_guid": row[0],
                    "player_name": name,
                    "value": int(row[2]) if row[2] is not None else 0,
                    "unit": unit,
                })
            categories[cat_name] = entries

        # --- most_wins: join with rounds to check winner_team ---
        wins_query = f"""
            SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                   COUNT(*) as value
            FROM player_comprehensive_stats pcs
            JOIN rounds r ON pcs.round_id = r.id
            WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0
              AND r.winner_team != 0
              AND pcs.team = r.winner_team
              {date_filter}
            GROUP BY pcs.player_guid
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(wins_query, tuple(params))
        entries = []
        for rank, row in enumerate(rows, 1):
            name = await resolve_display_name(db, row[0], row[1] or "Unknown")
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name,
                "value": int(row[2]) if row[2] is not None else 0,
                "unit": "wins",
            })
        categories["most_wins"] = entries

        # --- most_dpm: damage per minute with min 10 rounds ---
        dpm_min_rounds_param = f"${param_idx + 1}"
        dpm_params = list(params) + [10]
        dpm_query = f"""
            SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                   ROUND((SUM(pcs.damage_given)::numeric / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0)), 2) as value,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats pcs
            WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0 {date_filter}
            GROUP BY pcs.player_guid
            HAVING COUNT(*) >= {dpm_min_rounds_param}
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(dpm_query, tuple(dpm_params))
        entries = []
        for rank, row in enumerate(rows, 1):
            name = await resolve_display_name(db, row[0], row[1] or "Unknown")
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name,
                "value": float(row[2]) if row[2] is not None else 0.0,
                "unit": "dpm",
            })
        categories["most_dpm"] = entries

        # --- most_consecutive_games: consecutive gaming sessions ---
        # gaming_session_id lives on rounds, not player_comprehensive_stats
        consec_query = f"""
            WITH player_sessions AS (
                SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                       r.gaming_session_id
                FROM player_comprehensive_stats pcs
                JOIN rounds r ON pcs.round_id = r.id
                WHERE pcs.time_played_seconds > 0
                  AND r.gaming_session_id IS NOT NULL
                  {date_filter}
                GROUP BY pcs.player_guid, r.gaming_session_id
            ),
            all_sessions AS (
                SELECT DISTINCT r2.gaming_session_id
                FROM rounds r2
                JOIN player_comprehensive_stats pcs2 ON pcs2.round_id = r2.id
                WHERE r2.gaming_session_id IS NOT NULL
                  AND pcs2.time_played_seconds > 0
                  {date_filter.replace('pcs.', 'pcs2.')}
                ORDER BY r2.gaming_session_id
            ),
            numbered AS (
                SELECT ps.player_guid, ps.player_name, ps.gaming_session_id,
                       ROW_NUMBER() OVER (ORDER BY a.gaming_session_id) as global_rank,
                       ROW_NUMBER() OVER (PARTITION BY ps.player_guid ORDER BY ps.gaming_session_id) as player_rank
                FROM player_sessions ps
                JOIN all_sessions a ON ps.gaming_session_id = a.gaming_session_id
            ),
            streaks AS (
                SELECT player_guid, MAX(player_name) as player_name,
                       COUNT(*) as streak_len
                FROM numbered
                GROUP BY player_guid, (global_rank - player_rank)
            )
            SELECT player_guid, MAX(player_name) as player_name,
                   MAX(streak_len) as value
            FROM streaks
            GROUP BY player_guid
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(consec_query, tuple(params))
        entries = []
        for rank, row in enumerate(rows, 1):
            name = await resolve_display_name(db, row[0], row[1] or "Unknown")
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name,
                "value": int(row[2]) if row[2] is not None else 0,
                "unit": "sessions",
            })
        categories["most_consecutive_games"] = entries

        return {
            "categories": categories,
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Hall of Fame query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate Hall of Fame data")


# ========================================
# STATS TRENDS
# ========================================


@router.get("/stats/trends")
async def get_stats_trends(
    days: int = 14,
    metrics: str = "rounds,active_players,kills,maps",
    db: DatabaseAdapter = Depends(get_db),
):
    """Time-series trends for activity metrics."""
    days = max(1, min(days, 90))
    requested = {m.strip().lower() for m in metrics.split(",") if m.strip()}

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # Generate full date range
        date_list = []
        current = datetime.now() - timedelta(days=days)
        while current.date() <= datetime.now().date():
            date_list.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        result: Dict[str, Any] = {"dates": date_list}

        if "rounds" in requested or "active_players" in requested or "kills" in requested:
            query = """
                SELECT SUBSTR(CAST(r.round_date AS TEXT), 1, 10) as day,
                       COUNT(DISTINCT r.id) as round_count,
                       COUNT(DISTINCT pcs.player_guid) as player_count,
                       COALESCE(SUM(pcs.kills), 0) as total_kills
                FROM rounds r
                LEFT JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id
                WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) >= $1
                  AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) <= $2
                  AND r.round_number IN (1, 2)
                GROUP BY day
                ORDER BY day
            """
            rows = await db.fetch_all(query, (start_date, end_date))

            day_data = {}
            for row in rows:
                day_data[row[0]] = {
                    "rounds": int(row[1]),
                    "active_players": int(row[2]),
                    "kills": int(row[3]),
                }

            if "rounds" in requested:
                result["rounds"] = [day_data.get(d, {}).get("rounds", 0) for d in date_list]
            if "active_players" in requested:
                result["active_players"] = [day_data.get(d, {}).get("active_players", 0) for d in date_list]
            if "kills" in requested:
                result["kills"] = [day_data.get(d, {}).get("kills", 0) for d in date_list]

        if "maps" in requested:
            map_query = """
                SELECT r.map_name, COUNT(*) as play_count
                FROM rounds r
                WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) >= $1
                  AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) <= $2
                  AND r.round_number IN (1, 2)
                  AND r.map_name IS NOT NULL
                  AND TRIM(CAST(r.map_name AS TEXT)) <> ''
                GROUP BY r.map_name
                ORDER BY play_count DESC
            """
            map_rows = await db.fetch_all(map_query, (start_date, end_date))
            map_distribution: Dict[str, int] = {}
            for row in map_rows:
                normalized_map_name = _normalize_map_name(row[0])
                if not normalized_map_name:
                    continue

                play_count = int(row[1]) if row[1] is not None else 0
                if play_count <= 0:
                    continue

                map_distribution[normalized_map_name] = (
                    map_distribution.get(normalized_map_name, 0) + play_count
                )

            result["map_distribution"] = dict(
                sorted(
                    map_distribution.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            )

        return result

    except Exception as e:
        logger.error(f"Stats trends query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate trends data")


# ========================================
# RETRO-VIZ GALLERY
# ========================================


@router.get("/retro-viz/gallery")
async def get_retro_viz_gallery():
    """List PNG files in the retro-viz output directory."""
    gallery_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "retro-viz")
    gallery_dir = os.path.normpath(gallery_dir)

    if not os.path.isdir(gallery_dir):
        return {"images": []}

    images = []
    try:
        for fname in sorted(os.listdir(gallery_dir)):
            if not fname.lower().endswith(".png"):
                continue
            fpath = os.path.join(gallery_dir, fname)
            if not os.path.isfile(fpath):
                continue
            # Prevent symlink traversal outside gallery directory
            if not os.path.realpath(fpath).startswith(os.path.realpath(gallery_dir)):
                continue
            stat = os.stat(fpath)
            images.append({
                "filename": fname,
                "url": f"/data/retro-viz/{fname}",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.error(f"Retro-viz gallery listing failed: {e}")

    return {"images": images}


# ========================================
# ROUND VISUALIZATION
# ========================================


def _serialize_round_label(round_number: Any) -> str:
    """Convert round numbers to UI-safe labels."""
    if round_number is None:
        return "R?"
    try:
        normalized = int(round_number)
    except (TypeError, ValueError):
        return "R?"
    if normalized == 0:
        return "Match Summary"
    return f"R{normalized}"


@router.get("/rounds/recent")
async def get_recent_rounds(
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Return recent rounds for the round picker dropdown."""
    if limit < 1 or limit > 100:
        limit = 20

    rows = await db.fetch_all(
        """
        SELECT r.id, r.map_name, r.round_date, r.round_number,
               COUNT(pcs.id) AS player_count
        FROM rounds r
        JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id
        WHERE r.round_number > 0
        GROUP BY r.id, r.map_name, r.round_date, r.round_number
        ORDER BY r.id DESC
        LIMIT $1
        """,
        (limit,),
    )

    return [
        {
            "id": row[0],
            "map_name": row[1],
            "round_date": str(row[2]) if row[2] else None,
            "round_number": row[3],
            "round_label": _serialize_round_label(row[3]),
            "player_count": row[4],
        }
        for row in rows
    ]


@router.get("/rounds/{round_id}/viz")
async def get_round_viz(
    round_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Return all player data for a single round, shaped for the 6 chart components."""

    # Get round info
    round_row = await db.fetch_one(
        """
        SELECT id, map_name, round_date, round_number, winner_team,
               actual_duration_seconds
        FROM rounds WHERE id = $1
        """,
        (round_id,),
    )
    if not round_row:
        raise HTTPException(status_code=404, detail="Round not found")

    # Get all player stats for this round
    rows = await db.fetch_all(
        """
        SELECT player_name, player_guid, kills, deaths,
               damage_given, damage_received, team_damage_given,
               team_damage_received, time_played_seconds,
               ROUND(COALESCE(time_dead_minutes, 0) * 60)::int AS time_dead_seconds,
               COALESCE(revives_given, 0) AS revives_given,
               COALESCE(gibs, 0) AS gibs,
               COALESCE(self_kills, 0) AS self_kills,
               COALESCE(denied_playtime, 0) AS denied_playtime,
               COALESCE(xp, 0) AS xp,
               COALESCE(kill_assists, 0) AS kill_assists,
               COALESCE(efficiency, 0) AS efficiency,
               COALESCE(dpm, 0) AS dpm
        FROM player_comprehensive_stats
        WHERE round_id = $1
        ORDER BY kills DESC
        """,
        (round_id,),
    )

    players = []
    for r in rows:
        players.append({
            "name": r[0],
            "guid": r[1],
            "kills": r[2] or 0,
            "deaths": r[3] or 0,
            "damage_given": r[4] or 0,
            "damage_received": r[5] or 0,
            "team_damage_given": r[6] or 0,
            "team_damage_received": r[7] or 0,
            "time_played_seconds": r[8] or 0,
            "time_dead_seconds": r[9] or 0,
            "revives_given": r[10],
            "gibs": r[11],
            "self_kills": r[12],
            "denied_playtime": r[13],
            "xp": r[14],
            "kill_assists": r[15],
            "efficiency": float(r[16]),
            "dpm": float(r[17]),
        })

    # Compute highlights
    highlights = {}
    if players:
        mvp = max(players, key=lambda p: p["dpm"])
        highlights["mvp"] = {"name": mvp["name"], "dpm": mvp["dpm"]}
        top_kills = max(players, key=lambda p: p["kills"])
        highlights["most_kills"] = {"name": top_kills["name"], "kills": top_kills["kills"]}
        top_dmg = max(players, key=lambda p: p["damage_given"])
        highlights["most_damage"] = {"name": top_dmg["name"], "damage_given": top_dmg["damage_given"]}

    return {
        "round_id": round_row[0],
        "map_name": round_row[1],
        "round_date": str(round_row[2]) if round_row[2] else None,
        "round_number": round_row[3],
        "round_label": _serialize_round_label(round_row[3]),
        "winner_team": round_row[4],
        "duration_seconds": round_row[5],
        "player_count": len(players),
        "players": players,
        "highlights": highlights,
    }


# ========================================
# GEMINI SESSIONS API (P0 Redesign)
# ========================================


@router.get("/stats/sessions")
async def get_stats_sessions(
    limit: int = Query(default=20, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    search: str = "",
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get list of gaming sessions for the Gemini frontend.
    Supports search by map name or player name.
    Returns richer data than /sessions endpoint: timing, scores, duration.
    """
    search_filter = ""
    search_params: list = []
    param_idx = 1  # PostgreSQL $1, $2, ...

    if search.strip():
        safe_search = escape_like_pattern(search.strip())
        search_filter = f"""
            AND (
                sr.gaming_session_id IN (
                    SELECT r2.gaming_session_id FROM rounds r2
                    WHERE r2.gaming_session_id IS NOT NULL
                      AND r2.round_number IN (1, 2)
                      AND LOWER(r2.map_name) LIKE LOWER(${param_idx})
                )
                OR sr.gaming_session_id IN (
                    SELECT r3.gaming_session_id FROM rounds r3
                    INNER JOIN player_comprehensive_stats p2 ON p2.round_id = r3.id
                    WHERE r3.gaming_session_id IS NOT NULL
                      AND r3.round_number IN (1, 2)
                      AND LOWER(p2.player_name) LIKE LOWER(${param_idx})
                )
            )
        """
        search_params.append(f"%{safe_search}%")
        param_idx += 1

    limit_param = f"${param_idx}"
    offset_param = f"${param_idx + 1}"

    query = f"""
        WITH session_rounds AS (
            SELECT
                r.gaming_session_id,
                MIN(r.round_date) as first_date,
                MAX(r.round_date) as last_date,
                MIN(r.round_time) as first_time,
                MAX(r.round_time) as last_time,
                COUNT(r.id) as round_count,
                STRING_AGG(DISTINCT r.map_name, ', ' ORDER BY r.map_name) as maps_played,
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 1 THEN 1 END) as allies_wins,
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 2 THEN 1 END) as axis_wins
            FROM rounds r
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_players AS (
            SELECT
                r.gaming_session_id,
                COUNT(DISTINCT p.player_guid) as player_count,
                COALESCE(SUM(p.kills), 0) as total_kills,
                COALESCE(SUM(p.deaths), 0) as total_deaths
            FROM rounds r
            INNER JOIN player_comprehensive_stats p ON p.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_duration AS (
            SELECT
                r.gaming_session_id,
                COALESCE(SUM(lrt.actual_duration_seconds), 0) as total_duration_seconds
            FROM rounds r
            LEFT JOIN lua_round_teams lrt ON lrt.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_names AS (
            SELECT
                r.gaming_session_id,
                STRING_AGG(DISTINCT p.player_name, ', ' ORDER BY p.player_name) as player_names
            FROM rounds r
            INNER JOIN player_comprehensive_stats p ON p.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        )
        SELECT
            sr.gaming_session_id,
            sr.first_date,
            sr.last_date,
            sr.first_time,
            sr.last_time,
            sr.round_count,
            sr.maps_played,
            sr.allies_wins,
            sr.axis_wins,
            COALESCE(sp.player_count, 0) as player_count,
            COALESCE(sp.total_kills, 0) as total_kills,
            COALESCE(sp.total_deaths, 0) as total_deaths,
            COALESCE(sd.total_duration_seconds, 0) as duration_seconds,
            COALESCE(sn.player_names, '') as player_names
        FROM session_rounds sr
        LEFT JOIN session_players sp ON sr.gaming_session_id = sp.gaming_session_id
        LEFT JOIN session_duration sd ON sr.gaming_session_id = sd.gaming_session_id
        LEFT JOIN session_names sn ON sr.gaming_session_id = sn.gaming_session_id
        WHERE 1=1
        {search_filter}
        ORDER BY sr.gaming_session_id DESC
        LIMIT {limit_param} OFFSET {offset_param}
    """

    params = tuple(search_params + [limit, offset])

    try:
        rows = await db.fetch_all(query, params)
    except Exception as e:
        logger.error(f"Error fetching stats sessions: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    sessions = []
    for row in rows:
        session_id = row[0]
        first_date = row[1]
        first_time = str(row[3]) if row[3] else ""
        last_time = str(row[4]) if row[4] else ""
        round_count = row[5]
        maps_str = row[6]
        allies_wins = row[7]
        axis_wins = row[8]
        player_count = row[9]
        total_kills = row[10]
        total_deaths = row[11]
        duration_seconds = row[12]
        player_names_str = row[13] if len(row) > 13 else ""

        # Format date
        if isinstance(first_date, str):
            dt = datetime.strptime(first_date[:10], "%Y-%m-%d")
        else:
            dt = datetime.combine(first_date, datetime.min.time())

        # Format start/end times
        start_time_str = ""
        end_time_str = ""
        if first_time and len(first_time) >= 6:
            ft = first_time.replace(":", "")[:6]
            start_time_str = f"{ft[:2]}:{ft[2:4]}"
        if last_time and len(last_time) >= 6:
            lt = last_time.replace(":", "")[:6]
            end_time_str = f"{lt[:2]}:{lt[2:4]}"

        # Time ago
        now = datetime.now()
        diff = now - dt
        days = diff.days
        if days == 0:
            time_ago = "Today"
        elif days == 1:
            time_ago = "Yesterday"
        elif days < 7:
            time_ago = f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            time_ago = f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            time_ago = dt.strftime("%b %d, %Y")

        maps_played = [m.strip() for m in maps_str.split(",")] if maps_str else []
        player_names = [n.strip() for n in player_names_str.split(",")] if player_names_str else []

        sessions.append({
            "session_id": session_id,
            "date": str(first_date),
            "formatted_date": dt.strftime("%A, %B %d, %Y"),
            "time_ago": time_ago,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "round_count": round_count,
            "player_count": player_count,
            "maps_played": maps_played,
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "allies_wins": allies_wins,
            "axis_wins": axis_wins,
            "duration_seconds": duration_seconds,
            "player_names": player_names,
        })

    return sessions


@router.get("/stats/session/{gaming_session_id}/detail")
async def get_stats_session_detail(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get full session detail by gaming_session_id.
    Returns matches (grouped R1+R2), per-player stats, round metadata.
    """
    # 1. Get all rounds for this session (R1 and R2 only, exclude R0 summaries)
    rounds_query = """
        SELECT r.id, r.map_name, r.round_number, r.winner_team,
               r.round_date, r.round_time, r.actual_time, r.round_start_unix
        FROM rounds r
        WHERE r.gaming_session_id = $1
          AND r.round_number IN (1, 2)
          AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
        ORDER BY r.round_date, CAST(REPLACE(r.round_time, ':', '') AS INTEGER)
    """
    round_rows = await db.fetch_all(rounds_query, (gaming_session_id,))

    if not round_rows:
        raise HTTPException(status_code=404, detail="Session not found")

    round_ids = [r[0] for r in round_rows]
    placeholders = ", ".join(f"${i+1}" for i in range(len(round_ids)))

    # 2. Get lua_round_teams data for scores and duration
    lua_query = f"""
        SELECT round_id, round_number, allies_score, axis_score,
               actual_duration_seconds, winner_team, map_name
        FROM lua_round_teams
        WHERE round_id IN ({placeholders})
    """
    lua_rows = await db.fetch_all(lua_query, tuple(round_ids))
    lua_by_round = {}
    for lr in lua_rows:
        lua_by_round[lr[0]] = {
            "round_number": lr[1],
            "allies_score": lr[2],
            "axis_score": lr[3],
            "duration_seconds": lr[4],
            "winner_team": lr[5],
        }

    # 3. Build matches (group rounds by map in order of play)
    matches = []
    current_map = None
    current_rounds = []

    for rr in round_rows:
        round_id = rr[0]
        map_name = _normalize_map_name(rr[1])
        round_number = rr[2]
        winner_team = rr[3]
        round_date = str(rr[4]) if rr[4] else None
        round_time = str(rr[5]) if rr[5] else None

        lua = lua_by_round.get(round_id, {})
        # Parse actual_time (MM:SS string) as fallback if lua duration missing
        actual_time_raw = rr[6]
        actual_time_seconds = None
        if actual_time_raw:
            try:
                parts = str(actual_time_raw).split(":")
                if len(parts) == 2:
                    actual_time_seconds = int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                pass  # actual_time format not M:SS — use default 0
        duration = lua.get("duration_seconds") or actual_time_seconds

        round_obj = {
            "round_id": round_id,
            "round_number": round_number,
            "map_name": map_name,
            "winner_team": winner_team,
            "allies_score": lua.get("allies_score"),
            "axis_score": lua.get("axis_score"),
            "duration_seconds": duration,
            "round_date": round_date,
            "round_time": round_time,
            "round_start_unix": rr[7] or 0,
        }

        # Group consecutive rounds on same map into a match
        # But R1 after R2 on same map = new match (replayed map)
        is_new_match = (
            current_map != map_name
            or (round_number == 1 and current_rounds and current_rounds[-1]["round_number"] == 2)
        )
        if not is_new_match:
            current_rounds.append(round_obj)
        else:
            if current_rounds:
                matches.append({
                    "map_name": current_map,
                    "rounds": current_rounds,
                })
            current_map = map_name
            current_rounds = [round_obj]

    if current_rounds:
        matches.append({
            "map_name": current_map,
            "rounds": current_rounds,
        })

    # 4. Get per-player stats aggregated across session
    player_query = f"""
        SELECT
            p.player_guid,
            MAX(p.player_name) as player_name,
            SUM(p.kills) as kills,
            SUM(p.deaths) as deaths,
            SUM(p.damage_given) as damage_given,
            SUM(p.damage_received) as damage_received,
            CASE
                WHEN SUM(p.time_played_seconds) > 0
                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                ELSE 0
            END as dpm,
            CASE
                WHEN SUM(p.deaths) > 0
                THEN ROUND(SUM(p.kills)::numeric / SUM(p.deaths), 2)
                ELSE SUM(p.kills)::numeric
            END as kd,
            SUM(p.headshot_kills) as headshot_kills,
            SUM(p.kills) as total_kills_for_hs,
            SUM(p.gibs) as gibs,
            SUM(p.self_kills) as self_kills,
            SUM(p.revives_given) as revives_given,
            SUM(p.times_revived) as times_revived,
            SUM(p.time_played_seconds) as time_played_seconds,
            SUM(p.kill_assists) as kill_assists,
            SUM(p.time_dead_minutes) as time_dead_minutes,
            SUM(p.denied_playtime) as denied_playtime,
            COALESCE(SUM(w.hits), 0) as total_hits,
            COALESCE(SUM(w.shots), 0) as total_shots,
            COALESCE(SUM(w.headshots), 0) as weapon_headshots,
            SUM(p.time_played_percent * p.time_played_seconds) as tpp_weighted_sum,
            SUM(CASE WHEN p.time_played_percent > 0 THEN p.time_played_seconds ELSE 0 END) as tpp_weight
        FROM player_comprehensive_stats p
        LEFT JOIN (
            SELECT round_id, player_guid,
                SUM(hits) as hits, SUM(shots) as shots, SUM(headshots) as headshots
            FROM weapon_comprehensive_stats
            WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE',
                                      'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
            GROUP BY round_id, player_guid
        ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
        WHERE p.round_id IN ({placeholders})
        GROUP BY p.player_guid
        ORDER BY dpm DESC
    """
    player_rows = await db.fetch_all(player_query, tuple(round_ids))

    # Use duration from matches (lua fallback to actual_time) for all rounds
    total_session_duration_seconds = sum(
        round_obj.get("duration_seconds") or 0
        for match in matches
        for round_obj in match["rounds"]
    )

    players = []
    for pr in player_rows:
        kills = pr[2] or 0
        deaths = pr[3] or 0
        damage_given = pr[4] or 0
        damage_received = pr[5] or 0
        dpm = round(float(pr[6]), 1) if pr[6] else 0
        kd = float(pr[7]) if pr[7] else 0
        headshot_kills = pr[8] or 0
        total_kills_for_hs = pr[9] or 0
        gibs = pr[10] or 0
        self_kills = pr[11] or 0
        revives_given = pr[12] or 0
        times_revived = pr[13] or 0
        time_played_seconds = pr[14] or 0
        kill_assists = pr[15] or 0
        time_dead_minutes = float(pr[16]) if pr[16] else 0.0
        denied_playtime = pr[17] or 0
        total_hits = pr[18] or 0
        total_shots = pr[19] or 0
        weapon_headshots = pr[20] or 0
        tpp_weighted_sum = float(pr[21]) if pr[21] else 0.0
        tpp_weight = float(pr[22]) if pr[22] else 0.0

        hs_pct = round((weapon_headshots / total_hits * 100), 1) if total_hits > 0 else 0
        accuracy = round((total_hits / total_shots * 100), 1) if total_shots > 0 else 0
        efficiency = round((kills / (kills + deaths) * 100), 1) if (kills + deaths) > 0 else 0
        time_played_minutes = time_played_seconds / 60.0

        # Computed alive% (fallback — ignores limbo time, underestimates)
        alive_pct_computed = round(max(0.0, 100.0 - (time_dead_minutes / time_played_minutes * 100.0)), 1) if time_played_minutes > 0 else None

        # Engine alive% from TAB[8] (correct — excludes dead + limbo time)
        alive_pct_engine = round(tpp_weighted_sum / tpp_weight, 1) if tpp_weight > 0 else None

        # Primary: prefer engine value, fallback to computed
        alive_pct = alive_pct_engine if alive_pct_engine is not None else alive_pct_computed

        # Drift detection between sources
        alive_pct_diff = round(abs(alive_pct_engine - alive_pct_computed), 1) if (alive_pct_engine is not None and alive_pct_computed is not None) else None
        alive_pct_drift = (alive_pct_diff is not None and alive_pct_diff > 2.0)

        played_pct = min(100.0, round((time_played_seconds / total_session_duration_seconds) * 100.0, 1)) if total_session_duration_seconds > 0 else None

        players.append({
            "player_guid": pr[0],
            "player_name": pr[1],
            "kills": kills,
            "deaths": deaths,
            "damage_given": damage_given,
            "damage_received": damage_received,
            "dpm": dpm,
            "kd": kd,
            "efficiency": efficiency,
            "headshot_kills": headshot_kills,
            "headshot_pct": hs_pct,
            "gibs": gibs,
            "self_kills": self_kills,
            "revives_given": revives_given,
            "times_revived": times_revived,
            "kill_assists": kill_assists,
            "accuracy": accuracy,
            "time_played_seconds": time_played_seconds,
            "time_dead_minutes": round(time_dead_minutes, 2),
            "denied_playtime": denied_playtime,
            "alive_pct": alive_pct,
            "alive_pct_lua": alive_pct_engine,
            "alive_pct_diff": alive_pct_diff,
            "alive_pct_drift": alive_pct_drift,
            "played_pct": played_pct,
            "played_pct_lua": played_pct,  # same source (engine time), kept for frontend compat
        })

    # 5. Scoring — reuse StopwatchScoringService for team-aware map scoring
    first_date = round_rows[0][4] if round_rows else None
    scoring_payload = {"available": False}
    try:
        config = load_config()
        db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
        service = SessionDataService(db, db_path)
        scoring_service = StopwatchScoringService(db)
        session_date = str(first_date) if first_date else None
        if session_date:
            scoring_payload, _, _ = await build_session_scoring(
                session_date, round_ids, service, scoring_service
            )
    except Exception as e:
        logger.warning(f"Scoring unavailable for session {gaming_session_id}: {e}")

    return {
        "session_id": gaming_session_id,
        "date": str(first_date) if first_date else None,
        "player_count": len(players),
        "round_count": len(round_ids),
        "matches": matches,
        "players": players,
        "scoring": scoring_payload,
    }

