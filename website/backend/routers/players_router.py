"""
Player-related endpoints: search, link, profile, compare, leaderboard, matches, form, rounds.

Extracted from api.py to reduce file size and improve maintainability.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from bot.core.season_manager import SeasonManager
from bot.core.utils import escape_like_pattern
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    calculate_player_achievements,
    resolve_player_guid,
    resolve_display_name,
    batch_resolve_display_names,
)

router = APIRouter()
logger = get_app_logger("api.players")


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
