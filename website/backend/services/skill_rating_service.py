"""
ET:Legacy Individual Performance Rating (Option C).

Computes an ET_Rating per player based on percentile-normalized stats.
Inspired by HLTV 2.0/3.0, Valorant ACS, and PandaSkill research.

Formula:
  ET_Rating = w1*norm(DPM) + w2*norm(KPR) - w3*norm(DPR)
            + w4*norm(revive_rate) + w5*norm(objective_rate)
            + w6*norm(survival_rate) + w7*norm(useful_kill_rate)
            + w8*norm(denied_playtime_per_min) + constant

Each metric is percentile-normalized (0.0 to 1.0) against the player population.

Scoping:
  - Global: all-time rating across all rounds
  - Session: rating for a specific round_date (gaming session proxy)
  - Map: rating for a specific round_date + map_name
"""

import bisect
import json
import logging

logger = logging.getLogger(__name__)

# Default weights (v1.0 - balanced start, tune with community feedback)
WEIGHTS = {
    "dpm": 0.18,                  # Damage per minute (alive time)
    "kpr": 0.15,                  # Kills per round
    "dpr": -0.12,                 # Deaths per round (penalty)
    "revive_rate": 0.12,          # Revives per round (medic value)
    "objective_rate": 0.12,       # Objectives per round (engineer value)
    "survival_rate": 0.10,        # % of round time alive
    "useful_kill_rate": 0.10,     # Useful kills / total kills
    "denied_playtime_pm": 0.06,   # Denied enemy playtime per minute
    "accuracy": 0.05,             # Weapon accuracy
}
CONSTANT = 0.15  # Baseline so ratings center ~0.50 for average player

# Minimum rounds to be rated (global). Per-session has no minimum.
MIN_ROUNDS = 5

# Tier thresholds (must match frontend SkillRating.tsx getTier())
TIERS = [
    (0.85, "elite"),
    (0.70, "veteran"),
    (0.55, "experienced"),
    (0.40, "regular"),
    (0.00, "newcomer"),
]


def get_tier(rating: float) -> str:
    """Return tier name for a given rating."""
    for threshold, name in TIERS:
        if rating >= threshold:
            return name
    return "newcomer"

# Shared SQL fragment for the 9 metrics aggregate
_METRICS_SQL = """
    COALESCE(AVG(dpm) FILTER (WHERE dpm IS NOT NULL AND dpm > 0), 0) as avg_dpm,
    COALESCE(SUM(kills)::REAL / NULLIF(COUNT(*), 0), 0) as kpr,
    COALESCE(SUM(deaths)::REAL / NULLIF(COUNT(*), 0), 0) as dpr,
    COALESCE(SUM(revives_given)::REAL / NULLIF(COUNT(*), 0), 0) as revive_rate,
    COALESCE(
        (SUM(objectives_completed) + SUM(objectives_destroyed) + SUM(objectives_stolen) + SUM(objectives_returned))::REAL
        / NULLIF(COUNT(*), 0), 0
    ) as objective_rate,
    COALESCE(AVG(
        CASE WHEN time_played_seconds > 0
        THEN (time_played_seconds - COALESCE(
            CASE WHEN time_dead_minutes > 0 THEN time_dead_minutes * 60 ELSE 0 END, 0
        ))::REAL / time_played_seconds
        ELSE 0 END
    ), 0) as survival_rate,
    COALESCE(
        SUM(most_useful_kills)::REAL / NULLIF(SUM(kills), 0), 0
    ) as useful_kill_rate,
    COALESCE(
        SUM(denied_playtime)::REAL / NULLIF(SUM(time_played_seconds) / 60.0, 0), 0
    ) as denied_playtime_pm,
    COALESCE(AVG(accuracy) FILTER (WHERE accuracy IS NOT NULL AND accuracy > 0), 0) as avg_accuracy
"""


def _row_to_stats(r, offset: int = 0) -> dict:
    """Extract 9 metrics from a DB row starting at the given column offset."""
    return {
        "dpm": float(r[offset]),
        "kpr": float(r[offset + 1]),
        "dpr": float(r[offset + 2]),
        "revive_rate": float(r[offset + 3]),
        "objective_rate": float(r[offset + 4]),
        "survival_rate": float(r[offset + 5]),
        "useful_kill_rate": float(r[offset + 6]),
        "denied_playtime_pm": float(r[offset + 7]),
        "accuracy": float(r[offset + 8]),
    }


async def compute_population_percentiles(db) -> dict:
    """
    Query aggregate stats for all players with enough rounds,
    return sorted value lists for each metric (used for percentile lookup).
    """
    rows = await db.fetch_all(f"""
        SELECT player_guid, COUNT(*) as rounds, {_METRICS_SQL}
        FROM player_comprehensive_stats
        GROUP BY player_guid
        HAVING COUNT(*) >= $1
    """, (MIN_ROUNDS,))

    if not rows:
        return {}

    return {
        name: sorted([float(r[i]) for r in rows])
        for i, name in enumerate(WEIGHTS.keys(), start=2)
    }


def _percentile(sorted_values: list, value: float) -> float:
    """Return 0.0-1.0 percentile of value within sorted list (O(log n))."""
    if not sorted_values:
        return 0.5
    n = len(sorted_values)
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    return (left + right) / (2 * n)


def calculate_et_rating(player_stats: dict, percentiles: dict) -> tuple[float, dict]:
    """
    Calculate ET_Rating for a single player.

    Returns:
        (rating, components_dict) where components has per-metric breakdown.
    """
    components = {}
    rating = CONSTANT

    for metric, weight in WEIGHTS.items():
        value = player_stats.get(metric, 0)
        pct = _percentile(percentiles.get(metric, []), value)
        components[metric] = {
            "raw": round(value, 3),
            "percentile": round(pct, 3),
            "weight": weight,
            "contribution": round(weight * pct, 4),
        }
        rating += weight * pct

    # Clamp to 0.0 - 1.5 range (theoretical max ~1.15 for exceptional player)
    rating = max(0.0, min(1.5, rating))

    return round(rating, 4), components


async def compute_all_ratings(db) -> list[dict]:
    """
    Compute ET_Rating for all players with enough rounds.
    Returns sorted list of player rating dicts.
    """
    logger.info("Computing population percentiles...")
    percentiles = await compute_population_percentiles(db)
    if not percentiles:
        logger.warning("No player data for rating computation")
        return []

    logger.info("Querying player aggregates...")
    rows = await db.fetch_all(f"""
        SELECT player_guid, MAX(player_name) as display_name,
               COUNT(*) as rounds, {_METRICS_SQL}
        FROM player_comprehensive_stats
        GROUP BY player_guid
        HAVING COUNT(*) >= $1
        ORDER BY player_guid
    """, (MIN_ROUNDS,))

    results = []
    for r in rows:
        stats = _row_to_stats(r, offset=3)
        rating, components = calculate_et_rating(stats, percentiles)
        results.append({
            "player_guid": r[0],
            "display_name": r[1],
            "rounds": int(r[2]),
            "et_rating": rating,
            "components": components,
        })

    results.sort(key=lambda x: x["et_rating"], reverse=True)
    logger.info("Computed ratings for %d players", len(results))
    return results


async def compute_and_store_ratings(db) -> int:
    """Compute all ratings and upsert into player_skill_ratings table."""
    results = await compute_all_ratings(db)

    for player in results:
        components_json = json.dumps(player["components"])

        tier = get_tier(player["et_rating"])

        await db.execute(
            """INSERT INTO player_skill_ratings
               (player_guid, display_name, et_rating, rating_class, games_rated, last_rated_at, components)
               VALUES ($1, $2, $3, $4, $5, NOW(), $6)
               ON CONFLICT (player_guid) DO UPDATE SET
                   display_name = EXCLUDED.display_name,
                   et_rating = EXCLUDED.et_rating,
                   rating_class = EXCLUDED.rating_class,
                   games_rated = EXCLUDED.games_rated,
                   last_rated_at = NOW(),
                   components = EXCLUDED.components""",
            (player["player_guid"], player["display_name"], player["et_rating"],
             tier, player["rounds"], components_json),
        )

        # Track global rating history snapshot
        await db.execute(
            """INSERT INTO player_skill_history
               (player_guid, et_rating, components, calculated_at, scope, rounds_in_scope)
               VALUES ($1, $2, $3, NOW(), 'global', $4)""",
            (player["player_guid"], player["et_rating"],
             components_json, player["rounds"]),
        )

    logger.info("Stored ratings + history for %d players", len(results))
    return len(results)


# ---------------------------------------------------------------------------
# Per-session & per-map scoped ratings
# ---------------------------------------------------------------------------

async def compute_session_ratings(db, player_guid: str, session_date: str,
                                  percentiles: dict = None) -> dict | None:
    """
    Compute ET_Rating for a single player in a single session (round_date).
    Uses population percentiles for comparison (how you played THIS session
    vs how EVERYONE plays overall).

    Returns dict with rating, components, rounds, maps or None if no data.
    """
    if percentiles is None:
        percentiles = await compute_population_percentiles(db)
        if not percentiles:
            return None

    row = await db.fetch_one(f"""
        SELECT COUNT(*) as rounds,
               COUNT(DISTINCT map_name) as maps,
               {_METRICS_SQL}
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND round_date = $2
    """, (player_guid, session_date))

    if not row or int(row[0]) == 0:
        return None

    stats = _row_to_stats(row, offset=2)
    rating, components = calculate_et_rating(stats, percentiles)

    return {
        "session_date": session_date,
        "rounds": int(row[0]),
        "maps": int(row[1]),
        "session_rating": rating,
        "components": components,
    }


async def compute_session_map_ratings(db, player_guid: str, session_date: str,
                                      percentiles: dict = None) -> list[dict]:
    """
    Compute per-map ratings for a player within a session.
    Returns list of dicts sorted by map_name.
    """
    if percentiles is None:
        percentiles = await compute_population_percentiles(db)
        if not percentiles:
            return []

    rows = await db.fetch_all(f"""
        SELECT map_name, COUNT(*) as rounds, {_METRICS_SQL}
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND round_date = $2
        GROUP BY map_name
        ORDER BY map_name
    """, (player_guid, session_date))

    results = []
    for r in rows:
        stats = _row_to_stats(r, offset=2)
        rating, components = calculate_et_rating(stats, percentiles)
        results.append({
            "map_name": r[0],
            "rounds": int(r[1]),
            "map_rating": rating,
            "components": components,
        })

    results.sort(key=lambda x: x["map_rating"], reverse=True)
    return results


async def get_player_session_history(db, player_guid: str,
                                     range_days: int = 30) -> list[dict]:
    """
    Get rating for each gaming session (round_date) the player participated in.
    Each session rating is computed against the current population percentiles.

    Returns list of session dicts sorted chronologically.
    """
    percentiles = await compute_population_percentiles(db)
    if not percentiles:
        return []

    # Get all session dates for this player within range
    # round_date is TEXT (ISO format), so compare as string
    date_rows = await db.fetch_all("""
        SELECT DISTINCT round_date
        FROM player_comprehensive_stats
        WHERE player_guid = $1
          AND round_date >= TO_CHAR(CURRENT_DATE - $2::INTEGER, 'YYYY-MM-DD')
        ORDER BY round_date ASC
    """, (player_guid, range_days))

    sessions = []
    cumulative_rating = None

    for dr in date_rows:
        session_date = dr[0]
        date_str = session_date.isoformat() if hasattr(session_date, "isoformat") else str(session_date)

        result = await compute_session_ratings(db, player_guid, date_str, percentiles)
        if not result:
            continue

        # Compute cumulative rating up to and including this date
        # round_date is TEXT (ISO format), <= comparison works lexicographically
        cum_row = await db.fetch_one(f"""
            SELECT COUNT(*) as rounds, {_METRICS_SQL}
            FROM player_comprehensive_stats
            WHERE player_guid = $1 AND round_date <= $2
        """, (player_guid, date_str))

        cum_rating = None
        delta = None
        if cum_row and int(cum_row[0]) >= MIN_ROUNDS:
            cum_stats = _row_to_stats(cum_row, offset=1)
            cum_rating, _ = calculate_et_rating(cum_stats, percentiles)
            if cumulative_rating is not None:
                delta = round(cum_rating - cumulative_rating, 4)
            cumulative_rating = cum_rating

        result["cumulative_rating"] = cum_rating
        result["delta"] = delta
        sessions.append(result)

    return sessions
