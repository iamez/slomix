#!/usr/bin/env python3
"""Run /stats/session/{id}/basics and /awards in-process over EVERY gaming
session and report the distributions — the corpus proof behind stats 2.0
R2 (docs/design/18 §E.3): a handler that answers one sample is not a
handler that answers the archive.

Read-only: asyncpg with default_transaction_read_only, the same adapter
shim as scripts/backfill_kis_recompute.py, the handlers called directly.

Usage: venv/bin/python scripts/audit_session_basics.py [--json] [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fastapi import HTTPException  # noqa: E402


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
    def __init__(self, conn):
        self.conn = conn
        self._lock = asyncio.Lock()

    async def fetch_all(self, q, params=()):
        async with self._lock:
            return await self.conn.fetch(_tr(q), *params)

    async def fetch_one(self, q, params=()):
        async with self._lock:
            return await self.conn.fetchrow(_tr(q), *params)

    async def fetch_val(self, q, params=()):
        async with self._lock:
            return await self.conn.fetchval(_tr(q), *params)

    async def execute(self, q, params=()):
        raise RuntimeError("read-only audit tried to write")


def _dsn() -> str:
    from dotenv import dotenv_values

    env = {**dotenv_values(REPO / ".env"), **os.environ}
    return (
        f"postgresql://{env.get('POSTGRES_USER', 'etlegacy_user')}:{env.get('POSTGRES_PASSWORD', '')}"
        f"@{env.get('POSTGRES_HOST', '127.0.0.1')}:{env.get('POSTGRES_PORT', '5432')}/{env.get('POSTGRES_DATABASE', 'etlegacy')}"
    )


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    import asyncpg  # noqa: PLC0415

    from website.backend.routers.sessions_router import get_session_awards, get_session_basics  # noqa: PLC0415

    conn = await asyncpg.connect(_dsn())
    await conn.execute("SET default_transaction_read_only = on")
    db = Shim(conn)
    try:
        gsids = [r[0] for r in await conn.fetch(
            "SELECT DISTINCT gaming_session_id FROM rounds WHERE gaming_session_id IS NOT NULL ORDER BY 1"
        )]
        if args.limit:
            gsids = gsids[-args.limit:]
        per: list[dict] = []
        errors: list[tuple[int, str]] = []
        no_counted_rounds: list[int] = []
        for gsid in gsids:
            try:
                b = await get_session_basics(gsid, db)
                a = await get_session_awards(gsid, db)
            except HTTPException as e:
                if e.status_code == 404:
                    no_counted_rounds.append(gsid)  # every round invalid/bot — expected, not an error
                    continue
                errors.append((gsid, f"{e.status_code} {e.detail}"))
                continue
            except Exception as e:  # noqa: BLE001 — that IS the finding
                errors.append((gsid, f"EXC {type(e).__name__}: {e}"))
                continue
            ps = b["players"]
            per.append({
                "gsid": gsid,
                "players": len(ps),
                "rounds": b["coverage"]["rounds_counted"],
                "kis_covered": b["coverage"]["kis_covered"],
                "teams": b["coverage"]["teams_attributed"],
                "denied_max": max((p["denied_pct"] or 0) for p in ps) if ps else None,
                "denied_suspect": b["coverage"]["denied_suspect_players"],
                "dmr_max": max(p["dmr"] for p in ps) if ps else None,
                "played_over_100": sum(1 for p in ps if (p["played_pct"] or 0) > 100),
                "null_acc": sum(1 for p in ps if p["accuracy"] is None),
                "null_played": sum(1 for p in ps if p["played_pct"] is None),
                "team_null": sum(1 for p in ps if p["team"] is None),
                "awards": sum(len(c["awards"]) for c in a["categories"]),
                "rounds_with_awards": a["rounds_with_awards"],
            })
        summary = {
            "sessions": len(gsids),
            "answered": len(per),
            "no_counted_rounds": no_counted_rounds,
            "errors": errors,
            "kis_covered": sum(1 for r in per if r["kis_covered"]),
            "teams_attributed": sum(1 for r in per if r["teams"]),
            "denied_pct_max": max((r["denied_max"] or 0) for r in per) if per else None,
            "denied_suspect_rows": sum(r["denied_suspect"] for r in per),
            "dmr_max": max((r["dmr_max"] or 0) for r in per) if per else None,
            "played_over_100_rows": sum(r["played_over_100"] for r in per),
            "null_accuracy_rows": sum(r["null_acc"] for r in per),
            "null_played_rows": sum(r["null_played"] for r in per),
            "team_null_rows": sum(r["team_null"] for r in per),
            "awards_per_session_median": statistics.median([r["awards"] for r in per]) if per else None,
            "awards_per_session_min": min((r["awards"] for r in per), default=None),
            "sessions_without_engine_awards": sum(1 for r in per if r["rounds_with_awards"] == 0),
        }
        if args.json:
            print(json.dumps({"summary": summary, "sessions": per}, indent=1, default=str))
        else:
            for k, v in summary.items():
                print(f"{k:32} {v}")
        return 1 if errors else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
