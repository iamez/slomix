"""
Skill Rating API endpoints (experimental).

Completely isolated from existing routers - new /api/skill/* prefix.
"""

import json

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.services.skill_rating_service import (
    CONSTANT,
    MIN_ROUNDS,
    PROXIMITY_METRICS,
    WEIGHTS,
    compute_and_store_ratings,
    compute_session_map_ratings,
    compute_session_ratings,
    get_player_session_history,
    get_tier,
)

router = APIRouter()
logger = get_app_logger("api.skill")


def _parse_components(raw) -> dict:
    """Parse components from DB (JSONB or string)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
    return {}


async def _resolve_guid(db: DatabaseAdapter, identifier: str) -> str | None:
    """Resolve player identifier to GUID (try GUID first, then name)."""
    row = await db.fetch_one(
        "SELECT player_guid FROM player_skill_ratings WHERE player_guid = $1",
        (identifier,),
    )
    if row:
        return row[0]
    row = await db.fetch_one(
        "SELECT player_guid FROM player_skill_ratings WHERE LOWER(display_name) = LOWER($1)",
        (identifier,),
    )
    return row[0] if row else None


@router.get("/skill/leaderboard")
async def get_skill_leaderboard(
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    """Skill rating leaderboard. Auto-refreshes if stale (>1 hour since last compute)."""

    rows = await db.fetch_all(
        """SELECT player_guid, display_name, et_rating, games_rated,
                  last_rated_at, components
           FROM player_skill_ratings
           ORDER BY et_rating DESC
           LIMIT $1""",
        (limit,),
    )

    # Auto-refresh if empty or stale (last computed >1 hour ago)
    needs_refresh = not rows
    if rows and not needs_refresh:
        staleness = await db.fetch_val(
            "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(last_rated_at))) FROM player_skill_ratings"
        )
        needs_refresh = staleness is not None and float(staleness) > 3600

    if needs_refresh:
        count = await compute_and_store_ratings(db)
        if count == 0 and not rows:
            return {"status": "ok", "players": [], "meta": {"total": 0, "min_rounds": MIN_ROUNDS}}

        rows = await db.fetch_all(
            """SELECT player_guid, display_name, et_rating, games_rated,
                      last_rated_at, components
               FROM player_skill_ratings
               ORDER BY et_rating DESC
               LIMIT $1""",
            (limit,),
        )

    players = []
    for i, r in enumerate(rows):
        players.append({
            "rank": i + 1,
            "player_guid": r[0],
            "display_name": r[1] or "Unknown",
            "et_rating": float(r[2]),
            "games_rated": int(r[3]),
            "last_rated_at": str(r[4]) if r[4] else None,
            "components": _parse_components(r[5]),
            "confidence": round(min(1.0, int(r[3]) / 30), 2),
            "tier": get_tier(float(r[2])),
        })

    return {
        "status": "ok",
        "players": players,
        "meta": {
            "total": len(players),
            "min_rounds": MIN_ROUNDS,
            "weights": WEIGHTS,
            "constant": CONSTANT,
            "version": "2.0",
        },
    }


@router.get("/skill/player/{identifier}")
async def get_player_skill(
    identifier: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get skill rating for a specific player (by GUID or name)."""
    row = await db.fetch_one(
        """SELECT player_guid, display_name, et_rating, games_rated,
                  last_rated_at, components
           FROM player_skill_ratings WHERE player_guid = $1""",
        (identifier,),
    )

    if not row:
        row = await db.fetch_one(
            """SELECT player_guid, display_name, et_rating, games_rated,
                      last_rated_at, components
               FROM player_skill_ratings WHERE LOWER(display_name) = LOWER($1)""",
            (identifier,),
        )

    if not row:
        return {"status": "error", "detail": f"Player '{identifier}' not found or not rated (need {MIN_ROUNDS}+ rounds)"}

    rank_row = await db.fetch_one(
        """SELECT rank, total FROM (
            SELECT player_guid,
                   ROW_NUMBER() OVER (ORDER BY et_rating DESC) as rank,
                   COUNT(*) OVER () as total
            FROM player_skill_ratings
        ) sub WHERE player_guid = $1""",
        (row[0],),
    )

    return {
        "status": "ok",
        "player": {
            "player_guid": row[0],
            "display_name": row[1] or "Unknown",
            "et_rating": float(row[2]),
            "games_rated": int(row[3]),
            "last_rated_at": str(row[4]) if row[4] else None,
            "rank": int(rank_row[0]) if rank_row else 0,
            "total_rated": int(rank_row[1]) if rank_row else 0,
            "components": _parse_components(row[5]),
            "confidence": round(min(1.0, int(row[3]) / 30), 2),
            "tier": get_tier(float(row[2])),
        },
    }


# ---------------------------------------------------------------------------
# History endpoints — session/map scoped
# ---------------------------------------------------------------------------

@router.get("/skill/player/{identifier}/history")
async def get_player_skill_history(
    identifier: str,
    range_days: int = 30,
    session_date: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Rating history for a player.

    Without session_date: returns per-session ratings over time (FACEIT-style sparkline data).
      Each entry has: session_date, session_rating, cumulative_rating, delta, rounds, maps.

    With session_date: drill-down into a specific session showing per-map breakdown.
      Each entry has: map_name, map_rating, rounds, components.

    Query params:
      - range_days: 7, 30, 90, 365, 3650 (default: 30)
      - session_date: ISO date (e.g. 2026-03-25) for map drill-down
    """
    safe_range = max(1, min(range_days, 3650))

    guid = await _resolve_guid(db, identifier)
    if not guid:
        return {"status": "error", "detail": f"Player '{identifier}' not found"}

    # Drill-down: specific session → per-map breakdown
    if session_date:
        session_result = await compute_session_ratings(db, guid, session_date)
        maps = await compute_session_map_ratings(db, guid, session_date)

        return {
            "status": "ok",
            "player_guid": guid,
            "session_date": session_date,
            "session_summary": session_result,
            "maps": maps,
        }

    # Overview: per-session ratings over time range
    sessions = await get_player_session_history(db, guid, safe_range)

    return {
        "status": "ok",
        "player_guid": guid,
        "range_days": safe_range,
        "sessions": sessions,
        "total_sessions": len(sessions),
    }


@router.get("/skill/formula")
async def get_skill_formula():
    """Return the current rating formula details (transparency)."""
    return {
        "status": "ok",
        "version": "2.0",
        "name": "ET Rating v2",
        "description": (
            "Individual performance rating combining PCS stats + proximity analytics. "
            "Inspired by HLTV 2.0, Valorant ACS, PandaSkill, TrueSkill2, and "
            "competitive ET stopwatch format (class-based, objective-sequential, respawn). "
            "Format-agnostic: works in 3v3 (medic/engi/covy) and 6v6 (full roster)."
        ),
        "formula": "ET_Rating = constant + sum(weight_i * percentile(metric_i))",
        "constant": CONSTANT,
        "weights": WEIGHTS,
        "min_rounds": MIN_ROUNDS,
        "metrics": {
            "dpm": "Damage per minute (alive time)",
            "kpr": "Kills per round",
            "dpr": "Deaths per round (penalty — negative weight)",
            "accuracy": "Weapon accuracy",
            "revive_rate": "Revives given per round (medic = default class in 3v3)",
            "survival_rate": "Fraction of round time spent alive",
            "useful_kill_rate": "Useful kills / total kills",
            "objective_rate": "Objectives completed per round",
            "denied_playtime_pm": "Enemy playtime denied per minute",
            "kill_quality": "Kill Quality Index — gib-weighted outcome avg (simplified KIS proxy: gibbed=1.3, tapped=1.0, revived=0.5)",
            "crossfire_rate": "Crossfire kills / total kills — team coordination frequency",
            "trade_rate": "Trade kills / total kills — avenging teammate deaths within 3s",
            "kill_permanence": "Gib rate — permanent kills / total kill outcomes",
            "clutch_factor": "Low HP (<30) or outnumbered kills / total kills",
            "spawn_timing_eff": "Avg spawn timing score — how well-timed kills are vs enemy respawn waves",
        },
        "metric_sources": {
            "pcs": sorted(m for m in WEIGHTS if m not in PROXIMITY_METRICS),
            "proximity": sorted(PROXIMITY_METRICS),
        },
        "normalization": "Percentile rank (0.0 = worst, 1.0 = best) against all rated players",
        "range": "0.00 (theoretical min) to ~1.15 (exceptional), avg ~0.55",
    }


# ---------------------------------------------------------------------------
# Composite Stats — 5 advanced metrics per player per session
# ---------------------------------------------------------------------------

@router.get("/skill/composite")
async def get_composite_stats(
    session_date: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Composite advanced stats for all players in a session.
    5 metrics (0-100 scale each):
      - TIR: Team Impact Rating (crossfire + trade + push coordination)
      - CI:  Clutch Index (low HP / outnumbered kills)
      - KPI: Kill Permanence Index (gib rate)
      - SDS: Spawn Denial Score (spawn timing + denied playtime)
      - CP:  Combat Presence (survival + focus escape + alive time)

    Query: ?session_date=YYYY-MM-DD (defaults to latest proximity session)
    """
    # Resolve session date
    if not session_date:
        row = await db.fetch_one(
            "SELECT MAX(session_date) FROM proximity_kill_outcome"
        )
        if not row or not row[0]:
            return {"status": "ok", "session_date": None, "players": []}
        session_date = str(row[0])

    # Query per-player aggregates for this session from proximity + PCS
    rows = await db.fetch_all("""
        WITH session_pcs AS (
            SELECT player_guid, MAX(player_name) as player_name,
                SUM(kills) as kills, SUM(deaths) as deaths,
                SUM(gibs) as gibs,
                AVG(CASE WHEN time_played_seconds > 0
                    THEN (time_played_seconds - COALESCE(
                        CASE WHEN time_dead_minutes > 0 THEN time_dead_minutes * 60 ELSE 0 END, 0
                    ))::REAL / time_played_seconds ELSE 0 END) as survival_rate,
                AVG(COALESCE(time_dead_ratio, 0)) as avg_time_dead_pct,
                SUM(denied_playtime) as denied_playtime,
                SUM(time_played_seconds) as time_played_seconds
            FROM player_comprehensive_stats
            WHERE round_date = $1
              AND round_number > 0
            GROUP BY player_guid
        ),
        session_crossfire AS (
            SELECT killer_guid_canonical as guid_c,
                COUNT(*) FILTER (WHERE is_crossfire = true) as crossfire_kills
            FROM storytelling_kill_impact
            WHERE session_date = $1::date AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        ),
        session_trades AS (
            SELECT trader_guid_canonical as guid_c, COUNT(*) as trade_kills
            FROM proximity_lua_trade_kill
            WHERE session_date = $1::date AND trader_guid_canonical IS NOT NULL
            GROUP BY trader_guid_canonical
        ),
        session_permanence AS (
            SELECT killer_guid_canonical as guid_c,
                COUNT(*) as total_outcomes,
                COUNT(*) FILTER (WHERE outcome = 'gibbed') as gibbed_count
            FROM proximity_kill_outcome
            WHERE session_date = $1::date AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        ),
        session_clutch AS (
            SELECT attacker_guid_canonical as guid_c,
                COUNT(*) as total_combat_kills,
                COUNT(*) FILTER (
                    WHERE (killer_health > 0 AND killer_health < 30)
                       OR (attacker_team = 'AXIS' AND axis_alive < allies_alive)
                       OR (attacker_team = 'ALLIES' AND allies_alive < axis_alive)
                ) as clutch_kills
            FROM proximity_combat_position
            WHERE session_date = $1::date AND event_type = 'kill'
              AND attacker_guid_canonical IS NOT NULL
            GROUP BY attacker_guid_canonical
        ),
        session_spawn AS (
            SELECT killer_guid_canonical as guid_c,
                AVG(spawn_timing_score) as avg_spawn_score
            FROM proximity_spawn_timing
            WHERE session_date = $1::date AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        )
        SELECT
            pcs.player_guid,
            pcs.player_name,
            pcs.kills,
            COALESCE(sc.crossfire_kills, 0) as crossfire_kills,
            COALESCE(tr.trade_kills, 0) as trade_kills,
            COALESCE(perm.gibbed_count, 0) as gibbed_count,
            COALESCE(perm.total_outcomes, 0) as total_outcomes,
            COALESCE(cl.clutch_kills, 0) as clutch_kills,
            COALESCE(cl.total_combat_kills, 0) as total_combat_kills,
            COALESCE(sp.avg_spawn_score, 0) as avg_spawn_score,
            pcs.denied_playtime,
            pcs.time_played_seconds,
            pcs.survival_rate,
            0 as focus_escapes,
            0 as times_focused,
            pcs.avg_time_dead_pct
        FROM session_pcs pcs
        LEFT JOIN session_crossfire sc ON sc.guid_c = pcs.player_guid
        LEFT JOIN session_trades tr ON tr.guid_c = pcs.player_guid
        LEFT JOIN session_permanence perm ON perm.guid_c = pcs.player_guid
        LEFT JOIN session_clutch cl ON cl.guid_c = pcs.player_guid
        LEFT JOIN session_spawn sp ON sp.guid_c = pcs.player_guid
        WHERE pcs.kills > 0
        ORDER BY pcs.kills DESC
    """, (session_date,))

    players = []
    for r in rows:
        guid, name = r[0], r[1]
        kills = max(int(r[2]), 1)
        crossfire_kills, trade_kills = int(r[3]), int(r[4])
        gibbed, total_outcomes = int(r[5]), int(r[6])
        clutch_kills, total_combat_kills = int(r[7]), max(int(r[8]), 1)
        avg_spawn_score = float(r[9])
        denied_pt, time_played = int(r[10]), max(int(r[11]), 1)
        survival_rate = float(r[12])
        focus_escapes, times_focused = int(r[13]), int(r[14])
        avg_time_dead = float(r[15])

        # TIR: Team Impact Rating (0-100)
        # crossfire_pct + trade_pct are ratios (0-1); scale each to half the
        # 0-100 range so the sum stays bounded.
        crossfire_pct = min(1.0, crossfire_kills / kills) if kills else 0
        trade_pct = min(1.0, trade_kills / kills) if kills else 0
        tir = round(min(100, crossfire_pct * 50 + trade_pct * 50), 1)

        # CI: Clutch Index (0-100)
        ci = round(min(100, (clutch_kills / max(total_combat_kills, 1)) * 100), 1)

        # KPI: Kill Permanence Index (0-100%)
        kpi = round((gibbed / total_outcomes * 100) if total_outcomes > 0 else 0, 1)

        # SDS: Spawn Denial Score (0-100)
        denied_pct = min(1.0, (denied_pt / (time_played / 60.0)) / 10.0) if time_played > 0 else 0
        sds = round(min(100, (avg_spawn_score * 60 + denied_pct * 40)), 1)

        # CP: Combat Presence (0-100)
        focus_escape_rate = (focus_escapes / times_focused) if times_focused > 0 else 0.5
        cp = round(min(100, (
            survival_rate * 40 +
            focus_escape_rate * 30 +
            max(0, 1 - avg_time_dead) * 30
        )), 1)

        players.append({
            "player_guid": guid,
            "player_name": name,
            "kills": kills,
            "tir": tir,
            "ci": ci,
            "kpi": kpi,
            "sds": sds,
            "cp": cp,
            "details": {
                "crossfire_kills": crossfire_kills,
                "trade_kills": trade_kills,
                "clutch_kills": clutch_kills,
                "gibbed_count": gibbed,
                "total_outcomes": total_outcomes,
                "avg_spawn_score": round(avg_spawn_score, 3),
                "focus_escapes": focus_escapes,
                "times_focused": times_focused,
            },
        })

    return {
        "status": "ok",
        "session_date": session_date,
        "players": players,
        "meta": {
            "metrics": {
                "tir": "Team Impact Rating — crossfire + trade coordination (0-100)",
                "ci": "Clutch Index — low HP + outnumbered kill rate (0-100)",
                "kpi": "Kill Permanence Index — gib rate (0-100%)",
                "sds": "Spawn Denial Score — timing + denied playtime (0-100)",
                "cp": "Combat Presence — survival + focus escape + alive time (0-100)",
            },
        },
    }


# Form metrics: last session vs each player's OWN recent baseline. Cheap SQL
# aggregates (no percentiles) so /skill/movers stays one query. label + higher_is_better
# drive the UI copy + arrow direction (all current metrics: higher = better).
_MOVER_METRICS = {
    "dpm": {"label": "Damage / min", "unit": "dpm", "digits": 0},
    "kd": {"label": "Kills / death", "unit": "K/D", "digits": 2},
    "obj": {"label": "Objectives / round", "unit": "obj/rd", "digits": 2},
    "acc": {"label": "Accuracy", "unit": "%", "digits": 1},
    "kills": {"label": "Kills / session", "unit": "kills", "digits": 0},
}


def _metric_value(metric: str, kills, deaths, dpm, obj, acc):
    """Pick one session's value for the chosen form metric (None when absent)."""
    if metric == "dpm":
        return None if dpm is None else float(dpm)
    if metric == "kd":
        d = int(deaths or 0)
        return float(kills or 0) / d if d > 0 else float(kills or 0)
    if metric == "obj":
        return None if obj is None else float(obj)
    if metric == "acc":
        return None if acc is None else float(acc)
    if metric == "kills":
        return float(kills or 0)
    return None if dpm is None else float(dpm)


async def _form_rows(db, guid: str | None, session_limit: int):
    """Per-session raw metric rows over the most recent sessions. When guid is
    given, scope to that player's own sessions (for their profile form); else all
    players over the recent global sessions (for the movers board). Ordered newest
    session first."""
    scope = "AND pcs.player_guid = $1" if guid else ""
    params = (guid,) if guid else ()
    return await db.fetch_all(
        f"""
        WITH recent_sessions AS (
            SELECT DISTINCT r.gaming_session_id
            FROM rounds r
            {"JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id" if guid else ""}
            WHERE r.gaming_session_id IS NOT NULL
              AND r.is_valid IS DISTINCT FROM FALSE
              {scope}
            ORDER BY r.gaming_session_id DESC
            LIMIT {int(session_limit)}
        ),
        per_session AS (
            SELECT pcs.player_guid,
                   MAX(pcs.player_name) AS player_name,
                   r.gaming_session_id,
                   SUM(pcs.kills) AS kills,
                   SUM(pcs.deaths) AS deaths,
                   SUM(pcs.damage_given)::float
                       / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0) AS dpm,
                   (SUM(pcs.objectives_completed) + SUM(pcs.objectives_destroyed)
                    + SUM(pcs.objectives_stolen) + SUM(pcs.objectives_returned))::float
                       / NULLIF(COUNT(*), 0) AS obj,
                   AVG(pcs.accuracy) FILTER (WHERE pcs.accuracy IS NOT NULL AND pcs.accuracy > 0) AS acc
            FROM player_comprehensive_stats pcs
            JOIN rounds r ON r.id = pcs.round_id
            WHERE r.gaming_session_id IN (SELECT gaming_session_id FROM recent_sessions)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND pcs.time_played_seconds > 0
              {scope}
            GROUP BY pcs.player_guid, r.gaming_session_id
        )
        SELECT player_guid, player_name, gaming_session_id, kills, deaths, dpm, obj, acc
        FROM per_session
        ORDER BY gaming_session_id DESC
        """,
        params,
    )


@router.get("/skill/movers")
async def get_movers(
    top: int = 3,
    metric: str = "dpm",
    full: bool = False,
    db: DatabaseAdapter = Depends(get_db),
):
    """Form movers: last session vs each player's OWN recent baseline.

    VISION_2026 anti-goal compliance: this is rank-vs-self, NOT a global ladder —
    the delta is against the player's own trailing baseline for the chosen metric,
    so a bottom-half player on a hot night tops the movers list.

    metric: dpm | kd | obj | acc | kills.  full=true returns every mover (Form
    page); otherwise the top N up/down (home card). Each mover carries `series`
    (their per-session values, oldest→newest) for a sparkline.
    """
    if metric not in _MOVER_METRICS:
        metric = "dpm"
    top = max(1, min(top, 50 if full else 10))
    rows = await _form_rows(db, None, 11)
    if not rows:
        return {"status": "ok", "session_id": None, "metric": metric,
                "movers_up": [], "movers_down": [], "new_players": []}

    latest_sid = max(int(r[2]) for r in rows)
    latest_date = await db.fetch_val(
        "SELECT MAX(round_date) FROM rounds WHERE gaming_session_id = $1",
        (latest_sid,),
    )

    latest: dict[str, dict] = {}
    history: dict[str, list[float]] = {}  # oldest→newest per guid (excl. latest)
    for guid, name, sid, kills, deaths, dpm, obj, acc in rows:
        val = _metric_value(metric, kills, deaths, dpm, obj, acc)
        if int(sid) == latest_sid:
            latest[guid] = {"name": name, "val": val}
        elif val is not None:
            history.setdefault(guid, []).insert(0, round(val, 2))  # rows are DESC → prepend

    digits = _MOVER_METRICS[metric]["digits"]
    movers = []
    for guid, cur in latest.items():
        cur_val = cur["val"]
        hist = history.get(guid)
        hist_list = hist or []
        series = ([*hist_list, round(cur_val, 2)] if cur_val is not None else list(hist_list))
        if not hist or cur_val is None:
            movers.append({
                "guid": guid, "name": cur["name"], "latest": None if cur_val is None else round(cur_val, digits),
                "baseline": None, "delta_pct": None, "series": series, "is_new": True,
            })
            continue
        avg = sum(hist) / len(hist)
        if avg <= 0:
            continue
        movers.append({
            "guid": guid, "name": cur["name"],
            "latest": round(cur_val, digits), "baseline": round(avg, digits),
            "delta_pct": round((cur_val - avg) / avg * 100, 1),
            "series": series, "is_new": False,
        })

    ranked = sorted(
        (m for m in movers if m["delta_pct"] is not None),
        key=lambda m: m["delta_pct"], reverse=True,
    )
    up = [m for m in ranked if m["delta_pct"] > 0]
    down = [m for m in ranked if m["delta_pct"] < 0]
    if not full:
        up = up[:top]
        up_guids = {m["guid"] for m in up}
        down = [m for m in reversed(down[-top:]) if m["guid"] not in up_guids]
    else:
        down = list(reversed(down))  # most-down first
    return {
        "status": "ok",
        "session_id": latest_sid,
        "session_date": str(latest_date) if latest_date else None,
        "metric": metric,
        "metric_label": _MOVER_METRICS[metric]["label"],
        "baseline": f"own trailing ~10-session {metric}",
        "baseline_desc": "last session vs this player's own recent-session average (rank-vs-self, not a global ranking)",
        "movers_up": up,
        "movers_down": down,
        "new_players": [m for m in movers if m.get("is_new")],
    }


@router.get("/skill/player/{identifier}/form")
async def get_player_form(
    identifier: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """One player's form: latest session vs their OWN recent baseline, per metric,
    with a per-metric series for a sparkline. Powers the 'Your form' profile section.
    """
    guid = await _resolve_guid(db, identifier)
    if not guid:
        return {"status": "error", "detail": f"Player '{identifier}' not found"}
    rows = await _form_rows(db, guid, 10)
    if not rows:
        return {"status": "ok", "player_guid": guid, "session_id": None, "metrics": {}}

    latest_sid = max(int(r[2]) for r in rows)
    latest_date = await db.fetch_val(
        "SELECT MAX(round_date) FROM rounds WHERE gaming_session_id = $1",
        (latest_sid,),
    )
    # rows are this player's sessions, newest first
    metrics_out = {}
    for key, meta in _MOVER_METRICS.items():
        latest_val = None
        hist: list[float] = []
        for _guid, _name, sid, kills, deaths, dpm, obj, acc in rows:
            val = _metric_value(key, kills, deaths, dpm, obj, acc)
            if val is None:
                continue
            if int(sid) == latest_sid:
                latest_val = val
            else:
                hist.insert(0, round(val, 2))
        series = ([*hist, round(latest_val, 2)] if latest_val is not None else hist)
        avg = (sum(hist) / len(hist)) if hist else None
        metrics_out[key] = {
            "label": meta["label"], "unit": meta["unit"],
            "latest": None if latest_val is None else round(latest_val, meta["digits"]),
            "baseline": None if not avg else round(avg, meta["digits"]),
            "delta_pct": (round((latest_val - avg) / avg * 100, 1)
                          if (avg and avg > 0 and latest_val is not None) else None),
            "series": series,
        }
    name = rows[0][1]
    return {
        "status": "ok",
        "player_guid": guid,
        "player_name": name,
        "session_id": latest_sid,
        "session_date": str(latest_date) if latest_date else None,
        "baseline_desc": "last session vs your own recent-session average (rank-vs-self)",
        "metrics": metrics_out,
    }
