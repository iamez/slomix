#!/usr/bin/env python3
"""
Audit Round 1 / Round 2 pairing using the SAME logic as the parser.

Why this exists:
- R1 and R2 filenames never share timestamps (R2 happens later).
- Naive "same timestamp" pairing over-counts missing rounds.
- This script matches the bot's parser logic to avoid false "missing" reports.

Usage:
  PYTHONPATH=. python3 scripts/audit_round_pairs.py
  PYTHONPATH=. python3 scripts/audit_round_pairs.py --since-weeks 3
  PYTHONPATH=. python3 scripts/audit_round_pairs.py --stats-dir local_stats --window-minutes 60
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.config import BotConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d)\.txt$")


def parse_filename_dt(name: str) -> datetime | None:
    match = FILENAME_RE.match(name)
    if not match:
        return None
    date_str, time_str, _map, _round = match.groups()
    return datetime.strptime(date_str + time_str, "%Y-%m-%d%H%M%S")


def iter_round_files(stats_dir: Path) -> list[Path]:
    files = []
    for p in stats_dir.glob("*.txt"):
        name = p.name
        if name.endswith("_ws.txt") or name.endswith("-endstats.txt"):
            continue
        if not FILENAME_RE.match(name):
            continue
        files.append(p)
    return files


def main() -> int:
    logger.info("Script started: %s", __file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats-dir", default="local_stats")
    ap.add_argument("--since-weeks", type=int, default=3)
    ap.add_argument("--window-minutes", type=int, default=None)
    ap.add_argument("--out-dir", default="/tmp")
    args = ap.parse_args()

    stats_dir = Path(args.stats_dir)
    if not stats_dir.exists():
        raise SystemExit(f"Stats dir not found: {stats_dir}")

    config = BotConfig()
    window_minutes = args.window_minutes or config.round_match_window_minutes

    cutoff = datetime.now() - timedelta(weeks=args.since_weeks)
    parser = C0RNP0RN3StatsParser(round_match_window_minutes=window_minutes)

    all_files = iter_round_files(stats_dir)
    r1_files: list[Path] = []
    r2_files: list[Path] = []

    for p in all_files:
        dt = parse_filename_dt(p.name)
        if not dt or dt < cutoff:
            continue
        if "-round-1.txt" in p.name:
            r1_files.append(p)
        elif "-round-2.txt" in p.name:
            r2_files.append(p)

    matched_r1: set[str] = set()
    missing_r1_for_r2: list[str] = []

    for r2 in sorted(r2_files):
        r1 = parser.find_corresponding_round_1_file(str(r2))
        if r1:
            matched_r1.add(Path(r1).name)
        else:
            missing_r1_for_r2.append(r2.name)

    # R1s that are not matched by any R2 in-window
    missing_r2_for_r1 = [p.name for p in r1_files if p.name not in matched_r1]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "missing_r1_by_pairing.txt").write_text("\n".join(sorted(missing_r1_for_r2)))
    (out_dir / "missing_r2_by_pairing.txt").write_text("\n".join(sorted(missing_r2_for_r1)))

    print(f"cutoff: {cutoff.strftime('%Y-%m-%d')} | window_minutes: {window_minutes}")
    print(f"round2_without_r1: {len(missing_r1_for_r2)}")
    print(f"round1_without_r2: {len(missing_r2_for_r1)}")
    print(f"saved: {out_dir / 'missing_r1_by_pairing.txt'}")
    print(f"saved: {out_dir / 'missing_r2_by_pairing.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
