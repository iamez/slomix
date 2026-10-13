"""Canonical, quality-filtered identity for composite metrics and coverage."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException

from website.backend.services.session_scope import AmbiguousSessionDateError, GamingSessionScope

_ACCEPTED = """round_number IN (1, 2)
    AND is_valid IS DISTINCT FROM FALSE
    AND is_bot_round IS DISTINCT FROM TRUE
    AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)"""


def _unclaimed_key_sql(prefix):
    # Known canonical keys always win over conflicting linked IDs. Tuple LHS
    # is outside the subquery, avoiding inner-column name capture.
    return (
        f"({prefix}round_start_unix IS NULL OR "
        f"({prefix}round_start_unix, {prefix}map_name, {prefix}round_number, {prefix}session_date) "
        "NOT IN (SELECT _known.round_start_unix, _known.map_name, _known.round_number, "
        "CAST(_known.round_date AS date) FROM rounds _known "
        "WHERE _known.round_start_unix IS NOT NULL AND _known.map_name IS NOT NULL "
        "AND _known.round_number IS NOT NULL AND _known.round_date IS NOT NULL))"
    )


def composite_round_join_sql():
    """Same fallback admission for default-date discovery (fixed r/t aliases)."""
    return (
        "r.map_name = t.map_name AND r.round_number = t.round_number "
        "AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) = CAST(t.session_date AS TEXT) "
        "AND (r.round_start_unix = t.round_start_unix OR "
        f"(r.round_start_unix IS NULL AND r.id = t.round_id AND {_unclaimed_key_sql('t.')}))"
    )


@dataclass(frozen=True)
class CompositeScope(GamingSessionScope):
    """Prefer canonical keys; linked IDs only cover missing canonical timestamps."""

    fallback_rounds: tuple[tuple[int, str, int, str], ...] = ()

    def round_key_arrays(self):
        return (*super().round_key_arrays(),
                [r[0] for r in self.fallback_rounds], [r[1] for r in self.fallback_rounds],
                [r[2] for r in self.fallback_rounds], [date.fromisoformat(r[3]) for r in self.fallback_rounds])

    def round_key_filter_sql(self, first_param, alias=""):
        canonical = super().round_key_filter_sql(first_param, alias)
        prefix = f"{alias}." if alias else ""
        a, b, c, d = range(first_param + 3, first_param + 7)
        fallback = (
            f"EXISTS (SELECT 1 FROM unnest(${a}::int[], ${b}::text[], ${c}::int[], ${d}::date[]) "
            f"AS _rf(rid, mn, rn, rd) WHERE _rf.rid = {prefix}round_id "
            f"AND _rf.mn = {prefix}map_name AND _rf.rn = {prefix}round_number "
            f"AND _rf.rd = {prefix}session_date) "
            f"AND {_unclaimed_key_sql(prefix)}"
        )
        return f"({canonical} OR ({fallback}))"


async def resolve_composite_scope(db, *, gaming_session_id=None, session_date=None):
    """Resolve only accepted non-bot candidates; never merge ambiguous dates."""
    if gaming_session_id is None:
        if session_date is None:
            raise HTTPException(status_code=422, detail="A gaming session or date is required.")
        candidates = await db.fetch_all(f"""
            SELECT gaming_session_id,
                   MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)),
                   MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)), COUNT(*)
            FROM rounds
            WHERE gaming_session_id IN (
                SELECT DISTINCT gaming_session_id FROM rounds
                WHERE SUBSTR(CAST(round_date AS TEXT), 1, 10) = $1
                  AND gaming_session_id IS NOT NULL AND {_ACCEPTED}
            ) AND {_ACCEPTED}
            GROUP BY gaming_session_id ORDER BY gaming_session_id DESC
        """, (session_date,))
        if not candidates:
            raise HTTPException(status_code=404, detail="No accepted non-bot gaming session on this date.")
        if len(candidates) > 1:
            raise AmbiguousSessionDateError(session_date, [
                dict(gaming_session_id=r[0], start_date=r[1], end_date=r[2], round_count=r[3])
                for r in candidates
            ])
        gaming_session_id = candidates[0][0]
    rows = await db.fetch_all(f"""
        SELECT round_start_unix, map_name, round_number,
               SUBSTR(CAST(round_date AS TEXT), 1, 10) AS rdate, id
        FROM rounds
        WHERE gaming_session_id = $1 AND {_ACCEPTED}
        ORDER BY round_start_unix NULLS LAST, round_number
    """, (gaming_session_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="No accepted non-bot rounds in this gaming session.")
    # A linked round_id cannot disambiguate a canonical key: historical
    # proximity links can point at the wrong round. Refuse the entire result
    # rather than publish partial metrics or silently count both sessions.
    collisions = await db.fetch_all(f"""
        WITH accepted_keys AS (
            SELECT gaming_session_id, round_start_unix, map_name, round_number,
                   CAST(round_date AS date) AS round_date
            FROM rounds WHERE {_ACCEPTED}
              AND gaming_session_id IS NOT NULL AND round_start_unix IS NOT NULL
        )
        SELECT other.gaming_session_id
        FROM accepted_keys chosen JOIN accepted_keys other
          ON chosen.round_start_unix = other.round_start_unix
         AND chosen.map_name = other.map_name
         AND chosen.round_number = other.round_number
         AND chosen.round_date = other.round_date
         AND chosen.gaming_session_id <> other.gaming_session_id
        WHERE chosen.gaming_session_id = $1
        LIMIT 1
    """, (gaming_session_id,))
    if collisions:
        raise HTTPException(status_code=409, detail={
            "code": "ambiguous_round_key",
            "message": "An accepted round key belongs to multiple gaming sessions; composite metrics are unavailable.",
            "gaming_session_id": gaming_session_id,
        })
    return CompositeScope(
        gaming_session_id=gaming_session_id,
        dates=tuple(sorted({r[3] for r in rows if r[3]})),
        round_keys=tuple(sorted({(int(r[0]), r[1] or '', int(r[2])) for r in rows if r[0] is not None})),
        accepted_round_count=len(rows),
        distinct_map_names=tuple(sorted({r[1] for r in rows if r[1]})),
        fallback_rounds=tuple(sorted({(int(r[4]), r[1], int(r[2]), r[3]) for r in rows
                                     if r[0] is None and r[1] and r[3]})),
    )
