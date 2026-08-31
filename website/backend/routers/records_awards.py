"""Records sub-router: Awards, records, and hall of fame endpoints."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shared.season_manager import SeasonManager
from shared.utils import escape_like_pattern
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    batch_resolve_display_names,
    resolve_alias_guid_map,
    resolve_display_name,
    resolve_name_guid_map,
    resolve_player_guid,
    valid_human_rows_gate,
)

router = APIRouter()
logger = get_app_logger("api.records.awards")


class AwardLeaderRow(BaseModel):
    """One row of the awards leaderboard, as this endpoint returns it.

    ⚠️ MEASURED, NOT DESIGNED. Types are the union over all 20 rows of a live
    response, not the first row: `guid` is null on some of them, and a model
    that read only row 0 would have typed it `str` and dropped the nulls.

    ⛔ `response_model` FILTERS. A field the handler returns and a model omits
    disappears from the payload, silently, with a 200 — which is why
    `tests/unit/test_response_models_drop_nothing.py` compares handler output
    against the serialised model instead of trusting these classes.
    """

    rank: int
    player: str
    #: Null when the display name could not be resolved back to a guid.
    guid: str | None
    award_count: int
    top_award: str
    top_award_count: int


class AwardLeaderboardFilters(BaseModel):
    """Echo of the query that produced the rows above."""

    days: int
    #: Null means "no award_type filter was applied", not "unknown".
    award_type: str | None


class AwardLeaderboard(BaseModel):
    leaderboard: list[AwardLeaderRow]
    filters: AwardLeaderboardFilters


class AwardRow(BaseModel):
    """One awarded performance. `value` is a PRE-FORMATTED string, not a
    number — the handler renders it per award type, so a numeric type here
    would reject perfectly good rows."""

    award: str
    player: str
    guid: str
    value: str
    date: str
    map: str
    round_number: int
    round_id: int


class AwardsFilters(BaseModel):
    #: All three are null when the corresponding filter was not requested.
    player: str | None
    award_type: str | None
    days: int | None


class AwardsPage(BaseModel):
    awards: list[AwardRow]
    total: int
    limit: int
    offset: int
    filters: AwardsFilters


class HallOfFameRow(BaseModel):
    """One entry in a hall-of-fame category.

    `value` is `float` because one category (`most_dpm`) is fractional while the
    rest are counts. Typing it `int` would silently truncate DPM — a schema is
    as capable of corrupting a number as of dropping a field.
    """

    rank: int
    player_guid: str
    player_name: str
    value: float
    unit: str


class HallOfFame(BaseModel):
    """⚠️ `categories` is left as a plain mapping on purpose.

    Twelve category names are present today (`most_kills`, `most_dpm`, …) and
    the handler builds them from a list it can extend. Naming them here would
    make this model the gate on which categories may exist: adding one to the
    handler without editing this class would drop it from the response with a
    200. The mapping keeps the row shape typed while leaving the key set open.
    """

    categories: dict[str, list[HallOfFameRow]]
    period: str
    #: Null when no delta window was requested.
    delta_window_days: int | None
    generated_at: str



class RecordEntry(BaseModel):
    """One record holder in one category, as this endpoint returns it.

    ⚠️ MEASURED, NOT DESIGNED. `value` is `int` for the counting categories and
    `float` for `accuracy`, `xp` and `match_xp` — the union keeps each on the
    wire exactly as the query produced it. Widening it to a bare `float` would
    rewrite `"value": 5994` as `"value": 5994.0` for every counting category:
    a silent wire change on a page nobody would think to re-check.

    `map` and `date` are `str` and NOT nullable, even though
    `information_schema` reports all three columns of the `player_match_stats`
    VIEW as `is_nullable = YES`. That report is about aggregates, not about
    data: the view produces them as `max(map_name)` / `min(round_date)` over
    columns that are `NOT NULL` in `player_comprehensive_stats`, and an
    aggregate over a non-empty group cannot be null. Measured: 0 nulls in
    6,863 view rows.

    ⛔ This is the MIRROR of the `LEFT JOIN` trap in `SessionSummary`. There a
    `NOT NULL` column arrives null because there was no row to join; here a
    "nullable" column can never be null because the aggregate has one. The
    schema is wrong in BOTH cases, in opposite directions — which is why the
    rule is `schema -> handler -> what the query does to it`, and never the
    schema alone.
    """

    player: str
    #: ⛔ NON-NULL BY THE QUERY, NOT BY THE COLUMN. All thirteen statistic
    #: columns are nullable in the schema (0 NULLs today), and PostgreSQL puts
    #: NULLs FIRST on a `DESC` sort — so an unmeasured row could have been
    #: SELECTED AS THE RECORD and shown as the best, and this model would then
    #: have answered 500 on it. Both are closed by `AND {col} IS NOT NULL` in
    #: every category query: a record is a MEASURED value, which is what the
    #: word means (Codex on #830).
    value: int | float
    map: str
    date: str


class StatsRecords(BaseModel):
    """All-time records, keyed by category. EVERY FIELD IS OPTIONAL ON PURPOSE.

    ⛔ DO NOT make any category required. The handler omits a category's key
    entirely when its query succeeded with no rows (`if rows:` below), so a
    required field is a 500 on exactly the view that is hardest to notice: a
    filtered one. Measured, not theorised — `?map_name=goldrush` (a real ET map
    this server has never recorded) answers `{}` with HTTP 200, and every one
    of the 19 categories is absent. All 18 maps that DO have data return all 19.

    ⚠️ ABSENCE AND `[]` MEAN DIFFERENT THINGS HERE, and the meanings are the
    reverse of the intuitive reading:
      - key ABSENT  -> the query ran and found nothing (no records for this map)
      - key PRESENT as `[]` -> the query RAISED and was swallowed per-category
    `response_model_exclude_none=True` on the route preserves both states
    exactly: an absent category stays absent, a failed one stays `[]`. A reader
    cannot be expected to guess this, which is why it is written down here.
    """

    kills: list[RecordEntry] | None = None
    damage: list[RecordEntry] | None = None
    revives: list[RecordEntry] | None = None
    gibs: list[RecordEntry] | None = None
    headshots: list[RecordEntry] | None = None
    xp: list[RecordEntry] | None = None
    accuracy: list[RecordEntry] | None = None
    revived: list[RecordEntry] | None = None
    useful_kills: list[RecordEntry] | None = None
    obj_stolen: list[RecordEntry] | None = None
    obj_returned: list[RecordEntry] | None = None
    dyna_planted: list[RecordEntry] | None = None
    dyna_defused: list[RecordEntry] | None = None
    match_damage: list[RecordEntry] | None = None
    match_kills: list[RecordEntry] | None = None
    match_headshots: list[RecordEntry] | None = None
    match_xp: list[RecordEntry] | None = None
    match_revives: list[RecordEntry] | None = None
    match_gibs: list[RecordEntry] | None = None


@router.get(
    "/stats/records",
    response_model=StatsRecords,
    response_model_exclude_none=True,
)
async def get_records(
    map_name: str = None, limit: int = 1, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get all-time records (Hall of Fame).
    If map_name is provided, returns records for that map only.
    """
    # Categories to fetch
    categories = {
        "kills": {"col": "kills", "label": "Most Kills"},
        "damage": {"col": "damage_given", "label": "Most Damage"},
        "revives": {"col": "revives_given", "label": "Most Revives"},
        "gibs": {"col": "gibs", "label": "Most Gibs"},
        "headshots": {"col": "headshots", "label": "Most Headshots"},
        "xp": {"col": "xp", "label": "Most XP"},
        "accuracy": {
            "col": "accuracy",
            "label": "Best Accuracy",
            # The sample-size gate (>50 bullets) is only meaningful when the
            # bullet count itself can be trusted. It cannot be for the 2025
            # supastats backfill: 7,311 of its 9,698 rows carry a bullets_fired
            # above any physical fire rate (the old record row: 5,523 bullets
            # in 269 s = 20.5/s where an MP40 tops out at ~11.6/s), while the
            # 2026 live capture has zero such rows. The physics bound keeps the
            # record on rows whose sample size is PROVABLE — 15/s = max rate
            # plus margin — rather than letting corrupted counts qualify.
            "filter": "bullets_fired > 50"
                      " AND bullets_fired <= time_played_seconds * 15",
        },
        "revived": {"col": "times_revived", "label": "Most Times Revived"},
        "useful_kills": {"col": "most_useful_kills", "label": "Most Useful Kills"},
        "obj_stolen": {"col": "objectives_stolen", "label": "Objectives Stolen"},
        "obj_returned": {"col": "objectives_returned", "label": "Objectives Returned"},
        "dyna_planted": {"col": "dynamites_planted", "label": "Dynamites Planted"},
        "dyna_defused": {"col": "dynamites_defused", "label": "Dynamites Defused"},
    }

    # Records are the all-time Hall of Fame — bot/test rounds must never
    # enter it. is_valid on the round is the primary gate (bot rounds are
    # flagged is_valid = FALSE by the importer); the [BOT]/OMNIBOT identity
    # filter is defence in depth for any historical round that predates the
    # validity flag. (Owner saw [BOT]vid holding the kills record.)
    # round_status = 'orphan_r2' marks R2 rows whose R1 was never available:
    # they hold raw CUMULATIVE (R1+R2) values, so any per-round record built
    # on them is roughly doubled (the 2026-01-09 erdenberg "damage record"
    # was exactly this).
    base_where = (
        "WHERE round_number IN (1, 2) AND time_played_seconds > 0 "
        "AND player_name NOT LIKE '[BOT]%' "
        "AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') "
        "AND NOT EXISTS (SELECT 1 FROM rounds r "
        "                WHERE r.id = player_comprehensive_stats.round_id "
        "                  AND (r.is_valid IS FALSE "
        "                       OR r.round_status = 'orphan_r2'))"
    )
    if map_name:
        base_where += " AND map_name = $1"

    # Build per-category (query, params) plan, then fire all queries in
    # parallel via asyncio.gather. Previously this loop ran 13 queries
    # sequentially (~150 ms each → ~2 s page latency). With gather the
    # total time collapses to roughly a single query's RTT.
    #
    # A bounded semaphore caps simultaneous connection acquisitions per
    # request so a couple of concurrent /stats/records callers can't
    # exhaust the shared asyncpg pool (~20 conns) and queue every other
    # endpoint behind us. 5 is a balance: ≥80% of the latency win, ≤25%
    # of peak pool pressure.
    plans: list[tuple[str, str, tuple]] = []
    for key, config in categories.items():
        col = config["col"]
        extra_filter = f" AND {config['filter']}" if "filter" in config else ""
        limit_placeholder = "$2" if map_name else "$1"
        query = f"""
            SELECT
                player_name,
                {col} as value,
                map_name,
                round_date
            FROM player_comprehensive_stats
            {base_where} {extra_filter} AND {col} IS NOT NULL
            ORDER BY {col} DESC
            LIMIT {limit_placeholder}
        """
        q_params = (map_name, limit) if map_name else (limit,)
        plans.append((key, query, q_params))

    # Match-level records: both rounds of one map, summed per player. The sum
    # lives in the player_match_stats VIEW (migration 078), not in six copies
    # of the same GROUP BY here — and not in the round_number = 0 rows, which
    # are a stored copy of the R2 capture that nothing reads (docs/CLAUDE.md).
    # The view carries the structural gates (valid round, played half); the
    # human/bot policy stays here, where it belongs. Only summable counters get
    # a match category (ratios like accuracy do not survive summation). A match
    # missing its R2 simply sums lower — it can never fake-inflate a record.
    match_categories = (
        ("match_damage", "damage_given"),
        ("match_kills", "kills"),
        ("match_headshots", "headshots"),
        ("match_xp", "xp"),
        ("match_revives", "revives_given"),
        ("match_gibs", "gibs"),
    )
    # Ties are real here (two players with 72 headshots in a match, three with
    # 298 xp) and a bare `ORDER BY value DESC` leaves which one is shown to
    # whatever order the plan produces. That was stable in practice but never
    # specified — and it did change when this query moved to the view. The
    # tiebreak makes it explainable instead of incidental: most recent
    # achievement first, then name. Values are unaffected, only which of several
    # equal rows is displayed.
    match_where = (
        "WHERE player_name NOT LIKE '[BOT]%' "
        "AND player_guid IS NOT NULL "
        "AND player_guid NOT LIKE 'OMNIBOT%'"
    )
    if map_name:
        match_where += " AND map_name = $1"
    match_limit_placeholder = "$2" if map_name else "$1"
    for key, col in match_categories:
        query = f"""
            SELECT
                player_name,
                {col} as value,
                map_name,
                round_date
            FROM player_match_stats
            {match_where} AND {col} IS NOT NULL
            ORDER BY value DESC, round_date DESC, player_name ASC
            LIMIT {match_limit_placeholder}
        """
        q_params = (map_name, limit) if map_name else (limit,)
        plans.append((key, query, q_params))

    sem = asyncio.Semaphore(5)

    async def _run(q: str, p: tuple):
        async with sem:
            return await db.fetch_all(q, p)

    rows_per_category = await asyncio.gather(
        *(_run(q, p) for _, q, p in plans),
        return_exceptions=True,
    )

    results: dict[str, list[dict]] = {}
    for (key, _, _), outcome in zip(plans, rows_per_category):
        # Re-raise CancelledError so request cancellation / shutdown
        # signals propagate; only treat ordinary Exceptions as a
        # per-category failure to fall back to [].
        if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, Exception):
            # Match prior behavior: exception falls back to []
            logger.error(f"Error fetching record for {key}: {outcome}")
            results[key] = []
            continue
        rows = outcome or []
        if rows:
            # Match prior behavior: empty success result omits the key
            results[key] = [
                {"player": row[0], "value": row[1], "map": row[2], "date": row[3]}
                for row in rows
            ]

    return results


@router.get("/awards/leaderboard", response_model=AwardLeaderboard)
async def get_awards_leaderboard(
    limit: int = 20,
    days: int = 0,
    award_type: str = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get leaderboard of players by total awards won.

    Args:
        limit: Number of players to return
        days: Filter to last N days (0 = all time)
        award_type: Filter to specific award type
    """
    params = []
    where_clauses = [
        # Award records exclude bots (identity-level; round_awards has no
        # validity flag). Owner: Record Book showed bot award holders.
        "ra.player_name NOT LIKE '[BOT]%'",
        "(ra.player_guid IS NULL OR ra.player_guid NOT LIKE 'OMNIBOT%')",
    ]
    param_idx = 1

    if days > 0:
        where_clauses.append(
            f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')"
        )
        params.append(days)
        param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get player award counts with their most won award (GUID-aware)
    query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        ),
        player_counts AS (
            SELECT
                COALESCE(ra.player_guid, am.guid, nm.player_guid, ra.player_name) as player_key,
                COALESCE(ra.player_guid, am.guid, nm.player_guid) as resolved_guid,
                MAX(ra.player_name) as player_name,
                ra.award_name,
                COUNT(*) as award_specific_count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            {where_sql}
            GROUP BY player_key, resolved_guid, ra.award_name
        ),
        player_totals AS (
            SELECT
                player_key,
                MAX(resolved_guid) as player_guid,
                MAX(player_name) as player_name,
                SUM(award_specific_count) as total_awards
            FROM player_counts
            GROUP BY player_key
        ),
        top_awards AS (
            SELECT DISTINCT ON (player_key)
                player_key,
                award_name as top_award,
                award_specific_count as top_award_count
            FROM player_counts
            ORDER BY player_key, award_specific_count DESC
        )
        SELECT
            pt.player_guid,
            pt.player_name,
            pt.total_awards,
            ta.top_award,
            ta.top_award_count
        FROM player_totals pt
        JOIN top_awards ta ON pt.player_key = ta.player_key
        ORDER BY pt.total_awards DESC
        LIMIT ${param_idx}
    """
    params.append(limit)

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception:
        logger.debug("awards primary query failed, using fallback", exc_info=True)
        fallback_query = f"""
            WITH player_counts AS (
                SELECT
                    player_name,
                    COUNT(*) as award_count,
                    award_name,
                    COUNT(*) as award_specific_count
                FROM round_awards ra
                {where_sql}
                GROUP BY player_name, award_name
            ),
            player_totals AS (
                SELECT
                    player_name,
                    SUM(award_specific_count) as total_awards
                FROM player_counts
                GROUP BY player_name
            ),
            top_awards AS (
                SELECT DISTINCT ON (player_name)
                    player_name,
                    award_name as top_award,
                    award_specific_count as top_award_count
                FROM player_counts
                ORDER BY player_name, award_specific_count DESC
            )
            SELECT
                pt.player_name,
                pt.total_awards,
                ta.top_award,
                ta.top_award_count
            FROM player_totals pt
            JOIN top_awards ta ON pt.player_name = ta.player_name
            ORDER BY pt.total_awards DESC
            LIMIT ${param_idx}
        """
        rows = await db.fetch_all(fallback_query, tuple(params))

    # Build GUID enrichment map for any name-only rows
    name_pool = []
    for row in rows:
        if len(row) == 4:
            name_pool.append(row[0])
        else:
            name_pool.append(row[1])
    alias_map = await resolve_alias_guid_map(db, name_pool)
    name_map = await resolve_name_guid_map(db, name_pool)

    leaderboard = []
    for idx, row in enumerate(rows):
        if len(row) == 4:
            player_guid = None
            player_name, total_awards, top_award, top_award_count = row
        else:
            player_guid, player_name, total_awards, top_award, top_award_count = row
        if not player_guid and player_name:
            key = player_name.lower()
            player_guid = alias_map.get(key) or name_map.get(key)
        display_name = (
            await resolve_display_name(db, player_guid, player_name or "Unknown")
            if player_guid
            else (player_name or "Unknown")
        )
        leaderboard.append(
            {
                "rank": idx + 1,
                "player": display_name,
                "guid": player_guid,
                "award_count": total_awards,
                "top_award": top_award,
                "top_award_count": top_award_count,
            }
        )

    return {
        "leaderboard": leaderboard,
        "filters": {"days": days, "award_type": award_type},
    }


@router.get("/players/{identifier}/awards")
async def get_player_awards(
    identifier: str, limit: int = 10, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get awards won by a specific player.

    Args:
        identifier: Player name or GUID
        limit: Number of recent awards to return
    """
    resolved_guid = await resolve_player_guid(db, identifier)
    display_name = (
        await resolve_display_name(db, resolved_guid, identifier)
        if resolved_guid
        else identifier
    )

    if resolved_guid:
        count_query = """
            WITH alias_map AS (
                SELECT DISTINCT ON (alias) alias, guid
                FROM player_aliases
                ORDER BY alias, last_seen DESC
            ),
            name_map AS (
                SELECT DISTINCT ON (LOWER(player_name))
                    LOWER(player_name) as name_key,
                    player_guid
                FROM player_comprehensive_stats
                ORDER BY LOWER(player_name), round_date DESC
            )
            SELECT ra.award_name, COUNT(*) as count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            WHERE COALESCE(ra.player_guid, am.guid, nm.player_guid) = $1
            GROUP BY ra.award_name
            ORDER BY count DESC
        """
        recent_query = """
            WITH alias_map AS (
                SELECT DISTINCT ON (alias) alias, guid
                FROM player_aliases
                ORDER BY alias, last_seen DESC
            ),
            name_map AS (
                SELECT DISTINCT ON (LOWER(player_name))
                    LOWER(player_name) as name_key,
                    player_guid
                FROM player_comprehensive_stats
                ORDER BY LOWER(player_name), round_date DESC
            )
            SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            WHERE COALESCE(ra.player_guid, am.guid, nm.player_guid) = $1
            ORDER BY ra.created_at DESC
            LIMIT $2
        """
        try:
            count_rows = await db.fetch_all(count_query, (resolved_guid,))
            recent_rows = await db.fetch_all(recent_query, (resolved_guid, limit))
        except Exception:
            logger.debug("awards count/recent query failed, using fallback", exc_info=True)
            fallback_count = """
                SELECT award_name, COUNT(*) as count
                FROM round_awards
                WHERE player_guid = $1
                GROUP BY award_name
                ORDER BY count DESC
            """
            fallback_recent = """
                SELECT award_name, award_value, round_date, map_name, round_number
                FROM round_awards
                WHERE player_guid = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            count_rows = await db.fetch_all(fallback_count, (resolved_guid,))
            recent_rows = await db.fetch_all(fallback_recent, (resolved_guid, limit))
    else:
        # Fallback: name-based lookup
        count_query = """
            SELECT award_name, COUNT(*) as count
            FROM round_awards
            WHERE player_name ILIKE $1
            GROUP BY award_name
            ORDER BY count DESC
        """
        recent_query = """
            SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
            FROM round_awards ra
            WHERE ra.player_name ILIKE $1
            ORDER BY ra.created_at DESC
            LIMIT $2
        """
        count_rows = await db.fetch_all(count_query, (identifier,))
        recent_rows = await db.fetch_all(recent_query, (identifier, limit))

    total = sum(row[1] for row in count_rows)

    return {
        "player": display_name,
        "guid": resolved_guid,
        "total_awards": total,
        "by_type": {row[0]: row[1] for row in count_rows},
        "recent": [
            {
                "award": row[0],
                "value": row[1],
                "date": row[2],
                "map": row[3],
                "round": row[4],
            }
            for row in recent_rows
        ],
    }


@router.get("/awards", response_model=AwardsPage)
async def list_awards(
    limit: int = 50,
    offset: int = 0,
    player: str = None,
    award_type: str = None,
    days: int = 0,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    List all awards with pagination and filters.

    Args:
        limit: Number of awards per page
        offset: Pagination offset
        player: Filter by player name
        award_type: Filter by award type
        days: Filter to last N days
    """
    params = []
    where_clauses = [
        # Award records exclude bots (identity-level; round_awards has no
        # validity flag). Owner: Record Book showed bot award holders.
        "ra.player_name NOT LIKE '[BOT]%'",
        "(ra.player_guid IS NULL OR ra.player_guid NOT LIKE 'OMNIBOT%')",
    ]
    param_idx = 1

    resolved_player_guid = None
    if player:
        resolved_player_guid = await resolve_player_guid(db, player)
        if resolved_player_guid:
            where_clauses.append(
                f"COALESCE(ra.player_guid, am.guid) = ${param_idx}"
            )
            params.append(resolved_player_guid)
            param_idx += 1
        else:
            where_clauses.append(f"ra.player_name ILIKE ${param_idx}")
            params.append(f"%{escape_like_pattern(player)}%")
            param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    if days > 0:
        where_clauses.append(f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')")
        params.append(days)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get total count + awards (GUID-aware)
    count_query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        )
        SELECT COUNT(*)
        FROM round_awards ra
        LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
        LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
        {where_sql}
    """
    query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        )
        SELECT ra.award_name,
               ra.player_name,
               COALESCE(ra.player_guid, am.guid, nm.player_guid) as player_guid,
               ra.award_value,
               ra.round_date,
               ra.map_name,
               ra.round_number,
               ra.round_id
        FROM round_awards ra
        LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
        LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
        {where_sql}
        ORDER BY ra.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    try:
        count_row = await db.fetch_one(count_query, tuple(params[:-2]))
        total = count_row[0] if count_row else 0
        rows = await db.fetch_all(query, tuple(params))
    except Exception:
        # Fallback if alias table missing
        logger.debug("awards alias-join query failed, using fallback", exc_info=True)
        fallback_where_sql = where_sql.replace("COALESCE(ra.player_guid, am.guid, nm.player_guid)", "ra.player_guid")
        fallback_where_sql = fallback_where_sql.replace("COALESCE(ra.player_guid, am.guid)", "ra.player_guid")
        fallback_count = f"SELECT COUNT(*) FROM round_awards ra {fallback_where_sql}"
        count_row = await db.fetch_one(fallback_count, tuple(params[:-2]))
        total = count_row[0] if count_row else 0
        fallback_query = f"""
            SELECT ra.award_name, ra.player_name, ra.player_guid, ra.award_value,
                   ra.round_date, ra.map_name, ra.round_number, ra.round_id
            FROM round_awards ra
            {fallback_where_sql}
            ORDER BY ra.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        rows = await db.fetch_all(fallback_query, tuple(params))

    name_map = await batch_resolve_display_names(
        db,
        [(row[2], row[1] or "Unknown") for row in rows if row[2]],
    )
    return {
        "awards": [
            {
                "award": row[0],
                "player": (
                    name_map.get(row[2], row[1] or "Unknown")
                    if row[2]
                    else (row[1] or "Unknown")
                ),
                "guid": row[2],
                "value": row[3],
                "date": row[4],
                "map": row[5],
                "round_number": row[6],
                "round_id": row[7],
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {"player": player, "award_type": award_type, "days": days},
    }


@router.get("/hall-of-fame", response_model=HallOfFame)
async def get_hall_of_fame(
    period: str = "all_time",
    start_date: str | None = None,
    end_date: str | None = None,
    season_id: int | None = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Hall of Fame: top players across multiple stat categories."""
    limit = max(1, min(limit, 100))

    # Build date filter
    date_filter = ""
    params: list = []
    param_idx = 1

    if period == "season" or season_id is not None:
        sm = SeasonManager()
        season_start, season_end = sm.get_season_dates(season_id)
        date_filter = f"AND pcs.round_date >= ${param_idx} AND pcs.round_date <= ${param_idx + 1}"
        params.extend([season_start.strftime("%Y-%m-%d"), season_end.strftime("%Y-%m-%d")])
        param_idx += 2
    elif period == "custom" and start_date and end_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")  # noqa: DTZ007 date-only parsing, no time component used
            datetime.strptime(end_date, "%Y-%m-%d")  # noqa: DTZ007 date-only parsing, no time component used
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        date_filter = f"AND pcs.round_date >= ${param_idx} AND pcs.round_date <= ${param_idx + 1}"
        params.extend([start_date, end_date])
        param_idx += 2
    elif period == "7d":
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "14d":
        cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "30d":
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "90d":
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    # else: all_time - no date filter

    try:
        categories = await _hof_compute_categories(db, date_filter, params, param_idx, limit)

        # Rank deltas vs the PREVIOUS equal-length window (rolling periods
        # only — no snapshots needed). positive = climbed, negative = fell.
        delta_days = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}.get(period)
        if delta_days:
            prev_start = (datetime.now() - timedelta(days=2 * delta_days)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
            prev_end = (datetime.now() - timedelta(days=delta_days)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
            prev_filter = "AND pcs.round_date >= $1 AND pcs.round_date < $2"
            prev_categories = await _hof_compute_categories(
                db, prev_filter, [prev_start, prev_end], 3, 100,
            )
            for cat_name, entries in categories.items():
                prev_rank = {
                    e["player_guid"]: e["rank"]
                    for e in prev_categories.get(cat_name, [])
                }
                for e in entries:
                    prev = prev_rank.get(e["player_guid"])
                    if prev is None:
                        e["rank_delta"] = None
                        e["is_new"] = True
                    else:
                        e["rank_delta"] = prev - e["rank"]
                        e["is_new"] = False

        return {
            "categories": categories,
            "period": period,
            "delta_window_days": delta_days,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Hall of Fame query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate Hall of Fame data")


async def _hof_compute_categories(
    db: DatabaseAdapter, date_filter: str, base_params: list, param_idx: int, limit: int,
) -> dict:
    """All Hall of Fame category leaderboards for one date window."""
    params = list(base_params)
    limit_param = f"${param_idx}"
    params.append(limit)
    valid_gate = valid_human_rows_gate("pcs")

    categories = {}

    # --- Simple aggregation categories ---
    simple_cats = {
        "most_active": ("COUNT(*)", "rounds"),
        "most_damage": ("SUM(pcs.damage_given)", "damage"),
        "most_kills": ("SUM(pcs.kills)", "kills"),
        "most_revives": ("SUM(pcs.revives_given)", "revives"),
        "most_xp": ("SUM(pcs.xp)", "xp"),
        "most_assists": ("SUM(pcs.kill_assists)", "assists"),
        "most_deaths": ("SUM(pcs.deaths)", "deaths"),
        "most_selfkills": ("SUM(pcs.self_kills)", "selfkills"),
        "most_full_selfkills": ("SUM(pcs.full_selfkills)", "full_selfkills"),
    }

    for cat_name, (agg_expr, unit) in simple_cats.items():
        # nosec B608 - agg_expr and date_filter are static/controlled strings
        query = f"""
            SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                   {agg_expr} as value
            FROM player_comprehensive_stats pcs
            WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0{valid_gate} {date_filter}
            GROUP BY pcs.player_guid
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(query, tuple(params))
        name_map = await batch_resolve_display_names(
            db, [(row[0], row[1] or "Unknown") for row in rows]
        )
        entries = []
        for rank, row in enumerate(rows, 1):
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name_map.get(row[0], "Unknown"),
                "value": int(row[2]) if row[2] is not None else 0,
                "unit": unit,
            })
        categories[cat_name] = entries

    # --- most_wins: join with rounds to check winner_team ---
    wins_query = f"""
        SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
               COUNT(*) as value
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON pcs.round_id = r.id
        WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0{valid_gate}
          AND r.winner_team != 0
          AND pcs.team = r.winner_team
          {date_filter}
        GROUP BY pcs.player_guid
        ORDER BY value DESC
        LIMIT {limit_param}
    """
    rows = await db.fetch_all(wins_query, tuple(params))
    name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in rows]
    )
    entries = []
    for rank, row in enumerate(rows, 1):
        entries.append({
            "rank": rank,
            "player_guid": row[0],
            "player_name": name_map.get(row[0], "Unknown"),
            "value": int(row[2]) if row[2] is not None else 0,
            "unit": "wins",
        })
    categories["most_wins"] = entries

    # --- most_dpm: damage per minute with min 10 rounds ---
    dpm_min_rounds_param = f"${param_idx + 1}"
    dpm_params = list(params) + [10]
    dpm_query = f"""
        SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
               ROUND((SUM(pcs.damage_given)::numeric / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0)), 2) as value,
               COUNT(*) as rounds_played
        FROM player_comprehensive_stats pcs
        WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0{valid_gate} {date_filter}
        GROUP BY pcs.player_guid
        HAVING COUNT(*) >= {dpm_min_rounds_param}
        ORDER BY value DESC
        LIMIT {limit_param}
    """
    rows = await db.fetch_all(dpm_query, tuple(dpm_params))
    name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in rows]
    )
    entries = []
    for rank, row in enumerate(rows, 1):
        entries.append({
            "rank": rank,
            "player_guid": row[0],
            "player_name": name_map.get(row[0], "Unknown"),
            "value": float(row[2]) if row[2] is not None else 0.0,
            "unit": "dpm",
        })
    categories["most_dpm"] = entries

    # --- most_consecutive_games: consecutive gaming sessions ---
    # gaming_session_id lives on rounds, not player_comprehensive_stats
    consec_query = f"""
        WITH player_sessions AS (
            SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                   r.gaming_session_id
            FROM player_comprehensive_stats pcs
            JOIN rounds r ON pcs.round_id = r.id
            WHERE pcs.time_played_seconds > 0{valid_gate}
              AND r.gaming_session_id IS NOT NULL
              {date_filter}
            GROUP BY pcs.player_guid, r.gaming_session_id
        ),
        all_sessions AS (
            SELECT DISTINCT r2.gaming_session_id
            FROM rounds r2
            JOIN player_comprehensive_stats pcs2 ON pcs2.round_id = r2.id
            WHERE r2.gaming_session_id IS NOT NULL
              AND pcs2.time_played_seconds > 0
              {date_filter.replace('pcs.', 'pcs2.')}
            ORDER BY r2.gaming_session_id
        ),
        numbered AS (
            SELECT ps.player_guid, ps.player_name, ps.gaming_session_id,
                   ROW_NUMBER() OVER (ORDER BY a.gaming_session_id) as global_rank,
                   ROW_NUMBER() OVER (PARTITION BY ps.player_guid ORDER BY ps.gaming_session_id) as player_rank
            FROM player_sessions ps
            JOIN all_sessions a ON ps.gaming_session_id = a.gaming_session_id
        ),
        streaks AS (
            SELECT player_guid, MAX(player_name) as player_name,
                   COUNT(*) as streak_len
            FROM numbered
            GROUP BY player_guid, (global_rank - player_rank)
        )
        SELECT player_guid, MAX(player_name) as player_name,
               MAX(streak_len) as value
        FROM streaks
        GROUP BY player_guid
        ORDER BY value DESC
        LIMIT {limit_param}
    """
    rows = await db.fetch_all(consec_query, tuple(params))
    name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in rows]
    )
    entries = []
    for rank, row in enumerate(rows, 1):
        entries.append({
            "rank": rank,
            "player_guid": row[0],
            "player_name": name_map.get(row[0], "Unknown"),
            "value": int(row[2]) if row[2] is not None else 0,
            "unit": "sessions",
        })
    categories["most_consecutive_games"] = entries

    return categories
