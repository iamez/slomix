#!/usr/bin/env python3
"""Recompute KIS for every gaming session on the current formula (kis-v4).

Why: storytelling_kill_impact accumulated 26k+ rows under kis-v2 mixed with
7k under kis-v4 (no recompute path existed for a version bump — audit
2026-07-25). Every all-time consumer (SSR situational_share, Good Night
threshold, MVP kis_rank) silently aggregated mixed formulas, and
is_objective_area was structurally FALSE for every pre-v4 row. Owner
decision: full recompute so history is finally comparable across time.

DRY-RUN by default; --apply writes. Run scripts/db_backup.sh first.
Safety verified before writing this script (dev, 2026-07-25): every
existing kill_impact row has live proximity_kill_outcome source rows for
its round key, so a recompute regenerates everything it deletes. The
script still guards each session: a scope whose source query returns zero
kills is SKIPPED (rows left untouched at their old version) rather than
deleted-and-not-replaced.

Sessions are recomputed via compute_session_kis_for_gsid(force=True) — the
gsid-native path, so every rewritten row lands with gaming_session_id
stamped and formula_version = kis.FORMULA_VERSION.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from website.backend.services.storytelling.kis import FORMULA_VERSION  # noqa: E402
from website.backend.services.storytelling.service import StorytellingService  # noqa: E402


def _tr(q: str) -> str:
    out, i = [], 0
    for ch in q:
        if ch == "?":
            i += 1
            out.append(f"${i}")
        else:
            out.append(ch)
    return "".join(out)


class Shim:
    """asyncpg → adapter-interface shim (same pattern as
    backfill_s_effort_history.py), plus executemany for the KIS batch
    insert.

    Every operation is serialized through one asyncio.Lock: the KIS compute
    fires its 7 context loaders CONCURRENTLY (asyncio.gather in
    _load_context_for_dates) — fine on the website's connection POOL, but a
    single asyncpg connection raises InterfaceError("another operation is
    in progress") on the second concurrent query. A pool is not an option
    here because _store_scored_kills' transaction must share one connection
    with the statements inside it."""

    def __init__(self, conn):
        self.conn = conn
        self._lock = asyncio.Lock()

    async def fetch_all(self, q, params=()):
        async with self._lock:
            return await self.conn.fetch(_tr(q), *params)

    async def fetch_one(self, q, params=()):
        async with self._lock:
            return await self.conn.fetchrow(_tr(q), *params)

    async def execute(self, q, params=()):
        async with self._lock:
            return await self.conn.execute(_tr(q), *params)

    async def executemany(self, q, params_list):
        async with self._lock:
            return await self.conn.executemany(_tr(q), params_list)

    def transaction(self):
        # exposes asyncpg's transaction so _store_scored_kills runs atomically
        return self.conn.transaction()


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (else dry-run)")
    ap.add_argument("--i-have-a-backup", action="store_true",
                    help="required with --apply: confirms db_backup.sh was run")
    ap.add_argument("--gsid", type=int, default=None,
                    help="recompute only this gaming_session_id")
    args = ap.parse_args()
    if args.apply and not args.i_have_a_backup:
        print("Refusing --apply without --i-have-a-backup (run scripts/db_backup.sh first).")
        return 1

    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", os.getenv("DB_HOST", "127.0.0.1")),
        port=int(os.getenv("POSTGRES_PORT", os.getenv("DB_PORT", "5432"))),
        database=os.getenv("POSTGRES_DATABASE", os.getenv("DB_NAME", "etlegacy")),
        user=os.getenv("POSTGRES_USER", os.getenv("DB_USER", "etlegacy_user")),
        password=os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASSWORD", "")),
    )
    try:
        # Candidates: every gaming session that has kill-outcome source data
        # (round_id linkage — matches how the audit counted 38 on dev).
        rows = await conn.fetch(
            "SELECT DISTINCT r.gaming_session_id AS gsid "
            "FROM rounds r JOIN proximity_kill_outcome ko ON ko.round_id = r.id "
            "WHERE r.gaming_session_id IS NOT NULL "
            + ("AND r.gaming_session_id = $1 " if args.gsid else "")
            + "ORDER BY 1",
            *((args.gsid,) if args.gsid else ()),
        )
        gsids = [int(r["gsid"]) for r in rows]

        before = await conn.fetch(
            "SELECT formula_version, COUNT(*) AS n FROM storytelling_kill_impact "
            "GROUP BY 1 ORDER BY 1"
        )
        print(f"Formula target: {FORMULA_VERSION}")
        print(f"Sessions with kill-outcome source data: {len(gsids)}")
        print("Version mix before:", {r["formula_version"]: r["n"] for r in before})

        if not args.apply:
            print("\nDRY-RUN: no writes. Re-run with --apply --i-have-a-backup to recompute.")
            return 0

        svc = StorytellingService(db=Shim(conn))
        done = skipped = failed = 0
        for gsid in gsids:
            try:
                result = await svc.compute_session_kis_for_gsid(gsid, force=True)
                scored = int(result.get("kills_scored") or 0)
                if result.get("status") == "computed" and scored > 0:
                    done += 1
                    print(f"  gsid {gsid}: {scored} kills scored")
                else:
                    # A 0-kill result ("no_data") returns BEFORE the
                    # delete/insert step, so existing rows for the scope are
                    # left untouched at their old version — report so the
                    # summary shows the session was not migrated.
                    skipped += 1
                    print(f"  gsid {gsid}: SKIP/EMPTY ({result})")
            except HTTPException as e:
                # session_scope's resolver 404s a gaming_session_id with no
                # accepted rounds (all invalid/cancelled). That is the
                # resolver working as designed — such sessions shouldn't be
                # scored — not a recompute failure, so it must not flip the
                # exit code (dev: gsid 127). Anything but 404 is still real.
                if e.status_code == 404:
                    skipped += 1
                    print(f"  gsid {gsid}: SKIP (scope resolver: {e.detail})")
                else:
                    failed += 1
                    print(f"  gsid {gsid}: FAILED — HTTP {e.status_code}: {e.detail}")
            except Exception as e:  # noqa: BLE001 - per-session isolation, summary below
                failed += 1
                print(f"  gsid {gsid}: FAILED — {e}")

        after = await conn.fetch(
            "SELECT formula_version, COUNT(*) AS n FROM storytelling_kill_impact "
            "GROUP BY 1 ORDER BY 1"
        )
        null_gsid = await conn.fetchval(
            "SELECT COUNT(*) FROM storytelling_kill_impact WHERE gaming_session_id IS NULL"
        )
        print(f"\nRecomputed: {done}, empty/skipped: {skipped}, failed: {failed}")
        print("Version mix after:", {r["formula_version"]: r["n"] for r in after})
        print(f"Rows with NULL gaming_session_id after: {null_gsid}")
        return 0 if failed == 0 else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
