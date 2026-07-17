"""
Proximity Composite Scoring System (prox_combat, prox_team, prox_gamesense, prox_overall).

All weights and metric definitions live in FORMULA_CONFIG below.
To tweak: edit weights, add/remove metrics, change min_samples.

Percentile normalization: rank / pool_size (0.0 to 1.0).
Inverted metrics (lower = better): percentile is flipped.
"""

import asyncio
import bisect
import logging
import math
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# FORMULA CONFIG — edit this to tweak scoring
# ═══════════════════════════════════════════════════════════════════════════

# Canonical version bumped 1.0 → 2.0: this commit changes the actual scores
# (midrank normalization + coverage gating), so get_formula_config(), the
# formula registry, and the UI subtitle must not keep advertising v1.0 while
# responses carry prox-web-v2.0 (Codex review on #512).
FORMULA_VERSION = "2.0"
# Quality-contract semantics (audit AUD-008): a failed source withholds the
# ranking instead of silently substituting neutral 0.5; ties use midrank; a
# player is scored only above MIN_METRIC_WEIGHT_COVERAGE of real (non-missing)
# metric weight. The detailed variant string carried in score responses.
FORMULA_VERSION_QUALITY = "prox-web-v2.0"

# Minimum engagements/tracks to be scored (prevents noisy data)
MIN_ENGAGEMENTS = 10

# Minimum fraction of total metric weight a player must have REAL data for
# (not neutral-filled) before we publish a composite score for them.
MIN_METRIC_WEIGHT_COVERAGE = 0.80

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
    """Return percentile rank (0.0-1.0) for each value via bisect_right.

    Semantics intentionally pinned by tests
    (test_prox_scoring_helpers.test_percentile_rank_*):
      - Top value: exactly 1.0
      - Lowest value in a multi-element list: 1/n (NEVER 0.0)
      - Ties: all tied values get the SAME upper-edge percentile, not
        the midpoint average. Rationale: in this scoring system, "no
        signal" (everyone equal) treats all qualified players as
        co-leaders rather than collapsing them to mid-pack.
    """
    if not values:
        return []
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    result = []
    for v in values:
        # bisect_right places ties at the upper edge — 1-based position,
        # normalized by n.
        pos = bisect.bisect_right(sorted_vals, v)
        result.append(pos / n)
    return result


def _percentile_rank_midrank(values: list[float]) -> list[float]:
    """Midrank percentile (0.0-1.0) — the quality-contract semantics.

    Unlike `_percentile_rank` (bisect_right upper-edge), tied values share
    the AVERAGE of their rank span, so an all-equal cohort scores 0.5 rather
    than 1.0 (no false "everyone is a co-leader" signal — audit AUD-008).

    Fractional midrank over [0, 1]: percentile = (n_less + (n_equal-1)/2)/(n-1).
      - unique top value  → (n-1)/(n-1) = 1.0
      - unique bottom     → 0/(n-1) = 0.0
      - all equal         → ((n-1)/2)/(n-1) = 0.5
    A lone value has no cohort to rank against → neutral 0.5.
    """
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [0.5]
    sorted_vals = sorted(values)
    result = []
    for v in values:
        n_less = bisect.bisect_left(sorted_vals, v)
        n_equal = bisect.bisect_right(sorted_vals, v) - n_less
        result.append((n_less + (n_equal - 1) / 2) / (n - 1))
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


def _metric_effective_weights() -> dict[str, float]:
    """Each metric's share of the OVERALL composite.

    prox_overall weights CATEGORIES (Combat 0.40 / Team 0.35 / Game Sense 0.25),
    so a metric's real contribution is CATEGORY_WEIGHTS[cat] × its share within
    its category. Coverage MUST use these — summing raw within-category weights
    (as before) treated every category as ~1/3, so a player missing only a
    lightly-weighted category was dropped far more aggressively than the score
    formula implies (Copilot/Codex review on #512). Sums to Σ CATEGORY_WEIGHTS.
    """
    eff: dict[str, float] = {}
    for cat_key, cat in METRICS.items():
        cat_total = sum(m["weight"] for m in cat["metrics"].values()) or 1.0
        cw = CATEGORY_WEIGHTS.get(cat_key, 0.0)
        for mk, mc in cat["metrics"].items():
            eff[mk] = cw * mc["weight"] / cat_total
    return eff


_METRIC_EFFECTIVE_WEIGHT = _metric_effective_weights()
_TOTAL_EFFECTIVE_WEIGHT = sum(_METRIC_EFFECTIVE_WEIGHT.values())


def _degraded(sources: list[dict]) -> dict:
    """Quality-contract degraded response: NO ranking, NO neutral fill."""
    failed = [s["source"] for s in sources if not s["success"]]
    return {
        "status": "degraded",
        "formula_version": FORMULA_VERSION_QUALITY,
        "quality": {
            "ranking_available": False,
            "successful_sources": sum(1 for s in sources if s["success"]),
            "total_sources": len(sources),
            "failed_sources": failed,
            "metric_weight_coverage": 0.0,
        },
        "players": [],
    }


async def compute_prox_scores(db, range_days: int = 30, player_guid: str | None = None,
                              *, session_date=None, map_name: str | None = None,
                              round_number: int | None = None, round_start_unix: int | None = None):
    """
    Main entry point. Computes prox_combat, prox_team, prox_gamesense, prox_overall
    for all players (or one player) within range_days — or, when session_date/
    map_name/round_number/round_start_unix are supplied, scoped to exactly that
    selection (round_start_unix disambiguates a map/round played more than once).

    Returns a quality-contract dict (audit AUD-008):
        {
          "status": "ok" | "degraded",
          "formula_version": "prox-web-v2.0",
          "quality": {ranking_available, successful_sources, total_sources,
                      failed_sources, metric_weight_coverage},
          "players": [ ... ]   # each carries metric_weight_coverage + missing_metrics
        }
    On ANY source-query failure the ranking is withheld (status=degraded,
    players=[]) rather than substituting neutral 0.5 percentiles.
    """
    range_days = max(1, min(int(range_days), 365))
    raw_data, sources = await _fetch_raw_metrics(
        db, range_days, session_date=session_date,
        map_name=map_name, round_number=round_number, round_start_unix=round_start_unix,
    )

    # AUD-008: a failed source poisons the whole percentile pool — withhold.
    if any(not s["success"] for s in sources):
        return _degraded(sources)

    def _ok(players, coverage=None, dropped=0):
        # Response-level coverage reflects the ACTUAL returned players (min of
        # their per-player coverage), not a hard-coded 1.0 that misrepresented
        # the quality metadata (Copilot review on #512). Empty → 0.0.
        if coverage is None:
            coverage = min(
                (p["metric_weight_coverage"] for p in players), default=0.0
            )
        return {
            "status": "ok",
            "formula_version": FORMULA_VERSION_QUALITY,
            "quality": {
                "ranking_available": bool(players),
                "successful_sources": len(sources),
                "total_sources": len(sources),
                "failed_sources": [],
                "metric_weight_coverage": round(coverage, 3),
                # Always present so the quality-contract shape doesn't depend on
                # the dataset (empty/healthy responses carried it only after the
                # scoring loop before) — Codex review on #512.
                "below_coverage_dropped": dropped,
            },
            "players": players,
        }

    if not raw_data:
        return _ok([])

    all_guids = list(raw_data.keys())

    # Filter out players with too few engagements
    qualified_guids = [g for g in all_guids if raw_data[g].get("engagements", 0) >= MIN_ENGAGEMENTS]
    if not qualified_guids:
        return _ok([])

    # Compute percentile maps for each metric (midrank ties — AUD-008)
    all_metric_keys = set()
    for cat in METRICS.values():
        all_metric_keys.update(cat["metrics"].keys())

    percentile_maps: dict[str, dict[str, float]] = {}
    for mkey in all_metric_keys:
        # Only include players who have actual data for this metric
        with_data = [(g, raw_data[g][mkey]) for g in qualified_guids if raw_data[g].get(mkey) is not None]
        if with_data:
            vals_only = [v for _, v in with_data]
            pctls = _percentile_rank_midrank(vals_only)
            pctl_map = {g: p for (g, _), p in zip(with_data, pctls)}
        else:
            pctl_map = {}
        # Neutral 0.5 only fills the score arithmetic below; it never counts
        # toward coverage (a genuinely missing metric is tracked separately).
        percentile_maps[mkey] = {g: pctl_map.get(g, 0.5) for g in qualified_guids}

    # Compute scores per player
    results = []
    below_coverage = 0
    target_guids = [player_guid] if player_guid and player_guid in raw_data else qualified_guids

    for guid in target_guids:
        if guid not in qualified_guids and guid != player_guid:
            continue

        pdata = raw_data[guid]
        pdata["__guid__"] = guid

        # Coverage = fraction of the composite's EFFECTIVE metric weight this
        # player has REAL data for. Missing metrics (neutral-filled) don't count,
        # and the weighting matches how prox_overall combines categories.
        missing = [mk for mk in _METRIC_EFFECTIVE_WEIGHT if pdata.get(mk) is None]
        real_weight = sum(
            w for mk, w in _METRIC_EFFECTIVE_WEIGHT.items() if pdata.get(mk) is not None
        )
        coverage = real_weight / _TOTAL_EFFECTIVE_WEIGHT if _TOTAL_EFFECTIVE_WEIGHT else 0.0

        # AUD-008: don't publish a composite built mostly from neutral fill.
        # A single-player request still returns the player (with the coverage
        # flag) so the profile page can decide; leaderboard rows are dropped.
        if coverage < MIN_METRIC_WEIGHT_COVERAGE and guid != player_guid:
            below_coverage += 1
            continue

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
            "metric_weight_coverage": round(coverage, 3),
            "missing_metrics": missing,
        })

    # Sort by overall descending
    results.sort(key=lambda x: x["prox_overall"], reverse=True)

    # Add ranks
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return _ok(results, dropped=below_coverage)


def _sub_score(breakdowns: dict, cat_key: str, metric_keys: list[str]) -> float:
    """Average contribution of specific metrics — for radar sub-axes."""
    cat = breakdowns.get(cat_key, {})
    vals = [cat[k]["percentile"] * 100 for k in metric_keys if k in cat]
    return round(sum(vals) / max(len(vals), 1), 2)


# ═══════════════════════════════════════════════════════════════════════════
# DATA FETCHING — one query per source table
# ═══════════════════════════════════════════════════════════════════════════

async def _fetch_raw_metrics(db, range_days: int, *, session_date=None,
                             map_name: str | None = None,
                             round_number: int | None = None,
                             round_start_unix: int | None = None,
                             ) -> tuple[dict[str, dict], list[dict]]:
    """
    Fetch raw per-player metric values from all source tables.

    Returns a ``(players, sources)`` tuple:
      - ``players``: ``{guid: {metric_key: value, ...}}`` merged dict. A metric
        the source returned as NULL is OMITTED (kept as missing), never merged
        as a coalesced 0, so coverage counts only real data.
      - ``sources``: per-source ``{source, success, row_count, error_code,
        duration_ms}`` status the caller uses to withhold the ranking on any
        query failure (AUD-008).

    All 10 source queries are independent — run them concurrently via
    `asyncio.gather(..., return_exceptions=True)` so one slow table
    doesn't gate the rest. Results merge sequentially into `players`
    afterwards (no shared-state race).

    Scope: by default the trailing `range_days` window. When session_date/
    map_name/round_number are given, the queries are filtered to exactly that
    scope instead — so a date/map/round selected in the UI actually changes the
    scores rather than being silently ignored (all 9 source tables carry these
    three columns). The scope WHERE clause is built once and `.format()`-ed into
    every query (same $N params reused, incl. the two crossfire subqueries).
    """
    parts: list[str] = []
    params: list = []
    if session_date is not None:
        params.append(session_date)
        parts.append(f"session_date = ${len(params)}")
    else:
        params.append(datetime.now(timezone.utc).date() - timedelta(days=int(range_days)))
        parts.append(f"session_date >= ${len(params)}")
    if map_name:
        params.append(map_name)
        parts.append(f"map_name = ${len(params)}")
    if round_number is not None:
        params.append(round_number)
        parts.append(f"round_number = ${len(params)}")
    if round_start_unix is not None:
        # Disambiguates a map/round played more than once in the same session,
        # matching what buildScopeParams() sends from the Scope UI.
        params.append(round_start_unix)
        parts.append(f"round_start_unix = ${len(params)}")
    scope_sql = "WHERE " + " AND ".join(parts)
    scope_params = tuple(params)
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

    # Query catalog: (label, sql). Order matches legacy numbered sections
    # below so the handler dispatch stays readable.
    queries = [
        ("combat_engagement", """
            SELECT target_guid, MAX(target_name) as name,
                   COUNT(*) as engagements,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END)::REAL
                     / NULLIF(COUNT(*), 0) as escape_rate
            FROM combat_engagement
            {scope}
            GROUP BY target_guid
        """),
        ("proximity_reaction_metric", """
            SELECT target_guid, MAX(target_name),
                   AVG(return_fire_ms) as avg_rf,
                   AVG(dodge_reaction_ms) as avg_dodge,
                   AVG(support_reaction_ms) as avg_support
            FROM proximity_reaction_metric
            {scope}
            GROUP BY target_guid
        """),
        ("proximity_spawn_timing", """
            SELECT killer_guid, MAX(killer_name),
                   AVG(spawn_timing_score) as avg_score,
                   COUNT(*) as timed_kills
            FROM proximity_spawn_timing
            {scope}
            GROUP BY killer_guid
        """),
        ("player_track", """
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
            {scope}
              AND peak_speed IS NOT NULL
            GROUP BY player_guid
        """),
        ("proximity_kill_outcome_killer", """
            SELECT killer_guid, MAX(killer_name),
                   COUNT(*) as total_kills,
                   SUM(CASE WHEN outcome = 'gibbed' THEN 1 ELSE 0 END) as gibs,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) as revived_against,
                   AVG(effective_denied_ms) as avg_denied
            FROM proximity_kill_outcome
            {scope}
            GROUP BY killer_guid
            HAVING COUNT(*) >= 3
        """),
        ("proximity_kill_outcome_victim", """
            SELECT victim_guid, MAX(victim_name),
                   COUNT(*) as times_killed,
                   SUM(CASE WHEN outcome = 'revived' THEN 1 ELSE 0 END) as times_revived
            FROM proximity_kill_outcome
            {scope}
            GROUP BY victim_guid
            HAVING COUNT(*) >= 3
        """),
        ("proximity_hit_region", """
            SELECT attacker_guid, MAX(attacker_name),
                   SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END) as head_hits,
                   COUNT(*) as total_hits
            FROM proximity_hit_region
            {scope}
            GROUP BY attacker_guid
            HAVING COUNT(*) >= 20
        """),
        ("proximity_crossfire_opportunity", """
            SELECT guid, cf_total, cf_executed FROM (
                SELECT teammate1_guid as guid,
                       COUNT(*) as cf_total,
                       SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) as cf_executed
                FROM proximity_crossfire_opportunity
                {scope}
                GROUP BY teammate1_guid
                UNION ALL
                SELECT teammate2_guid,
                       COUNT(*),
                       SUM(CASE WHEN was_executed THEN 1 ELSE 0 END)
                FROM proximity_crossfire_opportunity
                {scope}
                GROUP BY teammate2_guid
            ) sub
        """),
        ("proximity_lua_trade_kill", """
            SELECT trader_guid, MAX(trader_name),
                   COUNT(*) as trades,
                   COUNT(DISTINCT session_date) as sessions
            FROM proximity_lua_trade_kill
            {scope}
            GROUP BY trader_guid
        """),
        ("proximity_focus_fire", """
            SELECT target_guid, MAX(target_name),
                   COUNT(*) as times_focused,
                   AVG(focus_score) as avg_focus_score
            FROM proximity_focus_fire
            {scope}
            GROUP BY target_guid
            HAVING COUNT(*) >= 3
        """),
    ]

    import time as _time
    _t0 = _time.monotonic()
    results = await asyncio.gather(
        *(db.fetch_all(q.format(scope=scope_sql), scope_params) for _, q in queries),
        return_exceptions=True,
    )
    _elapsed_ms = int((_time.monotonic() - _t0) * 1000)

    # Per-source status (audit AUD-008): the caller uses this to withhold the
    # ranking on ANY failure instead of silently substituting neutral scores.
    sources: list[dict] = []
    for idx, (label, _q) in enumerate(queries):
        r = results[idx]
        if isinstance(r, Exception):
            sources.append({
                "source": label, "success": False, "row_count": 0,
                "error_code": type(r).__name__,
            })
        else:
            sources.append({
                "source": label, "success": True, "row_count": len(r),
                "error_code": None,
            })

    def _rows(idx: int) -> list | None:
        r = results[idx]
        if isinstance(r, Exception):
            logger.warning("prox_scoring: %s query failed: %s", queries[idx][0], r)
            return None
        return r

    # 1. Engagements: escape_rate, engagement count
    if (rows := _rows(0)) is not None:
        for r in rows:
            _merge(r[0], r[1], {
                "engagements": int(r[2] or 0),
                "escape_rate": float(r[3] or 0),
            })

    # 2. Reactions: return_fire_ms, dodge_ms, support_reaction_ms
    if (rows := _rows(1)) is not None:
        for r in rows:
            _merge(r[0], r[1], {
                "return_fire_ms": float(r[2]) if r[2] else None,
                "dodge_ms": float(r[3]) if r[3] else None,
                "support_reaction_ms": float(r[4]) if r[4] else None,
            })

    # 3. Spawn timing
    if (rows := _rows(2)) is not None:
        for r in rows:
            _merge(r[0], r[1], {
                # AVG can be NULL when no scored kills exist — preserve None so
                # coverage doesn't count a coalesced 0 as real data (Codex #512).
                "spawn_score": float(r[2]) if r[2] is not None else None,
                "timed_kills": float(r[3] or 0),  # COUNT(*): always real for a row
            })

    # 4. Movement: speed, sprint, distance, stance, post_spawn
    if (rows := _rows(3)) is not None:
        for r in rows:
            tracks = int(r[2] or 0)
            standing = float(r[8] or 0)
            crouching = float(r[9] or 0)
            prone = float(r[10] or 0)
            total_stance = standing + crouching + prone
            stance_variety = 0.0
            if total_stance > 0:
                fracs = [standing / total_stance, crouching / total_stance, prone / total_stance]
                entropy = 0.0
                for f in fracs:
                    if f > 0:
                        entropy -= f * math.log(f)
                stance_variety = entropy / math.log(3)

            _merge(r[0], r[1], {
                "tracks": tracks,
                "peak_speed": float(r[4] or 0),  # query filters peak_speed IS NOT NULL
                # AVG aggregates can be NULL (no movement rows for the metric) —
                # preserve None so a coalesced 0 isn't counted toward metric
                # coverage (Codex review on #512).
                "sprint_discipline": float(r[5]) if r[5] is not None else None,
                "distance_per_life": float(r[6]) if r[6] is not None else None,
                "post_spawn_rush": float(r[7]) if r[7] is not None else None,
                "stance_variety": stance_variety if total_stance > 0 else None,
            })

    # 5. Kill outcomes: KPR (as killer)
    if (rows := _rows(4)) is not None:
        for r in rows:
            gibs = int(r[3] or 0)
            rev = int(r[4] or 0)
            kpr = gibs / max(gibs + rev, 1)
            _merge(r[0], r[1], {
                "kpr": kpr,
                # AVG effective_denied_ms is NULL when no denial telemetry —
                # preserve None rather than a coalesced 0 (Codex review on #512).
                "denied_time": float(r[5]) if r[5] is not None else None,
            })

    # 6. Kill outcomes: revive rate (as victim)
    if (rows := _rows(5)) is not None:
        for r in rows:
            killed = int(r[2] or 0)
            revived = int(r[3] or 0)
            _merge(r[0], r[1], {
                "revive_rate_as_victim": revived / max(killed, 1),
            })

    # 7. Hit regions: headshot %
    if (rows := _rows(6)) is not None:
        for r in rows:
            total = int(r[3] or 1)
            head = int(r[2] or 0)
            _merge(r[0], r[1], {
                "headshot_pct": head / max(total, 1),
            })

    # 8. Crossfire: execution rate (no name columns — guid only)
    if (rows := _rows(7)) is not None:
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

    # 9. Trade kills per session
    if (rows := _rows(8)) is not None:
        for r in rows:
            trades = int(r[2] or 0)
            sessions = max(int(r[3] or 1), 1)
            _merge(r[0], r[1], {
                "trades_per_session": trades / sessions,
            })

    # 10. Focus fire score
    if (rows := _rows(9)) is not None:
        for r in rows:
            _merge(r[0], r[1], {
                "focus_survival": float(r[3] or 0),
            })

    for s in sources:
        s["duration_ms"] = _elapsed_ms  # gather() is concurrent → shared wall time

    # Low-cardinality Prometheus signals (AUD-008): {source, outcome} + batch
    # duration. Import lazily so the service has no hard prometheus dependency.
    try:
        from website.backend.metrics import (
            PROX_SOURCE_QUERIES,
            PROX_SOURCE_QUERY_DURATION,
        )
        for s in sources:
            PROX_SOURCE_QUERIES.labels(
                source=s["source"],
                outcome="success" if s["success"] else "error",
            ).inc()
        PROX_SOURCE_QUERY_DURATION.observe(_elapsed_ms / 1000.0)
    except Exception:  # pragma: no cover - metrics must never break scoring
        logger.debug("prox_scoring: metrics emit skipped", exc_info=True)

    return players, sources


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
