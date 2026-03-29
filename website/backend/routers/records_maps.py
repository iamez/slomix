"""Records sub-router: Map stats endpoints."""

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger

router = APIRouter()
logger = get_app_logger("api.records.maps")


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
        logger.error(f"Error fetching map stats: {e}")
        return []
