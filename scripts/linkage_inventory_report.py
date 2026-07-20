#!/usr/bin/env python3
"""
Read-only wrong-round-linkage inventory report (Codex SS-E follow-up, §L4).

Enumerates rows across the proximity/combat tables whose stored
round_start_unix disagrees with the round_start_unix of the round they are
linked to via round_id, grouped by table and date, and flags whether a
deterministic correct target (round_start_unix + map_name + round_number)
exists. Prints a JSON report to stdout.

Prep/inventory only for a later, separate, owner-gated repair step
(L5/L6) — this script makes NO database writes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.config import load_config
from bot.core.database_adapter import create_adapter
from bot.services.linkage_inventory_service import (
    LINKAGE_INVENTORY_TABLES,
    build_linkage_inventory,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Read-only wrong-round-linkage inventory, grouped by table and date."
    )
    parser.add_argument("--since-date", default=None, help="Only include session_date >= this (YYYY-MM-DD).")
    parser.add_argument("--until-date", default=None, help="Only include session_date <= this (YYYY-MM-DD).")
    parser.add_argument("--sample-limit", type=int, default=10, help="Sample wrong rows per table.")
    parser.add_argument(
        "--table", action="append", dest="tables", default=None,
        help="Restrict to one table (repeatable). Defaults to all linkage-tracked tables.",
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    tables = tuple(args.tables) if args.tables else LINKAGE_INVENTORY_TABLES
    unknown = [t for t in tables if t not in LINKAGE_INVENTORY_TABLES]
    if unknown:
        logger.error("Unknown table(s) %s. Valid: %s", unknown, LINKAGE_INVENTORY_TABLES)
        return 2

    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    try:
        result = await build_linkage_inventory(
            adapter,
            since_date=args.since_date,
            until_date=args.until_date,
            sample_limit=args.sample_limit,
            tables=tables,
        )
    finally:
        await adapter.close()

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


def main() -> int:
    logger.info("Script started: %s", __file__)
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
