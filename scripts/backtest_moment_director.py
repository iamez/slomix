#!/usr/bin/env python3
"""Phase-0 backtest: Moment Director quality (READ-ONLY, Good Night plan B1).

Runs the REAL StorytellingService detectors over recent sessions and compares
the pre-B1 star-then-time cut against the new star-tiered director cut, both
picking a top-5 from the SAME uncut pool (svc._collect_moments), so we can see
the effect with a table before/after touching the ranking:

  - pool : total moments detected (all 11 detectors, UNCUT — via _collect_moments)
  - ply  : distinct players in the top-5, old -> new
  - lead : the top-5 as "type/player(stars)" so the human can eyeball tone

No writes: SET default_transaction_read_only = on, and the detectors are pure-read.
"""
import asyncio
import os
import sys
from collections import Counter

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website.backend.services.storytelling.moments import _select_director_cut  # noqa: E402
from website.backend.services.storytelling_service import StorytellingService  # noqa: E402


def _old_cut(moments, limit=5):
    """The pre-B1 selection: one best moment per type, then fill by (-stars, time),
    final sort by (-stars, time). Reimplemented locally for A/B comparison only."""
    by_type: dict = {}
    for m in moments:
        by_type.setdefault(m["type"], []).append(m)
    for bucket in by_type.values():
        bucket.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
    result, seen = [], set()
    for bucket in by_type.values():
        if bucket:
            result.append(bucket[0])
            seen.add(id(bucket[0]))
    remaining = [m for m in moments if id(m) not in seen]
    remaining.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
    result.extend(remaining[:max(0, limit - len(result))])
    result.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
    return result[:limit]


def _fmt_cut(cut):
    return ", ".join(
        f"{m['type'][:4]}/{str(m.get('player', '?'))[:8]}{m['impact_stars']}★" for m in cut)


class _Adapter:
    """Thin asyncpg-pool shim exposing the fetch_all/fetch_one the service expects.

    The detectors fan out 11 queries via asyncio.gather, so a single connection
    hits 'another operation is in progress' — production uses a pool, so we
    acquire a connection per call to match that concurrency. Storytelling
    detectors use native $1/$2 placeholders, so params pass straight through.
    """

    def __init__(self, pool):
        self.pool = pool

    async def fetch_all(self, query, params=()):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)

    async def fetch_one(self, query, params=()):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *params)


async def main():
    async def _init(conn):
        await conn.execute("SET default_transaction_read_only = on")

    pool = await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""),
        min_size=2, max_size=12, init=_init)

    async with pool.acquire() as conn:
        dates = await conn.fetch("""
            SELECT session_date, COUNT(*) AS n
            FROM proximity_kill_outcome
            GROUP BY session_date
            HAVING COUNT(*) >= 200
            ORDER BY session_date DESC
            LIMIT 12""")

    svc = StorytellingService(_Adapter(pool))

    print("A/B: pre-B1 star-cut  vs  new director-cut (both top-5, same pool)")
    print(f"{'date':<11}{'pool':>5} {'ply old->new':<13} lead old  ||  lead new")
    print("-" * 100)

    agg: Counter = Counter()
    for row in dates:
        sd = row["session_date"]
        moment_pool = await svc._collect_moments(sd)  # noqa: SLF001 - backtest harness reads the raw pool
        if not moment_pool:
            print(f"{str(sd):<11}{'0':>5}  (no moments)")
            continue
        agg.update(m["type"] for m in moment_pool)

        # Both cuts pick their top-5 from the exact same uncut pool -> fair A/B.
        old_c = _old_cut(moment_pool, limit=5)               # pre-B1 star-then-time
        new_c = _select_director_cut(moment_pool, limit=5)   # new star-tiered director

        old_players = len({m.get("player", "?") for m in old_c})
        new_players = len({m.get("player", "?") for m in new_c})

        print(f"{str(sd):<11}{len(moment_pool):>5} {f'{old_players}->{new_players}':<13} "
              f"{_fmt_cut(old_c)}\n{'':<31}|| {_fmt_cut(new_c)}")

    # Aggregate diversity signal across all sampled sessions (uncut pool).
    print("\n=== pool type frequency (all sampled sessions, uncut) ===")
    for t, c in agg.most_common():
        print(f"  {t:<20}{c:>5}")

    await pool.close()


asyncio.run(main())
