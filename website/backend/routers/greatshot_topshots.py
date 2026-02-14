"""Greatshot Topshots - Best performances across all analyzed demos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger

router = APIRouter()
logger = get_app_logger("greatshot.topshots")


def _require_user_id(request: Request) -> int:
    user = request.session.get("user")
    if not user or "id" not in user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return int(user["id"])
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session user") from exc


def _safe_json_field(value: Any) -> Optional[Dict]:
    """Parse JSON field, return None on error."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value) if isinstance(value, str) else None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


@router.get("/greatshot/topshots/kills")
async def get_top_kills(request: Request, limit: int = 10, db=Depends(get_db)):
    """Get demos with highest total kills.

    Returns:
        List of demos ranked by total kills across all players
    """
    # Optimized query using total_kills column (avoids N+1 file reads)
    user_id = _require_user_id(request)
    rows = await db.fetch_all(
        """
        SELECT
            d.id,
            d.original_filename,
            d.metadata_json,
            a.total_kills,
            a.stats_json,
            d.created_at
        FROM greatshot_demos d
        JOIN greatshot_analysis a ON a.demo_id = d.id
        WHERE d.status = 'analyzed'
          AND d.user_id = $1
          AND a.total_kills > 0
        ORDER BY a.total_kills DESC
        LIMIT $2
        """,
        (user_id, limit),
    )

    results = []
    for row in rows:
        demo_id, filename, metadata_json, total_kills, stats_json, created_at = row
        metadata = _safe_json_field(metadata_json) or {}
        stats = _safe_json_field(stats_json) or {}

        player_count = stats.get("player_count")
        if player_count is None:
            # Backward compatibility for legacy rows that may have full player_stats in stats_json.
            player_stats = stats.get("player_stats") or {}
            player_count = len(player_stats)

        results.append({
            "demo_id": demo_id,
            "filename": filename,
            "map": metadata.get("map"),
            "total_kills": total_kills,
            "player_count": int(player_count or 0),
            "created_at": str(created_at),
        })

    return results


@router.get("/greatshot/topshots/players")
async def get_top_players(request: Request, limit: int = 10, db=Depends(get_db)):
    """Get players with best individual round performances across all demos.

    Returns:
        List of player performances ranked by kills
    """
    user_id = _require_user_id(request)
    rows = await db.fetch_all(
        """
        SELECT
            d.id,
            d.original_filename,
            d.metadata_json,
            d.analysis_json_path,
            d.created_at
        FROM greatshot_demos d
        WHERE d.status = 'analyzed'
          AND d.user_id = $1
          AND d.analysis_json_path IS NOT NULL
        ORDER BY d.created_at DESC
        """,
        (user_id,)
    )

    performances = []

    for row in rows:
        demo_id, filename, metadata_json, analysis_path, created_at = row
        metadata = _safe_json_field(metadata_json) or {}

        if not analysis_path:
            continue

        try:
            analysis_file = Path(analysis_path)
            if not analysis_file.is_file():
                continue

            with analysis_file.open() as f:
                full_analysis = json.load(f)

            player_stats = full_analysis.get("player_stats") or {}

            for player_name, stats in player_stats.items():
                kills = stats.get("kills", 0)
                deaths = stats.get("deaths", 0)
                damage = stats.get("damage_given", 0)
                accuracy = stats.get("accuracy")
                headshots = stats.get("headshots", 0)

                kdr = kills / max(deaths, 1)

                performances.append({
                    "demo_id": demo_id,
                    "filename": filename,
                    "map": metadata.get("map"),
                    "player": player_name,
                    "kills": kills,
                    "deaths": deaths,
                    "kdr": round(kdr, 2),
                    "damage": damage,
                    "accuracy": accuracy,
                    "headshots": headshots,
                    "created_at": str(created_at),
                })
        except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning("Failed to process demo %s: %s", demo_id, str(e).replace('\n', ' ')[:200])
            continue

    # Sort by kills and return top N
    performances.sort(key=lambda x: x["kills"], reverse=True)
    return performances[:limit]


@router.get("/greatshot/topshots/accuracy")
async def get_top_accuracy(
    request: Request,
    min_kills: int = 10,
    limit: int = 10,
    db=Depends(get_db),
):
    """Get players with best accuracy across all demos.

    Args:
        min_kills: Minimum kills required to qualify (default 10)
        limit: Number of results to return (default 10)

    Returns:
        List of player performances ranked by accuracy
    """
    user_id = _require_user_id(request)
    rows = await db.fetch_all(
        """
        SELECT
            d.id,
            d.original_filename,
            d.metadata_json,
            d.analysis_json_path,
            d.created_at
        FROM greatshot_demos d
        WHERE d.status = 'analyzed'
          AND d.user_id = $1
          AND d.analysis_json_path IS NOT NULL
        ORDER BY d.created_at DESC
        """,
        (user_id,)
    )

    performances = []

    for row in rows:
        demo_id, filename, metadata_json, analysis_path, created_at = row
        metadata = _safe_json_field(metadata_json) or {}

        if not analysis_path:
            continue

        try:
            analysis_file = Path(analysis_path)
            if not analysis_file.is_file():
                continue

            with analysis_file.open() as f:
                full_analysis = json.load(f)

            player_stats = full_analysis.get("player_stats") or {}

            for player_name, stats in player_stats.items():
                kills = stats.get("kills", 0)
                accuracy = stats.get("accuracy")

                # Only include players with minimum kills and known accuracy
                if kills < min_kills or accuracy is None:
                    continue

                performances.append({
                    "demo_id": demo_id,
                    "filename": filename,
                    "map": metadata.get("map"),
                    "player": player_name,
                    "kills": kills,
                    "accuracy": round(accuracy, 1),
                    "created_at": str(created_at),
                })
        except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning("Failed to process demo %s: %s", demo_id, str(e).replace('\n', ' ')[:200])
            continue

    # Sort by accuracy and return top N
    performances.sort(key=lambda x: x["accuracy"], reverse=True)
    return performances[:limit]


@router.get("/greatshot/topshots/damage")
async def get_top_damage(request: Request, limit: int = 10, db=Depends(get_db)):
    """Get players with highest damage dealt across all demos.

    Returns:
        List of player performances ranked by damage
    """
    user_id = _require_user_id(request)
    rows = await db.fetch_all(
        """
        SELECT
            d.id,
            d.original_filename,
            d.metadata_json,
            d.analysis_json_path,
            d.created_at
        FROM greatshot_demos d
        WHERE d.status = 'analyzed'
          AND d.user_id = $1
          AND d.analysis_json_path IS NOT NULL
        ORDER BY d.created_at DESC
        """,
        (user_id,)
    )

    performances = []

    for row in rows:
        demo_id, filename, metadata_json, analysis_path, created_at = row
        metadata = _safe_json_field(metadata_json) or {}

        if not analysis_path:
            continue

        try:
            analysis_file = Path(analysis_path)
            if not analysis_file.is_file():
                continue

            with analysis_file.open() as f:
                full_analysis = json.load(f)

            player_stats = full_analysis.get("player_stats") or {}

            for player_name, stats in player_stats.items():
                damage = stats.get("damage_given", 0)
                kills = stats.get("kills", 0)

                performances.append({
                    "demo_id": demo_id,
                    "filename": filename,
                    "map": metadata.get("map"),
                    "player": player_name,
                    "damage": damage,
                    "kills": kills,
                    "created_at": str(created_at),
                })
        except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning("Failed to process demo %s: %s", demo_id, str(e).replace('\n', ' ')[:200])
            continue

    # Sort by damage and return top N
    performances.sort(key=lambda x: x["damage"], reverse=True)
    return performances[:limit]


@router.get("/greatshot/topshots/multikills")
async def get_top_multikills(request: Request, limit: int = 10, db=Depends(get_db)):
    """Get best multi-kill highlights across all demos.

    Returns:
        List of highlights ranked by kill count
    """
    user_id = _require_user_id(request)
    rows = await db.fetch_all(
        """
        SELECT
            h.id,
            h.demo_id,
            h.type,
            h.player,
            h.score,
            h.meta_json,
            d.original_filename,
            d.metadata_json,
            d.created_at
        FROM greatshot_highlights h
        JOIN greatshot_demos d ON d.id = h.demo_id
        WHERE h.type IN ('double_kill', 'triple_kill', 'quad_kill', 'penta_kill', 'multi_kill')
          AND d.status = 'analyzed'
          AND d.user_id = $1
        ORDER BY h.score DESC
        LIMIT $2
        """,
        (user_id, limit * 2)  # Get more to filter later
    )

    highlights = []
    for row in rows:
        (
            highlight_id, demo_id, highlight_type, player, score,
            meta_json, filename, metadata_json, created_at
        ) = row

        meta = _safe_json_field(meta_json) or {}
        metadata = _safe_json_field(metadata_json) or {}

        kill_count = meta.get("kill_count", 0)
        victims = meta.get("victims", [])
        weapons = meta.get("weapons_used", {})

        highlights.append({
            "highlight_id": highlight_id,
            "demo_id": demo_id,
            "type": highlight_type,
            "player": player,
            "score": score,
            "kill_count": kill_count,
            "victims": victims,
            "weapons": list(weapons.keys()) if weapons else [],
            "filename": filename,
            "map": metadata.get("map"),
            "created_at": str(created_at),
        })

    return highlights[:limit]
