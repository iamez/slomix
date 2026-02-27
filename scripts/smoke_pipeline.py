#!/usr/bin/env python3
"""System smoke test for the stats pipeline (no website/proximity).

This script:
- Finds a matching R1/R2 stats file pair
- Parses both rounds (primary parser, fallback to retro parser)
- Computes a stopwatch score
- Optionally runs read-only SQLite DB checks if a DB file exists

Usage:
  python3 scripts/smoke_pipeline.py
"""

from __future__ import annotations

import glob
import os
import sys
from typing import Dict, Optional, Tuple

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _find_round_pair(search_dirs) -> Optional[Tuple[str, str]]:
    files = []
    for d in search_dirs:
        pattern = os.path.join(d, "*-round-*.txt")
        for path in glob.glob(pattern):
            name = os.path.basename(path)
            if "endstats" in name:
                continue
            if "_ws" in name:
                continue
            files.append(path)

    # Group by base (everything before "-round-")
    groups: Dict[str, Dict[str, str]] = {}
    for path in files:
        base, tail = path.rsplit("-round-", 1)
        round_str = tail.split(".", 1)[0]
        if round_str not in ("1", "2"):
            continue
        groups.setdefault(base, {})[round_str] = path

    # Choose most recent pair by base prefix (lexical == time order for format)
    candidate_bases = [b for b, rounds in groups.items() if "1" in rounds and "2" in rounds]
    if not candidate_bases:
        return None

    best_base = sorted(candidate_bases)[-1]
    return groups[best_base]["1"], groups[best_base]["2"]


def _parse_stats_file(path: str) -> Dict[str, object]:
    # Try primary parser first
    try:
        from bot.community_stats_parser import C0RNP0RN3StatsParser

        parser = C0RNP0RN3StatsParser()
        data = parser.parse_stats_file(path)
        if data and data.get("success"):
            return {
                "parser": "community_stats_parser",
                "map_name": data.get("map_name"),
                "round_num": data.get("round_num"),
                "map_time": data.get("map_time"),
                "actual_time": data.get("actual_time"),
                "players": data.get("total_players", 0),
            }
    except Exception as exc:
        print(f"WARN: community_stats_parser failed on {os.path.basename(path)}: {exc}")

    # Fallback parser (no discord dependency)
    try:
        from bot.retro_text_stats import parse_stats_file_complete

        data = parse_stats_file_complete(path)
        if data:
            return {
                "parser": "retro_text_stats",
                "map_name": data.get("map_name"),
                "round_num": data.get("round_num"),
                "map_time": data.get("duration"),
                "actual_time": data.get("actual_time"),
                "players": len(data.get("players", [])),
            }
    except Exception as exc:
        print(f"ERROR: retro_text_stats failed on {os.path.basename(path)}: {exc}")

    raise RuntimeError(f"Unable to parse stats file: {path}")


def _time_to_seconds(time_str: str) -> int:
    if not time_str:
        return 0
    parts = str(time_str).split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]) * 60 + int(parts[1])
    try:
        return int(float(time_str))
    except ValueError:
        return 0


def _run_scoring(round1: Dict[str, object], round2: Dict[str, object]) -> None:
    from bot.services.stopwatch_scoring_service import StopwatchScoringService

    scorer = StopwatchScoringService(db_adapter=None)
    team1_score, team2_score, desc = scorer.calculate_map_score(
        str(round1.get("map_time")),
        str(round1.get("actual_time")),
        str(round2.get("actual_time")),
    )

    print("\nScoring (stopwatch):")
    print(f"  Team1 (R1 attackers): {team1_score}")
    print(f"  Team2 (R2 attackers): {team2_score}")
    print(f"  Detail: {desc}")


def _sqlite_smoke() -> None:
    import sqlite3

    candidates = [
        os.path.join(ROOT, "etlegacy_production.db"),
        os.path.join(ROOT, "bot", "etlegacy_production.db"),
    ]
    db_path = next((p for p in candidates if os.path.exists(p)), None)
    if not db_path:
        print("\nDB Smoke: SKIPPED (no sqlite db found)")
        return

    print(f"\nDB Smoke: sqlite file found at {os.path.relpath(db_path, ROOT)}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Basic presence checks
    for table in ("rounds", "player_comprehensive_stats"):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        row = cur.fetchone()
        print(f"  Table {table}: {'OK' if row else 'MISSING'}")

    # Latest round summary
    try:
        cur.execute(
            """
            SELECT round_date, round_time, map_name, round_number
            FROM rounds
            ORDER BY round_date DESC, round_time DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            print(f"  Latest round: {row[0]} {row[1]} {row[2]} R{row[3]}")
        else:
            print("  Latest round: none")
    except Exception as exc:
        print(f"  Latest round: ERROR ({exc})")

    # Lua data presence (best effort)
    try:
        cur.execute("SELECT COUNT(*) FROM lua_round_teams")
        count = cur.fetchone()[0]
        print(f"  lua_round_teams rows: {count}")
    except Exception:
        print("  lua_round_teams rows: table missing or not populated")

    conn.close()


def main() -> int:
    logger.info("Script started: %s", __file__)
    print("=== Slomix System Smoke Test (no website/proximity) ===")

    search_dirs = [
        os.path.join(ROOT, "local_stats"),
        os.path.join(ROOT, "test_files"),
    ]

    pair = _find_round_pair(search_dirs)
    if not pair:
        print("ERROR: No R1/R2 stats file pair found in local_stats/ or test_files/")
        return 1

    r1_path, r2_path = pair
    print(f"Using round files:\n  R1: {os.path.relpath(r1_path, ROOT)}\n  R2: {os.path.relpath(r2_path, ROOT)}")

    r1 = _parse_stats_file(r1_path)
    r2 = _parse_stats_file(r2_path)

    print("\nParsed Round 1:")
    print(f"  Parser: {r1['parser']}")
    print(f"  Map: {r1['map_name']} | Round: {r1['round_num']} | Players: {r1['players']}")
    print(f"  Time limit: {r1['map_time']} | Actual: {r1['actual_time']}")

    print("\nParsed Round 2:")
    print(f"  Parser: {r2['parser']}")
    print(f"  Map: {r2['map_name']} | Round: {r2['round_num']} | Players: {r2['players']}")
    print(f"  Time limit: {r1['map_time']} | Actual: {r2['actual_time']}")

    # Basic sanity checks
    limit_sec = _time_to_seconds(str(r1.get("map_time")))
    r1_sec = _time_to_seconds(str(r1.get("actual_time")))
    r2_sec = _time_to_seconds(str(r2.get("actual_time")))
    if limit_sec > 0:
        if r1_sec > limit_sec:
            print("WARN: Round 1 actual_time exceeds time_limit")
        if r2_sec > limit_sec:
            print("WARN: Round 2 actual_time exceeds time_limit")

    _run_scoring(r1, r2)

    if os.environ.get("SMOKE_DB", "0") == "1":
        _sqlite_smoke()
    else:
        print("\nDB Smoke: SKIPPED (set SMOKE_DB=1 to enable sqlite checks)")

    print("\nOK: Smoke test completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
