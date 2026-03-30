"""Records sub-router: Stats trends and retro-viz gallery endpoints."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    normalize_map_name as _normalize_map_name,
)

router = APIRouter()
logger = get_app_logger("api.records.trends")


@router.get("/stats/trends")
async def get_stats_trends(
    days: int = 14,
    metrics: str = "rounds,active_players,kills,maps",
    db: DatabaseAdapter = Depends(get_db),
):
    """Time-series trends for activity metrics."""
    days = max(1, min(days, 90))
    requested = {m.strip().lower() for m in metrics.split(",") if m.strip()}

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # Generate full date range
        date_list = []
        current = datetime.now() - timedelta(days=days)
        while current.date() <= datetime.now().date():
            date_list.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        result: dict[str, Any] = {"dates": date_list}

        if "rounds" in requested or "active_players" in requested or "kills" in requested:
            query = """
                SELECT SUBSTR(CAST(r.round_date AS TEXT), 1, 10) as day,
                       COUNT(DISTINCT r.id) as round_count,
                       COUNT(DISTINCT pcs.player_guid) as player_count,
                       COALESCE(SUM(pcs.kills), 0) as total_kills
                FROM rounds r
                LEFT JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id
                WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) >= $1
                  AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) <= $2
                  AND r.round_number IN (1, 2)
                GROUP BY day
                ORDER BY day
            """
            rows = await db.fetch_all(query, (start_date, end_date))

            day_data = {}
            for row in rows:
                day_data[row[0]] = {
                    "rounds": int(row[1]),
                    "active_players": int(row[2]),
                    "kills": int(row[3]),
                }

            if "rounds" in requested:
                result["rounds"] = [day_data.get(d, {}).get("rounds", 0) for d in date_list]
            if "active_players" in requested:
                result["active_players"] = [day_data.get(d, {}).get("active_players", 0) for d in date_list]
            if "kills" in requested:
                result["kills"] = [day_data.get(d, {}).get("kills", 0) for d in date_list]

        if "maps" in requested:
            map_query = """
                SELECT r.map_name, COUNT(*) as play_count
                FROM rounds r
                WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) >= $1
                  AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) <= $2
                  AND r.round_number IN (1, 2)
                  AND r.map_name IS NOT NULL
                  AND TRIM(CAST(r.map_name AS TEXT)) <> ''
                GROUP BY r.map_name
                ORDER BY play_count DESC
            """
            map_rows = await db.fetch_all(map_query, (start_date, end_date))
            map_distribution: dict[str, int] = {}
            for row in map_rows:
                normalized_map_name = _normalize_map_name(row[0])
                if not normalized_map_name:
                    continue

                play_count = int(row[1]) if row[1] is not None else 0
                if play_count <= 0:
                    continue

                map_distribution[normalized_map_name] = (
                    map_distribution.get(normalized_map_name, 0) + play_count
                )

            result["map_distribution"] = dict(
                sorted(
                    map_distribution.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            )

        return result

    except Exception as e:
        logger.error(f"Stats trends query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate trends data")


@router.get("/retro-viz/gallery")
async def get_retro_viz_gallery():
    """List PNG files in the retro-viz output directory."""
    gallery_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "retro-viz")
    gallery_dir = os.path.normpath(gallery_dir)

    if not os.path.isdir(gallery_dir):
        return {"images": []}

    images = []
    try:
        for fname in sorted(os.listdir(gallery_dir)):
            if not fname.lower().endswith(".png"):
                continue
            fpath = os.path.join(gallery_dir, fname)
            if not os.path.isfile(fpath):
                continue
            # Prevent symlink traversal outside gallery directory
            if not os.path.realpath(fpath).startswith(os.path.realpath(gallery_dir)):
                continue
            stat = os.stat(fpath)
            images.append({
                "filename": fname,
                "url": f"/data/retro-viz/{fname}",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.error(f"Retro-viz gallery listing failed: {e}")

    return {"images": images}
