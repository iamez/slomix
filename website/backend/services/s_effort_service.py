"""s.effort — SuperBoyy's session pool-adjusted performance (K-D, owner-approved).

    s.effort      = session_rating / pool_strength
    s.performance = s.effort / (lifetime_rating / POOL_NEUTRAL)

Pool variant chosen by owner after the 4-variant backtest
(scripts/backtest_s_effort.py): **A — all session participants, leave-one-out**
(closest to SuperBoyy's original sheet; A/B/C ordering was near-identical).
POOL_NEUTRAL = population average of et_rating (measured 0.564, range
[0.24, 0.76] — NOT a theoretical 1.0).

Persistence: player_skill_history rows with scope='session' (infra added by
migration 031, unused until now). Idempotent: DELETE+INSERT per
(player_guid, scope, session_date); components jsonb carries s_effort,
s_performance, pool_avg and FORMULA_VERSION so future formula changes never
mix silently with old rows (owner requirement).

Adjusted lifetime (SRS pattern, owner-corrected): AVG over sessions — never a
sum (volume bias) — with harder pool as a PLUS:
    adj(p) = AVG_s[ sess_rating(p,s) + (avg_pool_adj_LOO(s,p) - POOL_NEUTRAL) ]
seeded with current et_rating, iterated to convergence (<=5 rounds).
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
from statistics import mean

logger = logging.getLogger(__name__)

FORMULA_VERSION = "s.effort-v0.1"
POOL_NEUTRAL = 0.564
SRS_ITERATIONS = 5


def s_effort(session_rating: float, pool_strength: float) -> float | None:
    if not pool_strength or pool_strength <= 0:
        return None
    return session_rating / pool_strength


def s_performance(effort: float, lifetime_rating: float) -> float | None:
    if not lifetime_rating or lifetime_rating <= 0:
        return None
    return effort / (lifetime_rating / POOL_NEUTRAL)


def pool_strength_A(all_ratings: list[float], own_rating: float) -> float | None:
    """Variant A: mean lifetime rating of ALL participants, leave-one-out."""
    others = list(all_ratings)
    if own_rating in others:
        others.remove(own_rating)  # leave-one-out: drop one instance of self
    return mean(others) if others else None


def adjusted_lifetime(sessions_by_player: dict[str, list[tuple[str, float]]],
                      seed: dict[str, float],
                      participants_by_session: dict[str, list[str]],
                      iterations: int = SRS_ITERATIONS) -> dict[str, float]:
    """Owner-corrected SRS: adj(p) = AVG_s[sess_rating + (pool_adj_LOO - NEUTRAL)].

    sessions_by_player: player -> [(session_key, session_rating), ...]
    seed: player -> current lifetime et_rating
    participants_by_session: session_key -> [player, ...]
    """
    adj = dict(seed)
    for _ in range(iterations):
        nxt = {}
        for p, sess in sessions_by_player.items():
            vals = []
            for skey, srating in sess:
                others = [adj.get(q, POOL_NEUTRAL)
                          for q in participants_by_session.get(skey, []) if q != p]
                if not others:
                    continue
                vals.append(srating + (mean(others) - POOL_NEUTRAL))
            if vals:
                # AVG, never a sum (volume bias guard); 0.5 damping so small
                # closed loops (two players rating each other) converge
                # instead of oscillating — standard fixed-point relaxation.
                nxt[p] = 0.5 * adj.get(p, POOL_NEUTRAL) + 0.5 * mean(vals)
        adj.update(nxt)
    return adj


class SEffortService:
    def __init__(self, db):
        self.db = db

    async def _roster(self, session_date: str) -> list[str] | None:
        # UNION across ALL session_results rows for the date: on dates with
        # more than one gaming session, compute_session_ratings scores the
        # whole date (MIN(round_date) scoping), so the pool must match it
        # (codex, PR #455).
        rows = await self.db.fetch_all(
            "SELECT team_1_guids, team_2_guids FROM session_results "
            "WHERE session_date = ? AND team_1_guids IS NOT NULL",
            (session_date,),
        )
        out: list[str] = []
        seen = set()
        for row in (rows or []):
            for col in (row[0], row[1]):
                for g in json.loads(col):
                    gu = (g or "").upper()
                    if gu and gu not in seen:
                        seen.add(gu)
                        out.append(gu)
        return out or None

    async def compute_session(self, session_date: str) -> list[dict] | None:
        """s.effort/s.performance for every rated participant of one session."""
        from website.backend.services.skill_rating_service import (
            compute_population_percentiles,
            compute_session_ratings,
        )
        roster = await self._roster(session_date)
        if not roster:
            return None
        life_rows = await self.db.fetch_all(
            "SELECT player_guid, display_name, et_rating FROM player_skill_ratings")
        # UPPER is only the MATCH KEY — the ORIGINAL guid (as stored in
        # player_skill_ratings) is what downstream lookups receive, so a
        # lower/mixed-case guid still resolves (codex, PR #455).
        life = {r[0].upper(): (r[1], float(r[2]), r[0]) for r in (life_rows or [])}
        rated = [g for g in roster if g in life]
        if len(rated) < 3:
            return None
        percentiles = await compute_population_percentiles(self.db)
        all_lifetimes = [life[g][1] for g in rated]
        out = []
        for g in rated:
            sr = await compute_session_ratings(self.db, life[g][2], session_date, percentiles)
            sess = (sr or {}).get("session_rating") if isinstance(sr, dict) else None
            if sess is None:
                continue
            pool = pool_strength_A(all_lifetimes, life[g][1])
            eff = s_effort(float(sess), pool) if pool else None
            perf = s_performance(eff, life[g][1]) if eff is not None else None
            out.append({
                "player_guid": g, "name": life[g][0],
                "session_rating": round(float(sess), 4),
                "lifetime_rating": round(life[g][1], 4),
                "pool_strength": round(pool, 4) if pool else None,
                "s_effort": round(eff, 4) if eff is not None else None,
                "s_performance": round(perf, 4) if perf is not None else None,
                "rounds": (sr or {}).get("rounds"),
                "formula_version": FORMULA_VERSION,
            })
        return out or None

    async def persist_session(self, session_date: str,
                              rows: list[dict] | None = None) -> int:
        """Idempotent persist into player_skill_history scope='session'.

        Accepts precomputed rows (endpoint passes them — no double compute).
        Deletes ALL of the date's scope='session' rows first so players who
        dropped out of a corrected roster don't leave stale entries; wrapped
        in a transaction when the adapter supports one (atomicity).
        """
        if rows is None:
            rows = await self.compute_session(session_date)
        if not rows:
            return 0

        # player_skill_history.session_date is a DATE column (migration 031)
        # — the PG adapter needs a date object, not a string (codex, PR #455)
        d = _dt.date.fromisoformat(str(session_date)[:10])

        async def _write():
            await self.db.execute(
                "DELETE FROM player_skill_history "
                "WHERE scope = 'session' AND session_date = ?",
                (d,),
            )
            for r in rows:
                await self._insert_row(d, r)

        tx = getattr(self.db, "transaction", None)
        if callable(tx):
            async with tx():
                await _write()
        else:
            await _write()
        return len(rows)

    async def _insert_row(self, session_date, r: dict) -> None:
        await self.db.execute(
                "INSERT INTO player_skill_history "
                "(player_guid, scope, session_date, et_rating, rounds_in_scope, components) "
                "VALUES (?, 'session', ?, ?, ?, ?)",
                (r["player_guid"], session_date, r["session_rating"],
                 r.get("rounds") or 0,
                 json.dumps({
                     "s_effort": r["s_effort"],
                     "s_performance": r["s_performance"],
                     "pool_strength": r["pool_strength"],
                     "lifetime_rating": r["lifetime_rating"],
                     "formula_version": FORMULA_VERSION,
                 })),
            )

    async def compute_adjusted_lifetime(self) -> list[dict]:
        """SRS adjusted lifetime from PERSISTED scope='session' rows."""
        hist_all = await self.db.fetch_all(
            "SELECT player_guid, session_date, et_rating, components "
            "FROM player_skill_history "
            "WHERE scope = 'session' AND session_date IS NOT NULL")
        # only rows written by the CURRENT formula — the version guarantee
        # must hold on read, not just on write (Copilot, PR #455)
        hist = []
        for r in (hist_all or []):
            try:
                comp = json.loads(r[3]) if isinstance(r[3], str) else (r[3] or {})
            except (TypeError, ValueError):
                comp = {}
            if comp.get("formula_version") == FORMULA_VERSION:
                hist.append(r)
        life_rows = await self.db.fetch_all(
            "SELECT player_guid, display_name, et_rating FROM player_skill_ratings")
        life = {r[0].upper(): (r[1], float(r[2])) for r in (life_rows or [])}
        sess_by_p: dict[str, list] = {}
        parts: dict[str, list] = {}
        for r in (hist or []):
            p, skey = r[0].upper(), str(r[1])
            sess_by_p.setdefault(p, []).append((skey, float(r[2])))
            parts.setdefault(skey, []).append(p)
        if not sess_by_p:
            return []
        seed = {p: life.get(p, (None, POOL_NEUTRAL))[1] for p in sess_by_p}
        adj = adjusted_lifetime(sess_by_p, seed, parts)
        out = [{"player_guid": p, "name": life.get(p, (p, 0))[0],
                "lifetime_rating": round(life[p][1], 4) if p in life else None,
                "adjusted_lifetime": round(v, 4),
                "n_sessions": len(sess_by_p[p]),
                "formula_version": FORMULA_VERSION}
               for p, v in adj.items()]
        out.sort(key=lambda x: -(x["adjusted_lifetime"] or 0))
        return out
