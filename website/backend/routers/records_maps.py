"""Records sub-router: Map stats endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shared.round_time import round_duration_sql
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger

router = APIRouter()


class MapStats(BaseModel):
    """One map's aggregate line.

    ⚠️ TYPED FROM THE HANDLER, NOT THE SAMPLE. Every numeric field here passes
    through a `x or 0` / `int(x) if x else 0` guard, so they are genuinely
    non-null — the handler already decided that. `last_played` is the one that
    does NOT: `row[8]` goes through untouched and `rounds.round_date` is a
    nullable column, so it is typed nullable even though no live row shows it.
    """

    name: str
    total_rounds: int
    matches_played: int
    allies_wins: int
    axis_wins: int
    allies_win_rate: float
    axis_win_rate: float
    avg_duration: int
    min_duration: int
    max_duration: int
    #: Passed through unguarded from a nullable column.
    last_played: str | None
    total_kills: int
    total_deaths: int
    avg_dpm: float
    unique_players: int
    grenade_kills: int
    panzer_kills: int
    mortar_kills: int


class MapObjectiveRecord(BaseModel):
    """The fastest completion recorded for one map."""

    #: `rounds.map_name` is nullable; the group-by carries the null through.
    map_name: str | None
    fastest_seconds: int
    #: `M:SS`, rendered from the MEASURED duration — not the `actual_time`
    #: header, which is the stopwatch target and overstates ~15% of rounds.
    fastest_time: str
    played: str
    #: Nullable column: an unresolved round has no winner.
    winner_team: int | None
    #: 'Axis' | 'Allies' | 'Draw' — derived, so never null.
    winner_side: str
    gaming_session_id: int | None


class MapObjectiveRecords(BaseModel):
    """⛔ `status` CARRIES A FAILURE THAT STILL ANSWERS 200.

    The handler catches its own exception and returns
    `{"status": "error", "records": []}`. A model that dropped `status` would
    make that indistinguishable from a database with no records — the reader
    would see an empty list either way. It is kept, and typed as a plain string
    rather than an enum so a new state cannot be silently filtered out.
    """

    #: 'ok' when the query ran; 'error' when it raised and was swallowed.
    status: str
    records: list[MapObjectiveRecord]

logger = get_app_logger("api.records.maps")

# Measured duration (webhook first, header text fallback) — actual_time
# alone is the stopwatch TARGET and is inflated on surrender rounds
# (RCA 2026-08-18, see shared/round_time.py).
_DUR = round_duration_sql("r")


@router.get("/stats/maps", response_model=list[MapStats])
async def get_maps(db: DatabaseAdapter = Depends(get_db)):
    """
    Get comprehensive statistics for all maps.
    Returns times played, win rates, kill stats, etc.
    Note: In stopwatch mode, 2 rounds = 1 match.
    """
    query = f"""
        WITH map_stats AS (
            SELECT
                r.map_name,
                COUNT(*) as total_rounds,
                COUNT(*) / 2 as matches_played,
                -- winner_team 1 = Axis, 2 = Allies (TEAM_AXIS=1). Aliases were inverted.
                SUM(CASE WHEN r.winner_team = 2 THEN 1 ELSE 0 END) as allies_wins,
                SUM(CASE WHEN r.winner_team = 1 THEN 1 ELSE 0 END) as axis_wins,
                MAX(SUBSTR(CAST(r.round_date AS TEXT), 1, 10)) as last_played,
                -- Measured duration (RCA 2026-08-18), then avg/min/max
                AVG({_DUR}) as avg_duration,
                MIN({_DUR}) as min_duration,
                MAX({_DUR}) as max_duration
            FROM rounds r
            WHERE r.map_name IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid
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


@router.get("/records/maps/segments", response_model=MapObjectiveRecords)
async def get_map_objective_records(db: DatabaseAdapter = Depends(get_db)):
    """Fastest objective-completion time per map + when/which side held it.

    Stopwatch record board (VISION_2026 S4-D): the single fastest valid full-hold
    round per map. Reuses the M:SS -> seconds parse from /stats/maps; degenerate
    0:00 rounds are excluded. is_valid filter keeps bot/filler rounds out.
    """
    query = f"""
        SELECT DISTINCT ON (r.map_name)
            r.map_name,
            {_DUR} AS seconds,
            r.actual_time,
            SUBSTR(CAST(r.round_date AS TEXT), 1, 10) AS played,
            r.winner_team,
            r.gaming_session_id
        FROM rounds r
        WHERE r.map_name IS NOT NULL
          AND r.round_number IN (1, 2)
          AND r.is_valid IS DISTINCT FROM FALSE
          AND {_DUR} > 0
        ORDER BY r.map_name, seconds ASC
    """
    try:
        rows = await db.fetch_all(query)
        records = []
        for row in rows:
            winner = row[4]
            # winner_team 1 = Axis, 2 = Allies (TEAM_AXIS=1). Was inverted.
            side = "Axis" if winner == 1 else "Allies" if winner == 2 else "Draw"
            secs = int(row[1])
            records.append({
                "map_name": row[0],
                "fastest_seconds": secs,
                # Display from the measured duration, not the (possibly
                # inflated) actual_time header text.
                "fastest_time": f"{secs // 60}:{secs % 60:02d}",
                "played": row[3],
                "winner_team": winner,
                "winner_side": side,
                "gaming_session_id": row[5],
            })
        records.sort(key=lambda r: r["map_name"])
        return {"status": "ok", "records": records}
    except Exception as e:
        logger.error(f"Error fetching map objective records: {e}")
        return {"status": "error", "records": []}
