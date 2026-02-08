"""Cross-reference Greatshot demo analysis with ET:Legacy stats database."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from website.backend.logging_config import get_app_logger

logger = get_app_logger("greatshot.crossref")

# Winner mapping: UDT uses string names, DB uses team names
_WINNER_MAP = {
    "allies": "allies",
    "axis": "axis",
    "2": "allies",
    "1": "axis",
}


def _normalize_winner(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _WINNER_MAP.get(str(value).lower().strip())


async def find_matching_round(
    metadata: Dict[str, Any],
    db,
) -> Optional[Dict[str, Any]]:
    """Try to match a demo's metadata to a round in the database.

    Returns dict with round_id, confidence, and match details, or None.
    """
    demo_map = (metadata.get("map") or "").lower().strip()
    if not demo_map:
        return None

    duration_s = (metadata.get("duration_ms") or 0) / 1000.0
    rounds_info = metadata.get("rounds") or []
    demo_winner = None
    demo_first_score = None
    demo_second_score = None
    if rounds_info:
        r0 = rounds_info[0]
        demo_winner = _normalize_winner(r0.get("winner"))
        demo_first_score = r0.get("first_place_score")
        demo_second_score = r0.get("second_place_score")

    # Step 1: Find candidate rounds by map name
    candidates = await db.fetch_all(
        """
        SELECT
            r.id,
            r.match_id,
            r.round_number,
            r.round_date,
            r.round_time,
            r.map_name,
            r.actual_duration_seconds,
            r.winner_team,
            r.gaming_session_id,
            r.human_player_count,
            l.axis_score,
            l.allies_score
        FROM rounds r
        LEFT JOIN lua_round_teams l ON l.round_id = r.id
        WHERE LOWER(r.map_name) = $1
        ORDER BY r.round_date DESC, r.round_time DESC
        LIMIT 50
        """,
        (demo_map,),
    )

    if not candidates:
        return None

    best_match = None
    best_confidence = 0.0

    for row in candidates:
        (
            round_id, match_id, round_number, round_date, round_time,
            map_name, db_duration, db_winner, session_id, player_count,
            axis_score, allies_score,
        ) = row

        confidence = 0.0
        match_details: List[str] = []

        # Map match (already filtered, base confidence)
        confidence += 30.0
        match_details.append("map")

        # Duration match (±30s tolerance to account for warmup/pauses)
        if duration_s > 0 and db_duration:
            diff = abs(duration_s - float(db_duration))
            if diff <= 30:  # Increased from 5s - demos may include warmup
                confidence += 30.0
                match_details.append(f"duration (diff={diff:.1f}s)")
            elif diff <= 60:  # Increased from 15s
                confidence += 15.0
                match_details.append(f"duration-approx (diff={diff:.1f}s)")

        # Winner match
        if demo_winner and db_winner:
            if demo_winner == db_winner.lower().strip():
                confidence += 20.0
                match_details.append("winner")

        # Score match
        if demo_first_score is not None and axis_score is not None and allies_score is not None:
            db_scores = sorted([int(axis_score), int(allies_score)], reverse=True)
            demo_scores = sorted([int(demo_first_score), int(demo_second_score or 0)], reverse=True)
            if db_scores == demo_scores:
                confidence += 20.0
                match_details.append("scores")

        if confidence > best_confidence:
            best_confidence = confidence
            best_match = {
                "round_id": round_id,
                "match_id": match_id,
                "round_number": round_number,
                "round_date": str(round_date) if round_date else None,
                "round_time": str(round_time) if round_time else None,
                "map_name": map_name,
                "duration_seconds": float(db_duration) if db_duration else None,
                "winner_team": db_winner,
                "gaming_session_id": session_id,
                "player_count": player_count,
                "confidence": round(best_confidence, 1),
                "match_details": match_details,
            }

    if best_match and best_match["confidence"] < 30:
        return None

    return best_match


async def enrich_with_db_stats(
    round_id: int,
    db,
) -> Dict[str, Any]:
    """Fetch full player stats from player_comprehensive_stats for a matched round."""
    rows = await db.fetch_all(
        """
        SELECT
            player_name,
            player_guid,
            kills,
            deaths,
            damage_given,
            damage_received,
            accuracy,
            headshots,
            headshot_kills,
            revives_given,
            time_played_seconds,
            team,
            efficiency,
            kdr,
            skill_rating,
            dpm
        FROM player_comprehensive_stats
        WHERE round_id = $1
        ORDER BY kills DESC
        """,
        (round_id,),
    )

    players = {}
    for row in rows:
        (
            name, guid, kills, deaths, dmg_given, dmg_received,
            accuracy, headshots, hs_kills, revives,
            time_played, team, efficiency, kdr, skill, dpm,
        ) = row
        players[name] = {
            "player_guid": guid,
            "kills": kills,
            "deaths": deaths,
            "damage_given": dmg_given,
            "damage_received": dmg_received,
            "accuracy": accuracy,
            "headshots": headshots,
            "headshot_kills": hs_kills,
            "revives_given": revives,
            "time_played_seconds": time_played,
            "team": team,
            "efficiency": efficiency,
            "kdr": float(kdr) if kdr else None,
            "skill_rating": float(skill) if skill else None,
            "dpm": float(dpm) if dpm else None,
        }

    return players


async def build_comparison(
    demo_player_stats: Dict[str, Dict[str, Any]],
    db_player_stats: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compare demo-derived stats with DB stats for matched players."""
    comparisons = []

    # Try to match by name (case-insensitive)
    db_lower = {k.lower(): (k, v) for k, v in db_player_stats.items()}

    for demo_name, demo_stats in demo_player_stats.items():
        match = db_lower.get(demo_name.lower())
        if not match:
            comparisons.append({
                "demo_name": demo_name,
                "db_name": None,
                "matched": False,
                "demo_stats": demo_stats,
                "db_stats": None,
            })
            continue

        db_name, db_stats = match
        comparisons.append({
            "demo_name": demo_name,
            "db_name": db_name,
            "matched": True,
            "demo_stats": demo_stats,
            "db_stats": db_stats,
        })

    # Add DB-only players
    matched_lower = {n.lower() for n in demo_player_stats}
    for db_name, db_stats in db_player_stats.items():
        if db_name.lower() not in matched_lower:
            comparisons.append({
                "demo_name": None,
                "db_name": db_name,
                "matched": False,
                "demo_stats": None,
                "db_stats": db_stats,
            })

    comparisons.sort(key=lambda c: -(c.get("db_stats") or c.get("demo_stats") or {}).get("kills", 0))
    return comparisons
