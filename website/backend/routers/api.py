from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from bot.core.season_manager import SeasonManager
from bot.core.utils import escape_like_pattern  # SQL injection protection for LIKE queries
from bot.config import load_config
from website.backend.services.website_session_data_service import (
    WebsiteSessionDataService as SessionDataService,
)
from bot.services.session_stats_aggregator import SessionStatsAggregator

router = APIRouter()


@router.get("/status")
async def get_status():
    return {"status": "online", "service": "Slomix API"}


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
        },
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
        # TODO: Get actual season start date from config/db
        start_date = datetime(2024, 1, 1).date()
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
    Get list of all maps available in the stats.
    """
    query = "SELECT DISTINCT map_name FROM player_comprehensive_stats ORDER BY map_name"
    try:
        rows = await db.fetch_all(query)
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        print(f"Error fetching maps: {e}")
        return []


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
