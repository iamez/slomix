"""Proximity scoring endpoints: session-scores, leaderboards, prox-scores, prox-scores/formula, weapon-accuracy, revives."""

import math
from bisect import bisect_right
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.rate_limit import limiter
from website.backend.routers.proximity_helpers import (
    _parse_iso_date,
    logger,
)

router = APIRouter()


def _percentile_rank_map(guid_values: dict[str, float]) -> dict[str, float]:
    """Compute percentile rank (0.0-1.0) for a dict of guid->value.

    Returns empty dict if fewer than 3 players (not enough for meaningful percentiles).
    Filters out NaN/None values before computation.
    """
    clean = {g: v for g, v in guid_values.items() if v is not None and not math.isnan(v)}
    if len(clean) < 3:
        return {}
    sorted_vals = sorted(clean.values())
    n = len(sorted_vals)
    return {g: bisect_right(sorted_vals, v) / n for g, v in clean.items()}


@router.get("/proximity/session-scores")
async def get_proximity_session_scores(
    session_date: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-session composite proximity combat scores (0-100) across 7 categories."""
    try:
        from bot.services.proximity_session_score_service import ProximitySessionScoreService
        svc = ProximitySessionScoreService(db)

        if not session_date:
            session_date = await svc.get_latest_session_date()
        if not session_date:
            return {"status": "ok", "session_date": None, "players": []}

        # asyncpg needs date object, not string
        sd = datetime.strptime(session_date, "%Y-%m-%d").date() if isinstance(session_date, str) else session_date
        results = await svc.compute_session_scores(sd)
        return {"status": "ok", "session_date": session_date, "players": results}
    except Exception:
        logger.exception("session-scores failed")
        raise HTTPException(status_code=500, detail="session-scores computation failed")


@router.get("/proximity/leaderboards")
@limiter.limit("10/minute")
async def get_proximity_leaderboards(
    request: Request,
    category: str = "power",
    range_days: int = 30,
    limit: int = 10,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Multi-category proximity leaderboards. Supports scope filtering."""
    safe_limit = max(1, min(limit, 50))
    parsed_date = _parse_iso_date(session_date) if isinstance(session_date, str) else session_date
    # When scope is specified, use it instead of range_days
    if parsed_date:
        since = parsed_date
    else:
        since = datetime.utcnow().date() - timedelta(days=max(1, min(range_days, 3650)))

    # Build scope filter helper for leaderboard queries
    def _lb_scope(table_alias: str = "", has_round_number: bool = False):
        """Build WHERE clause fragments and params for leaderboard scope."""
        prefix = f"{table_alias}." if table_alias else ""
        clauses = [f"{prefix}session_date >= ${1}"]
        params = [since]
        idx = 2
        if map_name:
            clauses.append(f"{prefix}map_name = ${idx}")
            params.append(map_name)
            idx += 1
        if has_round_number and round_number is not None:
            clauses.append(f"{prefix}round_number = ${idx}")
            params.append(round_number)
            idx += 1
        return " AND ".join(clauses), tuple(params), idx

    try:
        if category == "power":
            scope_where, scope_params, _ = _lb_scope(has_round_number=True)
            # Composite radar score — batch queries (7 queries total, not per-player)
            # 1. Engagement stats + names per player
            eng_rows = await db.fetch_all(
                f"""
                SELECT target_guid, MAX(target_name) AS name,
                       COUNT(*) AS total,
                       SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes
                FROM combat_engagement
                WHERE {scope_where}
                GROUP BY target_guid
                HAVING COUNT(*) >= 5
                ORDER BY COUNT(*) DESC
                LIMIT 100
                """,
                scope_params,
            )
            if not eng_rows:
                return {"status": "ok", "category": "power", "entries": []}

            guid_set = {r[0] for r in eng_rows}
            eng_map: dict[str, dict] = {}
            for r in eng_rows:
                eng_map[r[0]] = {"name": r[1] or r[0][:8], "total": int(r[2] or 0), "escapes": int(r[3] or 0)}

            # 2. Movement (aggression axis)
            move_rows = await db.fetch_all(
                f"""
                SELECT player_guid,
                       ROUND(AVG(sprint_percentage)::numeric, 1) AS sp,
                       ROUND(AVG(avg_speed)::numeric, 1) AS spd
                FROM player_track
                WHERE {scope_where}
                GROUP BY player_guid
                """,
                scope_params,
            )
            move_map: dict[str, tuple[float, float]] = {}
            for r in (move_rows or []):
                if r[0] in guid_set:
                    move_map[r[0]] = (float(r[1] or 0), float(r[2] or 0))

            # 3. Dodge reaction (awareness axis)
            dodge_rows = await db.fetch_all(
                f"""
                SELECT target_guid,
                       ROUND(AVG(dodge_reaction_ms)::numeric, 0) AS avg_dodge
                FROM proximity_reaction_metric
                WHERE dodge_reaction_ms IS NOT NULL AND {scope_where}
                GROUP BY target_guid
                """,
                scope_params,
            )
            dodge_map: dict[str, int] = {}
            for r in (dodge_rows or []):
                if r[0] in guid_set:
                    dodge_map[r[0]] = int(r[1] or 5000)

            # 4. Crossfire participation (teamplay axis)
            cf_rows = await db.fetch_all(
                f"""
                SELECT guid, SUM(cnt) AS total FROM (
                    SELECT teammate1_guid AS guid, COUNT(*) AS cnt
                    FROM proximity_crossfire_opportunity
                    WHERE was_executed = true AND {scope_where}
                    GROUP BY teammate1_guid
                    UNION ALL
                    SELECT teammate2_guid AS guid, COUNT(*) AS cnt
                    FROM proximity_crossfire_opportunity
                    WHERE was_executed = true AND {scope_where}
                    GROUP BY teammate2_guid
                ) sub GROUP BY guid
                """,
                scope_params,
            )
            cf_map: dict[str, int] = {}
            for r in (cf_rows or []):
                if r[0] in guid_set:
                    cf_map[r[0]] = int(r[1] or 0)

            # 5. Trade kills (teamplay axis)
            trade_rows = await db.fetch_all(
                f"""
                SELECT trader_guid, COUNT(*) AS cnt
                FROM proximity_lua_trade_kill
                WHERE {scope_where}
                GROUP BY trader_guid
                """,
                scope_params,
            )
            trade_map: dict[str, int] = {}
            for r in (trade_rows or []):
                if r[0] in guid_set:
                    trade_map[r[0]] = int(r[1] or 0)

            # 6. Spawn timing (timing axis)
            timing_rows = await db.fetch_all(
                f"""
                SELECT killer_guid,
                       ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                       COUNT(*) AS cnt
                FROM proximity_spawn_timing
                WHERE {scope_where}
                GROUP BY killer_guid
                """,
                scope_params,
            )
            timing_map: dict[str, tuple[float, int]] = {}
            for r in (timing_rows or []):
                if r[0] in guid_set:
                    timing_map[r[0]] = (float(r[1] or 0), int(r[2] or 0))

            # 7. Return fire (mechanical axis)
            rf_rows = await db.fetch_all(
                f"""
                SELECT target_guid,
                       ROUND(AVG(return_fire_ms)::numeric, 0) AS avg_rf
                FROM proximity_reaction_metric
                WHERE return_fire_ms IS NOT NULL AND {scope_where}
                GROUP BY target_guid
                """,
                scope_params,
            )
            rf_map: dict[str, int] = {}
            for r in (rf_rows or []):
                if r[0] in guid_set:
                    rf_map[r[0]] = int(r[1] or 3000)

            # 8. Kill permanence (teamplay axis) — fraction of kills that stay dead
            perm_rows = await db.fetch_all(
                f"""
                SELECT killer_guid,
                       COUNT(*) FILTER (WHERE outcome != 'revived') * 1.0
                           / NULLIF(COUNT(*), 0) AS permanence
                FROM proximity_kill_outcome
                WHERE {scope_where}
                GROUP BY killer_guid
                """,
                scope_params,
            )
            perm_map: dict[str, float] = {}
            for r in (perm_rows or []):
                if r[0] in guid_set:
                    perm_map[r[0]] = float(r[1] or 0)

            # 9. Support reaction speed (teamplay axis) — how fast you help teammates
            support_rows = await db.fetch_all(
                f"""
                SELECT target_guid,
                       ROUND(AVG(support_reaction_ms)::numeric, 0) AS avg_support
                FROM proximity_reaction_metric
                WHERE support_reaction_ms IS NOT NULL AND {scope_where}
                GROUP BY target_guid
                """,
                scope_params,
            )
            support_map: dict[str, float] = {}
            for r in (support_rows or []):
                if r[0] in guid_set:
                    support_map[r[0]] = float(r[1] or 3000)

            # ── Teamplay: 5-metric percentile normalization ──
            # Collect raw values across all qualified players
            tp_cf = {g: float(cf_map.get(g, 0)) for g in eng_map}
            tp_tr = {g: float(trade_map.get(g, 0)) for g in eng_map}
            tp_st = {g: timing_map.get(g, (0.0, 0))[0] for g in eng_map}
            tp_pm = {g: perm_map.get(g, 0.0) for g in eng_map}
            tp_sp = {g: support_map.get(g, 3000.0) for g in eng_map}

            # Percentile ranks (empty dict if < 3 players)
            pct_cf = _percentile_rank_map(tp_cf)
            pct_tr = _percentile_rank_map(tp_tr)
            pct_st = _percentile_rank_map(tp_st)
            pct_pm = _percentile_rank_map(tp_pm)
            # Support speed: lower is better → invert percentile
            pct_sp_raw = _percentile_rank_map(tp_sp)
            pct_sp = {g: 1.0 - p for g, p in pct_sp_raw.items()}
            use_pct = bool(pct_cf)

            # Compute composite scores
            results = []
            for g, info in eng_map.items():
                sp, spd = move_map.get(g, (0.0, 0.0))
                aggression = min(100, sp * 0.6 + min(spd / 300, 1) * 100 * 0.4)

                esc_rate = info["escapes"] / max(info["total"], 1) * 100
                d_ms = dodge_map.get(g, 5000)
                awareness = min(100, esc_rate * 0.5 + max(0, 100 - d_ms / 50) * 0.5)

                # Teamplay: percentile-weighted across 5 ET-specific dimensions
                if use_pct:
                    teamplay = (
                        pct_st.get(g, 0.5) * 0.30    # Spawn Timing Intelligence
                        + pct_cf.get(g, 0.5) * 0.25  # Crossfire Coordination
                        + pct_tr.get(g, 0.5) * 0.15  # Trade Responsiveness
                        + pct_pm.get(g, 0.5) * 0.15  # Kill Permanence
                        + pct_sp.get(g, 0.5) * 0.15  # Support Speed
                    ) * 100
                else:
                    # Fallback for < 3 players: only CF+TR with raised thresholds.
                    # Spawn timing, kill permanence, support speed are omitted
                    # because percentile ranking requires a population to compare against.
                    cf_c = cf_map.get(g, 0)
                    tr_c = trade_map.get(g, 0)
                    teamplay = min(100, min(cf_c / 20, 1) * 50 + min(tr_c / 10, 1) * 50)

                avg_tm, tm_cnt = timing_map.get(g, (0.0, 0))
                timing = min(100, avg_tm * 100 * min(tm_cnt / 5, 1))

                rf_ms = rf_map.get(g, 3000)
                mechanical = min(100, max(0, 100 - rf_ms / 30))

                composite = round((aggression + awareness + teamplay + timing + mechanical) / 5, 1)
                results.append({
                    "guid": g, "name": info["name"], "value": composite,
                    "axes": {
                        "aggression": round(aggression, 1), "awareness": round(awareness, 1),
                        "teamplay": round(teamplay, 1), "timing": round(timing, 1),
                        "mechanical": round(mechanical, 1),
                    },
                })

            results.sort(key=lambda x: x["value"], reverse=True)
            return {"status": "ok", "category": "power", "entries": results[:safe_limit]}

        elif category == "spawn":
            scope_where, scope_params, next_idx = _lb_scope(has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT killer_guid, MAX(killer_name) AS name,
                       COUNT(*) AS timed_kills,
                       ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                       ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
                FROM proximity_spawn_timing
                WHERE {scope_where}
                GROUP BY killer_guid
                HAVING COUNT(*) >= 3
                ORDER BY avg_score DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "spawn",
                "entries": [
                    {"guid": r[0], "name": r[1], "timed_kills": int(r[2] or 0),
                     "value": float(r[3] or 0), "avg_denial_ms": int(r[4] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "crossfire":
            scope_where, scope_params, next_idx = _lb_scope(table_alias="c", has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT guid, name, SUM(cnt) AS total, ROUND(AVG(avg_angle)::numeric, 1) AS avg_angle
                FROM (
                    SELECT c.teammate1_guid AS guid,
                           COALESCE(MAX(ce.target_name), c.teammate1_guid) AS name,
                           COUNT(*) AS cnt, AVG(c.angular_separation) AS avg_angle
                    FROM proximity_crossfire_opportunity c
                    LEFT JOIN LATERAL (
                        SELECT target_name FROM combat_engagement
                        WHERE target_guid = c.teammate1_guid
                        ORDER BY session_date DESC LIMIT 1
                    ) ce ON true
                    WHERE c.was_executed = true AND {scope_where}
                    GROUP BY c.teammate1_guid
                    UNION ALL
                    SELECT c.teammate2_guid AS guid,
                           COALESCE(MAX(ce.target_name), c.teammate2_guid) AS name,
                           COUNT(*) AS cnt, AVG(c.angular_separation) AS avg_angle
                    FROM proximity_crossfire_opportunity c
                    LEFT JOIN LATERAL (
                        SELECT target_name FROM combat_engagement
                        WHERE target_guid = c.teammate2_guid
                        ORDER BY session_date DESC LIMIT 1
                    ) ce ON true
                    WHERE c.was_executed = true AND {scope_where}
                    GROUP BY c.teammate2_guid
                ) sub GROUP BY guid, name
                ORDER BY total DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "crossfire",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": int(r[2] or 0),
                     "avg_angle": float(r[3] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "trades":
            scope_where, scope_params, next_idx = _lb_scope(has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT trader_guid, MAX(trader_name) AS name,
                       COUNT(*) AS trades,
                       ROUND(AVG(delta_ms)::numeric, 0) AS avg_reaction
                FROM proximity_lua_trade_kill
                WHERE {scope_where}
                GROUP BY trader_guid
                HAVING COUNT(*) >= 2
                ORDER BY trades DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "trades",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": int(r[2] or 0),
                     "avg_reaction_ms": int(r[3] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "reactions":
            scope_where, scope_params, next_idx = _lb_scope(has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT target_guid, MAX(target_name) AS name,
                       ROUND(AVG(return_fire_ms)::numeric, 0) AS avg_rf,
                       COUNT(*) AS samples
                FROM proximity_reaction_metric
                WHERE return_fire_ms IS NOT NULL AND {scope_where}
                GROUP BY target_guid
                HAVING COUNT(*) >= 3
                ORDER BY avg_rf ASC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "reactions",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": int(r[2] or 0),
                     "samples": int(r[3] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "survivors":
            scope_where, scope_params, next_idx = _lb_scope(has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT target_guid, MAX(target_name) AS name,
                       ROUND(SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END)::numeric * 100
                             / NULLIF(COUNT(*), 0), 1) AS escape_pct,
                       COUNT(*) AS total_engagements,
                       ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration
                FROM combat_engagement
                WHERE {scope_where}
                GROUP BY target_guid
                HAVING COUNT(*) >= 5
                ORDER BY escape_pct DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "survivors",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": float(r[2] or 0),
                     "total_engagements": int(r[3] or 0), "avg_duration_ms": int(r[4] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "movement":
            scope_where, scope_params, next_idx = _lb_scope(has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT player_guid, MAX(player_name) AS name,
                       ROUND(AVG(avg_speed)::numeric, 1) AS avg_speed,
                       ROUND(AVG(sprint_percentage)::numeric, 1) AS sprint_pct,
                       SUM(total_distance)::int AS total_distance,
                       COUNT(*) AS tracks
                FROM player_track
                WHERE {scope_where}
                GROUP BY player_guid
                HAVING COUNT(*) >= 3
                ORDER BY avg_speed DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "movement",
                "entries": [
                    {"guid": r[0], "name": r[1], "value": float(r[2] or 0),
                     "sprint_pct": float(r[3] or 0), "total_distance": int(r[4] or 0),
                     "tracks": int(r[5] or 0)}
                    for r in (rows or [])
                ],
            }

        elif category == "focus_fire":
            scope_where, scope_params, next_idx = _lb_scope(has_round_number=True)
            rows = await db.fetch_all(
                f"""
                SELECT target_guid, MAX(target_name) AS name,
                       COUNT(*) AS times_focused,
                       ROUND(AVG(focus_score)::numeric, 3) AS avg_score,
                       ROUND(AVG(attacker_count)::numeric, 1) AS avg_attackers,
                       ROUND(AVG(total_damage)::numeric, 0) AS avg_damage
                FROM proximity_focus_fire
                WHERE {scope_where}
                GROUP BY target_guid
                HAVING COUNT(*) >= 2
                ORDER BY avg_score DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )
            return {
                "status": "ok", "category": "focus_fire",
                "entries": [
                    {"guid": r[0], "name": r[1], "times_focused": int(r[2] or 0),
                     "value": float(r[3] or 0), "avg_attackers": float(r[4] or 0),
                     "avg_damage": int(r[5] or 0)}
                    for r in (rows or [])
                ],
            }

        else:
            return {"status": "error", "detail": f"Unknown category: {category}. Valid: power, spawn, crossfire, trades, reactions, survivors, movement, focus_fire"}

    except Exception:
        logger.exception("leaderboards failed")
        raise HTTPException(status_code=500, detail="leaderboards computation failed")


@router.get("/proximity/prox-scores")
@limiter.limit("15/minute")
async def get_prox_scores(
    request: Request,
    range_days: int = 30,
    player_guid: str | None = None,
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Proximity composite scores: prox_combat, prox_team, prox_gamesense, prox_overall.
    Percentile-based scoring across all proximity metrics.
    """
    from website.backend.services.prox_scoring import compute_prox_scores
    try:
        results = await compute_prox_scores(db, range_days, player_guid)
        return {
            "status": "ok",
            "version": "1.0",
            "range_days": range_days,
            "player_count": len(results),
            "players": results[:limit],
        }
    except Exception:
        logger.exception("prox-scores failed")
        raise HTTPException(status_code=500, detail="prox-scores computation failed")


@router.get("/proximity/prox-scores/formula")
async def get_prox_scores_formula():
    """Return current formula config (weights, metrics, categories) for transparency."""
    from website.backend.services.prox_scoring import get_formula_config
    return {"status": "ok", **get_formula_config()}


@router.get("/proximity/weapon-accuracy")
async def get_proximity_weapon_accuracy(
    range_days: int = 30,
    player_guid: str | None = None,
    map_name: str | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Weapon accuracy leaderboard or per-player breakdown."""
    safe_limit = max(1, min(limit, 50))
    try:
        clauses = ["shots_fired >= 10"]
        params: list = []

        if player_guid:
            params.append(player_guid.strip())
            clauses.append(f"player_guid = ${len(params)}")
        if map_name:
            params.append(map_name.strip())
            clauses.append(f"map_name = ${len(params)}")

        where = "WHERE " + " AND ".join(clauses)

        rows = await db.fetch_all(
            f"""
            SELECT player_guid, MAX(player_name) AS name,
                   SUM(shots_fired) AS total_shots,
                   SUM(hits) AS total_hits,
                   SUM(kills) AS total_kills,
                   SUM(headshots) AS total_hs,
                   ROUND((SUM(hits)::numeric / NULLIF(SUM(shots_fired), 0)) * 100, 1) AS accuracy
            FROM proximity_weapon_accuracy {where}
            GROUP BY player_guid
            ORDER BY accuracy DESC
            LIMIT ${len(params) + 1}
            """,
            tuple(params) + (safe_limit,),
        )

        # Per-weapon breakdown (if player_guid specified)
        weapon_breakdown = []
        if player_guid:
            wrows = await db.fetch_all(
                """
                SELECT weapon_id, SUM(shots_fired), SUM(hits), SUM(kills), SUM(headshots),
                       ROUND((SUM(hits)::numeric / NULLIF(SUM(shots_fired), 0)) * 100, 1)
                FROM proximity_weapon_accuracy
                WHERE player_guid = $1 AND shots_fired > 0
                GROUP BY weapon_id ORDER BY SUM(kills) DESC
                """,
                (player_guid.strip(),),
            )
            weapon_breakdown = [
                {
                    "weapon_id": r[0],
                    "shots": int(r[1] or 0), "hits": int(r[2] or 0),
                    "kills": int(r[3] or 0), "headshots": int(r[4] or 0),
                    "accuracy": float(r[5] or 0),
                }
                for r in (wrows or [])
            ]

        return {
            "status": "ok",
            "leaders": [
                {
                    "guid": r[0], "name": r[1],
                    "shots": int(r[2] or 0), "hits": int(r[3] or 0),
                    "kills": int(r[4] or 0), "headshots": int(r[5] or 0),
                    "accuracy": float(r[6] or 0),
                }
                for r in (rows or [])
            ],
            "weapon_breakdown": weapon_breakdown,
        }
    except Exception:
        logger.exception("weapon-accuracy failed")
        raise HTTPException(status_code=500, detail="weapon-accuracy computation failed")


@router.get("/proximity/revives")
async def get_proximity_revives(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    player_guid: str | None = None,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Revive summary and medic leaderboard from proximity_revive table."""
    safe_limit = max(1, min(limit, 50))
    try:
        clauses: list[str] = []
        params: list = []

        if map_name:
            params.append(map_name.strip())
            clauses.append(f"map_name = ${len(params)}")
        if player_guid:
            params.append(player_guid.strip())
            clauses.append(f"medic_guid = ${len(params)}")

        # Apply range_days filter (proximity_revive has created_at, not session_date)
        params.append(range_days)
        clauses.append(f"created_at >= CURRENT_DATE - ${len(params)} * INTERVAL '1 day'")

        where_sql = "WHERE " + " AND ".join(clauses)
        medic_filter = "medic_guid IS NOT NULL AND medic_guid != ''"
        medic_where = "WHERE " + " AND ".join(clauses + [medic_filter])
        query_params = tuple(params)

        # Summary
        summary_row = await db.fetch_one(
            f"""
            SELECT COUNT(*) AS total_revives,
                   ROUND(AVG(distance_to_enemy)::numeric, 0) AS avg_enemy_distance,
                   ROUND(100.0 * SUM(CASE WHEN under_fire THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS under_fire_pct
            FROM proximity_revive {where_sql}
            """,
            query_params,
        )

        summary = {
            "total_revives": int(summary_row[0] or 0) if summary_row else 0,
            "avg_enemy_distance": float(summary_row[1] or 0) if summary_row else 0,
            "under_fire_pct": float(summary_row[2] or 0) if summary_row else 0,
        }

        # Medic leaderboard
        rows = await db.fetch_all(
            f"""
            SELECT medic_guid, MAX(medic_name) AS name,
                   COUNT(*) AS revives,
                   SUM(CASE WHEN under_fire THEN 1 ELSE 0 END) AS under_fire_count,
                   ROUND(AVG(distance_to_enemy)::numeric, 0) AS avg_enemy_dist
            FROM proximity_revive {medic_where}
            GROUP BY medic_guid
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT ${len(params) + 1}
            """,
            query_params + (safe_limit,),
        )

        leaders = [
            {
                "guid": r[0], "name": r[1],
                "revives": int(r[2] or 0),
                "under_fire_count": int(r[3] or 0),
                "avg_enemy_dist": float(r[4] or 0),
            }
            for r in (rows or [])
        ]

        return {"status": "ok", "summary": summary, "leaders": leaders}
    except Exception:
        logger.exception("revives failed")
        raise HTTPException(status_code=500, detail="revives computation failed")
