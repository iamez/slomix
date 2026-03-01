#!/usr/bin/env python3
"""slomix_audit.py — Unified audit tool for Slomix pipeline verification.

Consolidates 5 audit/verification scripts into a single CLI with subcommands:
  slomix_audit.py round-pairs [--stats-dir] [--since-weeks N] [--window-minutes N] [--out-dir]
  slomix_audit.py time-vs-lua [--stats-dir] [--limit N] [--dead-diff-min F] [--denied-diff-sec F] [--played-diff-sec F] [--ratio-diff F] [--max-samples N] [--output PATH]
  slomix_audit.py pipeline-health [-n N]
  slomix_audit.py proximity-schema
  slomix_audit.py pipeline-verify

All scripts use .env for database configuration (DB_HOST, DB_USER, etc).
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Setup sys.path and load .env
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from bot.config import BotConfig
from bot.core.database_adapter import PostgreSQLAdapter
from bot.automation.ssh_handler import SSHHandler
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.core.round_linker import resolve_round_id

# ============================================================================
# SUBCOMMAND: round-pairs
# ============================================================================

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d)\.txt$")


def _parse_filename_dt(name: str) -> Optional[datetime]:
    match = FILENAME_RE.match(name)
    if not match:
        return None
    date_str, time_str, _map, _round = match.groups()
    return datetime.strptime(date_str + time_str, "%Y-%m-%d%H%M%S")


def _iter_round_files(stats_dir: Path) -> List[Path]:
    files = []
    for p in stats_dir.glob("*.txt"):
        name = p.name
        if name.endswith("_ws.txt") or name.endswith("-endstats.txt"):
            continue
        if not FILENAME_RE.match(name):
            continue
        files.append(p)
    return files


def audit_round_pairs(
    stats_dir: str,
    since_weeks: int = 3,
    window_minutes: Optional[int] = None,
    out_dir: str = "/tmp",
) -> int:
    from bot.community_stats_parser import C0RNP0RN3StatsParser
    from bot.config import BotConfig

    stats_path = Path(stats_dir)
    if not stats_path.exists():
        raise SystemExit(f"Stats dir not found: {stats_path}")

    config = BotConfig()
    wm = window_minutes or config.round_match_window_minutes

    cutoff = datetime.now() - timedelta(weeks=since_weeks)
    parser = C0RNP0RN3StatsParser(round_match_window_minutes=wm)

    all_files = _iter_round_files(stats_path)
    r1_files: List[Path] = []
    r2_files: List[Path] = []

    for p in all_files:
        dt = _parse_filename_dt(p.name)
        if not dt or dt < cutoff:
            continue
        if "-round-1.txt" in p.name:
            r1_files.append(p)
        elif "-round-2.txt" in p.name:
            r2_files.append(p)

    matched_r1: Set[str] = set()
    missing_r1_for_r2: List[str] = []

    for r2 in sorted(r2_files):
        r1 = parser.find_corresponding_round_1_file(str(r2))
        if r1:
            matched_r1.add(Path(r1).name)
        else:
            missing_r1_for_r2.append(r2.name)

    # R1s that are not matched by any R2 in-window
    missing_r2_for_r1 = [p.name for p in r1_files if p.name not in matched_r1]

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    (out_path / "missing_r1_by_pairing.txt").write_text("\n".join(sorted(missing_r1_for_r2)))
    (out_path / "missing_r2_by_pairing.txt").write_text("\n".join(sorted(missing_r2_for_r1)))

    print(f"cutoff: {cutoff.strftime('%Y-%m-%d')} | window_minutes: {wm}")
    print(f"round2_without_r1: {len(missing_r1_for_r2)}")
    print(f"round1_without_r2: {len(missing_r2_for_r1)}")
    print(f"saved: {out_path / 'missing_r1_by_pairing.txt'}")
    print(f"saved: {out_path / 'missing_r2_by_pairing.txt'}")
    return 0


def cmd_round_pairs(args):
    return audit_round_pairs(
        args.stats_dir,
        since_weeks=args.since_weeks,
        window_minutes=args.window_minutes,
        out_dir=args.out_dir,
    )

# ============================================================================
# SUBCOMMAND: time-vs-lua
# ============================================================================


def _iter_stats_files(stats_dir: str):
    pattern = os.path.join(stats_dir, "*.txt")
    files = [f for f in glob.glob(pattern)]
    files = [
        f for f in files
        if not f.endswith("-endstats.txt")
        and not f.endswith("_ws.txt")
        and "endstats" not in os.path.basename(f)
    ]
    return sorted(files)


async def audit_time_vs_lua(
    stats_dir: Optional[str] = None,
    limit: int = 0,
    dead_diff_min: float = 0.05,
    denied_diff_sec: float = 2.0,
    played_diff_sec: float = 2.0,
    ratio_diff: float = 5.0,
    max_samples: int = 50,
    output: Optional[str] = None,
) -> int:
    from bot.automation.ssh_handler import SSHHandler
    from bot.community_stats_parser import C0RNP0RN3StatsParser
    from bot.config import BotConfig
    from bot.core.database_adapter import PostgreSQLAdapter
    from bot.core.round_linker import resolve_round_id

    logging.getLogger("bot.community_stats_parser").setLevel(logging.WARNING)
    logging.getLogger("bot.core.round_linker").setLevel(logging.WARNING)

    config = BotConfig()
    sd = stats_dir or getattr(config, 'stats_directory', None) or getattr(config, 'local_stats_path', None) or "local_stats"
    if not os.path.isabs(sd):
        sd = os.path.join(os.getcwd(), sd)
    if not os.path.isdir(sd):
        raise SystemExit(f"Stats directory not found: {sd}")

    files = _iter_stats_files(sd)
    if limit and limit > 0:
        files = files[-limit:]

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
            WHERE round_id = $1
            """,
            (round_id,),
        )

        db_by_guid = {}
        db_by_clean = {}
        for row in rows:
            guid, player_name, clean_name, dead_min, denied, played_sec, ratio_val = row
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
                if len(samples) < max_samples:
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

            dead_d = abs(db_dead - lua_dead)
            denied_d = abs(db_denied - lua_denied)
            played_d = abs(db_played - lua_played)

            ratio_calc = None
            ratio_d = None
            if lua_played > 0:
                ratio_calc = (lua_dead * 60.0 / lua_played) * 100.0
                ratio_d = abs(db_ratio - ratio_calc)

            flags = []
            if dead_d > dead_diff_min:
                summary["diff_dead"] += 1
                flags.append("dead_diff")
            if denied_d > denied_diff_sec:
                summary["diff_denied"] += 1
                flags.append("denied_diff")
            if played_d > played_diff_sec:
                summary["diff_played"] += 1
                flags.append("played_diff")
            if ratio_d is not None and ratio_d > ratio_diff:
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
                if len(samples) < max_samples:
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
                                "dead_minutes": round(dead_d, 4),
                                "denied_seconds": round(denied_d, 2),
                                "played_seconds": round(played_d, 2),
                                "ratio": round(ratio_d, 2) if ratio_d is not None else None,
                            },
                        }
                    )

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "stats_dir": sd,
        "thresholds": {
            "dead_diff_min": dead_diff_min,
            "denied_diff_sec": denied_diff_sec,
            "played_diff_sec": played_diff_sec,
            "ratio_diff": ratio_diff,
        },
        "summary": summary,
        "flag_counts": flag_counts,
        "parse_errors": parse_errors[:max_samples],
        "missing_rounds": missing_rounds[:max_samples],
        "samples": samples,
    }

    out = output
    if not out:
        date_tag = datetime.utcnow().strftime("%Y-%m-%d")
        out = os.path.join("docs", f"time_audit_report_{date_tag}.json")

    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote report: {out}")
    await db.close()
    return 0


def cmd_time_vs_lua(args):
    return asyncio.run(
        audit_time_vs_lua(
            stats_dir=args.stats_dir,
            limit=args.limit,
            dead_diff_min=args.dead_diff_min,
            denied_diff_sec=args.denied_diff_sec,
            played_diff_sec=args.played_diff_sec,
            ratio_diff=args.ratio_diff,
            max_samples=args.max_samples,
            output=args.output,
        )
    )

# ============================================================================
# SUBCOMMAND: pipeline-health
# ============================================================================


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_age(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 0:
        seconds = 0
    total = int(seconds)
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d{hours:02d}h"
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{sec:02d}s"


def _parse_round_timestamp(round_end_unix, round_date, round_time) -> datetime | None:
    if round_end_unix:
        try:
            return datetime.fromtimestamp(int(round_end_unix), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass

    if not round_date:
        return None

    time_value = (round_time or "00:00:00").strip()
    candidates = (
        f"{round_date} {time_value}",
        f"{round_date} {time_value}:00",
    )
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    )
    for text in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _normalize_db_datetime(value) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _run_pipeline_health(limit: int) -> int:
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

    query = """
        WITH recent_rounds AS (
            SELECT
                r.id AS round_id,
                r.map_name,
                r.round_number,
                r.round_date,
                r.round_time,
                r.round_status,
                r.round_end_unix
            FROM rounds r
            ORDER BY r.id DESC
            LIMIT $1
        ),
        stats_counts AS (
            SELECT
                p.round_id,
                COUNT(*)::int AS stats_rows
            FROM player_comprehensive_stats p
            WHERE p.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY p.round_id
        ),
        lua_counts AS (
            SELECT
                l.round_id,
                COUNT(*)::int AS lua_rows,
                MAX(l.captured_at) AS lua_last_captured_at
            FROM lua_round_teams l
            WHERE l.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY l.round_id
        ),
        endstats_flags AS (
            SELECT
                p.round_id,
                BOOL_OR(p.success) AS endstats_processed,
                MAX(p.processed_at) AS endstats_processed_at
            FROM processed_endstats_files p
            WHERE p.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY p.round_id
        ),
        awards_counts AS (
            SELECT
                a.round_id,
                COUNT(*)::int AS awards_rows
            FROM round_awards a
            WHERE a.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY a.round_id
        ),
        vs_counts AS (
            SELECT
                v.round_id,
                COUNT(*)::int AS vs_rows
            FROM round_vs_stats v
            WHERE v.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY v.round_id
        )
        SELECT
            rr.round_id,
            rr.map_name,
            rr.round_number,
            rr.round_date,
            rr.round_time,
            rr.round_status,
            rr.round_end_unix,
            COALESCE(sc.stats_rows, 0) AS stats_rows,
            COALESCE(lc.lua_rows, 0) AS lua_rows,
            COALESCE(ef.endstats_processed, FALSE) AS endstats_processed,
            ef.endstats_processed_at,
            lc.lua_last_captured_at,
            COALESCE(ac.awards_rows, 0) AS awards_rows,
            COALESCE(vc.vs_rows, 0) AS vs_rows
        FROM recent_rounds rr
        LEFT JOIN stats_counts sc ON sc.round_id = rr.round_id
        LEFT JOIN lua_counts lc ON lc.round_id = rr.round_id
        LEFT JOIN endstats_flags ef ON ef.round_id = rr.round_id
        LEFT JOIN awards_counts ac ON ac.round_id = rr.round_id
        LEFT JOIN vs_counts vc ON vc.round_id = rr.round_id
        ORDER BY rr.round_id DESC
    """

    try:
        rows = await adapter.fetch_all(query, (limit,))
    finally:
        await adapter.close()

    now = datetime.now(timezone.utc)
    print(f"Pipeline Health Report - {now.isoformat()}")
    print(f"Rounds inspected: {len(rows)}")
    print(
        "ID    Map           R  Status         Stats Lua Endstats EndRows RoundAge  LuaAge    EndstatsAge"
    )
    print(
        "----  ------------  -  -------------  ----- --- -------- ------- --------  --------  -----------"
    )

    complete_rounds = 0
    for row in rows:
        (round_id, map_name, round_number, round_date, round_time, round_status,
         round_end_unix, stats_rows, lua_rows, endstats_processed,
         endstats_processed_at, lua_last_captured_at, awards_rows, vs_rows) = row

        map_name = (map_name or "unknown")[:12]
        round_number = round_number or 0
        status = round_status if round_status is not None else "null"
        stats_rows = int(stats_rows or 0)
        lua_rows = int(lua_rows or 0)
        endstats_processed = bool(endstats_processed)
        endstats_rows = int(awards_rows or 0) + int(vs_rows or 0)

        stats_imported = stats_rows > 0
        lua_linked = lua_rows > 0
        if stats_imported and lua_linked and endstats_processed and endstats_rows > 0:
            complete_rounds += 1

        round_ts = _parse_round_timestamp(
            round_end_unix, round_date, round_time
        )
        round_age = _format_age((now - round_ts).total_seconds()) if round_ts else "-"

        lua_age = None
        lua_last_captured_at = _normalize_db_datetime(lua_last_captured_at)
        if lua_last_captured_at:
            lua_age = (now - lua_last_captured_at).total_seconds()

        endstats_age = None
        endstats_processed_at = _normalize_db_datetime(endstats_processed_at)
        if endstats_processed_at:
            endstats_age = (now - endstats_processed_at).total_seconds()

        print(
            f"{round_id:>4}  "
            f"{map_name:<12}  "
            f"{round_number:>1}  "
            f"{status:<13}  "
            f"{_format_bool(stats_imported):>5} "
            f"{_format_bool(lua_linked):>3} "
            f"{_format_bool(endstats_processed):>8} "
            f"{endstats_rows:>7} "
            f"{round_age:>8}  "
            f"{_format_age(lua_age):>8}  "
            f"{_format_age(endstats_age):>11}"
        )

    print("")
    print(
        f"Complete rounds (all stages + endstats rows): {complete_rounds}/{len(rows)}"
    )
    return 0


def cmd_pipeline_health(args):
    limit = max(1, int(args.limit))
    return asyncio.run(_run_pipeline_health(limit))

# ============================================================================
# SUBCOMMAND: proximity-schema
# ============================================================================


def _load_env_dict(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


async def _check_proximity_db(env: dict) -> None:
    try:
        import asyncpg  # type: ignore
    except Exception as exc:
        print(f"[WARN] asyncpg not available: {exc}")
        return

    required = [
        ("combat_engagement", "round_start_unix"),
        ("combat_engagement", "round_end_unix"),
        ("player_track", "round_start_unix"),
        ("player_track", "round_end_unix"),
        ("proximity_objective_focus", "round_start_unix"),
        ("proximity_objective_focus", "round_end_unix"),
    ]

    host = env.get("POSTGRES_HOST", "localhost")
    port = int(env.get("POSTGRES_PORT", "5432"))
    database = env.get("POSTGRES_DATABASE", "etlegacy")
    user = env.get("POSTGRES_USER", "etlegacy_user")
    password = env.get("POSTGRES_PASSWORD", "")

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except Exception as exc:
        print(f"[WARN] Could not connect to Postgres: {exc}")
        return

    try:
        for table, column in required:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = $1 AND column_name = $2
                """,
                table,
                column,
            )
            status = "OK" if row else "MISSING"
            print(f"[DB] {table}.{column}: {status}")
    finally:
        await conn.close()


def _check_sample_parse() -> None:
    try:
        from proximity.parser.parser import ProximityParserV4
    except Exception as exc:
        print(f"[WARN] ProximityParserV4 import failed: {exc}")
        return

    sample_path = Path("proximity/sample_engagements.txt")
    if not sample_path.exists():
        print("[WARN] Sample engagement file not found.")
        return

    parser = ProximityParserV4(db_adapter=None, output_dir=str(sample_path.parent))
    if parser.parse_file(str(sample_path)):
        print("[OK] Parsed sample engagement file.")
        print(f"     map={parser.metadata.get('map_name')} round={parser.metadata.get('round_num')}")
        print(f"     round_start_unix={parser.metadata.get('round_start_unix')} round_end_unix={parser.metadata.get('round_end_unix')}")
        print(f"     engagements={len(parser.engagements)} tracks={len(parser.player_tracks)}")
    else:
        print("[WARN] Failed to parse sample engagement file.")


def cmd_proximity_schema(args):
    env = _load_env_dict(ROOT / ".env")
    print("[INFO] Proximity schema verification")
    _check_sample_parse()
    asyncio.run(_check_proximity_db(env))
    return 0

# ============================================================================
# SUBCOMMAND: pipeline-verify
# ============================================================================


def _get_psycopg2_connection():
    """Get PostgreSQL connection using .env or environment variables."""
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


class PipelineVerifier:
    """Runs pipeline verification checks and reports results."""

    WARN_STALENESS_DAYS = 7
    FAIL_STALENESS_DAYS = 30

    def __init__(self):
        self.results = []
        self.conn = None

    def record(self, name, status, detail=""):
        self.results.append((name, status, detail))

    def check_db_connectivity(self):
        """Check 1: Can we connect to PostgreSQL?"""
        try:
            self.conn = _get_psycopg2_connection()
            self.conn.autocommit = True
            cur = self.conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            cur.close()
            self.record("DB Connectivity", "PASS", version.split(",")[0])
        except Exception as e:
            self.record("DB Connectivity", "FAIL", str(e))

    def check_recent_rounds(self):
        """Check 2: Are there rounds in the DB? What's the latest?"""
        if not self.conn:
            self.record("Recent Rounds", "SKIP", "No DB connection")
            return None

        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*), MAX(round_date), MAX(gaming_session_id) FROM rounds;"
        )
        count, latest_date, max_session = cur.fetchone()
        cur.close()

        if count == 0:
            self.record("Recent Rounds", "FAIL", "No rounds in database")
            return None

        self.record(
            "Recent Rounds",
            "PASS",
            f"{count} rounds, latest: {latest_date}, max session: {max_session}",
        )
        return latest_date

    def check_r1_r2_pairing(self):
        """Check 3: Do recent rounds have proper R1+R2 matches?"""
        if not self.conn:
            self.record("R1/R2 Pairing", "SKIP", "No DB connection")
            return

        cur = self.conn.cursor()
        cur.execute("""
            SELECT match_id,
                   array_agg(DISTINCT round_number ORDER BY round_number) AS rounds
            FROM rounds
            WHERE match_id IS NOT NULL AND round_number IN (1, 2)
            GROUP BY match_id
            ORDER BY match_id DESC
            LIMIT 20;
        """)
        rows = cur.fetchall()
        cur.close()

        if not rows:
            self.record("R1/R2 Pairing", "FAIL", "No matches found with R1/R2")
            return

        paired = sum(1 for _, rounds in rows if rounds == [1, 2])
        r1_only = sum(1 for _, rounds in rows if rounds == [1])
        total = len(rows)

        status = "PASS" if paired > 0 else "WARN"
        self.record(
            "R1/R2 Pairing",
            status,
            f"{paired}/{total} recent matches fully paired, {r1_only} R1-only",
        )

    def check_lua_webhook_data(self):
        """Check 4: Is there data in lua_round_teams? What's the latest?"""
        if not self.conn:
            self.record("Lua Webhook Data", "SKIP", "No DB connection")
            return None

        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*), MAX(captured_at) FROM lua_round_teams;"
        )
        count, latest_captured = cur.fetchone()
        cur.close()

        if count == 0:
            self.record("Lua Webhook Data", "WARN", "No data in lua_round_teams")
            return None

        self.record(
            "Lua Webhook Data",
            "PASS",
            f"{count} entries, latest captured: {latest_captured}",
        )
        return latest_captured

    def check_cross_reference(self):
        """Check 5: Do lua_round_teams entries match rounds table entries?"""
        if not self.conn:
            self.record("Cross-Reference", "SKIP", "No DB connection")
            return

        cur = self.conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) AS total_lua,
                COUNT(lrt.round_id) AS with_round_id,
                COUNT(r.id) AS matched_rounds
            FROM lua_round_teams lrt
            LEFT JOIN rounds r ON lrt.round_id = r.id;
        """)
        total_lua, with_round_id, matched = cur.fetchone()
        cur.close()

        if total_lua == 0:
            self.record("Cross-Reference", "WARN", "No lua data to cross-reference")
            return

        unlinked = total_lua - with_round_id
        orphaned = with_round_id - matched

        if orphaned > 0:
            status = "WARN"
            detail = (
                f"{matched}/{total_lua} linked to rounds, "
                f"{orphaned} orphaned round_id refs"
            )
        elif unlinked > 0:
            status = "PASS"
            detail = (
                f"{matched}/{total_lua} linked, "
                f"{unlinked} without round_id (may be unmatched)"
            )
        else:
            status = "PASS"
            detail = f"All {total_lua} lua entries linked to valid rounds"

        self.record("Cross-Reference", status, detail)

    def check_staleness(self, latest_round_date):
        """Check 6: How old is the newest data?"""
        if latest_round_date is None:
            self.record("Data Staleness", "FAIL", "No round data to check")
            return

        today = datetime.now().date()
        if isinstance(latest_round_date, str):
            latest_round_date = datetime.strptime(
                latest_round_date, "%Y-%m-%d"
            ).date()
        age_days = (today - latest_round_date).days

        if age_days > self.FAIL_STALENESS_DAYS:
            status = "FAIL"
        elif age_days > self.WARN_STALENESS_DAYS:
            status = "WARN"
        else:
            status = "PASS"

        self.record(
            "Data Staleness",
            status,
            f"Latest round: {latest_round_date} ({age_days} days ago)",
        )

    def run_all(self):
        """Run all checks and print report."""
        print("=" * 60)
        print("  ET:Legacy Pipeline Verification (WS1-007)")
        print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print()

        self.check_db_connectivity()
        latest_date = self.check_recent_rounds()
        self.check_r1_r2_pairing()
        self.check_lua_webhook_data()
        self.check_cross_reference()
        self.check_staleness(latest_date)

        if self.conn:
            self.conn.close()

        # Print results
        has_fail = False
        has_warn = False
        for name, status, detail in self.results:
            icon = {"PASS": "\u2713", "FAIL": "\u2717", "WARN": "!", "SKIP": "-"}[status]
            color_status = f"[{status}]"
            print(f"  {icon} {color_status:8s} {name}: {detail}")
            if status == "FAIL":
                has_fail = True
            if status == "WARN":
                has_warn = True

        print()
        if has_fail:
            print("RESULT: FAIL \u2014 Pipeline has critical issues")
            return 1
        elif has_warn:
            print("RESULT: PASS with warnings")
            return 0
        else:
            print("RESULT: PASS \u2014 Pipeline verified")
            return 0


def cmd_pipeline_verify(args):
    verifier = PipelineVerifier()
    return verifier.run_all()

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified audit tool for Slomix pipeline verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/slomix_audit.py round-pairs --since-weeks 4
  python tools/slomix_audit.py time-vs-lua --limit 50 --output /tmp/audit.json
  python tools/slomix_audit.py pipeline-health -n 30
  python tools/slomix_audit.py proximity-schema
  python tools/slomix_audit.py pipeline-verify
        """
    )

    subs = parser.add_subparsers(dest='command', required=True, help='Audit subcommand')

    # ROUND-PAIRS subcommand
    sub = subs.add_parser('round-pairs', help='Audit R1/R2 round pairing from stats files')
    sub.add_argument('--stats-dir', default='local_stats', help='Stats directory')
    sub.add_argument('--since-weeks', type=int, default=3, help='Only look at files from last N weeks')
    sub.add_argument('--window-minutes', type=int, default=None, help='R1-R2 matching window (default from config)')
    sub.add_argument('--out-dir', default='/tmp', help='Output directory for missing-file lists')
    sub.set_defaults(func=cmd_round_pairs)

    # TIME-VS-LUA subcommand
    sub = subs.add_parser('time-vs-lua', help='Audit Lua time fields vs DB values')
    sub.add_argument('--stats-dir', default=None, help='Stats directory (default from config)')
    sub.add_argument('--limit', type=int, default=0, help='Limit number of files (0 = all)')
    sub.add_argument('--dead-diff-min', type=float, default=0.05, help='Dead minutes diff threshold')
    sub.add_argument('--denied-diff-sec', type=float, default=2.0, help='Denied seconds diff threshold')
    sub.add_argument('--played-diff-sec', type=float, default=2.0, help='Played seconds diff threshold')
    sub.add_argument('--ratio-diff', type=float, default=5.0, help='Ratio diff threshold (percent)')
    sub.add_argument('--max-samples', type=int, default=50, help='Max mismatch samples to store')
    sub.add_argument('--output', default=None, help='Output JSON path (default: docs/time_audit_report_YYYY-MM-DD.json)')
    sub.set_defaults(func=cmd_time_vs_lua)

    # PIPELINE-HEALTH subcommand
    sub = subs.add_parser('pipeline-health', help='Show stage completeness/freshness for recent rounds')
    sub.add_argument('-n', '--limit', type=int,
                     default=int(os.environ.get("PIPELINE_HEALTH_LIMIT", "20")),
                     help='Number of most recent rounds to inspect (default: 20)')
    sub.set_defaults(func=cmd_pipeline_health)

    # PROXIMITY-SCHEMA subcommand
    sub = subs.add_parser('proximity-schema', help='Verify proximity schema readiness and sample parsing')
    sub.set_defaults(func=cmd_proximity_schema)

    # PIPELINE-VERIFY subcommand
    sub = subs.add_parser('pipeline-verify', help='Pipeline verification gate check (WS1-007)')
    sub.set_defaults(func=cmd_pipeline_verify)

    args = parser.parse_args()
    logger.info("Script started: %s with command: %s", __file__, args.command)

    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
