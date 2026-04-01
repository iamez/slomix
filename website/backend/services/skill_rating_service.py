"""
ET:Legacy Individual Performance Rating (v2.0).

Computes an ET_Rating per player based on percentile-normalized stats.
Inspired by HLTV 2.0/3.0, Valorant ACS, PandaSkill research, and
competitive ET stopwatch format (class-based, objective-sequential, respawn).

v2.0 extends from 9 PCS-only metrics to 15 metrics incorporating
proximity analytics: kill quality, crossfire coordination, trade kills,
kill permanence, clutch performance, and spawn timing efficiency.

Formula:
  ET_Rating = constant + Σ(weight_i × percentile(metric_i))

Each metric is percentile-normalized (0.0 to 1.0) against the player population.

Scoping:
  - Global: all-time rating across all rounds
  - Session: rating for a specific round_date (gaming session proxy)
  - Map: rating for a specific round_date + map_name

Format-agnostic: metrics work in 3v3 (medic/engi/covy) and 6v6 (full roster).
"""

import bisect
import json
import logging

logger = logging.getLogger(__name__)

# v2.0 weights: 9 PCS metrics + 6 proximity metrics = 15 total
WEIGHTS = {
    # ── PCS Core Combat (34%) ─────────────────────────────────────
    "dpm": 0.12,                  # Damage per minute (alive time)
    "kpr": 0.10,                  # Kills per round
    "dpr": -0.08,                 # Deaths per round (penalty)
    "accuracy": 0.04,             # Weapon accuracy
    # ── PCS Survival & Support (20%) ──────────────────────────────
    "revive_rate": 0.07,          # Revives per round (medic = default class in 3v3)
    "survival_rate": 0.07,        # % of round time alive
    "useful_kill_rate": 0.06,     # Useful kills / total kills
    # ── PCS Objective & Timing (10%) ──────────────────────────────
    "objective_rate": 0.06,       # Objectives per round
    "denied_playtime_pm": 0.04,   # Denied enemy playtime per minute
    # ── Proximity: Team Contribution (22%) ────────────────────────
    "kill_quality": 0.10,         # Kill Quality Index (simplified KIS proxy)
    "crossfire_rate": 0.06,       # Crossfire kills / total kills
    "trade_rate": 0.06,           # Trade kills / total kills
    # ── Proximity: Clutch & Permanence (10%) ──────────────────────
    "kill_permanence": 0.05,      # Gib rate (permanent kills / total kills)
    "clutch_factor": 0.05,        # Low HP + outnumbered kills / total kills
    # ── Proximity: Spawn Timing (4%) ─────────────────────────────
    "spawn_timing_eff": 0.04,     # Avg spawn timing score (0-1)
}
CONSTANT = 0.15  # Baseline so ratings center ~0.50 for average player

# Metrics sourced from proximity tables (need LEFT JOINs)
PROXIMITY_METRICS = frozenset({
    "kill_quality", "crossfire_rate", "trade_rate",
    "kill_permanence", "clutch_factor", "spawn_timing_eff",
})

# Metrics sourced from PCS only
PCS_METRICS = frozenset(WEIGHTS.keys()) - PROXIMITY_METRICS

# Column order as returned by compute_all_ratings() SQL (after guid, name, rounds)
# CRITICAL: this MUST match the SELECT column order, not WEIGHTS dict order!
_GLOBAL_SQL_COLUMNS = [
    "dpm", "kpr", "dpr", "revive_rate", "objective_rate",
    "survival_rate", "useful_kill_rate", "denied_playtime_pm", "accuracy",
    "kill_quality", "crossfire_rate", "trade_rate",
    "kill_permanence", "clutch_factor", "spawn_timing_eff",
]

# Column order for PCS-only queries (session/map scope)
_PCS_SQL_COLUMNS = [
    "dpm", "kpr", "dpr", "revive_rate", "objective_rate",
    "survival_rate", "useful_kill_rate", "denied_playtime_pm", "accuracy",
]

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


def _row_to_stats(r, offset: int = 0, *, has_proximity: bool = True) -> dict:
    """Extract metrics from a DB row starting at the given column offset.

    When has_proximity=True (default for global compute), expects 15 columns.
    When has_proximity=False (session/map scope), expects 9 PCS columns and
    fills proximity metrics with neutral defaults (0.5 percentile equivalent).
    """
    stats = {
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
    if has_proximity:
        stats.update({
            "kill_quality": float(r[offset + 9]),
            "crossfire_rate": float(r[offset + 10]),
            "trade_rate": float(r[offset + 11]),
            "kill_permanence": float(r[offset + 12]),
            "clutch_factor": float(r[offset + 13]),
            "spawn_timing_eff": float(r[offset + 14]),
        })
    else:
        # No proximity data available — use neutral defaults
        stats.update({
            "kill_quality": 1.0,
            "crossfire_rate": 0.0,
            "trade_rate": 0.0,
            "kill_permanence": 0.0,
            "clutch_factor": 0.0,
            "spawn_timing_eff": 0.0,
        })
    return stats


# DEPRECATED: Use compute_all_ratings() single-pass instead. Kept for backward compat.
async def compute_population_percentiles(db) -> dict:
    """
    Query aggregate stats for all players with enough rounds,
    return sorted value lists for each metric (used for percentile lookup).
    """
    rows = await db.fetch_all("""
        SELECT player_guid, COUNT(*) as rounds,
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
        FROM player_comprehensive_stats
        GROUP BY player_guid
        HAVING COUNT(*) >= $1
    """, (MIN_ROUNDS,))

    if not rows:
        return {}

    # Build percentiles using explicit PCS column order (NOT WEIGHTS dict order)
    return {
        col_name: sorted([float(r[i + 2]) for r in rows])
        for i, col_name in enumerate(_PCS_SQL_COLUMNS)
    }


def _percentile(sorted_values: list, value: float) -> float:
    """Return 0.0-1.0 percentile of value within sorted list (O(log n))."""
    if not sorted_values:
        return 0.5
    n = len(sorted_values)
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    return (left + right) / (2 * n)


def calculate_et_rating(player_stats: dict, percentiles: dict,
                        *, pcs_only: bool = False) -> tuple[float, dict]:
    """
    Calculate ET_Rating for a single player.

    When pcs_only=True (session/map scope without proximity data), only PCS
    metrics contribute. The rating is scaled so that an average PCS-only
    player scores ~0.50, same as an average global player. This prevents
    session ratings from being systematically lower than global ratings.

    Returns:
        (rating, components_dict) where components has per-metric breakdown.
    """
    components = {}
    rating = CONSTANT

    pcs_weight_sum = sum(abs(w) for m, w in WEIGHTS.items() if m in PCS_METRICS)
    # Scale factor: if only PCS metrics contribute, scale up so they fill the full range
    # pcs_weight_sum ≈ 0.64, total_weight_sum = 1.00, so scale ≈ 1.5625
    scale = 1.0 / pcs_weight_sum if pcs_only else 1.0

    for metric, weight in WEIGHTS.items():
        if pcs_only and metric in PROXIMITY_METRICS:
            # Skip proximity metrics entirely — don't penalize with 0th percentile
            components[metric] = {
                "raw": 0, "percentile": None, "weight": weight,
                "contribution": 0, "note": "proximity_data_unavailable",
            }
            continue

        value = player_stats.get(metric, 0)
        pct = _percentile(percentiles.get(metric, []), value)
        effective_weight = weight * scale if pcs_only else weight
        components[metric] = {
            "raw": round(value, 3),
            "percentile": round(pct, 3),
            "weight": round(effective_weight, 4),
            "contribution": round(effective_weight * pct, 4),
        }
        rating += effective_weight * pct

    # Clamp to 0.0 - 1.5 range (theoretical max ~1.15 for exceptional player)
    rating = max(0.0, min(1.5, rating))

    return round(rating, 4), components


async def compute_all_ratings(db) -> list[dict]:
    """
    Compute ET_Rating for all players with enough rounds (v2.0).
    Returns sorted list of player rating dicts.
    Single query: PCS aggregates + proximity LEFT JOINs, percentiles + ratings
    computed from the same result set.

    Proximity metrics:
      - kill_quality: Kill Quality Index (gib-weighted outcome avg, simplified KIS)
      - crossfire_rate: crossfire kills / total kills (from player_teamplay_stats)
      - trade_rate: trade kills / total kills (from proximity_lua_trade_kill)
      - kill_permanence: gibbed kills / total kill outcomes (from proximity_kill_outcome)
      - clutch_factor: low HP (<30) or outnumbered kills / total kills
      - spawn_timing_eff: avg spawn_timing_score (from proximity_spawn_timing)
    """
    logger.info("Querying player aggregates with proximity data (v2 single pass)...")
    rows = await db.fetch_all("""
        SELECT
            pcs.player_guid,
            MAX(pcs.player_name) as display_name,
            COUNT(*) as rounds,
            -- PCS metrics (9) ──────────────────────────────────────
            COALESCE(AVG(pcs.dpm) FILTER (WHERE pcs.dpm IS NOT NULL AND pcs.dpm > 0), 0) as avg_dpm,
            COALESCE(SUM(pcs.kills)::REAL / NULLIF(COUNT(*), 0), 0) as kpr,
            COALESCE(SUM(pcs.deaths)::REAL / NULLIF(COUNT(*), 0), 0) as dpr,
            COALESCE(SUM(pcs.revives_given)::REAL / NULLIF(COUNT(*), 0), 0) as revive_rate,
            COALESCE(
                (SUM(pcs.objectives_completed) + SUM(pcs.objectives_destroyed)
                 + SUM(pcs.objectives_stolen) + SUM(pcs.objectives_returned))::REAL
                / NULLIF(COUNT(*), 0), 0
            ) as objective_rate,
            COALESCE(AVG(
                CASE WHEN pcs.time_played_seconds > 0
                THEN (pcs.time_played_seconds - COALESCE(
                    CASE WHEN pcs.time_dead_minutes > 0 THEN pcs.time_dead_minutes * 60 ELSE 0 END, 0
                ))::REAL / pcs.time_played_seconds
                ELSE 0 END
            ), 0) as survival_rate,
            COALESCE(
                SUM(pcs.most_useful_kills)::REAL / NULLIF(SUM(pcs.kills), 0), 0
            ) as useful_kill_rate,
            COALESCE(
                SUM(pcs.denied_playtime)::REAL / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0), 0
            ) as denied_playtime_pm,
            COALESCE(AVG(pcs.accuracy) FILTER (WHERE pcs.accuracy IS NOT NULL AND pcs.accuracy > 0), 0) as avg_accuracy,
            -- Proximity metrics (6) ────────────────────────────────
            COALESCE(prox_quality.kill_quality, 1.0) as kill_quality,
            COALESCE(
                pts.crossfire_kills::REAL / NULLIF(SUM(pcs.kills), 0), 0
            ) as crossfire_rate,
            COALESCE(
                prox_trades.trade_count::REAL / NULLIF(SUM(pcs.kills), 0), 0
            ) as trade_rate,
            COALESCE(prox_perm.gib_rate, 0) as kill_permanence,
            COALESCE(prox_clutch.clutch_rate, 0) as clutch_factor,
            COALESCE(prox_spawn.avg_timing_score, 0) as spawn_timing_eff

        FROM player_comprehensive_stats pcs

        LEFT JOIN (
            SELECT player_guid_canonical as guid_c,
                SUM(crossfire_kills) as crossfire_kills
            FROM player_teamplay_stats
            WHERE player_guid_canonical IS NOT NULL
            GROUP BY player_guid_canonical
        ) pts ON pts.guid_c = pcs.player_guid

        LEFT JOIN (
            -- Kill Quality Index: gib-weighted outcome average (simplified KIS)
            SELECT killer_guid_canonical as guid_c,
                AVG(CASE outcome
                    WHEN 'gibbed' THEN 1.3
                    WHEN 'tapped_out' THEN 1.0
                    WHEN 'revived' THEN 0.5
                    ELSE 1.0
                END) as kill_quality
            FROM proximity_kill_outcome
            WHERE killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        ) prox_quality ON prox_quality.guid_c = pcs.player_guid

        LEFT JOIN (
            SELECT trader_guid_canonical as guid_c, COUNT(*) as trade_count
            FROM proximity_lua_trade_kill
            WHERE trader_guid_canonical IS NOT NULL
            GROUP BY trader_guid_canonical
        ) prox_trades ON prox_trades.guid_c = pcs.player_guid

        LEFT JOIN (
            SELECT killer_guid_canonical as guid_c,
                COUNT(*) FILTER (WHERE outcome = 'gibbed')::REAL
                / NULLIF(COUNT(*), 0) as gib_rate
            FROM proximity_kill_outcome
            WHERE killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        ) prox_perm ON prox_perm.guid_c = pcs.player_guid

        LEFT JOIN (
            -- Clutch: kills at low HP (<30) or outnumbered (team disadvantage)
            SELECT attacker_guid_canonical as guid_c,
                COUNT(*) FILTER (
                    WHERE (killer_health > 0 AND killer_health < 30)
                       OR (attacker_team = 'AXIS' AND axis_alive < allies_alive)
                       OR (attacker_team = 'ALLIES' AND allies_alive < axis_alive)
                )::REAL / NULLIF(COUNT(*), 0) as clutch_rate
            FROM proximity_combat_position
            WHERE event_type = 'kill' AND attacker_guid_canonical IS NOT NULL
            GROUP BY attacker_guid_canonical
        ) prox_clutch ON prox_clutch.guid_c = pcs.player_guid

        LEFT JOIN (
            SELECT killer_guid_canonical as guid_c, AVG(spawn_timing_score) as avg_timing_score
            FROM proximity_spawn_timing
            WHERE killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        ) prox_spawn ON prox_spawn.guid_c = pcs.player_guid

        GROUP BY pcs.player_guid, prox_quality.kill_quality,
                 pts.crossfire_kills, prox_trades.trade_count,
                 prox_perm.gib_rate, prox_clutch.clutch_rate,
                 prox_spawn.avg_timing_score
        HAVING COUNT(*) >= $1
        ORDER BY pcs.player_guid
    """, (MIN_ROUNDS,))

    if not rows:
        logger.warning("No player data for rating computation")
        return []

    # Build percentile lookup using explicit column mapping (NOT WEIGHTS dict order)
    # Columns: 0=guid, 1=name, 2=rounds, 3..11=PCS metrics, 12..17=proximity metrics
    percentiles = {
        col_name: sorted([float(r[i + 3]) for r in rows])
        for i, col_name in enumerate(_GLOBAL_SQL_COLUMNS)
    }

    results = []
    for r in rows:
        stats = _row_to_stats(r, offset=3, has_proximity=True)
        rating, components = calculate_et_rating(stats, percentiles)
        results.append({
            "player_guid": r[0],
            "display_name": r[1],
            "rounds": int(r[2]),
            "et_rating": rating,
            "components": components,
        })

    results.sort(key=lambda x: x["et_rating"], reverse=True)
    logger.info("Computed v2 ratings for %d players (15 metrics)", len(results))
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

    row = await db.fetch_one("""
        SELECT COUNT(*) as rounds,
        COUNT(DISTINCT map_name) as maps,
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
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND round_date = $2
    """, (player_guid, session_date))

    if not row or int(row[0]) == 0:
        return None

    stats = _row_to_stats(row, offset=2, has_proximity=False)
    rating, components = calculate_et_rating(stats, percentiles, pcs_only=True)

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

    rows = await db.fetch_all("""
        SELECT map_name, COUNT(*) as rounds,
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
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND round_date = $2
        GROUP BY map_name
        ORDER BY map_name
    """, (player_guid, session_date))

    results = []
    for r in rows:
        stats = _row_to_stats(r, offset=2, has_proximity=False)
        rating, components = calculate_et_rating(stats, percentiles, pcs_only=True)
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
        cum_row = await db.fetch_one("""
            SELECT COUNT(*) as rounds,
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
            FROM player_comprehensive_stats
            WHERE player_guid = $1 AND round_date <= $2
        """, (player_guid, date_str))

        cum_rating = None
        delta = None
        if cum_row and int(cum_row[0]) >= MIN_ROUNDS:
            cum_stats = _row_to_stats(cum_row, offset=1, has_proximity=False)
            cum_rating, _ = calculate_et_rating(cum_stats, percentiles, pcs_only=True)
            if cumulative_rating is not None:
                delta = round(cum_rating - cumulative_rating, 4)
            cumulative_rating = cum_rating

        result["cumulative_rating"] = cum_rating
        result["delta"] = delta
        sessions.append(result)

    return sessions
