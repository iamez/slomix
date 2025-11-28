from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from bot.core.season_manager import SeasonManager
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

    # Since each map usually has 2 rounds, divide by 2 for "matches" count, or just list unique maps
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


@router.get("/stats/leaderboard")
async def get_leaderboard(limit: int = 5, db: DatabaseAdapter = Depends(get_db)):
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

    # Case-insensitive search
    # Note: ILIKE is Postgres specific. If supporting SQLite, use LIKE with lower()
    sql = "SELECT DISTINCT player_name FROM player_comprehensive_stats WHERE player_name ILIKE ? ORDER BY player_name LIMIT 10"
    rows = await db.fetch_all(sql, (f"%{query}%",))
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
