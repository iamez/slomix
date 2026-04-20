"""Records sub-router: Awards, records, and hall of fame endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from shared.season_manager import SeasonManager
from shared.utils import escape_like_pattern
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    resolve_alias_guid_map,
    resolve_display_name,
    resolve_name_guid_map,
    resolve_player_guid,
)

router = APIRouter()
logger = get_app_logger("api.records.awards")


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
            logger.error(f"Error fetching record for {key}: {e}")
            results[key] = []

    return results


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
                COALESCE(ra.player_guid, am.guid, nm.player_guid) as resolved_guid,
                MAX(ra.player_name) as player_name,
                ra.award_name,
                COUNT(*) as award_specific_count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            {where_sql}
            GROUP BY player_key, resolved_guid, ra.award_name
        ),
        player_totals AS (
            SELECT
                player_key,
                MAX(resolved_guid) as player_guid,
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
            params.append(f"%{escape_like_pattern(player)}%")
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


@router.get("/hall-of-fame")
async def get_hall_of_fame(
    period: str = "all_time",
    start_date: str | None = None,
    end_date: str | None = None,
    season_id: int | None = None,
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
