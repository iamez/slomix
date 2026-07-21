"""GamingSessionScope — the canonical unit Smart Stats must use (Codex §5).

Root cause this closes: Smart Stats (Story) endpoints scope by calendar
`session_date`, while the rest of Slomix identifies a "gaming session" as
`rounds.gaming_session_id`. A session that crosses midnight splits into two
independent date fragments; the UI silently picks one and shows a fraction
of the real session (production example: session 137 — 23 rounds across two
dates — appeared as 4 rounds when scoped by the later date alone).

This module resolves EITHER a `gaming_session_id` OR a `session_date` into
one `GamingSessionScope` — never both silently merged, never a `LIMIT 1`
guess when a date holds more than one session (that ambiguity is a 409, per
owner decision). Every metric consumer should filter by `dates` +
`round_keys`, NOT by `round_id` — round_id linkage on the proximity tables
is independently known to be ~9% wrong on repeated maps (Codex §18); dates +
(round_start_unix, map_name, round_number) is the one identity every
proximity table can be trusted to carry correctly (it's written once, by the
parser, from the file itself — never re-linked).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from website.backend.local_database_adapter import DatabaseAdapter

SCOPE_VERSION = "gaming-session-v1"

# The one round-validity gate every canonical session/scope query in this
# module uses — copied verbatim from sessions_router.py's GET /sessions
# query (the existing, most-authoritative "what counts as a real session"
# definition) and matching the SQL the remediation plan's §5 specifies.
# `is_valid IS DISTINCT FROM FALSE` admits NULL (legacy rows never backfilled)
# as valid; only an explicit FALSE excludes a round.
_ROUND_GATE_SQL = (
    "round_number IN (1, 2) "
    "AND is_valid IS DISTINCT FROM FALSE "
    "AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)"
)


@dataclass(frozen=True)
class GamingSessionScope:
    """One resolved gaming session — the value object every Smart Stats
    endpoint should accept instead of a naked `session_date` string."""

    gaming_session_id: int
    dates: tuple[str, ...]  # every distinct calendar round_date touched, sorted
    round_keys: tuple[tuple[int, str, int], ...]  # (round_start_unix, map_name, round_number), sorted
    accepted_round_count: int
    distinct_map_names: tuple[str, ...]
    scope_version: str = SCOPE_VERSION

    def to_metadata(self) -> dict[str, Any]:
        """The `scope` block every scoped response should embed (§5)."""
        return {
            "kind": "gaming_session",
            "version": self.scope_version,
            "gaming_session_id": self.gaming_session_id,
            "dates": list(self.dates),
            "accepted_round_count": self.accepted_round_count,
            "distinct_map_names": list(self.distinct_map_names),
        }

    # ── Per-panel multi-date query filters (deep SS-C) ────────────────
    #
    # The storytelling panels historically scoped by a SINGLE session_date
    # (scope.dates[0]). A gaming session that crosses midnight spans two
    # calendar dates, so those panels showed only one fragment. These
    # helpers let each panel restrict to EXACTLY this session's rounds:
    #
    #  - Tables that carry `gaming_session_id` (storytelling_kill_impact)
    #    or JOIN `rounds` (PCS via round_id, reliable per plan D1): filter
    #    on `gaming_session_id = $n` directly — nothing here needed.
    #  - Raw proximity tables (no gsid column): filter on the canonical
    #    round key `(round_start_unix, map_name, round_number)` via
    #    `round_key_filter_sql` + `round_key_arrays`. This is precise even
    #    when two gaming sessions share a calendar date (6 such sessions
    #    exist in prod) — a `session_date = ANY(dates)` prefilter alone
    #    would wrongly pull the other session's rounds.

    def round_key_arrays(self) -> tuple[list[int], list[str], list[int]]:
        """The scope's round_keys unzipped into three parallel arrays
        (round_start_unix[], map_name[], round_number[]) to bind to the
        `unnest(...)` in `round_key_filter_sql`. Append them to the query
        params in exactly this order at the matching positional indices."""
        starts: list[int] = []
        maps: list[str] = []
        rnums: list[int] = []
        for rsu, mn, rn in self.round_keys:
            starts.append(int(rsu))
            maps.append(str(mn))
            rnums.append(int(rn))
        return starts, maps, rnums

    def round_key_filter_sql(self, first_param: int, alias: str = "") -> str:
        """A SQL boolean fragment (AND it into a WHERE) that keeps only
        rows whose (round_start_unix, map_name, round_number) is one of
        this scope's round_keys, via three arrays bound at $first_param,
        $first_param+1, $first_param+2 — pair with `round_key_arrays()`
        appended to the params in that order.

        `alias` qualifies the row columns (e.g. "st" -> st.round_start_unix)
        for queries that alias the proximity table; empty for an unaliased
        table.
        """
        prefix = f"{alias}." if alias else ""
        a, b, c = first_param, first_param + 1, first_param + 2
        return (
            f"EXISTS (SELECT 1 FROM unnest(${a}::bigint[], ${b}::text[], ${c}::int[]) "
            f"AS _rk(rsu, mn, rn) WHERE _rk.rsu = {prefix}round_start_unix "
            f"AND _rk.mn = {prefix}map_name AND _rk.rn = {prefix}round_number)"
        )


def _is_sqlite_adapter(db: DatabaseAdapter) -> bool:
    """Duck-type check matching proximity_quality.py's existing convention —
    the SQLite dev-fallback adapter class name starts with 'sqlite' and/or
    carries a db_path attribute the PostgreSQL adapter never has."""
    adapter_name = db.__class__.__name__.lower()
    return adapter_name.startswith("sqlite") or hasattr(db, "db_path")


class ScopeBackendUnsupportedError(HTTPException):
    """Raised instead of letting a PostgreSQL-only query (STRING_AGG) hit
    SQLite and crash with a raw 'no such function' error. Local SQLite mode
    is a dev/tooling fallback (CLAUDE.md), not a production target — this
    is an explicit, honest 503, not a silent empty-list fallback (D4)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            detail={
                "code": "SCOPE_BACKEND_UNSUPPORTED",
                "message": (
                    "Gaming session scope listing requires PostgreSQL "
                    "(STRING_AGG) and is unavailable in local SQLite mode."
                ),
            },
        )


class AmbiguousSessionDateError(HTTPException):
    """A date resolved to MORE THAN ONE gaming session — the caller must
    disambiguate (409), never get a silent `LIMIT 1` guess (§12: explicit
    non-solution)."""

    def __init__(self, session_date: str, candidates: list[dict[str, Any]]):
        super().__init__(
            status_code=409,
            detail={
                "code": "AMBIGUOUS_SESSION_DATE",
                "message": (
                    f"{session_date} has {len(candidates)} gaming sessions — "
                    "specify gaming_session_id."
                ),
                "candidates": candidates,
            },
        )


async def _find_gsids_for_date(db: DatabaseAdapter, session_date: str) -> list[dict[str, Any]]:
    """Every gaming session with at least one accepted round on this
    calendar date, with enough summary to disambiguate (gsid, its own full
    date range, round count)."""
    rows = await db.fetch_all(
        f"""
        SELECT
            gaming_session_id,
            MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS start_date,
            MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS end_date,
            COUNT(*) AS round_count
        FROM rounds
        WHERE gaming_session_id IN (
            SELECT DISTINCT gaming_session_id
            FROM rounds
            WHERE SUBSTR(CAST(round_date AS TEXT), 1, 10) = $1
              AND gaming_session_id IS NOT NULL
              AND {_ROUND_GATE_SQL}
        )
        AND {_ROUND_GATE_SQL}
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id DESC
        """,  # nosec B608 - _ROUND_GATE_SQL is a hardcoded constant, no interpolated input.
        (session_date,),
    )
    return [
        {
            "gaming_session_id": r[0],
            "start_date": r[1],
            "end_date": r[2],
            "round_count": r[3],
        }
        for r in rows
    ]


async def _fetch_scope_rounds(db: DatabaseAdapter, gaming_session_id: int) -> list[tuple]:
    rows = await db.fetch_all(
        f"""
        SELECT round_start_unix, map_name, round_number,
               SUBSTR(CAST(round_date AS TEXT), 1, 10) AS rdate
        FROM rounds
        WHERE gaming_session_id = $1
          AND {_ROUND_GATE_SQL}
        ORDER BY round_start_unix NULLS LAST, round_number
        """,  # nosec B608 - _ROUND_GATE_SQL is a hardcoded constant, no interpolated input.
        (gaming_session_id,),
    )
    return list(rows)


def _build_scope(gaming_session_id: int, rows: list[tuple]) -> GamingSessionScope:
    dates = sorted({r[3] for r in rows if r[3]})
    round_keys = sorted(
        {(int(r[0]) if r[0] is not None else 0, r[1] or "", int(r[2])) for r in rows}
    )
    maps = sorted({r[1] for r in rows if r[1]})
    return GamingSessionScope(
        gaming_session_id=gaming_session_id,
        dates=tuple(dates),
        round_keys=tuple(round_keys),
        accepted_round_count=len(rows),
        distinct_map_names=tuple(maps),
    )


async def list_recent_scopes(db: DatabaseAdapter, *, limit: int = 30) -> list[dict[str, Any]]:
    """Recent gaming sessions as scope summaries — the source for a Smart
    Stats session SELECTOR (§7.1): `{gaming_session_id, dates,
    accepted_round_count, distinct_map_names}` per session, newest first.
    Deliberately lighter than sessions_router's GET /sessions (no
    player_count/win-loss — a selector dropdown doesn't need them); reuses
    the identical round-validity gate so a session that appears in the
    selector is guaranteed resolvable by `resolve_gaming_session_scope`.

    Raises ScopeBackendUnsupportedError(503) on SQLite — the STRING_AGG
    aggregate below is PostgreSQL-only.
    """
    if _is_sqlite_adapter(db):
        raise ScopeBackendUnsupportedError()
    limit = max(1, min(int(limit), 200))
    rows = await db.fetch_all(
        f"""
        SELECT
            gaming_session_id,
            MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS start_date,
            MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS end_date,
            COUNT(*) AS round_count,
            STRING_AGG(DISTINCT map_name, ', ' ORDER BY map_name) AS maps
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
          AND {_ROUND_GATE_SQL}
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id DESC
        LIMIT $1
        """,  # nosec B608 - _ROUND_GATE_SQL is a hardcoded constant, no interpolated input.
        (limit,),
    )
    return [
        {
            "gaming_session_id": r[0],
            "start_date": r[1],
            "end_date": r[2],
            "accepted_round_count": r[3],
            "distinct_map_names": (r[4] or "").split(", ") if r[4] else [],
            "scope_version": SCOPE_VERSION,
        }
        for r in rows
    ]


async def resolve_gaming_session_scope(
    db: DatabaseAdapter,
    *,
    gaming_session_id: int | None = None,
    session_date: str | None = None,
) -> GamingSessionScope:
    """Resolve exactly ONE of `gaming_session_id` / `session_date` into a
    `GamingSessionScope`.

    Raises:
        HTTPException(422): both or neither parameter supplied.
        HTTPException(404): the id/date resolves to no accepted rounds.
        AmbiguousSessionDateError(409): the date matches >1 gaming session.
    """
    if (gaming_session_id is None) == (session_date is None):
        raise HTTPException(
            status_code=422,
            detail="Exactly one of gaming_session_id or session_date is required.",
        )

    if gaming_session_id is None:
        candidates = await _find_gsids_for_date(db, session_date)
        if not candidates:
            raise HTTPException(
                status_code=404,
                detail=f"No gaming session found for session_date={session_date}.",
            )
        if len(candidates) > 1:
            raise AmbiguousSessionDateError(session_date, candidates)
        gaming_session_id = candidates[0]["gaming_session_id"]

    rows = await _fetch_scope_rounds(db, gaming_session_id)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"gaming_session_id={gaming_session_id} has no accepted rounds.",
        )
    return _build_scope(gaming_session_id, rows)
