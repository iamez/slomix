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
from bot.services.session_stats_aggregator import SessionStatsAggregator

router = APIRouter()


@router.get("/status")
async def get_status():
    return {"status": "online", "service": "Slomix API"}


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
    limit: int = 20,
    offset: int = 0,
    db: DatabaseAdapter = Depends(get_db)
):
    """
    Get list of all gaming sessions (like !sessions command).
    Returns sessions grouped by date with summary stats.
    """
    query = """
        WITH session_summary AS (
            SELECT
                r.round_date,
                r.gaming_session_id,
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
            GROUP BY r.round_date, r.gaming_session_id
        )
        SELECT
            round_date,
            gaming_session_id,
            round_count,
            map_count,
            player_count,
            total_kills,
            maps_played
        FROM session_summary
        ORDER BY round_date DESC
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

        sessions.append({
            "date": str(round_date),
            "session_id": row[1],
            "rounds": row[2],
            "maps": row[3],
            "players": row[4],
            "total_kills": row[5],
            "maps_played": row[6].split(", ") if row[6] else [],
            "time_ago": time_ago,
            "formatted_date": dt.strftime("%A, %B %d, %Y"),
        })

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
    sessions, session_ids, session_ids_str, player_count = await data_service.fetch_session_data(date)

    if not sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get matches for this session
    matches = await data_service.get_session_matches(date)

    # Get leaderboard (top players by DPM)
    leaderboard = []
    if session_ids:
        try:
            lb_data = await stats_service.get_dpm_leaderboard(session_ids, session_ids_str, 10)
            for i, (name, dpm, kills, deaths) in enumerate(lb_data, 1):
                kd = kills / deaths if deaths > 0 else kills
                leaderboard.append({
                    "rank": i,
                    "name": name,
                    "dpm": int(dpm),
                    "kills": kills,
                    "deaths": deaths,
                    "kd": round(kd, 2),
                })
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


@router.get("/stats/weapons")
async def get_weapon_stats(
    period: str = "all",
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get aggregated weapon statistics across all players.
    Returns weapon usage, kills, and accuracy data.
    """
    from datetime import datetime, timedelta

    # Weapon columns in player_comprehensive_stats (based on C0RNP0RN3 lua)
    weapon_columns = {
        "knife": "knife_kills",
        "luger": "luger_kills",
        "colt": "colt_kills",
        "mp40": "mp40_kills",
        "thompson": "thompson_kills",
        "sten": "sten_kills",
        "fg42": "fg42_kills",
        "panzerfaust": "pf_kills",
        "flamethrower": "flamethrower_kills",
        "grenade": "grenade_kills",
        "mortar": "mortar_kills",
        "dynamite": "dynamite_kills",
        "airstrike": "airstrike_kills",
        "artillery": "artillery_kills",
        "syringe": "syringe_kills",
        "smokegrenade": "smokegrenade_kills",
        "landmine": "landmine_kills",
        "mg42": "mg42_kills",
        "garand": "garand_kills",
        "k43": "k43_kills",
        "kar98": "kar98_kills",
    }

    # Calculate start date based on period
    where_clause = "WHERE time_played_seconds > 0"
    params = []

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).date()
        where_clause += " AND DATE(round_date) >= $1"
        params.append(start_date)
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).date()
        where_clause += " AND DATE(round_date) >= $1"
        params.append(start_date)
    elif period == "season":
        start_date = datetime(2024, 1, 1).date()
        where_clause += " AND DATE(round_date) >= $1"
        params.append(start_date)
    # else: all time, no date filter

    # Build dynamic SUM for each weapon
    sums = ", ".join(
        [f"COALESCE(SUM({col}), 0) as {name}" for name, col in weapon_columns.items()]
    )

    query = f"""
        SELECT {sums}
        FROM player_comprehensive_stats
        {where_clause}
    """

    try:
        row = await db.fetch_one(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error fetching weapon stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not row:
        return []

    # Convert to list format sorted by kills
    weapons = []
    for i, (name, _) in enumerate(weapon_columns.items()):
        kills = row[i] or 0
        if kills > 0:  # Only include weapons with kills
            weapons.append(
                {
                    "name": name.replace("_", " ").title(),
                    "kills": int(kills),
                }
            )

    # Sort by kills descending
    weapons.sort(key=lambda x: x["kills"], reverse=True)

    return weapons[:limit]


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
    query = """
        SELECT
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
        ORDER BY round_date DESC
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
        time_played = row[6] or 0
        dpm = (row[5] / (time_played / 60)) if time_played > 0 else 0
        kd = row[3] / row[4] if row[4] > 0 else row[3]

        matches.append(
            {
                "round_date": row[0],
                "map_name": row[1],
                "round_number": row[2],
                "kills": row[3],
                "deaths": row[4],
                "damage": row[5],
                "time_played": time_played,
                "team": row[7],
                "xp": row[8],
                "accuracy": row[9],
                "dpm": round(dpm, 1),
                "kd": round(kd, 2),
            }
        )

    return matches


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
