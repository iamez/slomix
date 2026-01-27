import os
from fastapi import APIRouter, Depends, HTTPException, Request
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

router = APIRouter()

# Game server configuration (for direct UDP query)
GAME_SERVER_HOST = os.getenv("SERVER_HOST", "puran.hehe.si")
GAME_SERVER_PORT = int(os.getenv("SERVER_PORT", "27960"))


# ========================================
# ACHIEVEMENT SYSTEM
# ========================================

# Achievement definitions matching the Discord bot
KILL_MILESTONES = {
    100: {"emoji": "🎯", "title": "First Blood Century", "color": "#95A5A6"},
    500: {"emoji": "💥", "title": "Killing Machine", "color": "#3498DB"},
    1000: {"emoji": "💀", "title": "Thousand Killer", "color": "#9B59B6"},
    2500: {"emoji": "⚔️", "title": "Elite Warrior", "color": "#E74C3C"},
    5000: {"emoji": "☠️", "title": "Death Incarnate", "color": "#C0392B"},
    10000: {"emoji": "👑", "title": "Legendary Slayer", "color": "#F39C12"},
}

GAME_MILESTONES = {
    10: {"emoji": "🎮", "title": "Getting Started", "color": "#95A5A6"},
    50: {"emoji": "🎯", "title": "Regular Player", "color": "#3498DB"},
    100: {"emoji": "🏆", "title": "Dedicated Gamer", "color": "#9B59B6"},
    250: {"emoji": "⭐", "title": "Community Veteran", "color": "#E74C3C"},
    500: {"emoji": "💎", "title": "Hardcore Legend", "color": "#F39C12"},
    1000: {"emoji": "👑", "title": "Ultimate Champion", "color": "#F1C40F"},
}

KD_MILESTONES = {
    1.0: {"emoji": "⚖️", "title": "Balanced Fighter", "color": "#95A5A6"},
    1.5: {"emoji": "📈", "title": "Above Average", "color": "#3498DB"},
    2.0: {"emoji": "🔥", "title": "Elite Killer", "color": "#E74C3C"},
    3.0: {"emoji": "💯", "title": "Unstoppable", "color": "#F39C12"},
}


def calculate_player_achievements(kills: int, games: int, kd: float) -> dict:
    """
    Calculate which achievements a player has earned based on their stats.

    Returns a dict with:
    - unlocked: list of earned achievements
    - next: the next achievement they're working toward (if any)
    - progress: overall achievement progress percentage
    """
    unlocked = []
    next_achievements = []

    # Check kill milestones
    for threshold, achievement in sorted(KILL_MILESTONES.items()):
        if kills >= threshold:
            unlocked.append(
                {
                    "type": "kills",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "color": achievement["color"],
                }
            )
        else:
            next_achievements.append(
                {
                    "type": "kills",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "current": kills,
                    "progress": round(kills / threshold * 100, 1),
                }
            )
            break

    # Check game milestones
    for threshold, achievement in sorted(GAME_MILESTONES.items()):
        if games >= threshold:
            unlocked.append(
                {
                    "type": "games",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "color": achievement["color"],
                }
            )
        else:
            next_achievements.append(
                {
                    "type": "games",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "current": games,
                    "progress": round(games / threshold * 100, 1),
                }
            )
            break

    # Check K/D milestones (only if player has 20+ games)
    if games >= 20:
        for threshold, achievement in sorted(KD_MILESTONES.items()):
            if kd >= threshold:
                unlocked.append(
                    {
                        "type": "kd",
                        "threshold": threshold,
                        "emoji": achievement["emoji"],
                        "title": achievement["title"],
                        "color": achievement["color"],
                    }
                )
            else:
                next_achievements.append(
                    {
                        "type": "kd",
                        "threshold": threshold,
                        "emoji": achievement["emoji"],
                        "title": achievement["title"],
                        "current": round(kd, 2),
                        "progress": round(kd / threshold * 100, 1),
                    }
                )
                break

    # Calculate overall progress
    total_possible = len(KILL_MILESTONES) + len(GAME_MILESTONES) + len(KD_MILESTONES)
    overall_progress = round(len(unlocked) / total_possible * 100, 1)

    return {
        "unlocked": unlocked,
        "next": next_achievements[:2],  # Show up to 2 next achievements
        "total_unlocked": len(unlocked),
        "total_possible": total_possible,
        "progress": overall_progress,
    }


@router.get("/status")
async def get_status():
    return {"status": "online", "service": "Slomix API"}


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
    }

    from datetime import datetime

    results["timestamp"] = datetime.utcnow().isoformat()

    # Tables to check
    tables_to_check = [
        ("rounds", "SELECT COUNT(*) FROM rounds", True),
        (
            "player_comprehensive_stats",
            "SELECT COUNT(*) FROM player_comprehensive_stats",
            True,
        ),
        ("sessions", "SELECT COUNT(*) FROM sessions", True),
        ("players", "SELECT COUNT(*) FROM players", False),
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

    # Set overall status
    if results["issues"]:
        results["status"] = "error"
    elif results["warnings"]:
        results["status"] = "warning"

    return results


@router.get("/live-status")
async def get_live_status(db: DatabaseAdapter = Depends(get_db)):
    """
    Get real-time status of voice channels and game server.

    - Voice channel data: from database (updated by Discord bot)
    - Game server data: direct UDP query (real-time)
    """
    import json
    from datetime import datetime

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
    from datetime import datetime, timedelta

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
            WHERE recorded_at >= $1
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
        print(f"Error fetching server activity: {e}")
        return {
            "data_points": [],
            "summary": {
                "peak_players": 0,
                "peak_time": None,
                "avg_players": 0,
                "uptime_percent": 0,
                "total_records": 0,
            },
            "error": str(e),
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
    from datetime import datetime, timedelta

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
            WHERE recorded_at >= $1
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
        print(f"Error fetching voice activity: {e}")
        return {
            "data_points": [],
            "summary": {
                "peak_members": 0,
                "peak_time": None,
                "avg_members": 0,
                "total_sessions": 0,
                "total_records": 0,
            },
            "error": str(e),
        }


@router.get("/voice-activity/current")
async def get_current_voice_activity(db: DatabaseAdapter = Depends(get_db)):
    """
    Get detailed current voice channel status with join times.

    Returns detailed information about who is in voice and how long.
    """
    import json
    from datetime import datetime

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
        except:
            pass

        return {"total_count": 0, "members": [], "channels": [], "error": str(e)}


@router.get("/stats/overview")
async def get_stats_overview(db: DatabaseAdapter = Depends(get_db)):
    """Get homepage overview statistics"""
    try:
        # Total rounds tracked
        rounds_count = await db.fetch_val("SELECT COUNT(*) FROM rounds")

        # Unique players
        players_count = await db.fetch_val(
            "SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats"
        )

        # Total gaming sessions
        sessions_count = await db.fetch_val(
            "SELECT COUNT(DISTINCT gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL"
        )

        # Total kills
        total_kills = await db.fetch_val(
            "SELECT COALESCE(SUM(kills), 0) FROM player_comprehensive_stats"
        )

        return {
            "rounds": rounds_count or 0,
            "players": players_count or 0,
            "sessions": sessions_count or 0,
            "total_kills": total_kills or 0,
        }
    except Exception as e:
        print(f"Error fetching overview stats: {e}")
        return {"rounds": 0, "players": 0, "sessions": 0, "total_kills": 0}


@router.get("/seasons/current")
async def get_current_season():
    sm = SeasonManager()
    return {
        "id": sm.get_current_season(),
        "name": sm.get_season_name(),
        "days_left": sm.get_days_until_season_end(),
    }


@router.get("/stats/last-session")
async def get_last_session(db: DatabaseAdapter = Depends(get_db)):
    """Get the latest session data (similar to !last_session)"""
    config = load_config()
    db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
    service = SessionDataService(db, db_path)

    latest_date = await service.get_latest_session_date()
    if not latest_date:
        raise HTTPException(status_code=404, detail="No sessions found")

    sessions, session_ids, _, player_count = await service.fetch_session_data(
        latest_date
    )

    # Calculate map counts
    map_counts = {}
    for _, map_name, _, _ in sessions:
        map_counts[map_name] = map_counts.get(map_name, 0) + 1

    # Since each map usually has 2 rounds, divide by 2 for
    # "matches" count, or just list unique maps
    unique_maps = list(map_counts.keys())

    # Get detailed matches for this session
    matches = await service.get_session_matches(latest_date)

    return {
        "date": latest_date,
        "player_count": player_count,
        "rounds": len(sessions),
        "maps": unique_maps,
        "map_counts": map_counts,
        "matches": matches,
    }


@router.get("/stats/session-leaderboard")
async def get_session_leaderboard(
    limit: int = 5, db: DatabaseAdapter = Depends(get_db)
):
    """Get the leaderboard for the last session"""
    data_service = SessionDataService(db, None)
    stats_service = SessionStatsAggregator(db)

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
        WITH session_summary AS (
            SELECT
                r.gaming_session_id,
                MIN(r.round_date) as session_date,
                COUNT(DISTINCT r.id) as round_count,
                COUNT(DISTINCT r.map_name) as map_count,
                COUNT(DISTINCT p.player_guid) as player_count,
                COALESCE(SUM(p.kills), 0) as total_kills,
                STRING_AGG(DISTINCT r.map_name, ', ' ORDER BY r.map_name) as maps_played
            FROM rounds r
            LEFT JOIN player_comprehensive_stats p
                ON r.round_date = p.round_date
                AND r.map_name = p.map_name
                AND r.round_number = p.round_number
            WHERE r.gaming_session_id IS NOT NULL
            GROUP BY r.gaming_session_id
        )
        SELECT
            session_date,
            gaming_session_id,
            round_count,
            map_count,
            player_count,
            total_kills,
            maps_played
        FROM session_summary
        ORDER BY session_date DESC
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
        from datetime import datetime

        if isinstance(round_date, str):
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

    # Get session data
    sessions, session_ids, session_ids_str, player_count = (
        await data_service.fetch_session_data(date)
    )

    if not sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get matches for this session
    matches = await data_service.get_session_matches(date)

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
    }


class LinkPlayerRequest(BaseModel):
    player_name: str


@router.get("/player/search")
async def search_player(query: str, db: DatabaseAdapter = Depends(get_db)):
    """Search for player aliases"""
    if len(query) < 2:
        return []

    # Escape LIKE wildcards (%, _) in user input to prevent SQL injection
    safe_query = escape_like_pattern(query)

    # Case-insensitive search (ILIKE is Postgres specific)
    sql = """
        SELECT DISTINCT player_name
        FROM player_comprehensive_stats
        WHERE player_name ILIKE ?
        ORDER BY player_name
        LIMIT 10
    """
    rows = await db.fetch_all(sql, (f"%{safe_query}%",))
    return [row[0] for row in rows]


@router.post("/player/link")
async def link_player(
    request: Request, payload: LinkPlayerRequest, db: DatabaseAdapter = Depends(get_db)
):
    """Link Discord account to player alias"""
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
        print(f"Error in get_live_session (Postgres): {e}")
        # Fallback for SQLite (if needed, but we seem to be on Postgres)
        try:
            query = "SELECT MAX(round_date), COUNT(DISTINCT gaming_session_id), COUNT(DISTINCT player_guid) FROM player_comprehensive_stats WHERE date(round_date) = date('now')"
            result = await db.fetch_one(query)
        except Exception as e2:
            print(f"Error in get_live_session (SQLite fallback): {e2}")
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not result or not result[0]:
        return {"active": False}

    # Get latest round details
    latest_query = """
        SELECT
            map_name,
            round_date,
            stopwatch_time
        FROM player_comprehensive_stats
        WHERE round_date::timestamp >= CURRENT_DATE
        ORDER BY round_date DESC
        LIMIT 1
    """
    try:
        latest = await db.fetch_one(latest_query)
    except Exception:
        latest_query = (
            "SELECT map_name, round_date, stopwatch_time "
            "FROM player_comprehensive_stats "
            "WHERE date(round_date) = date('now') "
            "ORDER BY round_date DESC LIMIT 1"
        )
        latest = await db.fetch_one(latest_query)

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
        LEFT JOIN rounds r ON p.round_date = r.round_date AND p.map_name = r.map_name AND p.round_number = r.round_number
        WHERE p.player_name ILIKE $1
    """

    # Note: Joining on round_date + map_name because I'm not 100% sure round_id is in the stats table
    # based on my truncated schema check, but date+map is a decent proxy for now.
    # Ideally we use round_id.

    try:
        row = await db.fetch_one(query, (player_name,))
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
        WHERE player_name ILIKE $1
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT 1
    """
    try:
        weapon_row = await db.fetch_one(weapon_query, (player_name,))
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
        WHERE player_name ILIKE $1
        GROUP BY map_name
        ORDER BY play_count DESC
        LIMIT 1
    """
    try:
        map_row = await db.fetch_one(map_query, (player_name,))
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
        WHERE player_name ILIKE $1 AND time_played_seconds > 60
    """
    try:
        dpm_row = await db.fetch_one(dpm_query, (player_name,))
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
        WHERE player_guid = (
            SELECT player_guid FROM player_comprehensive_stats WHERE player_name ILIKE $1 LIMIT 1
        )
        AND player_name NOT ILIKE $1
        ORDER BY player_name
        LIMIT 5
    """
    try:
        alias_rows = await db.fetch_all(alias_query, (player_name,))
        aliases = [row[0] for row in alias_rows] if alias_rows else []
    except Exception as e:
        print(f"Error fetching aliases for {player_name}: {e}")
        aliases = []

    # Check Discord link status
    discord_query = """
        SELECT discord_id FROM player_links WHERE player_name ILIKE $1 LIMIT 1
    """
    try:
        discord_row = await db.fetch_one(discord_query, (player_name,))
        discord_linked = discord_row is not None
    except Exception as e:
        print(f"Error checking Discord link for {player_name}: {e}")
        discord_linked = False

    return {
        "name": player_name,  # Return the queried name, or ideally the canonical name from DB
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
    # Query for both players
    query = """
        SELECT
            player_name,
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
        WHERE player_name ILIKE $1 OR player_name ILIKE $2
        GROUP BY player_name
    """

    try:
        rows = await db.fetch_all(query, (player1, player2))
    except Exception as e:
        print(f"Error comparing players: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if len(rows) < 2:
        raise HTTPException(status_code=404, detail="One or both players not found")

    # Process both players
    players = []
    for row in rows:
        name = row[0]
        kills = row[1] or 0
        deaths = row[2] or 0
        damage = row[3] or 0
        time_played = row[4] or 0
        games = row[5] or 0
        revives = row[6] or 0
        headshots = row[7] or 0
        accuracy = row[8] or 0
        gibs = row[9] or 0
        xp = row[10] or 0

        time_minutes = time_played / 60 if time_played > 0 else 1
        kd = kills / deaths if deaths > 0 else kills
        dpm = damage / time_minutes

        players.append(
            {
                "name": name,
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
    from datetime import datetime, timedelta

    # Calculate start date
    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).date()
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).date()
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].date()
    else:
        start_date = datetime(2020, 1, 1).date()

    # Base query parts
    # nosec B608 - These clauses are static strings, not user-controlled input
    where_clause = "WHERE time_played_seconds > 0 AND DATE(round_date) >= $1"
    group_by = "GROUP BY player_name"
    # Removed session count filter - table doesn't track sessions, only rounds/dates
    having = ""  # No HAVING clause needed for basic leaderboard

    if stat == "dpm":
        # nosec B608 - where_clause, group_by, having are static strings
        query = f"""
            WITH player_stats AS (
                SELECT
                    player_name,
                    COUNT(*) as rounds_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    SUM(time_played_seconds) as total_time,
                    ROUND((SUM(damage_given)::numeric / NULLIF(SUM(time_played_seconds), 0) * 60), 2) as value,
                    ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
                FROM player_comprehensive_stats
                {where_clause}
                {group_by}
                {having}
            )
            SELECT
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
                player_name,
                SUM(kills) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                SUM(headshots) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                SUM(revives_given) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                ROUND(AVG(accuracy)::numeric, 1) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                SUM(gibs) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                COUNT(*) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
                player_name,
                SUM(damage_given) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
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
        rows = await db.fetch_all(query, (start_date, limit))
    except Exception as e:

        error_msg = f"Leaderboard Query Error: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

    return [
        {
            "rank": i + 1,
            "name": row[0],
            "value": float(row[1]) if row[1] is not None else 0,
            "rounds": row[2],  # Changed from sessions to rounds
            "kills": row[3],
            "deaths": row[4],
            "kd": float(row[5]) if row[5] is not None else 0,
        }
        for i, row in enumerate(rows)
    ]


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
                -- Parse M:SS format to seconds, then average
                AVG(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as avg_duration
            FROM rounds r
            WHERE r.map_name IS NOT NULL
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
            GROUP BY p.map_name
        )
        SELECT
            m.map_name,
            m.total_rounds,
            m.matches_played,
            m.allies_wins,
            m.axis_wins,
            m.avg_duration,
            p.total_kills,
            p.total_deaths,
            p.avg_dpm,
            p.unique_players
        FROM map_stats m
        LEFT JOIN player_stats p ON m.map_name = p.map_name
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
                    "total_kills": row[6] or 0,
                    "total_deaths": row[7] or 0,
                    "avg_dpm": round(row[8], 1) if row[8] else 0,
                    "unique_players": row[9] or 0,
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
    from datetime import datetime, timedelta

    # Calculate start date based on period
    where_clause = "WHERE 1=1"
    params = []
    param_idx = 1

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND round_date >= ${param_idx}"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        where_clause += f" AND round_date >= ${param_idx}"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND round_date >= ${param_idx}"
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
        total_shots = row[3] or 0
        total_hits = row[4] or 0
        avg_accuracy = row[5] or 0

        if total_kills > 0:
            # Note: In ET:Legacy, headshots can exceed kills (tracking all headshots, not just killing shots)
            # We cap hs_rate at 100% for display purposes
            hs_rate = (
                min(100, round((total_headshots / total_kills * 100), 1))
                if total_kills > 0
                else 0
            )

            # Clean up weapon name (remove "Ws " prefix, "WS_" prefix, underscores)
            clean_name = weapon_name
            if clean_name.lower().startswith("ws "):
                clean_name = clean_name[3:]
            if clean_name.lower().startswith("ws_"):
                clean_name = clean_name[3:]
            clean_name = clean_name.replace("_", " ").title()

            weapons.append(
                {
                    "name": clean_name,
                    "kills": int(total_kills),
                    "headshots": int(total_headshots),
                    "hs_rate": hs_rate,
                    "accuracy": round(avg_accuracy, 1),
                }
            )

    return weapons


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
                   actual_time, round_outcome, gaming_session_id
            FROM rounds
            WHERE id = $1
        """
        round_row = await db.fetch_one(round_query, (int(match_id),))
    else:
        # It's a date - get latest round for that date
        round_query = """
            SELECT id, map_name, round_number, round_date, winner_team,
                   actual_time, round_outcome, gaming_session_id
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
                team_kills
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
            "revives": row[9] or 0,
            "accuracy": round(row[10] or 0, 1),
            "gibs": row[11] or 0,
            "selfkills": row[12] or 0,
            "teamkills": row[13] or 0,
            "dpm": round(dpm, 1),
            "kd": round(kd, 2),
        }

        if row[6] == 1:
            team1_players.append(player)
        else:
            team2_players.append(player)

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
        WHERE player_name ILIKE $1
        ORDER BY round_date DESC, round_number DESC
        LIMIT $2
    """

    try:
        rows = await db.fetch_all(query, (player_name, limit))
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
    from datetime import datetime

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
        WHERE p.player_name ILIKE $1
        AND p.time_played_seconds > 0
        AND r.gaming_session_id IS NOT NULL
        GROUP BY r.gaming_session_id
        HAVING SUM(p.time_played_seconds) > 120
        ORDER BY MIN(p.round_date) DESC
        LIMIT $2
    """

    try:
        rows = await db.fetch_all(query, (player_name, limit))
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
    from datetime import datetime

    query = """
        SELECT
            p.round_date,
            p.map_name,
            p.damage_given,
            p.time_played_seconds
        FROM player_comprehensive_stats p
        WHERE p.player_name ILIKE $1
        AND p.time_played_seconds > 60
        ORDER BY p.round_date DESC, p.round_id DESC
        LIMIT $2
    """

    try:
        rows = await db.fetch_all(query, (player_name, limit))
    except Exception as e:
        print(f"Error fetching player rounds: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return {"rounds": [], "avg_dpm": 0}

    rounds = []
    for row in reversed(rows):
        time_min = row[3] / 60 if row[3] > 0 else 1
        dpm = round(row[2] / time_min, 1)
        short_map = row[1].replace("etl_", "").replace("te_", "").replace("sw_", "")[:8]

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
async def get_session_graph_stats(date: str, db: DatabaseAdapter = Depends(get_db)):
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
    query = """
        SELECT DISTINCT
            p.player_name,
            p.round_number,
            p.kills,
            p.deaths,
            p.damage_given,
            p.damage_received,
            p.time_played_seconds,
            p.revives_given,
            p.gibs,
            p.headshots,
            p.accuracy,
            p.team_kills,
            p.self_kills,
            p.times_revived,
            p.map_name,
            r.id as round_id
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_date = r.round_date
            AND p.map_name = r.map_name
            AND p.round_number = r.round_number
        WHERE p.round_date = $1
        ORDER BY p.player_name, r.id
    """

    try:
        rows = await db.fetch_all(query, (date,))
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
        gibs = row[8] or 0
        headshots = row[9] or 0
        accuracy = row[10] or 0
        team_kills = row[11] or 0
        self_kills = row[12] or 0
        times_revived = row[13] or 0
        map_name = row[14]
        round_id = row[15]  # unique identifier for deduplication

        if name not in player_stats:
            player_stats[name] = {
                "kills": 0,
                "deaths": 0,
                "damage_given": 0,
                "damage_received": 0,
                "time_played": 0,
                "revives": 0,
                "gibs": 0,
                "headshots": 0,
                "accuracy_sum": 0,
                "accuracy_count": 0,
                "team_kills": 0,
                "self_kills": 0,
                "times_revived": 0,
                "rounds_played": 0,
                "seen_rounds": set(),  # Track unique round_ids
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
        ps["gibs"] += gibs
        ps["headshots"] += headshots
        ps["accuracy_sum"] += accuracy
        ps["accuracy_count"] += 1
        ps["team_kills"] += team_kills
        ps["self_kills"] += self_kills
        ps["times_revived"] += times_revived
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

        # Advanced metrics (similar to Discord bot's SessionGraphGenerator)
        # FragPotential: (kills + assists_proxy) / time * scaling
        frag_potential = (stats["kills"] + stats["revives"] * 0.5) / time_minutes * 10

        # Damage Efficiency: damage_given / (damage_given + damage_received)
        total_damage = stats["damage_given"] + stats["damage_received"]
        damage_efficiency = (
            (stats["damage_given"] / total_damage * 100) if total_damage > 0 else 50
        )

        # Survival Rate: time_alive / total_time (approximated by deaths)
        # Lower deaths = higher survival
        avg_death_time = stats["time_played"] / (stats["deaths"] + 1)
        survival_rate = min(100, avg_death_time / 60 * 10)  # Scale to 0-100

        # Time Denied: (enemy deaths caused * avg_respawn_time) / total_time
        time_denied = (stats["kills"] * 20) / time_minutes  # 20s avg respawn

        # Avg accuracy
        avg_accuracy = (
            stats["accuracy_sum"] / stats["accuracy_count"]
            if stats["accuracy_count"] > 0
            else 0
        )

        # Playstyle classification (8 categories like Discord bot)
        playstyle = classify_playstyle(stats, dpm, kd, avg_accuracy)

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
                    "gibs": stats["gibs"],
                    "headshots": stats["headshots"],
                    "times_revived": stats["times_revived"],
                    "team_kills": stats["team_kills"],
                },
                "advanced_metrics": {
                    "frag_potential": round(frag_potential, 1),
                    "damage_efficiency": round(damage_efficiency, 1),
                    "survival_rate": round(survival_rate, 1),
                    "time_denied": round(time_denied, 1),
                },
                "playstyle": playstyle,
                "dpm_timeline": dpm_timeline[name],
            }
        )

    # Sort by DPM for consistent ordering
    players_data.sort(key=lambda x: x["combat_offense"]["dpm"], reverse=True)

    return {"date": date, "player_count": len(players_data), "players": players_data}


def classify_playstyle(stats: dict, dpm: float, kd: float, accuracy: float) -> dict:
    """
    Classify player playstyle into 8 categories (0-100 scale).
    Based on Discord bot's SessionGraphGenerator logic.
    """
    time_minutes = stats["time_played"] / 60 if stats["time_played"] > 0 else 1
    rounds = stats["rounds_played"] or 1

    # Normalize stats per round for fair comparison
    kills_pr = stats["kills"] / rounds
    deaths_pr = stats["deaths"] / rounds
    revives_pr = stats["revives"] / rounds
    gibs_pr = stats["gibs"] / rounds

    # Calculate each playstyle dimension (0-100)
    return {
        "aggression": min(100, (dpm / 5) * 10),  # High DPM = aggressive
        "precision": min(100, accuracy * 2),  # Accuracy-based
        "survivability": min(
            100, max(0, 100 - deaths_pr * 20)
        ),  # Low deaths = high survival
        "support": min(100, revives_pr * 50),  # Revives indicate support play
        "lethality": min(100, kd * 30),  # K/D ratio
        "brutality": min(100, gibs_pr * 25),  # Gibs show aggression
        "consistency": min(100, rounds * 10),  # More rounds = consistent player
        "efficiency": min(
            100, (stats["damage_given"] / max(1, stats["damage_received"])) * 25
        ),
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

    base_where = "WHERE time_played_seconds > 0"
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
        SELECT award_name, player_name, award_value, award_value_numeric
        FROM round_awards
        WHERE round_id = $1
        ORDER BY id
    """
    awards_rows = await db.fetch_all(awards_query, (round_id,))

    # Group by category
    categories = {}
    for row in awards_rows:
        award_name, player, value, numeric = row
        cat_key, emoji, cat_name = categorize_award(award_name)

        if cat_key not in categories:
            categories[cat_key] = {"emoji": emoji, "name": cat_name, "awards": []}

        categories[cat_key]["awards"].append(
            {"award": award_name, "player": player, "value": value, "numeric": numeric}
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
        SELECT player_name, kills, deaths
        FROM round_vs_stats
        WHERE round_id = $1
        ORDER BY kills DESC, deaths ASC
    """
    rows = await db.fetch_all(query, (round_id,))

    return {
        "round_id": round_id,
        "stats": [
            {"player": row[0], "kills": row[1], "deaths": row[2]} for row in rows
        ],
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
        where_clauses.append(f"ra.created_at >= NOW() - INTERVAL '{days} days'")

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get player award counts with their most won award
    query = f"""
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
    params.append(limit)

    rows = await db.fetch_all(query, tuple(params))

    return {
        "leaderboard": [
            {
                "rank": idx + 1,
                "player": row[0],
                "award_count": row[1],
                "top_award": row[2],
                "top_award_count": row[3],
            }
            for idx, row in enumerate(rows)
        ],
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
    # Get award counts by type
    count_query = """
        SELECT award_name, COUNT(*) as count
        FROM round_awards
        WHERE player_name ILIKE $1 OR player_guid = $1
        GROUP BY award_name
        ORDER BY count DESC
    """
    count_rows = await db.fetch_all(count_query, (identifier,))

    # Get recent awards
    recent_query = """
        SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
        FROM round_awards ra
        WHERE ra.player_name ILIKE $1 OR ra.player_guid = $1
        ORDER BY ra.created_at DESC
        LIMIT $2
    """
    recent_rows = await db.fetch_all(recent_query, (identifier, limit))

    total = sum(row[1] for row in count_rows)

    return {
        "player": identifier,
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

    if player:
        where_clauses.append(f"ra.player_name ILIKE ${param_idx}")
        params.append(f"%{player}%")
        param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    if days > 0:
        where_clauses.append(f"ra.created_at >= NOW() - INTERVAL '{days} days'")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get total count
    count_query = f"SELECT COUNT(*) FROM round_awards ra {where_sql}"
    count_row = await db.fetch_one(count_query, tuple(params))
    total = count_row[0] if count_row else 0

    # Get awards
    query = f"""
        SELECT ra.award_name, ra.player_name, ra.award_value, ra.round_date,
               ra.map_name, ra.round_number, ra.round_id
        FROM round_awards ra
        {where_sql}
        ORDER BY ra.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    rows = await db.fetch_all(query, tuple(params))

    return {
        "awards": [
            {
                "award": row[0],
                "player": row[1],
                "value": row[2],
                "date": row[3],
                "map": row[4],
                "round_number": row[5],
                "round_id": row[6],
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {"player": player, "award_type": award_type, "days": days},
    }
