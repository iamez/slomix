"""Records sub-router: Overview + activity calendar endpoints."""

from contextvars import ContextVar
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import resolve_display_name

router = APIRouter()


class ActivityCalendar(BaseModel):
    """Rounds played per day over the lookback window.

    ⛔ THREE STATES, NOT TWO, AND THE CLIENT MUST NOT DERIVE THEM FROM LENGTH.
    Until now both branches returned `{days, activity}`, so an empty calendar
    and a failed query were identical on the wire — the page could only guess
    from `Object.keys(activity).length === 0`, which reads a measurement and a
    missing measurement the same way.

      ok           the query ran; `activity` is what was measured, empty or not
      no_data      the query ran and the window genuinely holds no rounds
      unavailable  the query failed; `activity` is empty because we do not know

    `status` is a plain string, not an enum, so a state added later is not
    filtered out by the schema before anyone sees it.
    """

    #: Size of the lookback window, echoed so the caller can label the chart.
    days: int
    #: ISO date -> rounds played. Days with none are absent, not zero.
    activity: dict[str, int]
    #: 'ok' | 'no_data' | 'unavailable'
    status: str
    #: One short sentence when the state is not `ok`; null otherwise.
    note: str | None = None

logger = get_app_logger("api.records.overview")


# Legal rounds = completed / substitution, plus pre-round_status rows, and
# `is_valid` — the column the parser sets FALSE on filler and mixed
# human/bot test rounds, and the gate the rating service already applies.
# Without it the row-level bot predicates below strip the bot rows from a
# test round and keep the human tester's kills (Codex on #837). Measured
# 2026-08-29: it removes 95 of 1,977 rounds and 36 of 110,816 kills — the
# excluded rounds are nearly empty, which is why nobody noticed, and is also
# why counting them was never worth defending.
# Applied to every `rounds` aggregation so the overview matches what the
# rest of the site counts as a valid round.
_ROUND_FILTER = """
    WHERE round_number IN (1, 2)
      AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
      AND is_valid
"""

# The same gate expressed for a query that reads player rows: bots are not
# players, and a round the parser rejected is not a round.
_HUMAN_ROWS = """
          AND player_guid NOT LIKE 'OMNIBOT%'
          AND player_name NOT LIKE '[BOT]%'
"""


#: Which overview queries failed while serving THIS request.
#:
#: ⛔ WHY THIS EXISTS. `_safe_val` returns its default and `_safe_one` returns
#: None, so a database outage arrived at the homepage as `rounds: 0,
#: players: 0, total_kills: 0` — a payload identical to a database that has
#: never recorded a round. Measured by running the endpoint against an adapter
#: that raises on every query: HTTP 200, every figure zero, nothing saying so.
#:
#: A ContextVar rather than a parameter: the twelve call sites live inside
#: three fetch helpers, and threading a list through all of them would touch
#: far more code than the fix is worth. Each request runs in its own asyncio
#: task, so each gets its own copy of this context — a concurrent request
#: cannot see another's failures.
_OVERVIEW_FAILURES: ContextVar[list[str] | None] = ContextVar(
    "overview_failures", default=None,
)


def _note_failure(metric: str) -> None:
    bucket = _OVERVIEW_FAILURES.get()
    if bucket is not None:
        bucket.append(metric or "unknown")


async def _safe_val(
    db: DatabaseAdapter,
    query: str,
    params: tuple | None = None,
    default=0,
    metric: str = "",
):
    try:
        return await db.fetch_val(query, params)
    except Exception as e:
        # Copilot review on PR #123: without a metric label the
        # warning line doesn't say which aggregation failed — debugging
        # this endpoint under 6 back-to-back queries was ambiguous.
        label = metric or "unknown"
        logger.warning("[overview] query failed (%s): %s", label, e)
        _note_failure(label)
        return default


async def _safe_one(
    db: DatabaseAdapter,
    query: str,
    params: tuple | None = None,
    metric: str = "",
):
    try:
        return await db.fetch_one(query, params)
    except Exception as e:
        label = metric or "unknown"
        logger.warning("[overview] query failed (%s): %s", label, e)
        _note_failure(label)
        return None


async def _fetch_rounds_stats(db: DatabaseAdapter, start_date_str: str) -> dict:
    """Count rounds + distinct gaming sessions, overall and in the lookback.

    nosec B608 rationale: every `{_ROUND_FILTER}` interpolation is a
    module-level constant defined at import time; no user input reaches
    these queries. Date filters use $1 parameters.
    """
    rounds_count = await _safe_val(db, f"SELECT COUNT(*) FROM rounds {_ROUND_FILTER}", metric="rounds_count")  # nosec B608 - trusted module constant, not user input
    rounds_first = await _safe_val(
        db,
        f"SELECT MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {_ROUND_FILTER}",  # nosec B608 - trusted module constant, not user input
        default=None,
        metric="rounds_first",
    )
    rounds_latest = await _safe_val(
        db,
        f"SELECT MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {_ROUND_FILTER}",  # nosec B608 - trusted module constant, not user input
        default=None,
        metric="rounds_latest",
    )
    rounds_recent = await _safe_val(
        db,
        f"""
        SELECT COUNT(*)
        FROM rounds
        {_ROUND_FILTER}
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,  # nosec B608 - trusted module constant, not user input
        (start_date_str,),
        metric="rounds_recent",
    )
    sessions_count = await _safe_val(
        db,
        f"""
        SELECT COUNT(DISTINCT gaming_session_id)
        FROM rounds
        {_ROUND_FILTER}
          AND gaming_session_id IS NOT NULL
        """,  # nosec B608 - trusted module constant, not user input
        metric="sessions_count",
    )
    sessions_recent = await _safe_val(
        db,
        f"""
        SELECT COUNT(DISTINCT gaming_session_id)
        FROM rounds
        {_ROUND_FILTER}
          AND gaming_session_id IS NOT NULL
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,  # nosec B608 - trusted module constant, not user input
        (start_date_str,),
        metric="sessions_recent",
    )
    return {
        "rounds_count": rounds_count,
        "rounds_first": rounds_first,
        "rounds_latest": rounds_latest,
        "rounds_recent": rounds_recent,
        "sessions_count": sessions_count,
        "sessions_recent": sessions_recent,
    }


async def _fetch_player_stats(db: DatabaseAdapter, start_date_str: str) -> dict:
    """Distinct player counts and total kills, overall and in the lookback."""
    # Bots are not players. Measured 2026-08-29: 67 distinct guids matched
    # this query and 30 of them were OMNIBOT/[BOT] — so the site's headline
    # "players known" was counting the training bots as most of the
    # community. Every leaderboard in this product already excludes them and
    # says so; this figure now agrees with them.
    players_all_time = await _safe_val(
        db,
        f"""
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
          {_HUMAN_ROWS}
          AND round_id IN (SELECT id FROM rounds {_ROUND_FILTER})
        """,  # nosec B608 - trusted module constants, not user input
        metric="players_all_time",
    )
    players_recent = await _safe_val(
        db,
        f"""
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
          {_HUMAN_ROWS}
          AND round_id IN (SELECT id FROM rounds {_ROUND_FILTER})
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,  # nosec B608 - trusted module constants, not user input
        (start_date_str,),
        metric="players_recent",
    )
    # …and counted over the same rounds this endpoint counts. rounds_count
    # applies _ROUND_FILTER; this sum did not, so one response published
    # 124,629 kills across 1,977 rounds — a total drawn partly from rounds
    # the same response had excluded, by players it did not count. Measured
    # 2026-08-29: 124,629 unfiltered, 116,914 with the round filter alone,
    # 110,816 with both.
    total_kills = await _safe_val(
        db,
        f"""
        SELECT COALESCE(SUM(kills), 0)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          {_HUMAN_ROWS}
          AND round_id IN (SELECT id FROM rounds {_ROUND_FILTER})
        """,  # nosec B608 - trusted module constant, not user input
        metric="total_kills",
    )
    total_kills_recent = await _safe_val(
        db,
        f"""
        SELECT COALESCE(SUM(kills), 0)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          {_HUMAN_ROWS}
          AND round_id IN (SELECT id FROM rounds {_ROUND_FILTER})
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,  # nosec B608 - trusted module constant, not user input
        (start_date_str,),
        metric="total_kills_recent",
    )
    return {
        "players_all_time": players_all_time,
        "players_recent": players_recent,
        "total_kills": total_kills,
        "total_kills_recent": total_kills_recent,
    }


async def _fetch_most_active(db: DatabaseAdapter, start_date_str: str) -> tuple:
    """Top player by round count, overall and in the lookback."""
    # Same gate as every other figure here. A bot never actually topped this
    # (measured 2026-08-29: olz 1,811 rounds either way), but an ungated
    # SELECT beside gated headlines is a contradiction waiting for the first
    # heavy OMNIBOT week to surface it (Codex on #837).
    active_overall = await _safe_one(
        db,
        f"""
        SELECT canonical_guid(player_guid) as player_guid,
               MAX(player_name) as player_name,
               COUNT(DISTINCT round_id) as rounds_played
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
          {_HUMAN_ROWS}
          AND round_id IN (SELECT id FROM rounds {_ROUND_FILTER})
        GROUP BY canonical_guid(player_guid)
        ORDER BY rounds_played DESC
        LIMIT 1
        """,  # nosec B608 - trusted module constants, not user input
        metric="active_overall",
    )
    active_recent = await _safe_one(
        db,
        f"""
        SELECT canonical_guid(player_guid) as player_guid,
               MAX(player_name) as player_name,
               COUNT(DISTINCT round_id) as rounds_played
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
          {_HUMAN_ROWS}
          AND round_id IN (SELECT id FROM rounds {_ROUND_FILTER})
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        GROUP BY canonical_guid(player_guid)
        ORDER BY rounds_played DESC
        LIMIT 1
        """,  # nosec B608 - trusted module constants, not user input
        (start_date_str,),
        metric="active_recent",
    )
    return active_overall, active_recent


async def _resolve_active_payload(db: DatabaseAdapter, row) -> dict | None:
    if not row:
        return None
    return {
        "name": await resolve_display_name(db, row[0], row[1] or "Unknown"),
        "rounds": row[2],
    }


class MostActivePlayer(BaseModel):
    """Null when the window produced no rows at all, never a zero-round player."""

    name: str
    rounds: int


class StatsOverview(BaseModel):
    """The homepage figures, as this endpoint actually returns them.

    ⚠️ MEASURED, NOT DESIGNED. Every field and every nullability here was read
    off a live response and cross-checked against the handler; the hand-written
    client type in `website/frontend/src/app/lib/types.ts` was derived the same
    way from a recorded fixture, and the two now check each other.

    ⛔ `response_model` FILTERS. A field the handler returns and this model
    omits is dropped from the response — silently, with a 200. That is why
    `tests/unit/test_response_models_drop_nothing.py` compares the handler's
    own keys against the serialised model rather than trusting this class to
    be complete.

    ⭐ THE ZEROS NOW SAY WHICH KIND THEY ARE, and this class used to end by
    naming that as an unfixed limit: "a zero here means 'none, or the query
    failed', and no schema can tell them apart… fixing it means giving
    `_safe_val` a per-metric error flag, which is a separate change." This is
    that change. `status`, `note` and `failed_metrics` carry it, the same
    contract `activity-calendar` already answers one endpoint over.

    ⛔ HOW THE GAP WAS FOUND, because reading would not have: every GET
    endpoint was run against a database adapter that raises on every query.
    Eleven answered 200 with a payload indistinguishable from an empty
    database — this one among them, reporting `rounds: 0, players: 0,
    total_kills: 0` as the site's headline figures during an outage.

    ⚠️ AND THE FIRST ATTEMPT AT THIS FIX WAS SWALLOWED BY THIS VERY MODEL.
    The handler returned the three new keys and the response did not carry
    them, because `response_model` drops what the model does not declare —
    silently, with a 200. The paragraph above warns about exactly that, and it
    still took a measurement to notice.
    """

    #: "ok" when every query answered, "partial" when at least one did not.
    status: str
    #: Null when `status` is "ok"; otherwise says the zeros are missing data.
    note: str | None
    #: Names of the metrics whose query raised — empty on the healthy path.
    failed_metrics: list[str]
    rounds: int
    players: int
    sessions: int
    total_kills: int
    #: MIN/MAX over the filtered rounds — null on a database with none.
    rounds_since: str | None
    rounds_latest: str | None
    rounds_14d: int
    players_all_time: int
    players_14d: int
    sessions_14d: int
    total_kills_14d: int
    most_active_overall: MostActivePlayer | None
    most_active_14d: MostActivePlayer | None
    #: The lookback every `*_14d` field above is measured over.
    window_days: int = Field(examples=[14])


@router.get("/stats/overview", response_model=StatsOverview)
async def get_stats_overview(db: DatabaseAdapter = Depends(get_db)):
    """Get homepage overview statistics."""
    lookback_days = 14
    start_date_str = (
        (datetime.now() - timedelta(days=lookback_days))  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        .date()
        .strftime("%Y-%m-%d")
    )

    failures: list[str] = []
    token = _OVERVIEW_FAILURES.set(failures)
    try:
        rounds_stats = await _fetch_rounds_stats(db, start_date_str)
        player_stats = await _fetch_player_stats(db, start_date_str)
        active_overall, active_recent = await _fetch_most_active(db, start_date_str)
    finally:
        _OVERVIEW_FAILURES.reset(token)

    return {
        # ⛔ THE FIGURES BELOW ARE ZERO FOR TWO DIFFERENT REASONS and until
        # now the payload could not tell them apart: a quiet fortnight, and a
        # database that answered nothing. `_safe_val` returns its default on
        # failure, so an outage rendered as "0 rounds, 0 players, 0 kills" on
        # the homepage — the site's most visible numbers, stating a fact
        # nobody had measured. `activity-calendar` in this same file already
        # answers `status`/`note`; this is the same contract, one endpoint
        # over.
        #
        # `ok` means every query answered. `partial` names which ones did not,
        # so a reader knows the zeros beside them are missing rather than
        # true.
        "status": "ok" if not failures else "partial",
        "note": None if not failures
                else f"{len(failures)} of the overview queries failed; the "
                     f"figures they feed are missing, not zero",
        "failed_metrics": failures,
        "rounds": rounds_stats["rounds_count"] or 0,
        "players": player_stats["players_recent"] or 0,
        "sessions": rounds_stats["sessions_count"] or 0,
        "total_kills": player_stats["total_kills"] or 0,
        "rounds_since": rounds_stats["rounds_first"],
        "rounds_latest": rounds_stats["rounds_latest"],
        "rounds_14d": rounds_stats["rounds_recent"] or 0,
        "players_all_time": player_stats["players_all_time"] or 0,
        "players_14d": player_stats["players_recent"] or 0,
        "sessions_14d": rounds_stats["sessions_recent"] or 0,
        "total_kills_14d": player_stats["total_kills_recent"] or 0,
        "most_active_overall": await _resolve_active_payload(db, active_overall),
        "most_active_14d": await _resolve_active_payload(db, active_recent),
        "window_days": lookback_days,
    }


@router.get("/stats/activity-calendar", response_model=ActivityCalendar)
async def get_activity_calendar(
    days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """Return a simple activity calendar (rounds per day) for the last N days."""
    lookback_days = max(1, min(days, 365))
    start_date = (datetime.now() - timedelta(days=lookback_days)).date().strftime(  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        "%Y-%m-%d"
    )

    query = """
        SELECT SUBSTR(CAST(round_date AS TEXT), 1, 10) as day, COUNT(*) as rounds
        FROM rounds
        WHERE round_number IN (1, 2)
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
          -- ⛔ `round_status` ALONE IS NOT THE VALIDITY GATE, and this counted
          -- rounds nobody played. Measured before the fix: 2026-08-12 showed
          -- 9 rounds where the real answer is 0 — every one a bot or invalid
          -- round; 2026-08-11 showed 22 where 14 were real. Six days in the
          -- last 90 were wrong, always upward, so the calendar drew activity
          -- on days the server sat idle.
          AND is_valid IS NOT FALSE
          AND NOT COALESCE(is_bot_round, FALSE)
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        GROUP BY SUBSTR(CAST(round_date AS TEXT), 1, 10)
        ORDER BY day
    """

    try:
        rows = await db.fetch_all(query, (start_date,))
    except Exception as e:
        logger.warning("[activity-calendar] query failed: %s", e)
        return {"days": lookback_days, "activity": {}, "status": "unavailable",
                "note": "the activity query failed; this is not an empty calendar"}

    activity = {str(row[0]): int(row[1]) for row in rows}
    return {
        "days": lookback_days,
        "activity": activity,
        "status": "ok" if activity else "no_data",
        "note": None if activity else "no rounds were played in this window",
    }
