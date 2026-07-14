#!/usr/bin/env python3
"""Phase-0 backtest: Moment Director quality (READ-ONLY, Good Night plan B1).

Runs the REAL StorytellingService.detect_moments() over recent sessions and
characterizes the *current* top-5 "director's cut" so we can see, with a table,
whether the selection is diverse before touching the ranking:

  - pool  : total moments detected (all 11 detectors, pre-truncation)
  - types : distinct moment types in the full pool
  - t5typ : distinct types among the shown top-5
  - t5ply : distinct players among the shown top-5
  - dom%  : share of the top-5 taken by its single most common type
  - stars : star histogram of the top-5 (e.g. "5:3 4:2" = three 5-star, two 4-star)
  - lead  : the top-5 as "type/player(stars)" so the human can eyeball tone

No writes: SET default_transaction_read_only = on, and detect_moments is pure-read.
"""
import asyncio
import os
import sys
from collections import Counter

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

    for row in dates:
        sd = row["session_date"]
        full = await svc.detect_moments(sd, limit=100)    # full pool (unique moments)
        if not full:
            print(f"{str(sd):<11}{'0':>5}  (no moments)")
            continue

        new_cut = await svc.detect_moments(sd, limit=5)   # director's cut (new logic)
        old_cut = _old_cut(full, limit=5)                 # pre-B1 selection, same pool

        old_players = len({m.get("player", "?") for m in old_cut})
        new_players = len({m.get("player", "?") for m in new_cut})

        print(f"{str(sd):<11}{len(full):>5} {f'{old_players}->{new_players}':<13} "
              f"{_fmt_cut(old_cut)}\n{'':<31}|| {_fmt_cut(new_cut)}")

    # Aggregate the diversity signal across all sampled sessions.
    print("\n=== pool type frequency (all sampled sessions) ===")
    agg: Counter = Counter()
    for row in dates:
        pool_moments = await svc.detect_moments(row["session_date"], limit=100)
        agg.update(m["type"] for m in pool_moments)
    for t, c in agg.most_common():
        print(f"  {t:<20}{c:>5}")

    await pool.close()


asyncio.run(main())
