#!/usr/bin/env python3
"""Backfill player_skill_history scope='session' + s.effort for all sessions.

DRY-RUN by default; --apply writes (idempotent DELETE+INSERT per player/session,
formula_version stamped in components — see s_effort_service). Uses asyncpg
(the driver the repo ships). Run scripts/db_backup.sh first for --apply.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg  # noqa: E402

from website.backend.services.s_effort_service import FORMULA_VERSION, SEffortService  # noqa: E402


def _tr(q):
    out, i = [], 0
    for ch in q:
        if ch == "?":
            i += 1
            out.append(f"${i}")
        else:
            out.append(ch)
    return "".join(out)


class Shim:
    def __init__(self, conn):
        self.conn = conn

    async def fetch_all(self, q, params=()):
        return await self.conn.fetch(_tr(q), *params)

    async def fetch_one(self, q, params=()):
        return await self.conn.fetchrow(_tr(q), *params)

    async def execute(self, q, params=()):
        return await self.conn.execute(_tr(q), *params)

    def transaction(self):
        # exposes asyncpg's transaction so persist_session runs atomically
        return self.conn.transaction()


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (else dry-run)")
    ap.add_argument("--i-have-a-backup", action="store_true",
                    help="required with --apply: confirms db_backup.sh was run")
    args = ap.parse_args()
    if args.apply and not args.i_have_a_backup:
        print("Refusing --apply without --i-have-a-backup (run scripts/db_backup.sh first).")
        return 1

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    if not args.apply:
        await conn.execute("SET default_transaction_read_only = on")
    svc = SEffortService(Shim(conn))

    # iterate session START dates (MIN(round_date) per gaming session) — the
    # same scoping the rating and the roster fix use; session_results dates
    # can finalize across midnight (codex, PR #455 round 5)
    dates = [str(r[0])[:10] for r in await conn.fetch(
        "SELECT MIN(SUBSTRING(round_date, 1, 10)) AS d FROM rounds "
        "WHERE gaming_session_id IS NOT NULL AND is_valid "
        "GROUP BY gaming_session_id ORDER BY d")]
    dates = sorted(set(dates))
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== s.effort history backfill — {mode}  {FORMULA_VERSION} ===")
    print(f"sessions_with_rosters={len(dates)}")
    total = 0
    for d in dates:
        date = str(d)[:10]
        if args.apply:
            n = await svc.persist_session(date)
        else:
            rows = await svc.compute_session(date)
            n = len(rows or [])
        total += n
        print(f"  {date}: {n} players")
    print(f"total player-session rows: {total}")
    if not args.apply:
        print("\nDRY-RUN — nothing written. db_backup.sh, then --apply.")
    await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
