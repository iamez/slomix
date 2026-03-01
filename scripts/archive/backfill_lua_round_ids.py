#!/usr/bin/env python3
"""Backfill lua_round_teams.round_id using round_linker matching."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import Optional

from bot.config import BotConfig
from bot.core.database_adapter import PostgreSQLAdapter
from bot.core.round_linker import resolve_round_id

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def _to_dt(unix_ts: Optional[int]) -> Optional[datetime]:
    if not unix_ts:
        return None
    try:
        return datetime.fromtimestamp(int(unix_ts))
    except (TypeError, ValueError, OSError):
        return None


async def backfill(limit: Optional[int], dry_run: bool) -> int:
    config = BotConfig()
    adapter = PostgreSQLAdapter(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password,
        min_pool_size=config.postgres_min_pool,
        max_pool_size=config.postgres_max_pool,
        ssl_mode=getattr(config, "postgres_ssl_mode", "disable"),
        ssl_cert=getattr(config, "postgres_ssl_cert", ""),
        ssl_key=getattr(config, "postgres_ssl_key", ""),
        ssl_root_cert=getattr(config, "postgres_ssl_root_cert", ""),
    )

    await adapter.connect()

    window_minutes = getattr(config, "round_match_window_minutes", 45)
    rows = await adapter.fetch_all(
        """
        SELECT id, map_name, round_number, round_start_unix, round_end_unix, captured_at
        FROM lua_round_teams
        WHERE round_id IS NULL
        ORDER BY id DESC
        """
    )

    updated = 0
    scanned = 0
    for row in rows:
        if limit is not None and scanned >= limit:
            break
        scanned += 1

        lua_id, map_name, round_number, round_start, round_end, captured_at = row
        if not map_name or not round_number:
            continue

        target_dt = _to_dt(round_end) or _to_dt(round_start)
        if not target_dt and captured_at:
            if isinstance(captured_at, str):
                try:
                    captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
                except ValueError:
                    captured_at = None
            if captured_at:
                target_dt = captured_at.replace(tzinfo=None) if getattr(captured_at, "tzinfo", None) else captured_at

        round_id = await resolve_round_id(
            adapter,
            map_name,
            int(round_number),
            target_dt=target_dt,
            round_date=target_dt.strftime("%Y-%m-%d") if target_dt else None,
            round_time=target_dt.strftime("%H%M%S") if target_dt else None,
            window_minutes=window_minutes,
        )

        if round_id and not dry_run:
            await adapter.execute(
                "UPDATE lua_round_teams SET round_id = ? WHERE id = ?",
                (round_id, lua_id),
            )
            updated += 1
        elif round_id:
            updated += 1

    await adapter.close()
    print(f"Backfill lua_round_teams.round_id done. scanned={scanned}, updated={updated}, dry_run={dry_run}")
    return 0


def main() -> int:
    logger.info("Script started: %s", __file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return asyncio.run(backfill(args.limit, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
