"""
Proximity Composite Scoring System (prox_combat, prox_team, prox_gamesense, prox_overall).

All weights and metric definitions live in FORMULA_CONFIG below.
To tweak: edit weights, add/remove metrics, change min_samples.

Percentile normalization: rank / pool_size (0.0 to 1.0).
Inverted metrics (lower = better): percentile is flipped.
"""

import bisect
import logging
import math
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# FORMULA CONFIG — edit this to tweak scoring
# ═══════════════════════════════════════════════════════════════════════════

FORMULA_VERSION = "1.0"

# Minimum engagements/tracks to be scored (prevents noisy data)
MIN_ENGAGEMENTS = 10

# Category weights for prox_overall
CATEGORY_WEIGHTS = {
    "prox_combat": 0.40,
    "prox_team": 0.35,
    "prox_gamesense": 0.25,
}

# Metric definitions per category.
# Each metric: weight within category, invert (lower=better), label.
# The SQL queries that populate these are in _fetch_raw_metrics().
METRICS = {
    "prox_combat": {
        "label": "Combat",
        "description": "Individual fighting skill — aim, reflexes, kill quality",
        "metrics": {
            "headshot_pct":     {"weight": 0.20, "invert": False, "label": "Headshot %"},
            "escape_rate":      {"weight": 0.20, "invert": False, "label": "Escape Rate"},
            "return_fire_ms":   {"weight": 0.20, "invert": True,  "label": "Return Fire Speed"},
            "kpr":              {"weight": 0.15, "invert": False, "label": "Kill Permanence"},
            "peak_speed":       {"weight": 0.10, "invert": False, "label": "Peak Speed"},
            "dodge_ms":         {"weight": 0.15, "invert": True,  "label": "Dodge Speed"},
        },
    },
    "prox_team": {
        "label": "Team",
        "description": "Team coordination — trades, crossfire, support, revive dependency",
        "metrics": {
            "spawn_score":           {"weight": 0.20, "invert": False, "label": "Spawn Timing"},
            "crossfire_rate":        {"weight": 0.20, "invert": False, "label": "Crossfire Rate"},
            "support_reaction_ms":   {"weight": 0.15, "invert": True,  "label": "Support Speed"},
            "trades_per_session":    {"weight": 0.20, "invert": False, "label": "Trade Kills"},
            "revive_rate_as_victim": {"weight": 0.15, "invert": False, "label": "Revive Magnet"},
            "focus_survival":        {"weight": 0.10, "invert": False, "label": "Focus Survival"},
        },
    },
    "prox_gamesense": {
        "label": "Game Sense",
        "description": "Positioning, movement discipline, timing",
        "metrics": {
            "distance_per_life":  {"weight": 0.15, "invert": False, "label": "Distance/Life"},
            "sprint_discipline":  {"weight": 0.15, "invert": False, "label": "Sprint Usage"},
            "post_spawn_rush":    {"weight": 0.15, "invert": False, "label": "Post-Spawn Rush"},
            "stance_variety":     {"weight": 0.15, "invert": False, "label": "Stance Variety"},
            "timed_kills":        {"weight": 0.20, "invert": False, "label": "Timed Kills"},
            "denied_time":        {"weight": 0.20, "invert": False, "label": "Denied Enemy Time"},
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# COMPUTATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def _percentile_rank(values: list[float]) -> list[float]:
    """Return percentile rank (0.0-1.0) for each value. Ties get average rank."""
    if not values:
        return []
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    result = []
    for v in values:
        # Position in sorted list (0-based), normalized to 0-1
        pos = bisect.bisect_right(sorted_vals, v)
        result.append(pos / n)
    return result


def _compute_category_score(
    player_raw: dict[str, float],
    category_key: str,
    percentile_maps: dict[str, dict[str, float]],
) -> tuple[float, dict]:
    """Compute weighted score for one category. Returns (score, breakdown)."""
    cat_config = METRICS[category_key]
    total_weight = sum(m["weight"] for m in cat_config["metrics"].values())
    score = 0.0
    breakdown = {}

    for metric_key, metric_cfg in cat_config["metrics"].items():
        raw = player_raw.get(metric_key)
        pctl = percentile_maps.get(metric_key, {}).get(
            player_raw.get("__guid__", ""), 0.5
        )
        if metric_cfg["invert"]:
            pctl = 1.0 - pctl

        weight_norm = metric_cfg["weight"] / total_weight
        contribution = pctl * weight_norm * 100
        score += contribution

        breakdown[metric_key] = {
            "raw": round(raw, 3) if raw is not None else None,
            "percentile": round(pctl, 3),
            "weight": metric_cfg["weight"],
            "contribution": round(contribution, 2),
            "label": metric_cfg["label"],
        }

    return round(score, 2), breakdown


async def compute_prox_scores(db, range_days: int = 30, player_guid: str | None = None):
    """
    Main entry point. Computes prox_combat, prox_team, prox_gamesense, prox_overall
    for all players (or one player) within range_days.

    Returns list of player score dicts.
    """
    range_days = max(1, min(int(range_days), 365))
    raw_data = await _fetch_raw_metrics(db, range_days)

    if not raw_data:
        return []

    # Filter to single player if requested (but keep all for percentile context)
    all_guids = list(raw_data.keys())

    # Filter out players with too few engagements
    qualified_guids = [g for g in all_guids if raw_data[g].get("engagements", 0) >= MIN_ENGAGEMENTS]
    if not qualified_guids:
        return []

    # Compute percentile maps for each metric
    all_metric_keys = set()
    for cat in METRICS.values():
        all_metric_keys.update(cat["metrics"].keys())

    percentile_maps: dict[str, dict[str, float]] = {}
    for mkey in all_metric_keys:
        # Only include players who have actual data for this metric
        with_data = [(g, raw_data[g][mkey]) for g in qualified_guids if raw_data[g].get(mkey) is not None]
        if with_data:
            vals_only = [v for _, v in with_data]
            pctls = _percentile_rank(vals_only)
            pctl_map = {g: p for (g, _), p in zip(with_data, pctls)}
        else:
            pctl_map = {}
        # Players without data for this metric get neutral 0.5
        percentile_maps[mkey] = {g: pctl_map.get(g, 0.5) for g in qualified_guids}

    # Compute scores per player
    results = []
    target_guids = [player_guid] if player_guid and player_guid in raw_data else qualified_guids

    for guid in target_guids:
        if guid not in qualified_guids and guid != player_guid:
            continue

        pdata = raw_data[guid]
        pdata["__guid__"] = guid
        category_scores = {}
        category_breakdowns = {}

        for cat_key in METRICS:
            score, breakdown = _compute_category_score(pdata, cat_key, percentile_maps)
            category_scores[cat_key] = score
            category_breakdowns[cat_key] = breakdown

        # Overall
        overall = sum(
            category_scores[k] * CATEGORY_WEIGHTS[k]
            for k in CATEGORY_WEIGHTS
        )

        # Radar data (5-axis: three categories + 2 highlight axes)
        radar = [
            {"label": METRICS["prox_combat"]["label"], "value": category_scores["prox_combat"]},
            {"label": METRICS["prox_team"]["label"], "value": category_scores["prox_team"]},
            {"label": METRICS["prox_gamesense"]["label"], "value": category_scores["prox_gamesense"]},
            {"label": "Aim", "value": _sub_score(category_breakdowns, "prox_combat", ["headshot_pct", "return_fire_ms"])},
            {"label": "Clutch", "value": _sub_score(category_breakdowns, "prox_combat", ["escape_rate", "dodge_ms"])},
        ]

        results.append({
            "guid": guid,
            "name": pdata.get("name", guid[:8]),
            "engagements": pdata.get("engagements", 0),
            "tracks": pdata.get("tracks", 0),
            "prox_combat": category_scores.get("prox_combat", 0),
            "prox_team": category_scores.get("prox_team", 0),
            "prox_gamesense": category_scores.get("prox_gamesense", 0),
            "prox_overall": round(overall, 2),
            "prox_radar": radar,
            "breakdown": category_breakdowns,
        })

    # Sort by overall descending
    results.sort(key=lambda x: x["prox_overall"], reverse=True)

    # Add ranks
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


def _sub_score(breakdowns: dict, cat_key: str, metric_keys: list[str]) -> float:
    """Average contribution of specific metrics — for radar sub-axes."""
    cat = breakdowns.get(cat_key, {})
    vals = [cat[k]["percentile"] * 100 for k in metric_keys if k in cat]
    return round(sum(vals) / max(len(vals), 1), 2)


# ═══════════════════════════════════════════════════════════════════════════
# DATA FETCHING — one query per source table
# ═══════════════════════════════════════════════════════════════════════════

async def _fetch_raw_metrics(db, range_days: int) -> dict[str, dict]:
    """
    Fetch raw per-player metric values from all source tables.
    Returns {guid: {metric_key: value, ...}} merged dict.
    """
    since_date = date.today() - timedelta(days=int(range_days))
    players: dict[str, dict] = {}

    def _merge(guid: str, name: str, data: dict):
        if not guid:
            return
        if guid not in players:
            players[guid] = {"name": name, "engagements": 0, "tracks": 0}
        players[guid].update({k: v for k, v in data.items() if v is not None})
        # Keep best name (longest, likely most recent)
        if name and len(name) > len(players[guid].get("name", "")):
            players[guid]["name"] = name

    # 1. Engagements: escape_rate, engagement count
    try:
        rows = await db.fetch_all("""
            SELECT target_guid, MAX(target_name) as name,
                   COUNT(*) as engagements,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END)::REAL
                     / NULLIF(COUNT(*), 0) as escape_rate
            FROM combat_engagement
            WHERE session_date >= $1
            GROUP BY target_guid
        """, (since_date,))
        for r in rows:
            _merge(r[0], r[1], {
                "engagements": int(r[2] or 0),
                "escape_rate": float(r[3] or 0),
            })
    except Exception as e:
        logger.warning("prox_scoring: combat_engagement query failed: %s", e)

    # 2. Reactions: return_fire_ms, dodge_ms, support_reaction_ms
    try:
        rows = await db.fetch_all("""
            SELECT target_guid, MAX(target_name),
                   AVG(return_fire_ms) as avg_rf,
                   AVG(dodge_reaction_ms) as avg_dodge,
                   AVG(support_reaction_ms) as avg_support
            FROM proximity_reaction_metric
            WHERE session_date >= $1
            GROUP BY target_guid
        """, (since_date,))
        for r in rows:
            _merge(r[0], r[1], {
                "return_fire_ms": float(r[2]) if r[2] else None,
                "dodge_ms": float(r[3]) if r[3] else None,
                "support_reaction_ms": float(r[4]) if r[4] else None,
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_reaction_metric query failed: %s", e)

    # 3. Spawn timing: avg score, timed kills
    try:
        rows = await db.fetch_all("""
            SELECT killer_guid, MAX(killer_name),
                   AVG(spawn_timing_score) as avg_score,
                   COUNT(*) as timed_kills
            FROM proximity_spawn_timing
            WHERE session_date >= $1
            GROUP BY killer_guid
        """, (since_date,))
        for r in rows:
            _merge(r[0], r[1], {
                "spawn_score": float(r[2] or 0),
                "timed_kills": float(r[3] or 0),
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_spawn_timing query failed: %s", e)

    # 4. Movement: speed, sprint, distance, stance, post_spawn
    try:
        rows = await db.fetch_all("""
            SELECT player_guid, MAX(player_name),
                   COUNT(*) as tracks,
                   AVG(avg_speed) as avg_speed,
                   MAX(peak_speed) as peak_speed,
                   AVG(sprint_percentage) as sprint_pct,
                   AVG(total_distance) as avg_distance,
                   AVG(post_spawn_distance) as avg_post_spawn,
                   AVG(stance_standing_sec) as avg_standing,
                   AVG(stance_crouching_sec) as avg_crouching,
                   AVG(stance_prone_sec) as avg_prone
            FROM player_track
            WHERE session_date >= $1
              AND peak_speed IS NOT NULL
            GROUP BY player_guid
        """, (since_date,))
        for r in rows:
            tracks = int(r[2] or 0)
            standing = float(r[8] or 0)
            crouching = float(r[9] or 0)
            prone = float(r[10] or 0)
            total_stance = standing + crouching + prone
            # Stance variety: entropy-like measure (max when evenly split = 1.0)
            stance_variety = 0.0
            if total_stance > 0:
                fracs = [standing / total_stance, crouching / total_stance, prone / total_stance]
                # Normalized entropy: -sum(p*log(p)) / log(3)
                entropy = 0.0
                for f in fracs:
                    if f > 0:
                        entropy -= f * math.log(f)
                stance_variety = entropy / math.log(3)  # 0 to 1

            _merge(r[0], r[1], {
                "tracks": tracks,
                "peak_speed": float(r[4] or 0),
                "sprint_discipline": float(r[5] or 0),
                "distance_per_life": float(r[6] or 0),
                "post_spawn_rush": float(r[7] or 0),
                "stance_variety": stance_variety,
            })
    except Exception as e:
        logger.warning("prox_scoring: player_track query failed: %s", e)

    # 5. Kill outcomes: KPR (as killer)
    try:
        rows = await db.fetch_all("""
            SELECT killer_guid, MAX(killer_name),
                   COUNT(*) as total_kills,
                   SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END) as gibs,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) as revived_against,
                   AVG(effective_denied_ms) as avg_denied
            FROM proximity_kill_outcome
            WHERE session_date >= $1
            GROUP BY killer_guid
            HAVING COUNT(*) >= 3
        """, (since_date,))
        for r in rows:
            gibs = int(r[3] or 0)
            rev = int(r[4] or 0)
            kpr = gibs / max(gibs + rev, 1)
            _merge(r[0], r[1], {
                "kpr": kpr,
                "denied_time": float(r[5] or 0),
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_kill_outcome (killer) query failed: %s", e)

    # 6. Kill outcomes: revive rate (as victim)
    try:
        rows = await db.fetch_all("""
            SELECT victim_guid, MAX(victim_name),
                   COUNT(*) as times_killed,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) as times_revived
            FROM proximity_kill_outcome
            WHERE session_date >= $1
            GROUP BY victim_guid
            HAVING COUNT(*) >= 3
        """, (since_date,))
        for r in rows:
            killed = int(r[2] or 0)
            revived = int(r[3] or 0)
            _merge(r[0], r[1], {
                "revive_rate_as_victim": revived / max(killed, 1),
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_kill_outcome (victim) query failed: %s", e)

    # 7. Hit regions: headshot %
    try:
        rows = await db.fetch_all("""
            SELECT attacker_guid, MAX(attacker_name),
                   SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END) as head_hits,
                   COUNT(*) as total_hits
            FROM proximity_hit_region
            WHERE session_date >= $1
            GROUP BY attacker_guid
            HAVING COUNT(*) >= 20
        """, (since_date,))
        for r in rows:
            total = int(r[3] or 1)
            head = int(r[2] or 0)
            _merge(r[0], r[1], {
                "headshot_pct": head / max(total, 1),
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_hit_region query failed: %s", e)

    # 8. Crossfire: execution rate (no name columns — guid only)
    try:
        rows = await db.fetch_all("""
            SELECT guid, cf_total, cf_executed FROM (
                SELECT teammate1_guid as guid,
                       COUNT(*) as cf_total,
                       SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) as cf_executed
                FROM proximity_crossfire_opportunity
                WHERE session_date >= $1
                GROUP BY teammate1_guid
                UNION ALL
                SELECT teammate2_guid,
                       COUNT(*),
                       SUM(CASE WHEN was_executed THEN 1 ELSE 0 END)
                FROM proximity_crossfire_opportunity
                WHERE session_date >= $1
                GROUP BY teammate2_guid
            ) sub
        """, (since_date,))
        # Merge duplicates (player appears as teammate1 AND teammate2)
        cf_agg: dict[str, tuple[int, int]] = {}
        for r in rows:
            g = r[0]
            if g not in cf_agg:
                cf_agg[g] = (0, 0)
            prev_total, prev_exec = cf_agg[g]
            cf_agg[g] = (
                prev_total + int(r[1] or 0),
                prev_exec + int(r[2] or 0),
            )
        for g, (total, executed) in cf_agg.items():
            _merge(g, "", {
                "crossfire_rate": executed / max(total, 1),
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_crossfire_opportunity query failed: %s", e)

    # 9. Trade kills per session
    try:
        rows = await db.fetch_all("""
            SELECT trader_guid, MAX(trader_name),
                   COUNT(*) as trades,
                   COUNT(DISTINCT session_date) as sessions
            FROM proximity_lua_trade_kill
            WHERE session_date >= $1
            GROUP BY trader_guid
        """, (since_date,))
        for r in rows:
            trades = int(r[2] or 0)
            sessions = max(int(r[3] or 1), 1)
            _merge(r[0], r[1], {
                "trades_per_session": trades / sessions,
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_lua_trade_kill query failed: %s", e)

    # 10. Focus fire score (avg focus_score — higher = better performance under pressure)
    try:
        rows = await db.fetch_all("""
            SELECT target_guid, MAX(target_name),
                   COUNT(*) as times_focused,
                   AVG(focus_score) as avg_focus_score
            FROM proximity_focus_fire
            WHERE session_date >= $1
            GROUP BY target_guid
            HAVING COUNT(*) >= 3
        """, (since_date,))
        for r in rows:
            _merge(r[0], r[1], {
                "focus_survival": float(r[3] or 0),
            })
    except Exception as e:
        logger.warning("prox_scoring: proximity_focus_fire query failed: %s", e)

    return players


def get_formula_config() -> dict:
    """Return current formula config for the /prox-scores/formula endpoint."""
    return {
        "version": FORMULA_VERSION,
        "min_engagements": MIN_ENGAGEMENTS,
        "category_weights": CATEGORY_WEIGHTS,
        "categories": {
            cat_key: {
                "label": cat["label"],
                "description": cat["description"],
                "weight_in_overall": CATEGORY_WEIGHTS.get(cat_key, 0),
                "metrics": {
                    mk: {
                        "label": mc["label"],
                        "weight": mc["weight"],
                        "invert": mc["invert"],
                    }
                    for mk, mc in cat["metrics"].items()
                },
            }
            for cat_key, cat in METRICS.items()
        },
    }
