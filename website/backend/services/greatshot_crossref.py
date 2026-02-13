"""Cross-reference Greatshot demo analysis with ET:Legacy stats database."""

from __future__ import annotations

import logging
import re
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
    try:
        normalized = str(value).lower().strip()
    except Exception:
        return None
    return _WINNER_MAP.get(normalized)


def _extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract YYYY-MM-DD from demo filename if present.

    Examples:
        "2026-02-08-capture.dm_84" -> "2026-02-08"
        "demo_2026_02_08.dm_84" -> "2026-02-08"
        "gameplay.dm_84" -> None
    """
    if not filename:
        return None

    # Try standard format: YYYY-MM-DD
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)

    # Try underscore format: YYYY_MM_DD
    match = re.search(r'(\d{4})_(\d{2})_(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return None


_KD_RATIO_COLUMN_CACHE: Optional[str] = None
_KD_RATIO_COLUMN_CANDIDATES = ("kd_ratio", "kdr")


async def _resolve_kd_ratio_column(db) -> str:
    global _KD_RATIO_COLUMN_CACHE
    if _KD_RATIO_COLUMN_CACHE:
        return _KD_RATIO_COLUMN_CACHE

    for column in _KD_RATIO_COLUMN_CANDIDATES:
        row = await db.fetch_one(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'player_comprehensive_stats'
              AND column_name = $1
            LIMIT 1
            """,
            (column,),
        )
        if row:
            _KD_RATIO_COLUMN_CACHE = column
            break

    if not _KD_RATIO_COLUMN_CACHE:
        logger.warning("Greatshot crossref: no kd_ratio/kdr column found, defaulting to kd_ratio")
        _KD_RATIO_COLUMN_CACHE = "kd_ratio"

    return _KD_RATIO_COLUMN_CACHE


async def _calculate_player_overlap(
    demo_player_names: List[str],
    round_id: int,
    db,
) -> float:
    """Calculate percentage of player name overlap between demo and DB round.

    Returns:
        Float between 0.0 and 1.0 representing overlap percentage
    """
    if not demo_player_names:
        return 0.0

    db_result = await db.fetch_all(
        "SELECT DISTINCT player_name FROM player_comprehensive_stats WHERE round_id = $1",
        (round_id,)
    )

    if not db_result:
        return 0.0

    db_players = set([row[0].lower().strip() for row in db_result])
    demo_players = set([name.lower().strip() for name in demo_player_names])

    overlap_count = len(demo_players & db_players)
    return overlap_count / len(demo_players)


async def _validate_stats_match(
    demo_player_stats: Dict[str, Any],
    round_id: int,
    db,
) -> float:
    """Compare demo aggregate stats to DB stats, return confidence adjustment.

    Returns:
        Confidence adjustment (-30 to +15)
    """
    if not demo_player_stats:
        return 0.0

    # Calculate demo totals
    demo_kills = sum([p.get("kills", 0) for p in demo_player_stats.values()])

    if demo_kills == 0:
        return 0.0

    # Fetch DB totals
    db_result = await db.fetch_one(
        """SELECT
            SUM(kills) as total_kills,
            SUM(damage_given) as total_damage
           FROM player_comprehensive_stats
           WHERE round_id = $1""",
        (round_id,)
    )

    if not db_result or not db_result[0]:
        return 0.0

    db_kills = db_result[0] or 0

    if db_kills == 0:
        return 0.0

    # Calculate kill difference percentage
    kill_diff_pct = abs(demo_kills - db_kills) / db_kills

    # Confidence adjustments based on accuracy
    if kill_diff_pct <= 0.05:  # Within 5%
        return 15.0
    elif kill_diff_pct <= 0.15:  # Within 15%
        return 5.0
    elif kill_diff_pct >= 0.5:  # 50%+ difference - probably wrong
        return -30.0

    return 0.0


async def _match_single_round(
    demo_map: str,
    demo_round_data: Optional[Dict[str, Any]],
    demo_filename: str,
    demo_player_names: List[str],
    demo_player_stats: Dict[str, Any],
    db,
) -> Optional[Dict[str, Any]]:
    """Try to match a single demo round to a database round.

    Args:
        demo_map: Map name from demo
        demo_round_data: Round metadata (duration, winner, scores) or None
        demo_filename: Demo filename for date extraction
        demo_player_names: List of player names from demo
        demo_player_stats: Player stats dict from demo
        db: Database adapter

    Returns:
        Match dict with confidence or None
    """
    # Extract round-specific data
    duration_s = 0.0
    demo_winner = None
    demo_first_score = None
    demo_second_score = None

    if demo_round_data:
        duration_s = (demo_round_data.get("duration_ms") or 0) / 1000.0
        demo_winner = _normalize_winner(demo_round_data.get("winner"))
        demo_first_score = demo_round_data.get("first_place_score")
        demo_second_score = demo_round_data.get("second_place_score")

    # Extract date from filename for filtering
    demo_date = _extract_date_from_filename(demo_filename)

    # Step 1: Find candidate rounds by map name (and optionally date)
    if demo_date:
        # Filter by date to reduce false positives
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
              AND r.round_date = $2
            ORDER BY r.round_time DESC
            LIMIT 50
            """,
            (demo_map, demo_date),
        )
    else:
        # Fallback: just map name
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
            db_winner_norm = _normalize_winner(db_winner)
            if db_winner_norm and demo_winner == db_winner_norm:
                confidence += 20.0
                match_details.append("winner")

        # Score match
        if demo_first_score is not None and axis_score is not None and allies_score is not None:
            db_scores = sorted([int(axis_score), int(allies_score)], reverse=True)
            demo_scores = sorted([int(demo_first_score), int(demo_second_score or 0)], reverse=True)
            if db_scores == demo_scores:
                confidence += 20.0
                match_details.append("scores")

        # Player overlap validation (Phase 4)
        if demo_player_names:
            overlap = await _calculate_player_overlap(demo_player_names, round_id, db)
            if overlap >= 0.8:  # 80%+ players match
                confidence += 20.0
                match_details.append(f"players-{int(overlap*100)}%")
            elif overlap >= 0.5:  # 50%+ players match
                confidence += 10.0
                match_details.append(f"players-{int(overlap*100)}%")
            elif overlap > 0 and overlap < 0.3:  # < 30% overlap - suspicious
                confidence -= 10.0
                match_details.append(f"players-low-{int(overlap*100)}%")

        # Stats comparison validation (Phase 5)
        if demo_player_stats:
            stats_adj = await _validate_stats_match(demo_player_stats, round_id, db)
            confidence += stats_adj
            if stats_adj > 0:
                match_details.append("stats-validated")
            elif stats_adj < 0:
                match_details.append("stats-mismatch")

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

    # Minimum confidence threshold: 30 (map only) or 40 if we have date
    min_confidence = 40 if demo_date else 30
    if best_match and best_match["confidence"] < min_confidence:
        return None

    return best_match


async def find_matching_round(
    metadata: Dict[str, Any],
    db,
    demo_player_stats: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Try to match a demo's metadata to a round in the database.

    Supports multi-round demos (e.g., R1+R2 in one file).

    Args:
        metadata: Demo metadata including map, rounds, filename
        db: Database adapter
        demo_player_stats: Optional player stats from demo for validation

    Returns:
        Best match dict with round_id, confidence, and match details, or None
    """
    raw_map = metadata.get("map")
    if raw_map is None:
        demo_map = ""
    else:
        demo_map = str(raw_map).lower().strip()
    if not demo_map:
        return None

    demo_filename = metadata.get("filename", "")
    rounds_info = metadata.get("rounds") or []

    # Extract player names from stats for overlap validation
    demo_player_names = []
    if demo_player_stats:
        demo_player_names = list(demo_player_stats.keys())

    # Phase 2: Multi-round matching
    # Try to match each round in the demo
    if not rounds_info:
        # No per-round entries: preserve top-level metadata for matching.
        fallback_round_data = {
            "duration_ms": int(metadata.get("duration_ms") or 0),
            "winner": metadata.get("winner") or metadata.get("winning_team"),
            "first_place_score": metadata.get("first_place_score", metadata.get("firstPlaceScore")),
            "second_place_score": metadata.get("second_place_score", metadata.get("secondPlaceScore")),
        }
        return await _match_single_round(
            demo_map=demo_map,
            demo_round_data=fallback_round_data,
            demo_filename=demo_filename,
            demo_player_names=demo_player_names,
            demo_player_stats=demo_player_stats or {},
            db=db,
        )

    best_match = None
    best_confidence = 0.0

    for i, demo_round in enumerate(rounds_info):
        match = await _match_single_round(
            demo_map=demo_map,
            demo_round_data=demo_round,
            demo_filename=demo_filename,
            demo_player_names=demo_player_names,
            demo_player_stats=demo_player_stats or {},
            db=db,
        )

        if match and match["confidence"] > best_confidence:
            best_match = match
            best_confidence = match["confidence"]
            # Add which demo round this matched
            best_match["demo_round_index"] = i

    return best_match


async def enrich_with_db_stats(
    round_id: int,
    db,
) -> Dict[str, Any]:
    """Fetch full player stats from player_comprehensive_stats for a matched round."""
    kd_column = await _resolve_kd_ratio_column(db)
    rows = await db.fetch_all(
        f"""
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
            {kd_column} AS kdr,
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
        time_played_seconds = int(time_played) if time_played else 0
        time_played_minutes = round(time_played_seconds / 60.0, 2) if time_played_seconds > 0 else None
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
            "time_played_seconds": time_played_seconds,
            "time_played_minutes": time_played_minutes,
            # TPM in this context means time played minutes.
            "tpm": time_played_minutes,
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
