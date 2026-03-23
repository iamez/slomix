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
"""

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

# Minimum rounds to be rated
MIN_ROUNDS = 5


async def compute_population_percentiles(db) -> dict:
    """
    Query aggregate stats for all players with enough rounds,
    return percentile breakpoints for each metric.
    """
    rows = await db.fetch_all(f"""
        SELECT
            player_guid,
            COUNT(*) as rounds,
            COALESCE(AVG(NULLIF(dpm, 0)), 0) as avg_dpm,
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
            COALESCE(AVG(NULLIF(accuracy, 0)), 0) as avg_accuracy
        FROM player_comprehensive_stats
        GROUP BY player_guid
        HAVING COUNT(*) >= {MIN_ROUNDS}
    """)

    if not rows:
        return {}

    # Build sorted lists for each metric
    metrics = {
        "dpm": sorted([float(r[2]) for r in rows]),
        "kpr": sorted([float(r[3]) for r in rows]),
        "dpr": sorted([float(r[4]) for r in rows]),
        "revive_rate": sorted([float(r[5]) for r in rows]),
        "objective_rate": sorted([float(r[6]) for r in rows]),
        "survival_rate": sorted([float(r[7]) for r in rows]),
        "useful_kill_rate": sorted([float(r[8]) for r in rows]),
        "denied_playtime_pm": sorted([float(r[9]) for r in rows]),
        "accuracy": sorted([float(r[10]) for r in rows]),
    }

    return metrics


def _percentile(sorted_values: list, value: float) -> float:
    """Return 0.0–1.0 percentile of value within sorted list."""
    if not sorted_values:
        return 0.5
    n = len(sorted_values)
    count_below = sum(1 for v in sorted_values if v < value)
    count_equal = sum(1 for v in sorted_values if v == value)
    return (count_below + count_equal * 0.5) / n


def calculate_et_rating(player_stats: dict, percentiles: dict) -> tuple[float, dict]:
    """
    Calculate ET_Rating for a single player.

    Args:
        player_stats: dict with keys matching metric names
        percentiles: dict of sorted value lists per metric

    Returns:
        (rating, components_dict)
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
        SELECT
            player_guid,
            MAX(player_name) as display_name,
            COUNT(*) as rounds,
            COALESCE(AVG(NULLIF(dpm, 0)), 0) as avg_dpm,
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
            COALESCE(AVG(NULLIF(accuracy, 0)), 0) as avg_accuracy
        FROM player_comprehensive_stats
        GROUP BY player_guid
        HAVING COUNT(*) >= {MIN_ROUNDS}
        ORDER BY player_guid
    """)

    results = []
    for r in rows:
        stats = {
            "dpm": float(r[3]),
            "kpr": float(r[4]),
            "dpr": float(r[5]),
            "revive_rate": float(r[6]),
            "objective_rate": float(r[7]),
            "survival_rate": float(r[8]),
            "useful_kill_rate": float(r[9]),
            "denied_playtime_pm": float(r[10]),
            "accuracy": float(r[11]),
        }

        rating, components = calculate_et_rating(stats, percentiles)

        results.append({
            "player_guid": r[0],
            "display_name": r[1],
            "rounds": int(r[2]),
            "et_rating": rating,
            "components": components,
        })

    results.sort(key=lambda x: x["et_rating"], reverse=True)
    logger.info(f"Computed ratings for {len(results)} players")
    return results


async def compute_and_store_ratings(db) -> int:
    """Compute all ratings and upsert into player_skill_ratings table."""
    results = await compute_all_ratings(db)

    for player in results:
        await db.execute(
            """INSERT INTO player_skill_ratings
               (player_guid, display_name, et_rating, games_rated, last_rated_at, components)
               VALUES ($1, $2, $3, $4, NOW(), $5)
               ON CONFLICT (player_guid) DO UPDATE SET
                   display_name = EXCLUDED.display_name,
                   et_rating = EXCLUDED.et_rating,
                   games_rated = EXCLUDED.games_rated,
                   last_rated_at = NOW(),
                   components = EXCLUDED.components""",
            (player["player_guid"], player["display_name"], player["et_rating"],
             player["rounds"], json.dumps(player["components"])),
        )

    return len(results)
