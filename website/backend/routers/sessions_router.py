"""
Session-related endpoints: last-session, session lists, session details, graphs.

Extracted from api.py to reduce file size and improve maintainability.
"""

import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from bot.config import load_config
from bot.core.utils import escape_like_pattern
from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.stopwatch_scoring_service import StopwatchScoringService
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    normalize_map_name as _normalize_map_name,
)
from website.backend.services.website_session_data_service import (
    WebsiteSessionDataService as SessionDataService,
)

router = APIRouter()
logger = get_app_logger("api.sessions")


async def build_session_scoring(
    session_date: str,
    session_ids: list | None,
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
            logger.warning(
                "Failed to fetch raw dead-time aggregates for session_ids=%s",
                session_ids,
                exc_info=True,
            )
            raw_dead_map = {}

        try:
            player_rows = await stats_service.aggregate_all_player_stats(
                session_ids, session_ids_str
            )
        except Exception:
            logger.error(
                "Failed to aggregate player stats for session_ids=%s — "
                "session will appear empty to the user",
                session_ids,
                exc_info=True,
            )
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
    session_id: int | None = None,
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
        logger.error(f"Error fetching sessions list: {e}")
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
            logger.error(f"Error fetching session leaderboard: {e}")

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


@router.get("/sessions/{date}/graphs")
async def get_session_graph_stats(
    date: str,
    gaming_session_id: int | None = None,
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
        logger.error(f"Error fetching session graph stats: {e}")
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
        # row[29] = bullets_fired (reserved for accuracy calc)
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
    value: Any, values: list[Any], invert: bool = False, neutral: float = 50.0
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


def _apply_session_aggression_model(players_data: list[dict[str, Any]]) -> None:
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
        # pr[9] = total_kills_for_hs (reserved for future headshot% calc)
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


