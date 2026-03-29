"""Proximity trade endpoints: trades/summary, trades/player-stats, trades/events."""

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _proximity_stub_meta,
    _table_column_exists,
    logger,
)

router = APIRouter()


@router.get("/proximity/trades/summary")
async def get_proximity_trades_summary(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Trade summary for scoped proximity analytics.
    """
    payload = _proximity_stub_meta(range_days)
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )
    query_params = tuple(params)
    try:
        row = await db.fetch_one(
            "SELECT COUNT(*) AS events, "
            "SUM(opportunity_count) AS opportunities, "
            "SUM(attempt_count) AS attempts, "
            "SUM(success_count) AS successes, "
            "SUM(missed_count) AS missed, "
            "SUM(CASE WHEN is_isolation_death THEN 1 ELSE 0 END) AS isolation_deaths "
            f"FROM proximity_trade_event {where_sql}",
            query_params,
        )
        events = row[0] if row else 0
        support_row = await db.fetch_one(
            "SELECT SUM(support_samples) AS support_samples, "
            "SUM(total_samples) AS total_samples "
            f"FROM proximity_support_summary {where_sql}",
            query_params,
        )
        support_samples = support_row[0] if support_row else None
        total_samples = support_row[1] if support_row else None
        support_pct = None
        if support_samples is not None and total_samples:
            support_pct = round(support_samples * 100 / total_samples, 2)
        payload.update(
            {
                "status": "ok" if (events or 0) > 0 else "prototype",
                "ready": (events or 0) > 0,
                "message": None if (events or 0) > 0 else payload["message"],
                "scope": scope,
                "events": int(events or 0),
                "trade_opportunities": int(row[1] or 0) if row else 0,
                "trade_attempts": int(row[2] or 0) if row else 0,
                "trade_success": int(row[3] or 0) if row else 0,
                "missed_trade_candidates": int(row[4] or 0) if row else 0,
                "support_uptime_pct": support_pct,
                "isolation_deaths": int(row[5] or 0) if row else 0,
            }
        )
    except Exception:
        logger.exception("Proximity trades summary query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "events": 0,
                "trade_opportunities": 0,
                "trade_attempts": 0,
                "trade_success": 0,
                "missed_trade_candidates": 0,
                "support_uptime_pct": None,
                "isolation_deaths": None,
            }
        )
    return payload


@router.get("/proximity/trades/player-stats")
async def get_proximity_trades_player_stats(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Per-player trade kill stats for session detail views.
    Returns aggregated trade success/attempt/avenged counts per player.
    """
    payload = _proximity_stub_meta(range_days)
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )
    query_params = tuple(params)
    try:
        # Victim-side stats: how often were this player's deaths traded by teammates
        victim_query = f"""
            SELECT victim_guid AS guid, victim_name AS name,
                   SUM(opportunity_count) AS trade_opps,
                   SUM(attempt_count) AS trade_attempts,
                   SUM(success_count) AS trade_success,
                   SUM(missed_count) AS trade_missed,
                   SUM(CASE WHEN is_isolation_death THEN 1 ELSE 0 END) AS isolation_deaths
            FROM proximity_trade_event {where_sql}
            GROUP BY victim_guid, victim_name
        """
        victim_rows = await db.fetch_all(victim_query, query_params)

        # Avenger-side stats: how often did this player avenge a teammate's death
        # successes JSON array contains trader info: each element has trader_guid
        avenger_where, avenger_params, _ = _build_proximity_where_clause(
            range_days, session_date, map_name, round_number, round_start_unix,
            alias="e",
        )
        avenger_query = f"""
            SELECT
                s->>'guid' AS guid,
                s->>'name' AS name,
                COUNT(*) AS avenged_count,
                COUNT(DISTINCT e.id) AS avenger_attempt_events,
                COALESCE(SUM(CASE WHEN s->>'damage' IS NOT NULL THEN (s->>'damage')::numeric ELSE 0 END), 0) AS avenger_attempt_damage
            FROM proximity_trade_event e
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(e.successes, '[]'::jsonb)
            ) AS s
            {avenger_where}
            GROUP BY s->>'guid', s->>'name'
        """
        avenger_rows = await db.fetch_all(avenger_query, tuple(avenger_params))

        # Merge victim + avenger stats per player
        players_map = {}
        for row in victim_rows:
            guid = row[0] or ""
            short_guid = guid[:8] if len(guid) > 8 else guid
            key = short_guid or row[1]
            players_map[key] = {
                "guid": short_guid,
                "name": row[1],
                "trade_opps": int(row[2] or 0),
                "trade_attempts": int(row[3] or 0),
                "trade_success": int(row[4] or 0),
                "trade_missed": int(row[5] or 0),
                "isolation_deaths": int(row[6] or 0),
                "avenged_count": 0,
                "avenger_attempt_events": 0,
                "avenger_attempt_damage": 0,
            }
        for row in avenger_rows:
            guid = row[0] or ""
            short_guid = guid[:8] if len(guid) > 8 else guid
            key = short_guid or row[1]
            if key not in players_map:
                players_map[key] = {
                    "guid": short_guid,
                    "name": row[1],
                    "trade_opps": 0,
                    "trade_attempts": 0,
                    "trade_success": 0,
                    "trade_missed": 0,
                    "isolation_deaths": 0,
                    "avenged_count": 0,
                    "avenger_attempt_events": 0,
                    "avenger_attempt_damage": 0,
                }
            players_map[key]["avenged_count"] = int(row[2] or 0)
            players_map[key]["avenger_attempt_events"] = int(row[3] or 0)
            players_map[key]["avenger_attempt_damage"] = float(row[4] or 0)

        payload.update({
            "status": "ok" if players_map else "prototype",
            "ready": bool(players_map),
            "message": None if players_map else payload["message"],
            "scope": scope,
            "players": list(players_map.values()),
        })
    except Exception:
        logger.exception("Proximity trades player-stats query failed")
        payload.update({
            "status": "error",
            "ready": False,
            "message": "Proximity query failed",
            "scope": scope,
            "players": [],
        })
    return payload


@router.get("/proximity/trades/events")
async def get_proximity_trade_events(
    range_days: int = 30,
    limit: int = 50,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Latest trade events (scoped).
    """
    payload = _proximity_stub_meta(range_days)
    safe_limit = max(1, min(int(limit or 50), 250))
    where_sql, params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
        alias="e",
    )
    scoped_params = list(params)
    scoped_params.append(safe_limit)
    limit_placeholder = len(scoped_params)

    try:
        has_round_id_column = await _table_column_exists(
            db, "proximity_trade_event", "round_id"
        )
        if has_round_id_column:
            query = """
                SELECT e.session_date, e.round_number, e.map_name, e.victim_name, e.killer_name,
                       e.opportunity_count, e.attempt_count, e.success_count, e.missed_count,
                       COALESCE(r_exact.id, r_fallback.id) AS round_id,
                       COALESCE(r_exact.round_date, r_fallback.round_date) AS round_date,
                       COALESCE(r_exact.round_time, r_fallback.round_time) AS round_time
                FROM proximity_trade_event e
                LEFT JOIN rounds r_exact
                  ON r_exact.id = e.round_id
                LEFT JOIN LATERAL (
                    SELECT id, round_date, round_time
                    FROM rounds r
                    WHERE r_exact.id IS NULL
                      AND r.map_name = e.map_name
                      AND r.round_number = e.round_number
                      AND e.round_start_unix > 0
                      AND r.round_start_unix > 0
                      AND ABS(r.round_start_unix - e.round_start_unix) <= 120
                    ORDER BY ABS(r.round_start_unix - e.round_start_unix)
                    LIMIT 1
                ) r_fallback ON true
            """
        else:
            query = """
                SELECT e.session_date, e.round_number, e.map_name, e.victim_name, e.killer_name,
                       e.opportunity_count, e.attempt_count, e.success_count, e.missed_count,
                       r.id AS round_id, r.round_date, r.round_time
                FROM proximity_trade_event e
                LEFT JOIN LATERAL (
                    SELECT id, round_date, round_time
                    FROM rounds r
                    WHERE r.map_name = e.map_name
                      AND r.round_number = e.round_number
                      AND e.round_start_unix > 0
                      AND r.round_start_unix > 0
                      AND ABS(r.round_start_unix - e.round_start_unix) <= 120
                    ORDER BY ABS(r.round_start_unix - e.round_start_unix)
                    LIMIT 1
                ) r ON true
            """

        rows = await db.fetch_all(
            query
            + f" {where_sql} "
            + "ORDER BY e.session_date DESC, e.round_number DESC, e.death_time_ms DESC "
            + f"LIMIT ${limit_placeholder}",
            tuple(scoped_params),
        )
        payload.update(
            {
                "status": "ok" if rows else "prototype",
                "ready": bool(rows),
                "message": None if rows else payload["message"],
                "scope": scope,
                "limit": safe_limit,
                "events": [
                    {
                        "date": row[0].isoformat(),
                        "round": row[1],
                        "map": row[2],
                        "victim": row[3],
                        "killer": row[4],
                        "opportunities": int(row[5] or 0),
                        "attempts": int(row[6] or 0),
                        "success": int(row[7] or 0),
                        "missed": int(row[8] or 0),
                        "round_id": row[9],
                        "round_date": row[10],
                        "round_time": row[11],
                        "outcome": (
                            "trade_success"
                            if (row[7] or 0) > 0
                            else "trade_attempt"
                            if (row[6] or 0) > 0
                            else "missed_candidate"
                            if (row[8] or 0) > 0
                            else "trade_event"
                        ),
                    }
                    for row in rows
                ],
            }
        )
    except Exception:
        logger.exception("Proximity trade events query failed")
        payload.update(
            {
                "status": "error",
                "ready": False,
                "message": "Proximity query failed",
                "scope": scope,
                "limit": safe_limit,
                "events": [],
            }
        )
    return payload
