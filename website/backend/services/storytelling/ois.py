"""OIS — Objective Impact Score (owner answer A2, 2026-07-07).

KIS-scale credit for NON-KILL objective acts. KIS stays a pure KILL impact
score (owner: "KIS naj bi bil kill impact score"); OIS is the parallel ledger
for the work KIS is blind to — doc returns, defuses, constructions — so
engineers and doc-returners stop being invisible. The two scores meet only at
the SSR aggregate level; no formula mixes them silently.

Base values (KIS-comparable by design: a carrier kill is 3.0 in KIS):
    doc return            3.0  x speed multiplier (fast return denies more)
    dynamite defuse       2.5  (near-miss defense; K-B2 evidence: defenders
                                coming back is exactly what kills pushes)
    construction complete 2.0  x contested multiplier

Construction rows include defensive/optional repairs (the Lua logs the
generic Repair: message). For OIS that is acceptable ON PURPOSE: the actor
did objective work either way — unlike the K-B2 case-control, crediting the
actor needs no attacker/advance attribution.

Read-only compute (v0): no persistence; the SSR aggregate calls this per
session. formula stays versioned for the registry.
"""
from __future__ import annotations

import datetime as _dt
from datetime import date

FORMULA_VERSION = "ois-v0.1"

DOC_RETURN_BASE = 3.0
DEFUSE_BASE = 2.5
CONSTRUCTION_BASE = 2.0

# return_delay_ms thresholds: instant grabs deny the most enemy progress
RETURN_FAST_MS = 2_000
RETURN_SLOW_MS = 15_000
RETURN_FAST_MULT = 1.3
RETURN_SLOW_MULT = 0.8

# construction counts as contested when an enemy kill lands nearby in time
CONTESTED_WINDOW_MS = 10_000
CONTESTED_MULT = 1.3


def doc_return_score(return_delay_ms: int | None) -> float:
    """3.0 x speed multiplier; unknown delay scores neutral."""
    if return_delay_ms is None or return_delay_ms < 0:
        return DOC_RETURN_BASE
    if return_delay_ms <= RETURN_FAST_MS:
        return DOC_RETURN_BASE * RETURN_FAST_MULT
    if return_delay_ms >= RETURN_SLOW_MS:
        return DOC_RETURN_BASE * RETURN_SLOW_MULT
    return DOC_RETURN_BASE


def defuse_score() -> float:
    return DEFUSE_BASE


def construction_score(contested: bool) -> float:
    return CONSTRUCTION_BASE * (CONTESTED_MULT if contested else 1.0)


class OisService:
    """Session-scoped OIS compute over proximity objective tables."""

    def __init__(self, db):
        self.db = db

    async def compute_session_ois(self, session_date: str | date) -> list[dict]:
        """Per-player OIS rows for one calendar session date.

        Calendar-date scoped ON PURPOSE: every joined table (carrier_return,
        construction_event, kill_impact) keys on the proximity file date —
        the same scope KIS uses (see the PWC note in win_contribution.py;
        unification is a tracked owner decision, B7).
        """
        # DATE column: asyncpg needs a date object, not a string (the same
        # trap persist_session hit — see s_effort_service)
        sd = _dt.date.fromisoformat(str(session_date)[:10])

        returns = await self.db.fetch_all(
            "SELECT UPPER(LEFT(returner_guid, 8)) AS g8,"
            "       MAX(returner_name) AS name,"
            "       return_delay_ms "
            "FROM proximity_carrier_return cr "
            "LEFT JOIN rounds r ON r.id = cr.round_id "
            "WHERE cr.session_date = ? AND (r.id IS NULL OR r.is_valid) "
            "  AND cr.returner_guid IS NOT NULL "
            "  AND cr.returner_guid NOT LIKE 'OMNIBOT%' "
            "GROUP BY UPPER(LEFT(returner_guid, 8)), cr.id, return_delay_ms",
            (sd,),
        )

        events = await self.db.fetch_all(
            "SELECT UPPER(LEFT(ce.player_guid, 8)) AS g8,"
            "       MAX(ce.player_name) AS name,"
            "       ce.event_type, ce.round_start_unix, ce.event_time "
            "FROM proximity_construction_event ce "
            "LEFT JOIN rounds r ON r.id = ce.round_id "
            "WHERE ce.session_date = ? AND (r.id IS NULL OR r.is_valid) "
            "  AND ce.event_type IN ('dynamite_defuse', 'construction_complete') "
            "  AND ce.player_guid IS NOT NULL "
            "  AND ce.player_guid NOT LIKE 'OMNIBOT%' "
            "GROUP BY UPPER(LEFT(ce.player_guid, 8)), ce.id, ce.event_type,"
            "         ce.round_start_unix, ce.event_time",
            (sd,),
        )

        # contested lookup: kill timestamps per round (one query, session-wide)
        kills = await self.db.fetch_all(
            "SELECT round_start_unix, kill_time_ms "
            "FROM storytelling_kill_impact WHERE session_date = ?",
            (sd,),
        )
        kill_times: dict[int, list[int]] = {}
        for k in kills or []:
            kill_times.setdefault(int(k[0] or 0), []).append(int(k[1] or 0))

        def _contested(rsu, t) -> bool:
            return any(abs(kt - int(t or 0)) <= CONTESTED_WINDOW_MS
                       for kt in kill_times.get(int(rsu or 0), ()))

        players: dict[str, dict] = {}

        def _acc(g8: str, name: str, kind: str, score: float) -> None:
            p = players.setdefault(g8, {
                "player_guid": g8, "name": name, "ois_total": 0.0,
                "doc_returns": 0, "defuses": 0, "constructions": 0,
                "formula_version": FORMULA_VERSION,
            })
            p["ois_total"] = round(p["ois_total"] + score, 3)
            p[kind] += 1
            if name:
                p["name"] = name

        for r in returns or []:
            _acc(r[0], r[1], "doc_returns", doc_return_score(r[2]))
        for e in events or []:
            if e[2] == "dynamite_defuse":
                _acc(e[0], e[1], "defuses", defuse_score())
            else:
                _acc(e[0], e[1], "constructions",
                     construction_score(_contested(e[3], e[4])))

        out = sorted(players.values(), key=lambda p: -p["ois_total"])
        return out
