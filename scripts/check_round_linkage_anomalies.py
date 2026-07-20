#!/usr/bin/env python3
"""
Check round/match linkage anomalies with thresholded breach reporting.

Read-only script: runs diagnostic queries and prints JSON summary.
Use --fail-on-breach to make non-zero exit on threshold breaches.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.config import load_config
from bot.core.database_adapter import create_adapter
from bot.services.round_linkage_anomaly_service import assess_round_linkage_anomalies

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run read-only round linkage anomaly checks with thresholds."
    )
    parser.add_argument("--sample-limit", type=int, default=20, help="Sample rows per anomaly class.")
    parser.add_argument(
        "--max-unlinked-lua-ratio",
        type=float,
        default=0.20,
        help="Threshold for unlinked lua_round_teams ratio (0.0-1.0).",
    )
    parser.add_argument(
        "--max-wrong-start-lua",
        type=int,
        default=0,
        help="Threshold for lua_round_teams rows linked to the WRONG round "
             "(round_start_unix disagrees with the linked round's own "
             "round_start_unix — the real mislink signal, Codex §18.5).",
    )
    parser.add_argument("--max-map-mismatch", type=int, default=0)
    parser.add_argument("--max-round-number-mismatch", type=int, default=0)
    parser.add_argument("--max-duplicate-links", type=int, default=0)
    parser.add_argument(
        "--max-correlation-mismatch",
        type=int,
        default=0,
        help="Threshold for round_correlations rows whose map_name disagrees "
             "with the linked round's map_name (match_id-equality dropped, "
             "Codex §18.4 — it compared two independently-generated IDs).",
    )
    parser.add_argument("--max-complete-missing-core", type=int, default=0)
    parser.add_argument(
        "--fail-on-breach",
        action="store_true",
        help="Exit non-zero when thresholds are breached.",
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    try:
        result = await assess_round_linkage_anomalies(
            adapter,
            sample_limit=args.sample_limit,
            thresholds={
                "max_unlinked_lua_ratio": args.max_unlinked_lua_ratio,
                "max_wrong_start_lua_rows": args.max_wrong_start_lua,
                "max_map_name_mismatch_rows": args.max_map_mismatch,
                "max_round_number_mismatch_rows": args.max_round_number_mismatch,
                "max_duplicate_lua_round_links": args.max_duplicate_links,
                "max_correlation_map_mismatch_rows": args.max_correlation_mismatch,
                "max_complete_missing_core_rows": args.max_complete_missing_core,
            },
        )
    finally:
        await adapter.close()

    print(json.dumps(result, indent=2, sort_keys=True))

    if result.get("status") == "error":
        return 1
    if args.fail_on_breach and result.get("breaches"):
        return 2
    return 0


def main() -> int:
    logger.info("Script started: %s", __file__)
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
