#!/usr/bin/env python3
"""The two dev-DB rows behind the e2e/fixture sentinel (website_user_id -1).

scripts/e2e_owner_session.py mints a session for a SENTINEL identity —
Discord id -1, website user -1 — so no recorded fixture or Playwright run
ever carries a real account (Codex on #855, round seven). With
E2E_OWNER_PLAYER_NAME set, that session already counts as Discord-linked
(availability.py:_is_discord_linked reads the session's linked_player
first). Two gates still look the database in the eye:

  * the wallet: user_points.user_id is a FOREIGN KEY to website_users(id),
    and bets_router keys the wallet by the session's Discord id — with no
    website_users row for -1 the first GET /api/bets/wallet bootstraps a
    row and dies on the FK (BACKLOG, found on #887);
  * the promoter gate: availability.py:_is_promoter_user reads
    user_permissions.tier for the Discord id (root|admin).

This script adds exactly those two rows, idempotently, and removes them
(plus everything the sentinel wrote through the availability API) on
request. It is dry-run by default: without --apply/--remove it prints the
SQL and the current counts and changes nothing.

Dev only. It refuses to run when ENVIRONMENT=production (the same variable
website/backend/main.py reads) — the sentinel has no business in prod.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SENTINEL_ID = -1

# Every table the sentinel can touch, with the column that names it.
# website_users first on insert (FK target), last on delete.
INSERTS: tuple[tuple[str, str, tuple], ...] = (
    (
        "website_users",
        "INSERT INTO website_users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
        (SENTINEL_ID,),
    ),
    (
        "user_permissions",
        "INSERT INTO user_permissions (discord_id, username, tier, reason) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (discord_id) DO NOTHING",
        (SENTINEL_ID, "e2e-sentinel", "admin", "e2e sentinel — scripts/e2e_sentinel_rows.py"),
    ),
)

# (table, id column) — the rows the sentinel's own API writes leave behind.
SENTINEL_TABLES: tuple[tuple[str, str], ...] = (
    ("availability_channel_links", "user_id"),
    ("availability_subscriptions", "user_id"),
    ("availability_user_settings", "user_id"),
    ("availability_entries", "user_id"),
    ("subscription_preferences", "user_id"),
    ("parimutuel_bets", "user_id"),
    ("uploads", "uploader_discord_id"),  # upload_tags cascades
    ("user_points", "user_id"),
    ("user_permissions", "discord_id"),
    ("website_users", "id"),
)


def _load_env() -> None:
    from dotenv import dotenv_values

    for env in (REPO / ".env", REPO / "website" / ".env"):
        if env.exists():
            for key, value in dotenv_values(env).items():
                if value is not None:
                    os.environ.setdefault(key, value)


def _dsn() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DATABASE", "etlegacy"),
        "user": os.getenv("POSTGRES_USER", "etlegacy_user"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


def counts(cur) -> dict[str, int]:
    from psycopg2 import sql as pgsql

    out: dict[str, int] = {}
    for table, column in SENTINEL_TABLES:
        # Identifiers composed, never formatted into the string: the table
        # and column come from the constant tuple above, but the driver's
        # own quoting is the form that cannot be misread later.
        cur.execute(
            pgsql.SQL("SELECT count(*) FROM {} WHERE {} = %s").format(
                pgsql.Identifier(table), pgsql.Identifier(column)
            ),
            (SENTINEL_ID,),
        )
        out[table] = int(cur.fetchone()[0])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="insert the two sentinel rows (idempotent)")
    mode.add_argument("--remove", action="store_true", help="delete every sentinel row, API leftovers included")
    args = parser.parse_args(argv)

    _load_env()
    if os.getenv("ENVIRONMENT", "").lower() == "production":
        print("refusing: ENVIRONMENT=production — the sentinel is a dev rig", file=sys.stderr)
        return 2

    import psycopg2

    conn = psycopg2.connect(**_dsn())
    try:
        with conn, conn.cursor() as cur:
            before = counts(cur)
            print("sentinel rows before:", {k: v for k, v in before.items() if v})
            if args.apply:
                for table, statement, params in INSERTS:
                    cur.execute(statement, params)
                    print(f"  {table}: {'inserted' if cur.rowcount else 'already present'}")
            elif args.remove:
                from psycopg2 import sql as pgsql

                for table, column in SENTINEL_TABLES:
                    cur.execute(
                        pgsql.SQL("DELETE FROM {} WHERE {} = %s").format(
                            pgsql.Identifier(table), pgsql.Identifier(column)
                        ),
                        (SENTINEL_ID,),
                    )
                    if cur.rowcount:
                        print(f"  {table}: deleted {cur.rowcount}")
            else:
                print("dry run — would execute with --apply:")
                for _table, statement, params in INSERTS:
                    print("  ", statement % tuple(repr(p) for p in params))
                print("would execute with --remove:")
                for table, column in SENTINEL_TABLES:
                    print(f"   DELETE FROM {table} WHERE {column} = {SENTINEL_ID}")
            after = counts(cur)
            print("sentinel rows after: ", {k: v for k, v in after.items() if v})
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
