"""
Skill Rating API endpoints (experimental).

Completely isolated from existing routers - new /api/skill/* prefix.
"""

import json

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db, require_internal_secret
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import fetch_identity_links
from website.backend.services.skill_rating_service import (
    CONSTANT,
    MIN_ROUNDS,
    PROXIMITY_METRICS,
    SHRINKAGE_K,
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


async def _pool_mean(db) -> float | None:
    """Mean RAW rating over every rated player — the shrinkage prior.

    Raw is `constant + Σ contribution`, which is what the stored components
    add up to (shrinkage is applied after they are built and never folded
    back into them). Returns None when nothing is rated, so the page can say
    so instead of printing a zero it would have to explain.
    """
    rows = await db.fetch_all("SELECT components FROM player_skill_ratings")
    raws = []
    for row in rows or []:
        components = _parse_components(row[0])
        if not components:
            continue
        raws.append(CONSTANT + sum(c.get("contribution", 0.0) for c in components.values()))
    return round(sum(raws) / len(raws), 4) if raws else None


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
        players.append(
            {
                "rank": i + 1,
                "player_guid": r[0],
                "display_name": r[1] or "Unknown",
                "et_rating": float(r[2]),
                "games_rated": int(r[3]),
                "last_rated_at": str(r[4]) if r[4] else None,
                "components": _parse_components(r[5]),
                "confidence": round(min(1.0, int(r[3]) / 30), 2),
                "tier": get_tier(float(r[2])),
            }
        )

    # The pool mean the shrinkage was computed against. Without it a reader
    # can see the components (which decompose the RAW rating) and the
    # published rating, and has no way to get from one to the other:
    #   published = (n·raw + k·pool_mean) / (n + k)
    # It is recomputed here from the same stored components rather than
    # persisted, because since the cohort reconciliation the table holds
    # exactly the players of the last run — the same set the write-time mean
    # was taken over. Verified on dev: reconstructing every published rating
    # this way lands within 0.0003, which is the components' own rounding.
    pool_mean = await _pool_mean(db)

    return {
        "status": "ok",
        "players": players,
        "meta": {
            "total": len(players),
            "min_rounds": MIN_ROUNDS,
            "weights": WEIGHTS,
            "constant": CONSTANT,
            "version": "2.1",
            "shrinkage_k": SHRINKAGE_K,
            "pool_mean": pool_mean,
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
        return {
            "status": "error",
            "detail": f"Player '{identifier}' not found or not rated (need {MIN_ROUNDS}+ rounds)",
        }

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


@router.get("/skill/s-effort")
async def get_s_effort(
    session_date: str,
    _internal: None = Depends(require_internal_secret),
    db=Depends(get_db),
):
    """s.effort / s.performance for one session (SuperBoyy's pool-adjusted
    performance; pool variant A leave-one-out per owner decision). Computes
    live and idempotently persists scope='session' history rows."""
    from website.backend.services.s_effort_service import FORMULA_VERSION, SEffortService

    svc = SEffortService(db)
    rows = await svc.compute_session(session_date)
    if not rows:
        # still clear any stale persisted rows for the date (roster may have
        # been invalidated since the last persist)
        try:
            await svc.persist_session(session_date, rows=[])
        except Exception:
            import logging

            logging.getLogger(__name__).exception("s.effort stale-clear failed")
        return {"status": "ok", "available": False, "session_date": session_date}
    try:
        await svc.persist_session(session_date, rows=rows)
    except Exception:  # persist is best-effort; the response is the compute
        import logging

        logging.getLogger(__name__).exception("s.effort persist failed")
    rows.sort(key=lambda r: -(r.get("s_performance") or 0))
    return {
        "status": "ok",
        "available": True,
        "session_date": session_date,
        "formula_version": FORMULA_VERSION,
        "players": rows,
    }


@router.get("/skill/adjusted-lifetime")
async def get_adjusted_lifetime(db=Depends(get_db)):
    """Pool-adjusted lifetime rating (SRS iteration over persisted session
    rows; AVG per owner correction — volume cannot inflate it). Requires
    scope='session' history (run /skill/s-effort per session or the backfill
    script first)."""
    from website.backend.services.s_effort_service import FORMULA_VERSION, SEffortService

    rows = await SEffortService(db).compute_adjusted_lifetime()
    return {"status": "ok", "available": bool(rows), "formula_version": FORMULA_VERSION, "players": rows}


@router.get("/skill/ssr")
async def get_ssr(db=Depends(get_db)):
    """Situational Skill Rating v0 (owner A4): group-relative aggregate of
    clutch KIS, situational KIS share, OIS, permanence, target acquisition
    and spawn readiness. Research surface — numbers are percentile-based
    (0..1) within the rated cohort, min 5 sessions (A6)."""
    from website.backend.services.ssr_service import SsrService

    return {"status": "ok", **(await SsrService(db).compute())}


@router.get("/skill/formula")
async def get_skill_formula():
    """Return the current rating formula details (transparency)."""
    return {
        "status": "ok",
        "version": "2.1",
        "name": "ET Rating v2",
        "description": (
            "Individual performance rating combining PCS stats + proximity analytics. "
            "Inspired by HLTV 2.0, Valorant ACS, PandaSkill, TrueSkill2, and "
            "competitive ET stopwatch format (class-based, objective-sequential, respawn). "
            "Format-agnostic: works in 3v3 (medic/engi/covy) and 6v6 (full roster). "
            "v2.1: published rating is sample-size shrunk toward the pool mean "
            "(Bayesian pseudo-count prior), so a handful of hot rounds no longer "
            "outranks a thousand-round track record."
        ),
        "formula": (
            "raw = constant + sum(weight_i * percentile(metric_i)); "
            "ET_Rating = (n * raw + shrinkage_k * pool_mean) / (n + shrinkage_k)"
        ),
        "constant": CONSTANT,
        "weights": WEIGHTS,
        "min_rounds": MIN_ROUNDS,
        "shrinkage_k": SHRINKAGE_K,
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


@router.get("/skill/v3-shadow")
async def get_et_performance_v3_shadow(
    db: DatabaseAdapter = Depends(get_db),
    _internal: None = Depends(require_internal_secret),
):
    """ET Performance v3 SHADOW rating (audit AUD-007).

    Owner-review only — gated behind require_internal_secret like the other
    non-public skill endpoints (Copilot/Codex P1 #513): it is not user-visible
    and triggers an expensive full recomputation. This is the corrected formula
    (directed midrank + absolute weights, no constant, mean 0.50) over a common
    telemetry epoch, exposed for review before any promotion. v2 remains
    canonical at /skill/leaderboard.
    """
    from website.backend.services.skill_rating_v3 import compute_et_performance_v3

    try:
        result = await compute_et_performance_v3(db)
        return {"status": "ok", "shadow": True, **result}
    except Exception:
        logger.exception("v3-shadow rating failed")
        return {"status": "error", "shadow": True, "detail": "v3 shadow computation failed"}


# ---------------------------------------------------------------------------
# Composite Stats — 5 advanced metrics per player per session
# ---------------------------------------------------------------------------


_COMPOSITE_METRIC_DESCRIPTIONS = {
    "tir": "Team Impact Rating — crossfire + trade coordination (0-100)",
    "ci": "Clutch Index — low HP + outnumbered kill rate (0-100)",
    "kpi": "Kill Permanence Index — gib rate (0-100%)",
    "sds": "Spawn Denial Score — timing + denied playtime (0-100)",
    # ⚠️ Two of the three inputs this used to advertise are not
    # measured per session. `focus_escapes`/`times_focused` are
    # selected as literal 0 in the query above, so
    # focus_escape_rate is 0.5 for every player in every session —
    # a fixed 15 of the 100 points. Measured: 158 of 158 sampled
    # players carry 0/0. The only source in the database
    # (`player_teamplay_stats`) is a 32-row LIFETIME aggregate
    # with no round or session key, so it cannot answer a
    # per-session question; wiring it in would be wrong, not just
    # missing. The description now says what the number is.
    "cp": (
        "Combat Presence — survival + alive time (0-100), "
        "plus a fixed 15 points: the focus-escape term has no "
        "per-session source and is held at its 0.5 default for "
        "every player"
    ),
}


@router.get("/skill/composite")
async def get_composite_stats(
    session_date: str | None = None,
    gaming_session_id: int | None = None,
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

    Scope (prefer ?gaming_session_id — see below):
      - ?gaming_session_id=N  → the ONE gaming session, the correct scope.
        Every CTE is bound to that session's rounds (round_id / gsid), and bot
        rounds are excluded. This is the fix for the date-scoping bug: two
        sessions on the same calendar date (e.g. a real match + a bot test that
        carries gaming_session_id=NULL) share a round_date, so ?session_date
        merged BOTH — surfacing phantom [BOT]… players from the other session.
      - ?session_date=YYYY-MM-DD → legacy date scope (kept for callers that
        only have a date; still merges everything played that day).
      - neither → latest proximity session_date.
    """
    # Scope resolution: gaming_session_id wins; else fall back to session_date.
    if gaming_session_id is not None:
        scope_param: object = gaming_session_id
        # gsid-bound predicates. pcs joins rounds (no gsid column of its own);
        # storytelling_kill_impact carries gaming_session_id directly; the
        # proximity_* tables are round-keyed, so restrict to this session's
        # round set. Bot rounds are dropped at the driving table (session_pcs
        # LEFT-JOINs the rest, so excluding bots here removes them everywhere).
        pcs_from = "player_comprehensive_stats p JOIN rounds r ON r.id = p.round_id"
        pcs_cols = (
            "p.player_guid, MAX(p.player_name) as player_name, "
            "SUM(p.kills) as kills, SUM(p.deaths) as deaths, "
            "SUM(p.gibs) as gibs"
        )
        # Round-quality gate, the same one every other KPI applies (S6 audit):
        # excluding bots by NAME is not enough. Session 121 carries one round
        # flagged is_valid = FALSE, and its 53 kills were inflating the
        # composite by 8-16 % for the four players in it (SuperBoyy 147 -> 135,
        # qmr 128 -> 108) — invisible, because the players are real.
        pcs_where = (
            "WHERE r.gaming_session_id = $1 AND r.round_number > 0 "
            "AND r.is_valid IS DISTINCT FROM FALSE "
            "AND r.is_bot_round IS DISTINCT FROM TRUE "
            "AND p.player_guid NOT LIKE 'OMNIBOT%' "
            "AND p.player_name NOT LIKE '[BOT]%'"
        )
        pcs_group = "GROUP BY p.player_guid"
        pcs_alias = "p."
        ski_where = "WHERE gaming_session_id = $1"
        round_set = (
            "round_id IN (SELECT id FROM rounds "
            "WHERE gaming_session_id = $1 "
            "  AND is_valid IS DISTINCT FROM FALSE "
            "  AND is_bot_round IS DISTINCT FROM TRUE)"
        )
    else:
        if not session_date:
            # ⛔ The fallback scope reads ALL five coverage sources, not one
            # (Codex on #848): with proximity_kill_outcome empty but any other
            # instrument still writing, a single-table MAX said "nothing
            # anywhere" and the early return below hard-coded five zeros that
            # were never counted. GREATEST over the union makes that return
            # reachable only when every source is empty — at which point the
            # zeros are true by construction rather than by assertion.
            row = await db.fetch_one(
                """
                SELECT GREATEST(
                    (SELECT MAX(session_date) FROM proximity_kill_outcome),
                    (SELECT MAX(session_date) FROM proximity_crossfire_opportunity),
                    (SELECT MAX(session_date) FROM proximity_lua_trade_kill),
                    (SELECT MAX(session_date) FROM proximity_combat_position),
                    (SELECT MAX(session_date) FROM proximity_spawn_timing)
                )
                """
            )
            if not row or not row[0]:
                # No proximity rows anywhere, so there is no default scope to
                # pick. This used to return a SHORTER shape than the one
                # below — no `coverage`, no `meta` — which is the same trap
                # the coverage block exists to close: a caller that reads
                # `coverage.unmeasured_metrics` would get a KeyError on
                # exactly the state where the answer matters most. Same keys,
                # every time.
                return {
                    "status": "ok",
                    "session_date": None,
                    "gaming_session_id": None,
                    "players": [],
                    "coverage": {
                        "unmeasured_metrics": ["ci", "kpi", "sds", "tir"],
                        "source_rows": {
                            "crossfire": 0,
                            "crossfire_cache": 0,
                            "trades": 0,
                            "combat_positions": 0,
                            "kill_outcomes": 0,
                            "spawn_timing": 0,
                        },
                    },
                    "meta": {"metrics": _COMPOSITE_METRIC_DESCRIPTIONS},
                }
            session_date = str(row[0])
        scope_param = session_date
        # The legacy date path cannot separate two sessions sharing a date —
        # that is its known limitation — but it can at least apply the same
        # quality gate, so an invalid round never counts on either path.
        pcs_from = "player_comprehensive_stats p JOIN rounds r ON r.id = p.round_id"
        pcs_cols = (
            "p.player_guid, MAX(p.player_name) as player_name, "
            "SUM(p.kills) as kills, SUM(p.deaths) as deaths, "
            "SUM(p.gibs) as gibs"
        )
        pcs_where = (
            "WHERE p.round_date = $1 AND p.round_number > 0 "
            "AND r.is_valid IS DISTINCT FROM FALSE "
            "AND r.is_bot_round IS DISTINCT FROM TRUE"
        )
        pcs_group = "GROUP BY p.player_guid"
        pcs_alias = "p."
        ski_where = "WHERE session_date = $1::date"
        round_set = (
            "round_id IN (SELECT id FROM rounds "
            "WHERE SUBSTR(CAST(round_date AS TEXT), 1, 10) = $1 "
            "  AND is_valid IS DISTINCT FROM FALSE "
            "  AND is_bot_round IS DISTINCT FROM TRUE)"
        )

    # Query per-player aggregates for this session from proximity + PCS. The
    # scope fragments above are code-controlled (no user input) and the scope
    # value always flows through the $1 bind parameter.
    rows = await db.fetch_all(
        f"""
        WITH session_pcs AS (
            SELECT {pcs_cols},
                AVG(CASE WHEN {pcs_alias}time_played_seconds > 0
                    THEN ({pcs_alias}time_played_seconds - COALESCE(
                        CASE WHEN {pcs_alias}time_dead_minutes > 0 THEN {pcs_alias}time_dead_minutes * 60 ELSE 0 END, 0
                    ))::REAL / {pcs_alias}time_played_seconds ELSE 0 END) as survival_rate,
                AVG(COALESCE({pcs_alias}time_dead_ratio, 0)) as avg_time_dead_pct,
                SUM({pcs_alias}denied_playtime) as denied_playtime,
                SUM({pcs_alias}time_played_seconds) as time_played_seconds
            FROM {pcs_from}
            {pcs_where}
            {pcs_group}
        ),
        session_crossfire AS (
            SELECT killer_guid_canonical as guid_c,
                COUNT(*) FILTER (WHERE is_crossfire = true) as crossfire_kills
            FROM storytelling_kill_impact
            {ski_where} AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        ),
        session_trades AS (
            SELECT trader_guid_canonical as guid_c, COUNT(*) as trade_kills
            FROM proximity_lua_trade_kill
            WHERE {round_set} AND trader_guid_canonical IS NOT NULL
            GROUP BY trader_guid_canonical
        ),
        session_permanence AS (
            SELECT killer_guid_canonical as guid_c,
                COUNT(*) as total_outcomes,
                COUNT(*) FILTER (WHERE outcome = 'gibbed') as gibbed_count
            FROM proximity_kill_outcome
            WHERE {round_set} AND killer_guid_canonical IS NOT NULL
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
            WHERE {round_set} AND event_type = 'kill'
              AND attacker_guid_canonical IS NOT NULL
            GROUP BY attacker_guid_canonical
        ),
        session_spawn AS (
            SELECT killer_guid_canonical as guid_c,
                AVG(spawn_timing_score) as avg_spawn_score
            FROM proximity_spawn_timing
            WHERE {round_set} AND killer_guid_canonical IS NOT NULL
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
    """,
        (scope_param,),
    )

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
        cp = round(min(100, (survival_rate * 40 + focus_escape_rate * 30 + max(0, 1 - avg_time_dead) * 30)), 1)

        players.append(
            {
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
            }
        )

    # ⛔ WITHOUT THIS BLOCK A METRIC NOBODY MEASURED IS INDISTINGUISHABLE FROM
    # A METRIC THAT CAME OUT ZERO. Four of the five draw from the proximity
    # tables, and 98 of 151 gaming sessions have no proximity rows at all —
    # `shot_fired` has been off on the game server since 2026-08-11, and the
    # capture only ever covered part of the history. Measured over a random
    # 24-session sample of this database:
    #
    #   proximity absent (18 sessions):  ci 18/18 all-zero, kpi 18/18,
    #                                    tir 17/18, sds <= 40.0 for 124/124
    #                                    players (avg_spawn_score is 60 % of
    #                                    the SDS weight and it is missing)
    #   proximity present (5 sessions):  none of the five ever all-zero
    #
    # So the zeros are the shape of an unasked question, and the answer used
    # to be `status: "ok"` either way. Same class as the outage that read as
    # an empty database: absence and zero have the same shape on the wire, so
    # the response has to name which one it is.
    #
    # ⚠️ The flag is derived from whether the SOURCE ROWS exist in scope, not
    # from whether the scores came out zero. Reading it off the zeros would be
    # circular — it would also flag a session that was fully measured and
    # genuinely had no clutch kills, which is a real answer, not a missing one.
    # ⚠️ Three corrections from review (Codex + CodeRabbit on #848), each an
    # instance of one rule — count what the metric queries can USE:
    #
    # - The crossfire leg counts the RAW instrument
    #   (proximity_crossfire_opportunity), not the KIS cache it feeds: a
    #   cached is_crossfire computed against an empty crossfire context is
    #   a value, not a measurement. ⚠️ Measured TWICE, because the first
    #   number was wrong: UNGATED, cache>0 with raw=0 happens in 0
    #   sessions — but this count runs THROUGH round_set, and gated it
    #   happens in SIX. The verifier's independent measurement caught the
    #   discrepancy; the first claim compared the raw table without the
    #   gate the code applies. So this change flips tir to
    #   honestly-unmeasured in 6 live sessions, plus the 5 where every
    #   cache row is a bot row.
    # - Every count carries the canonical-GUID predicate its metric CTE
    #   carries (IS NOT NULL): a row the CTE filters out cannot make its
    #   metric "measured". 0 nulls in today's data; the predicate mirrors
    #   the CTEs, not the sample.
    # - OMNIBOT canonical GUIDs are excluded the way session_pcs excludes
    #   bot players. Through round_set alone 0 sessions flip today, but
    #   the round flag has been insufficient before and the count must not
    #   rely on it (8,358 OMNIBOT rows in kill_outcome alone).
    coverage_row = await db.fetch_one(
        f"""
        SELECT
            (SELECT COUNT(*) FROM proximity_crossfire_opportunity
              WHERE {round_set}),
            (SELECT COUNT(*) FROM storytelling_kill_impact
              {ski_where} AND killer_guid_canonical IS NOT NULL
                AND killer_guid_canonical NOT LIKE 'OMNIBOT%'),
            (SELECT COUNT(*) FROM proximity_lua_trade_kill
              WHERE {round_set} AND trader_guid_canonical IS NOT NULL
                AND trader_guid_canonical NOT LIKE 'OMNIBOT%'),
            (SELECT COUNT(*) FROM proximity_combat_position
              WHERE {round_set} AND event_type = 'kill'
                AND attacker_guid_canonical IS NOT NULL
                AND attacker_guid_canonical NOT LIKE 'OMNIBOT%'),
            (SELECT COUNT(*) FROM proximity_kill_outcome
              WHERE {round_set} AND killer_guid_canonical IS NOT NULL
                AND killer_guid_canonical NOT LIKE 'OMNIBOT%'),
            (SELECT COUNT(*) FROM proximity_spawn_timing
              WHERE {round_set} AND killer_guid_canonical IS NOT NULL
                AND killer_guid_canonical NOT LIKE 'OMNIBOT%')
    """,
        (scope_param,),
    )

    # ⚠️ Read positionally and defensively, never by unpacking. This block is
    # an ANNOTATION on the answer; it must never be able to take the answer
    # down. Unpacking five names from the row raises ValueError on a row of
    # any other width — which is exactly what happened the first time this
    # shipped: `tests/unit/test_composite_validity_gate.py` uses a stub whose
    # `fetch_one` answers every query with a 1-tuple, and a working endpoint
    # turned into a 500 over a field nobody reads yet. A missing count reads
    # as 0, which flags the metric as unmeasured — the cautious direction.
    def _count(index: int) -> int:
        try:
            return int(coverage_row[index] or 0)
        except (TypeError, IndexError, ValueError):
            return 0

    crossfire_rows, crossfire_cache_rows, trade_rows, combat_rows, outcome_rows, spawn_rows = (
        _count(0),
        _count(1),
        _count(2),
        _count(3),
        _count(4),
        _count(5),
    )

    # metric -> the source counts it needs. A metric is "measured" when at
    # least one of its inputs produced rows for this scope; "unmeasured" when
    # none did, and its number below is a floor rather than a measurement.
    # ⛔ Crossfire is a TWO-STAGE pipeline and tir needs both stages plus
    # trades (verifier on #848, round two): the raw instrument
    # (crossfire_opportunity) says the capture ran; the KIS cache says the
    # storytelling pipeline actually produced the rows the session_crossfire
    # CTE reads. Counting only the raw side re-broke four sessions the
    # source swap was meant to fix: 94/95/97/98 have raw rows and trades
    # but ZERO cache rows — the pipeline never ran for them — so tir was
    # floored by up to 50 points and labelled measured. Neither stage reads
    # is_crossfire, so neither is circular. Measured: tir measured in
    # 47/151 sessions with two sources, 43/151 with three — the difference
    # is exactly those four.
    metric_sources = {
        "tir": (crossfire_rows, crossfire_cache_rows, trade_rows),
        "ci": (combat_rows,),
        "kpi": (outcome_rows,),
        "sds": (spawn_rows,),
    }

    # ⛔ TIR needs BOTH of its sources; the single-source metrics need
    # their one (verifier's finding on #848): tir = crossfire*50 +
    # trade*50 is a SUM of two halves, not a choice between substitutes,
    # so one present half with the other missing floors the score by up
    # to 50 points while any() called it measured. Measured: 1 live
    # session carries exactly one half. The cautious direction costs a
    # false "unmeasured" only for a session where genuinely nobody
    # traded — a floor reported as a floor.
    def _is_unmeasured(metric: str, counts: tuple[int, ...]) -> bool:
        if metric == "tir":
            return not all(counts)
        return not any(counts)

    unmeasured = sorted(m for m, counts in metric_sources.items() if _is_unmeasured(m, counts))

    return {
        "status": "ok",
        "session_date": session_date,
        "gaming_session_id": gaming_session_id,
        "players": players,
        "coverage": {
            # Always present, always a list — an empty list means "everything
            # in scope was measured", which is a different statement from the
            # key being absent, and the UI must be able to tell them apart.
            "unmeasured_metrics": unmeasured,
            "source_rows": {
                "crossfire": crossfire_rows,
                "crossfire_cache": crossfire_cache_rows,
                "trades": trade_rows,
                "combat_positions": combat_rows,
                "kill_outcomes": outcome_rows,
                "spawn_timing": spawn_rows,
            },
        },
        "meta": {"metrics": _COMPOSITE_METRIC_DESCRIPTIONS},
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
    # Impact = per-session proximity blend: gib-weighted kill quality (the same
    # simplified-KIS proxy ET Rating uses) + trade rate + clutch rate. Only present
    # for sessions with proximity coverage; the composite renormalizes without it.
    "impact": {"label": "Impact (kills that stick)", "unit": "idx", "digits": 2},
}

# Composite "Form Index": blend all per-metric self-relative ratios into ONE number
# (100 = the player's own usual across every metric). Impact-weighted; dpm & kills
# overlap so kills is weighted low. Weights are shown in the UI explainer for
# transparency. Ratios are clamped so a tiny baseline can't blow up the index.
_FORM_METRIC_KEYS = tuple(_MOVER_METRICS)
_FORM_WEIGHTS = {"dpm": 0.25, "kd": 0.20, "obj": 0.15, "acc": 0.10, "kills": 0.05, "impact": 0.25}
_FORM_RATIO_CLAMP = (0.4, 2.5)
_OVERALL_LABEL = "Overall form"


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
        ,
        prox_quality AS (
            -- Gib-weighted kill quality per (player, session) — the simplified-KIS
            -- proxy used by ET Rating, here scoped per session via round_id.
            SELECT r2.gaming_session_id, pko.killer_guid_canonical AS guid,
                   AVG(CASE pko.outcome
                       WHEN 'gibbed' THEN 1.3
                       WHEN 'tapped_out' THEN 1.0
                       WHEN 'revived' THEN 0.5
                       ELSE 1.0
                   END) AS kill_quality
            FROM proximity_kill_outcome pko
            JOIN rounds r2 ON r2.id = pko.round_id
            WHERE r2.gaming_session_id IN (SELECT gaming_session_id FROM recent_sessions)
              AND r2.is_valid IS DISTINCT FROM FALSE
              AND pko.killer_guid_canonical IS NOT NULL
            GROUP BY r2.gaming_session_id, pko.killer_guid_canonical
        ),
        prox_trades AS (
            SELECT r2.gaming_session_id, t.trader_guid_canonical AS guid,
                   COUNT(*) AS trades
            FROM proximity_lua_trade_kill t
            JOIN rounds r2 ON r2.id = t.round_id
            WHERE r2.gaming_session_id IN (SELECT gaming_session_id FROM recent_sessions)
              AND r2.is_valid IS DISTINCT FROM FALSE
              AND t.trader_guid_canonical IS NOT NULL
            GROUP BY r2.gaming_session_id, t.trader_guid_canonical
        ),
        prox_clutch AS (
            -- Clutch: kills at low HP or outnumbered (same definition as ET Rating).
            SELECT r2.gaming_session_id, c.attacker_guid_canonical AS guid,
                   COUNT(*) FILTER (
                       WHERE (c.killer_health > 0 AND c.killer_health < 30)
                          OR (c.attacker_team = 'AXIS' AND c.axis_alive < c.allies_alive)
                          OR (c.attacker_team = 'ALLIES' AND c.allies_alive < c.axis_alive)
                   )::REAL / NULLIF(COUNT(*), 0) AS clutch_rate
            FROM proximity_combat_position c
            JOIN rounds r2 ON r2.id = c.round_id
            WHERE r2.gaming_session_id IN (SELECT gaming_session_id FROM recent_sessions)
              AND r2.is_valid IS DISTINCT FROM FALSE
              AND c.event_type = 'kill'
              AND c.attacker_guid_canonical IS NOT NULL
            GROUP BY r2.gaming_session_id, c.attacker_guid_canonical
        )
        SELECT ps.player_guid, ps.player_name, ps.gaming_session_id,
               ps.kills, ps.deaths, ps.dpm, ps.obj, ps.acc,
               pq.kill_quality, pt.trades, pc.clutch_rate
        FROM per_session ps
        LEFT JOIN prox_quality pq
            ON pq.guid = ps.player_guid AND pq.gaming_session_id = ps.gaming_session_id
        LEFT JOIN prox_trades pt
            ON pt.guid = ps.player_guid AND pt.gaming_session_id = ps.gaming_session_id
        LEFT JOIN prox_clutch pc
            ON pc.guid = ps.player_guid AND pc.gaming_session_id = ps.gaming_session_id
        ORDER BY ps.gaming_session_id DESC
        """,
        params,
    )


def _per_player_metrics(rows, latest_sid: int) -> dict:
    """Fold _form_rows output into per-player per-metric form data (one pass, reused
    by both the movers board and a single player's form). Returns
    ``dict[guid] -> {name, latest_sid, sessions: {sid: {key: raw_val}}, metrics}``
    where ``metrics[key] = {latest, latest_raw, baseline, baseline_raw, delta_pct, series}``.
    ``series`` is oldest→newest raw values; ``baseline`` is the own trailing average
    (prior sessions only); delta is latest-vs-baseline (rank-vs-self)."""
    players: dict[str, dict] = {}
    for guid, name, sid, kills, deaths, dpm, obj, acc, kq, trades, clutch in rows:
        sid = int(sid)
        p = players.setdefault(guid, {"name": name, "latest_name": None, "sessions": {}})
        vals = {}
        for key in _FORM_METRIC_KEYS:
            if key == "impact":
                # Impact only exists for sessions with proximity coverage — kill
                # quality is the anchor (≈0.5-1.3); trade + clutch rates add on top.
                if kq is None:
                    continue
                k = float(kills or 0)
                trade_rate = (float(trades or 0) / k) if k > 0 else 0.0
                vals[key] = float(kq) + trade_rate + float(clutch or 0.0)
                continue
            v = _metric_value(key, kills, deaths, dpm, obj, acc)
            if v is not None:
                vals[key] = v
        p["sessions"][sid] = vals
        if sid == latest_sid:
            p["latest_name"] = name

    out: dict[str, dict] = {}
    for guid, p in players.items():
        sids = sorted(p["sessions"].keys())  # oldest→newest
        metrics = {}
        for key, meta in _MOVER_METRICS.items():
            series = [p["sessions"][s][key] for s in sids if key in p["sessions"][s]]
            latest_val = p["sessions"].get(latest_sid, {}).get(key)
            hist = [p["sessions"][s][key] for s in sids if s != latest_sid and key in p["sessions"][s]]
            avg = (sum(hist) / len(hist)) if hist else None
            metrics[key] = {
                "latest": None if latest_val is None else round(latest_val, meta["digits"]),
                "latest_raw": latest_val,
                # avg is None ≠ avg == 0.0: a 0.0 trailing average (e.g. zero
                # objectives) is a real baseline, not a missing one.
                "baseline": None if avg is None else round(avg, meta["digits"]),
                "baseline_raw": avg,
                "delta_pct": (
                    round((latest_val - avg) / avg * 100, 1)
                    if (avg is not None and avg > 0 and latest_val is not None)
                    else None
                ),
                "series": [round(v, 2) for v in series],
            }
        out[guid] = {
            "name": p["latest_name"] or p["name"],
            "latest_sid": latest_sid,
            "sessions": {s: p["sessions"][s] for s in sids},
            "metrics": metrics,
        }
    return out


def _composite_form(player: dict) -> dict | None:
    """Blend a player's per-metric ratios into a single Form Index (100 = their own
    usual). Weights (``_FORM_WEIGHTS``) are renormalized over the metrics that have a
    usable baseline, so a missing metric (e.g. acc NULL) just drops out. Returns None
    when the player has no usable data at all; ``is_new=True`` when they played the
    latest session but have no prior baseline."""
    metrics = player["metrics"]
    baselines = {k: m["baseline_raw"] for k, m in metrics.items() if m.get("baseline_raw") and m["baseline_raw"] > 0}
    has_latest = any(m.get("latest_raw") is not None for m in metrics.values())
    has_prior = any(s != player["latest_sid"] for s in player["sessions"])
    if not baselines:
        if has_latest and not has_prior:
            # Genuinely new: the latest session is their only session.
            return {"latest": None, "baseline": 100, "delta_pct": None, "series": [], "breakdown": [], "is_new": True}
        # Prior sessions exist but every baseline is zero/missing — can't rank
        # vs self, and it is NOT a first night. No composite.
        return None

    lo, hi = _FORM_RATIO_CLAMP

    def _blend(vals: dict) -> float | None:
        num = wsum = 0.0
        for key, base in baselines.items():
            v = vals.get(key)
            if v is None:
                continue
            ratio = max(lo, min(hi, v / base))
            w = _FORM_WEIGHTS[key]
            num += w * ratio
            wsum += w
        return (100.0 * num / wsum) if wsum > 0 else None

    series = []
    for s in sorted(player["sessions"].keys()):  # oldest→newest
        idx = _blend(player["sessions"][s])
        if idx is not None:
            series.append(round(idx, 1))

    latest_idx = _blend(player["sessions"].get(player["latest_sid"], {}))
    if latest_idx is None:
        return {"latest": None, "baseline": 100, "delta_pct": None, "series": series, "breakdown": [], "is_new": False}

    breakdown = [
        {
            "metric": k,
            "label": _MOVER_METRICS[k]["label"],
            "delta_pct": m["delta_pct"],
            "latest": m["latest"],
            "baseline": m["baseline"],
        }
        for k, m in metrics.items()
        if m.get("delta_pct") is not None
    ]
    return {
        "latest": round(latest_idx, 1),
        "baseline": 100,
        "delta_pct": round(latest_idx - 100.0, 1),
        "series": series,
        "breakdown": breakdown,
        "is_new": False,
    }


@router.get("/skill/movers")
async def get_movers(
    top: int = 3,
    metric: str = "overall",
    full: bool = False,
    db: DatabaseAdapter = Depends(get_db),
):
    """Form movers: last session vs each player's OWN recent baseline.

    VISION_2026 anti-goal compliance: this is rank-vs-self, NOT a global ladder —
    the delta is against the player's own trailing baseline, so a bottom-half player
    on a hot night tops the movers list.

    metric: overall (composite Form Index — the default) | dpm | kd | obj | acc |
    kills (per-metric drill-down). full=true returns every mover (Form page); otherwise
    the top N up/down (home card). Each mover carries `series` (per-session values,
    oldest→newest) for a sparkline; overall movers also carry `breakdown` (per-metric
    deltas that make up the composite).
    """
    metric = metric if (metric == "overall" or metric in _MOVER_METRICS) else "overall"
    top = max(1, min(top, 50 if full else 10))
    rows = await _form_rows(db, None, 11)
    if not rows:
        return {
            "status": "ok",
            "session_id": None,
            "metric": metric,
            "movers_up": [],
            "movers_down": [],
            "new_players": [],
        }

    latest_sid = max(int(r[2]) for r in rows)
    latest_date = await db.fetch_val(
        "SELECT MAX(round_date) FROM rounds WHERE gaming_session_id = $1",
        (latest_sid,),
    )
    per_player = _per_player_metrics(rows, latest_sid)

    movers = []
    for guid, p in per_player.items():
        if metric == "overall":
            comp = _composite_form(p)
            if comp is None:
                continue
            entry = {
                "guid": guid,
                "name": p["name"],
                **{k: comp[k] for k in ("latest", "baseline", "delta_pct", "series", "is_new")},
                "breakdown": comp["breakdown"],
            }
        else:
            m = p["metrics"][metric]
            if m["latest_raw"] is None:
                # No value for this metric in the latest session (e.g. acc NULL) — can't
                # rank, and it does NOT mean "new player". Skip rather than mislabel.
                continue
            if m["baseline_raw"] is None and any(s != latest_sid for s in p["sessions"]):
                # Prior sessions exist but none carried this metric — no baseline to
                # rank against, and NOT a first night either. Skip rather than mislabel.
                continue
            entry = {
                "guid": guid,
                "name": p["name"],
                "latest": m["latest"],
                "baseline": m["baseline"],
                "delta_pct": m["delta_pct"],
                "series": m["series"],
                "is_new": m["baseline_raw"] is None,
            }
        if entry["delta_pct"] is None and not entry["is_new"]:
            continue
        movers.append(entry)

    # Attribute known sick-leave / renamed guids (migration 073) so the UI can
    # badge them "🩹 <primary> · on sick leave" rather than presenting a fresh
    # cl_guid as a genuine newcomer (e.g. carniee playing as ownator after an
    # injury). Stats stay separate; this only adds a label to the entry.
    links = await fetch_identity_links(db, [m["guid"] for m in movers])
    for m in movers:
        link = links.get(m["guid"])
        if link and link.get("role") == "alt" and link.get("link_type") == "sick_leave":
            m["sick_leave"] = {
                "primary_guid": link["primary_guid"],
                "primary_name": link["primary_name"],
                "reason": link.get("reason"),
                "active": link.get("active", True),
            }

    ranked = sorted(
        (m for m in movers if m["delta_pct"] is not None),
        key=lambda m: m["delta_pct"],
        reverse=True,
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
        "metric_label": _OVERALL_LABEL if metric == "overall" else _MOVER_METRICS[metric]["label"],
        "baseline": (
            "own trailing ~10-session form index (100 = usual)"
            if metric == "overall"
            else f"own trailing ~10-session {metric}"
        ),
        "baseline_desc": "last session vs this player's own recent-session average (rank-vs-self, not a global ranking)",
        "form_weights": _FORM_WEIGHTS,
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
        # Form comes from player_comprehensive_stats, so also resolve players who
        # have PCS rows but no player_skill_ratings row yet (unrated, < MIN_ROUNDS).
        row = await db.fetch_one(
            "SELECT player_guid FROM player_comprehensive_stats WHERE player_guid = $1 LIMIT 1",
            (identifier,),
        )
        if not row:
            row = await db.fetch_one(
                "SELECT player_guid FROM player_comprehensive_stats "
                "WHERE LOWER(player_name) = LOWER($1) "
                "GROUP BY player_guid ORDER BY COUNT(*) DESC LIMIT 1",
                (identifier,),
            )
        guid = row[0] if row else None
    if not guid:
        return {"status": "error", "detail": f"Player '{identifier}' not found"}
    rows = await _form_rows(db, guid, 11)
    if not rows:
        return {"status": "ok", "player_guid": guid, "session_id": None, "metrics": {}, "composite": None}

    latest_sid = max(int(r[2]) for r in rows)
    latest_date = await db.fetch_val(
        "SELECT MAX(round_date) FROM rounds WHERE gaming_session_id = $1",
        (latest_sid,),
    )
    per_player = _per_player_metrics(rows, latest_sid)
    p = per_player.get(guid)
    if not p:
        return {"status": "ok", "player_guid": guid, "session_id": latest_sid, "metrics": {}, "composite": None}

    metrics_out = {}
    for key, meta in _MOVER_METRICS.items():
        m = p["metrics"][key]
        metrics_out[key] = {
            "label": meta["label"],
            "unit": meta["unit"],
            "latest": m["latest"],
            "baseline": m["baseline"],
            "delta_pct": m["delta_pct"],
            "series": m["series"],
        }
    return {
        "status": "ok",
        "player_guid": guid,
        "player_name": p["name"],
        "session_id": latest_sid,
        "session_date": str(latest_date) if latest_date else None,
        "baseline_desc": "last session vs your own recent-session average (rank-vs-self)",
        "form_weights": _FORM_WEIGHTS,
        "composite": _composite_form(p),
        "metrics": metrics_out,
    }
