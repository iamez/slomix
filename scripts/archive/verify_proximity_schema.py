#!/usr/bin/env python3
"""
Verify proximity schema readiness and sample parsing.

Usage:
  python scripts/verify_proximity_schema.py
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def load_env(path: Path) -> dict:
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


async def check_db(env: dict) -> None:
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


def check_sample_parse() -> None:
    try:
        from proximity.parser import ProximityParserV3
    except Exception as exc:
        print(f"[WARN] ProximityParserV3 import failed: {exc}")
        return

    sample_path = Path("proximity/sample_engagements.txt")
    if not sample_path.exists():
        print("[WARN] Sample engagement file not found.")
        return

    parser = ProximityParserV3(db_adapter=None, output_dir=str(sample_path.parent))
    if parser.parse_file(str(sample_path)):
        print("[OK] Parsed sample engagement file.")
        print(f"     map={parser.metadata.get('map_name')} round={parser.metadata.get('round_num')}")
        print(f"     round_start_unix={parser.metadata.get('round_start_unix')} round_end_unix={parser.metadata.get('round_end_unix')}")
        print(f"     engagements={len(parser.engagements)} tracks={len(parser.player_tracks)}")
    else:
        print("[WARN] Failed to parse sample engagement file.")


def main() -> None:
    logger.info("Script started: %s", __file__)
    env = load_env(Path(".env"))
    print("[INFO] Proximity schema verification")
    check_sample_parse()
    asyncio.run(check_db(env))


if __name__ == "__main__":
    main()
