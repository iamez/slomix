"""Proximity scoring endpoints: session-scores, leaderboards, prox-scores, prox-scores/formula, weapon-accuracy, revives."""

import math
from bisect import bisect_right
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from shared.guid_utils import short_guid
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.rate_limit import limiter
from website.backend.routers.proximity_helpers import (
    _load_scoped_guid_name_map,
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
        sd = datetime.strptime(session_date, "%Y-%m-%d").date() if isinstance(session_date, str) else session_date  # noqa: DTZ007 date-only parsing, no time component used
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
        since = datetime.now(timezone.utc).replace(tzinfo=None).date() - timedelta(days=max(1, min(range_days, 3650)))

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
            # Audit P6: previous version ran per-row `LEFT JOIN LATERAL
            # (SELECT target_name FROM combat_engagement …)` to resolve
            # teammate names — O(N × index+sort) against a 58k-row
            # combat_engagement table for every crossfire row. Replaced
            # with a single scope-wide player_track name map, then
            # resolve names in Python. Matches the pattern the other
            # leaderboards already use (`MAX(name_col)` in-query).
            scope_where, scope_params, next_idx = _lb_scope(table_alias="c", has_round_number=True)
            pt_where, pt_params, _ = _lb_scope(has_round_number=True)
            guid_name_map = await _load_scoped_guid_name_map(
                db, f"WHERE {pt_where}", pt_params,
            )
            rows = await db.fetch_all(
                f"""
                SELECT guid, SUM(cnt) AS total, ROUND(AVG(avg_angle)::numeric, 1) AS avg_angle
                FROM (
                    SELECT c.teammate1_guid AS guid,
                           COUNT(*) AS cnt, AVG(c.angular_separation) AS avg_angle
                    FROM proximity_crossfire_opportunity c
                    WHERE c.was_executed = true AND {scope_where}
                    GROUP BY c.teammate1_guid
                    UNION ALL
                    SELECT c.teammate2_guid AS guid,
                           COUNT(*) AS cnt, AVG(c.angular_separation) AS avg_angle
                    FROM proximity_crossfire_opportunity c
                    WHERE c.was_executed = true AND {scope_where}
                    GROUP BY c.teammate2_guid
                ) sub GROUP BY guid
                ORDER BY total DESC
                LIMIT ${next_idx}
                """,
                scope_params + (safe_limit,),
            )

            def _resolve_name(guid: str) -> str:
                if not guid:
                    return ""
                if guid in guid_name_map:
                    return guid_name_map[guid]
                # Short-prefix fallback (map is double-indexed by 8-char prefix)
                short = short_guid(guid)
                return guid_name_map.get(short, guid)

            return {
                "status": "ok", "category": "crossfire",
                "entries": [
                    {"guid": r[0], "name": _resolve_name(r[0]),
                     "value": int(r[1] or 0),
                     "avg_angle": float(r[2] or 0)}
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

        elif category == "krogt":
            # Per-LIFE KROGT — % of lives with a Kill/Revive/Objective/Gib/Traded
            # contribution. ET translation of KAST/KOST (a CS/R6 round == one
            # life); per-round saturates here because everyone frags in a 10min
            # round. Lives come from player_track (one row per spawn->death,
            # including selfkill/world deaths). Validated + tuned in
            # scripts/backtest_krogt_perlife.py (owner-reviewed 2026-07-05).
            # round_start_unix narrows the LIVES query only (player_track has
            # the column; proximity_revive does NOT — filtering it there would
            # be an undefined-column error, codex P2 round 2). Event queries
            # don't need it: they join lives by (round_id, guid), so events
            # from other rounds can never credit a selected round's lives.
            scope_where, scope_params, rsu_idx = _lb_scope("pt", has_round_number=True)
            if round_start_unix is not None:
                scope_where += f" AND pt.round_start_unix = ${rsu_idx}"
                scope_params = (*scope_params, round_start_unix)
            lives_rows = await db.fetch_all(
                f"""
                SELECT pt.round_id, UPPER(LEFT(pt.player_guid, 8)),
                       MAX(pt.player_name), pt.spawn_time_ms, pt.death_time_ms
                FROM player_track pt
                WHERE {scope_where}
                  AND pt.round_id IS NOT NULL
                  AND pt.player_guid NOT LIKE 'OMNIBOT%'
                  AND pt.player_name NOT LIKE '[BOT]%'
                GROUP BY pt.round_id, UPPER(LEFT(pt.player_guid, 8)),
                         pt.spawn_time_ms, pt.death_time_ms
                """,
                scope_params,
            )
            if not lives_rows:
                return {"status": "ok", "category": "krogt", "entries": []}

            async def _krogt_events(sql: str, alias: str, has_rn: bool) -> list:
                where_sql, params, _idx = _lb_scope(alias, has_round_number=has_rn)
                return await db.fetch_all(sql.format(scope=where_sql), params)

            events: list = []
            events += await _krogt_events(
                "SELECT cp.round_id, UPPER(LEFT(cp.attacker_guid, 8)), cp.event_time "
                "FROM proximity_combat_position cp WHERE {scope} "
                "AND cp.round_id IS NOT NULL AND cp.attacker_guid IS NOT NULL "
                "AND cp.attacker_team <> cp.victim_team", "cp", True)
            events += await _krogt_events(
                "SELECT rv.round_id, UPPER(LEFT(rv.medic_guid, 8)), rv.revive_time "
                "FROM proximity_revive rv WHERE {scope} "
                "AND rv.round_id IS NOT NULL AND rv.medic_guid IS NOT NULL", "rv", False)
            events += await _krogt_events(
                "SELECT orun.round_id, UPPER(LEFT(orun.engineer_guid, 8)), orun.action_time "
                "FROM proximity_objective_run orun WHERE {scope} "
                "AND orun.round_id IS NOT NULL AND orun.engineer_guid IS NOT NULL "
                "AND COALESCE(orun.action_type, '') <> 'approach_killed' "
                "AND COALESCE(orun.run_type, '') <> 'denied'", "orun", True)
            events += await _krogt_events(
                "SELECT ko.round_id, UPPER(LEFT(ko.gibber_guid, 8)), ko.outcome_time "
                "FROM proximity_kill_outcome ko WHERE {scope} "
                "AND ko.round_id IS NOT NULL AND ko.outcome = 'gibbed' "
                "AND ko.gibber_guid IS NOT NULL", "ko", True)
            traded_rows = await _krogt_events(
                "SELECT tk.round_id, UPPER(LEFT(tk.original_victim_guid, 8)), tk.original_kill_time "
                "FROM proximity_lua_trade_kill tk WHERE {scope} "
                "AND tk.round_id IS NOT NULL", "tk", True)

            ev_by: dict[tuple, list] = {}
            for rid, gg, t in events:
                if t is not None:
                    ev_by.setdefault((rid, gg), []).append(int(t))
            traded_by: dict[tuple, list] = {}
            for rid, gg, t in traded_rows:
                if t is not None:
                    traded_by.setdefault((rid, gg), []).append(int(t))

            # death_time_ms is intentionally NULL for a survived-to-round-end
            # life (proximity schema) — those lives belong in the denominator
            # (codex P2 round 2); close them at the round's actual duration.
            null_death_rids = {r[0] for r in lives_rows if r[4] is None}
            durations: dict[int, int] = {}
            if null_death_rids:
                dur_rows = await db.fetch_all(
                    "SELECT id, COALESCE(actual_duration_seconds, 0) * 1000 "
                    "FROM rounds WHERE id = ANY($1)",
                    (list(null_death_rids),),
                )
                durations = {r[0]: int(r[1] or 0) for r in (dur_rows or [])}

            per_player: dict[str, dict] = {}
            lives_by: dict[tuple, list] = {}
            for rid, gg, name, spawn_ms, death_ms in lives_rows:
                if spawn_ms is None:
                    continue
                hi = int(death_ms) if death_ms is not None else durations.get(rid, 0)
                if hi <= int(spawn_ms):
                    continue
                lives_by.setdefault((rid, gg), []).append((int(spawn_ms), hi))
                per_player.setdefault(gg, {"name": name, "lives": 0, "contrib": 0})
                if name:
                    per_player[gg]["name"] = name

            for (rid, gg), windows in lives_by.items():
                windows.sort()
                evs = sorted(ev_by.get((rid, gg), []))
                traded_times = traded_by.get((rid, gg), [])
                ei = 0
                for lo, hi in windows:
                    per_player[gg]["lives"] += 1
                    while ei < len(evs) and evs[ei] <= lo:
                        ei += 1
                    contributed = ei < len(evs) and evs[ei] <= hi
                    # traded death ends the life within +/-1s (different Lua clocks)
                    if not contributed and any(abs(t - hi) <= 1000 for t in traded_times):
                        contributed = True
                    if contributed:
                        per_player[gg]["contrib"] += 1

            scoped = (parsed_date or map_name or round_number is not None
                      or round_start_unix is not None)
            min_lives = 10 if scoped else 50
            entries = [
                {
                    "guid": gg, "name": p["name"] or gg,
                    "value": round(100.0 * p["contrib"] / p["lives"], 1),
                    "lives": p["lives"],
                }
                for gg, p in per_player.items() if p["lives"] >= min_lives
            ]
            entries.sort(key=lambda e: -e["value"])
            return {"status": "ok", "category": "krogt", "entries": entries[:safe_limit]}

        else:
            return {"status": "error", "detail": f"Unknown category: {category}. Valid: power, spawn, crossfire, trades, reactions, survivors, movement, focus_fire, krogt"}

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
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Proximity composite scores: prox_combat, prox_team, prox_gamesense, prox_overall.
    Percentile-based scoring across all proximity metrics.

    Honours the scope the UI sends (session_date/map_name/round_number/
    round_start_unix) instead of silently always returning the range_days window —
    previously a selected date/map made prox_overall *look* scoped while showing
    the 30-day global score. round_start_unix disambiguates a repeated map/round.
    """
    from website.backend.services.prox_scoring import (
        FORMULA_VERSION_QUALITY,
        compute_prox_scores,
    )
    parsed_date = _parse_iso_date(session_date) if isinstance(session_date, str) else session_date
    try:
        result = await compute_prox_scores(
            db, range_days, player_guid,
            session_date=parsed_date, map_name=map_name, round_number=round_number,
            round_start_unix=round_start_unix,
        )
        players = result.get("players", [])
        quality = result.get("quality", {})
        scoped = bool(parsed_date or map_name or round_number is not None or round_start_unix is not None)
        return {
            # AUD-008: propagate degraded status + quality metadata so callers
            # never mistake a data failure for a real (all-neutral) ranking.
            "status": result.get("status", "ok"),
            "version": "1.0",  # legacy field kept for back-compat
            "formula_version": result.get("formula_version", FORMULA_VERSION_QUALITY),
            "quality": quality,
            "range_days": range_days,
            "scope": {
                "scoped": scoped,
                "session_date": str(parsed_date) if parsed_date else None,
                "map_name": map_name,
                "round_number": round_number,
                "round_start_unix": round_start_unix,
            },
            "player_count": len(players),
            "players": players[:limit],
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

        # Audit P8 + migration 043: previously `range_days` was accepted
        # but never applied to the query — the endpoint returned all-time
        # rows. Filter on `session_date` (play time) with created_at
        # fallback for rows whose re-linker hasn't populated round_id yet.
        params.append(range_days)
        clauses.append(
            "(session_date >= CURRENT_DATE - $" + str(len(params)) + " * INTERVAL '1 day' "
            "OR (session_date IS NULL AND created_at >= CURRENT_DATE - $" + str(len(params)) + " * INTERVAL '1 day'))"
        )

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

        # Audit P8 + migration 043: filter on session_date (play time)
        # now that the column exists and is backfilled. Rows with NULL
        # session_date (re-linker hasn't populated round_id yet) fall
        # back to created_at so the endpoint still surfaces them during
        # the catch-up window.
        params.append(range_days)
        clauses.append(
            "(session_date >= CURRENT_DATE - $" + str(len(params)) + " * INTERVAL '1 day' "
            "OR (session_date IS NULL AND created_at >= CURRENT_DATE - $" + str(len(params)) + " * INTERVAL '1 day'))"
        )

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
