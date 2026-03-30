"""Records sub-router: Match and round detail endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    resolve_alias_guid_map,
    resolve_display_name,
    resolve_name_guid_map,
)
from website.backend.routers.records_helpers import (
    categorize_award,
    serialize_round_label,
)

router = APIRouter()
logger = get_app_logger("api.records.matches")


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
    winner = "Axis" if winner_team == 1 else "Allies" if winner_team == 2 else "Draw"

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
        logger.error(f"Error fetching match details: {e}")
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
            "round_label": serialize_round_label(row[3]),
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
    highlights: dict[str, Any] = {}
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
        "round_label": serialize_round_label(round_row[3]),
        "winner_team": round_row[4],
        "duration_seconds": round_row[5],
        "player_count": len(players),
        "players": players,
        "highlights": highlights,
    }
