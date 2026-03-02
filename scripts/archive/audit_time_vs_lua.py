#!/usr/bin/env python3
"""
Full audit: compare raw Lua stats files vs DB time fields.

Checks:
- time_dead_minutes (Lua) vs DB
- denied_playtime (Lua seconds) vs DB
- time_played_seconds (Lua) vs DB
- ratio sanity (computed vs stored)

Outputs JSON report with summary + sample mismatches.
"""

import argparse
import asyncio
import glob
import json
import logging
import os
import sys
from datetime import datetime

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bot.automation.ssh_handler import SSHHandler
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.config import BotConfig
from bot.core.database_adapter import PostgreSQLAdapter
from bot.core.round_linker import resolve_round_id


def parse_args():
    parser = argparse.ArgumentParser(description="Audit Lua time fields vs DB.")
    parser.add_argument("--stats-dir", default=None, help="Stats directory (default from config).")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files (0 = all).")
    parser.add_argument("--dead-diff-min", type=float, default=0.05, help="Dead minutes diff threshold.")
    parser.add_argument("--denied-diff-sec", type=float, default=2.0, help="Denied seconds diff threshold.")
    parser.add_argument("--played-diff-sec", type=float, default=2.0, help="Played seconds diff threshold.")
    parser.add_argument("--ratio-diff", type=float, default=5.0, help="Ratio diff threshold (percent).")
    parser.add_argument("--max-samples", type=int, default=50, help="Max mismatch samples to store.")
    parser.add_argument("--output", default=None, help="Output JSON path (default: docs/time_audit_report_YYYY-MM-DD.json).")
    return parser.parse_args()


def iter_stats_files(stats_dir: str):
    pattern = os.path.join(stats_dir, "*.txt")
    files = [f for f in glob.glob(pattern)]
    files = [
        f for f in files
        if not f.endswith("-endstats.txt")
        and not f.endswith("_ws.txt")
        and "endstats" not in os.path.basename(f)
    ]
    return sorted(files)


async def main():
    args = parse_args()

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("bot.community_stats_parser").setLevel(logging.WARNING)
    logging.getLogger("bot.core.round_linker").setLevel(logging.WARNING)

    config = BotConfig()
    stats_dir = args.stats_dir or config.stats_directory or config.local_stats_path or "local_stats"
    if not os.path.isabs(stats_dir):
        stats_dir = os.path.join(os.getcwd(), stats_dir)
    if not os.path.isdir(stats_dir):
        raise SystemExit(f"Stats directory not found: {stats_dir}")

    files = iter_stats_files(stats_dir)
    if args.limit and args.limit > 0:
        files = files[-args.limit:]

    parser = C0RNP0RN3StatsParser()

    db = PostgreSQLAdapter(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password,
        min_pool_size=config.postgres_min_pool,
        max_pool_size=config.postgres_max_pool,
        ssl_mode=config.postgres_ssl_mode,
        ssl_cert=config.postgres_ssl_cert,
        ssl_key=config.postgres_ssl_key,
        ssl_root_cert=config.postgres_ssl_root_cert,
    )
    await db.connect()

    summary = {
        "files_total": len(files),
        "files_parsed": 0,
        "files_parse_errors": 0,
        "files_missing_round": 0,
        "rounds_matched": 0,
        "players_total": 0,
        "players_missing_db": 0,
        "players_mismatched": 0,
        "dead_gt_played": 0,
        "denied_gt_played": 0,
        "ratio_mismatch": 0,
        "map_name_mismatch": 0,
        "diff_dead": 0,
        "diff_denied": 0,
        "diff_played": 0,
        "ratio_mismatch_r1": 0,
        "ratio_mismatch_r2": 0,
        "ratio_mismatch_other": 0,
    }
    flag_counts = {}
    samples = []
    parse_errors = []
    missing_rounds = []

    for idx, path in enumerate(files, start=1):
        filename = os.path.basename(path)
        meta = SSHHandler.parse_gamestats_filename(filename)
        if not meta:
            summary["files_parse_errors"] += 1
            parse_errors.append({"file": filename, "error": "bad_filename"})
            continue

        result = parser.parse_stats_file(path)
        if not result.get("success"):
            summary["files_parse_errors"] += 1
            parse_errors.append({"file": filename, "error": result.get("error", "parse_failed")})
            continue

        summary["files_parsed"] += 1

        map_name = result.get("map_name")
        round_num = result.get("round_num")
        is_round_2 = int(round_num or 0) == 2
        is_differential = bool(result.get("differential_calculation"))
        if map_name and meta.get("map_name") and map_name != meta.get("map_name"):
            summary["map_name_mismatch"] += 1

        round_id = await resolve_round_id(
            db,
            map_name,
            int(round_num or 0),
            round_date=meta.get("date"),
            round_time=meta.get("time"),
            window_minutes=getattr(config, "round_match_window_minutes", 45),
        )
        if not round_id:
            summary["files_missing_round"] += 1
            missing_rounds.append(
                {
                    "file": filename,
                    "map_name": map_name,
                    "round_number": round_num,
                    "round_date": meta.get("date"),
                    "round_time": meta.get("time"),
                }
            )
            continue

        summary["rounds_matched"] += 1

        rows = await db.fetch_all(
            """
            SELECT player_guid, player_name, clean_name,
                   time_dead_minutes, denied_playtime,
                   time_played_seconds, time_dead_ratio
            FROM player_comprehensive_stats
            WHERE round_id = ?
            """,
            (round_id,),
        )

        db_by_guid = {}
        db_by_clean = {}
        for row in rows:
            guid, player_name, clean_name, dead_min, denied, played_sec, ratio = row
            if guid:
                db_by_guid[str(guid).upper()] = row
            if clean_name:
                db_by_clean[str(clean_name).lower()] = row

        for player in result.get("players", []):
            summary["players_total"] += 1
            guid = str(player.get("guid", "") or "").upper()
            name = player.get("name") or ""
            clean = parser.strip_color_codes(name).lower()
            obj = player.get("objective_stats", {}) or {}

            lua_dead = float(obj.get("time_dead_minutes", 0) or 0)
            lua_denied = float(obj.get("denied_playtime", 0) or 0)
            lua_played = float(player.get("time_played_seconds", 0) or 0)
            lua_ratio = float(obj.get("time_dead_ratio", 0) or 0)

            row = db_by_guid.get(guid) or db_by_clean.get(clean)
            if not row:
                summary["players_missing_db"] += 1
                if len(samples) < args.max_samples:
                    samples.append(
                        {
                            "type": "missing_db",
                            "file": filename,
                            "round_id": round_id,
                            "player_guid": guid,
                            "player_name": name,
                            "lua": {
                                "time_dead_minutes": lua_dead,
                                "denied_playtime": lua_denied,
                                "time_played_seconds": lua_played,
                                "time_dead_ratio": lua_ratio,
                            },
                        }
                    )
                continue

            db_dead = float(row[3] or 0)
            db_denied = float(row[4] or 0)
            db_played = float(row[5] or 0)
            db_ratio = float(row[6] or 0)

            dead_diff = abs(db_dead - lua_dead)
            denied_diff = abs(db_denied - lua_denied)
            played_diff = abs(db_played - lua_played)

            ratio_calc = None
            ratio_diff = None
            if lua_played > 0:
                ratio_calc = (lua_dead * 60.0 / lua_played) * 100.0
                ratio_diff = abs(db_ratio - ratio_calc)

            flags = []
            if dead_diff > args.dead_diff_min:
                summary["diff_dead"] += 1
                flags.append("dead_diff")
            if denied_diff > args.denied_diff_sec:
                summary["diff_denied"] += 1
                flags.append("denied_diff")
            if played_diff > args.played_diff_sec:
                summary["diff_played"] += 1
                flags.append("played_diff")
            if ratio_diff is not None and ratio_diff > args.ratio_diff:
                flags.append("ratio_diff")
                if is_round_2 and is_differential:
                    summary["ratio_mismatch_r2"] += 1
                elif int(round_num or 0) == 1:
                    summary["ratio_mismatch_r1"] += 1
                else:
                    summary["ratio_mismatch_other"] += 1

            if lua_played > 0 and (lua_dead * 60.0) > lua_played + 1:
                summary["dead_gt_played"] += 1
                flags.append("lua_dead_gt_played")
            if db_played > 0 and (db_dead * 60.0) > db_played + 1:
                summary["dead_gt_played"] += 1
                flags.append("db_dead_gt_played")
            if lua_played > 0 and lua_denied > lua_played + 1:
                summary["denied_gt_played"] += 1
                flags.append("lua_denied_gt_played")
            if db_played > 0 and db_denied > db_played + 1:
                summary["denied_gt_played"] += 1
                flags.append("db_denied_gt_played")

            if flags:
                summary["players_mismatched"] += 1
                if "ratio_diff" in flags:
                    summary["ratio_mismatch"] += 1
                for f in flags:
                    flag_counts[f] = flag_counts.get(f, 0) + 1
                if len(samples) < args.max_samples:
                    samples.append(
                        {
                            "type": "mismatch",
                            "file": filename,
                            "round_id": round_id,
                            "player_guid": guid,
                            "player_name": name,
                            "flags": flags,
                            "lua": {
                                "time_dead_minutes": lua_dead,
                                "denied_playtime": lua_denied,
                                "time_played_seconds": lua_played,
                                "time_dead_ratio": lua_ratio,
                                "ratio_calc": round(ratio_calc, 2) if ratio_calc is not None else None,
                            },
                            "db": {
                                "time_dead_minutes": db_dead,
                                "denied_playtime": db_denied,
                                "time_played_seconds": db_played,
                                "time_dead_ratio": db_ratio,
                            },
                            "diffs": {
                                "dead_minutes": round(dead_diff, 4),
                                "denied_seconds": round(denied_diff, 2),
                                "played_seconds": round(played_diff, 2),
                                "ratio": round(ratio_diff, 2) if ratio_diff is not None else None,
                            },
                        }
                    )

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "stats_dir": stats_dir,
        "thresholds": {
            "dead_diff_min": args.dead_diff_min,
            "denied_diff_sec": args.denied_diff_sec,
            "played_diff_sec": args.played_diff_sec,
            "ratio_diff": args.ratio_diff,
        },
        "summary": summary,
        "flag_counts": flag_counts,
        "parse_errors": parse_errors[: args.max_samples],
        "missing_rounds": missing_rounds[: args.max_samples],
        "samples": samples,
    }

    output = args.output
    if not output:
        date_tag = datetime.utcnow().strftime("%Y-%m-%d")
        output = os.path.join("docs", f"time_audit_report_{date_tag}.json")

    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote report: {output}")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
