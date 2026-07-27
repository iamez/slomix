#!/usr/bin/env python3
"""Repair wrong lua_round_teams.round_id values without guessing.

Dry-run is the default. It fingerprints the exact action set:

* one exact source-key target -> rebind to that round;
* no/multiple exact targets -> set round_id NULL;
* any duplicate non-NULL round_id remaining in the projected state -> refuse.

``--apply`` requires the dry-run counts, fingerprint, target database identity,
and an explicit backup acknowledgement. The candidate set is re-measured after
a table lock and all postconditions are checked before commit.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import psycopg2 as _pg
except ImportError:  # pragma: no cover
    try:
        import psycopg as _pg  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover
        _pg = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RepairAction:
    row_id: int
    old_round_id: int
    new_round_id: int | None
    candidate_count: int

    @property
    def kind(self) -> str:
        return "rebind" if self.new_round_id is not None else "quarantine"


def _connect():
    if _pg is None:
        raise SystemExit(
            "This script needs a PostgreSQL driver: pip install psycopg2-binary"
        )
    with contextlib.suppress(Exception):
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    return _pg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DATABASE", "etlegacy"),
        user=os.getenv("POSTGRES_USER", "etlegacy_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def fingerprint_actions(actions: list[RepairAction]) -> str:
    payload = "\n".join(
        f"{a.row_id}:{a.old_round_id}:{a.new_round_id if a.new_round_id is not None else 'NULL'}"
        for a in sorted(actions, key=lambda item: item.row_id)
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _duplicate_groups(round_ids: list[int | None]) -> int:
    counts: dict[int, int] = {}
    for round_id in round_ids:
        if round_id is not None:
            counts[round_id] = counts.get(round_id, 0) + 1
    return sum(1 for count in counts.values() if count > 1)


def measure(cur) -> dict[str, Any]:
    cur.execute(
        """
        SELECT
            l.id,
            l.round_id,
            COUNT(target.id) AS candidate_count,
            MIN(target.id) AS target_round_id,
            l.captured_at::date AS captured_date
        FROM lua_round_teams l
        JOIN rounds linked ON linked.id = l.round_id
        LEFT JOIN rounds target
          ON target.round_start_unix = l.round_start_unix
         AND LOWER(BTRIM(target.map_name)) = LOWER(BTRIM(l.map_name))
         AND target.round_number = l.round_number
        WHERE l.round_start_unix IS NOT NULL
          AND l.round_start_unix > 0
          AND linked.round_start_unix IS NOT NULL
          AND l.round_start_unix <> linked.round_start_unix
        GROUP BY l.id, l.round_id, l.captured_at
        ORDER BY l.id
        """
    )
    rows = cur.fetchall()
    actions = [
        RepairAction(
            row_id=int(row[0]),
            old_round_id=int(row[1]),
            new_round_id=int(row[3]) if int(row[2]) == 1 else None,
            candidate_count=int(row[2]),
        )
        for row in rows
    ]

    cur.execute("SELECT id, round_id FROM lua_round_teams ORDER BY id")
    all_links = [(int(row[0]), int(row[1]) if row[1] is not None else None) for row in cur.fetchall()]
    projected_by_id = {row_id: round_id for row_id, round_id in all_links}
    for action in actions:
        projected_by_id[action.row_id] = action.new_round_id

    cur.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT round_id
            FROM lua_round_teams
            WHERE round_id IS NOT NULL
            GROUP BY round_id
            HAVING COUNT(*) > 1
        ) duplicate_groups
        """
    )
    current_duplicate_groups = int(cur.fetchone()[0])
    captured_dates = [row[4] for row in rows if row[4] is not None]

    return {
        "actions": actions,
        "wrong_count": len(actions),
        "rebind_count": sum(action.kind == "rebind" for action in actions),
        "quarantine_count": sum(action.kind == "quarantine" for action in actions),
        "ambiguous_count": sum(action.candidate_count > 1 for action in actions),
        "missing_count": sum(action.candidate_count == 0 for action in actions),
        "current_duplicate_groups": current_duplicate_groups,
        "projected_duplicate_groups": _duplicate_groups(list(projected_by_id.values())),
        "latest_date": max(captured_dates, default=None),
        "fingerprint": fingerprint_actions(actions),
    }


def check_expectations(stats: dict[str, Any], args) -> list[str]:
    checks = (
        ("rebind-count", stats["rebind_count"], args.expect_rebind_count),
        ("quarantine-count", stats["quarantine_count"], args.expect_quarantine_count),
        (
            "current-duplicate-groups",
            stats["current_duplicate_groups"],
            args.expect_current_duplicate_groups,
        ),
        ("latest-date", str(stats["latest_date"]), args.expect_latest_date),
        ("fingerprint", stats["fingerprint"], args.expect_fingerprint),
        ("db", stats["db_identity"], args.expect_db),
    )
    problems = []
    for name, measured, expected in checks:
        if expected is None:
            problems.append(f"--expect-{name} is required with --apply")
        elif str(measured) != str(expected):
            problems.append(
                f"--expect-{name} mismatch: expected {expected}, measured {measured}"
            )
    if stats["projected_duplicate_groups"]:
        problems.append(
            "repair projection retains "
            f"{stats['projected_duplicate_groups']} duplicate round_id group(s)"
        )
    return problems


def _print_report(stats: dict[str, Any], *, apply: bool) -> None:
    print("=" * 72)
    print("LUA ROUND LINK REPAIR - " + ("APPLY" if apply else "DRY-RUN"))
    print("=" * 72)
    print(f"target database: {stats['db_identity']}")
    print(f"wrong linked rows: {stats['wrong_count']}")
    print(f"  exact rebind: {stats['rebind_count']}")
    print(f"  quarantine to NULL: {stats['quarantine_count']}")
    print(f"    missing exact target: {stats['missing_count']}")
    print(f"    ambiguous exact target: {stats['ambiguous_count']}")
    print(f"current duplicate round_id groups: {stats['current_duplicate_groups']}")
    print(f"projected duplicate round_id groups: {stats['projected_duplicate_groups']}")
    print(f"latest affected date: {stats['latest_date']}")
    print(f"action fingerprint: {stats['fingerprint']}")


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--i-have-a-backup", action="store_true", help="required with --apply")
    parser.add_argument("--expect-rebind-count", type=int)
    parser.add_argument("--expect-quarantine-count", type=int)
    parser.add_argument("--expect-current-duplicate-groups", type=int)
    parser.add_argument("--expect-latest-date")
    parser.add_argument("--expect-fingerprint")
    parser.add_argument("--expect-db")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.apply and not args.i_have_a_backup:
        print("Refusing --apply without --i-have-a-backup (run scripts/db_backup.sh first).")
        return 1

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("SELECT current_database()")
        db_name = cur.fetchone()[0]
        db_identity = "{}:{}/{}".format(
            os.getenv("POSTGRES_HOST", "localhost"),
            os.getenv("POSTGRES_PORT", "5432"),
            db_name,
        )

        if args.apply:
            cur.execute("LOCK TABLE lua_round_teams IN SHARE MODE")

        stats = measure(cur)
        stats["db_identity"] = db_identity
        _print_report(stats, apply=args.apply)

        if not args.apply:
            conn.rollback()
            if stats["projected_duplicate_groups"]:
                print("\nREFUSED: projected duplicate links remain; no safe automatic apply.")
                return 1
            print("\nDRY-RUN - no changes written. After a backup, re-run with:")
            print(
                f"  --apply --i-have-a-backup "
                f"--expect-rebind-count {stats['rebind_count']} "
                f"--expect-quarantine-count {stats['quarantine_count']} "
                "--expect-current-duplicate-groups "
                f"{stats['current_duplicate_groups']} "
                f"--expect-latest-date {stats['latest_date']} "
                f"--expect-fingerprint {stats['fingerprint']} "
                f"--expect-db {stats['db_identity']}"
            )
            return 0

        problems = check_expectations(stats, args)
        if problems:
            conn.rollback()
            print("\nABORTED - preconditions failed, nothing written:")
            for problem in problems:
                print(f"  - {problem}")
            return 1

        changed = 0
        for action in stats["actions"]:
            cur.execute(
                "UPDATE lua_round_teams SET round_id = %s "
                "WHERE id = %s AND round_id IS NOT DISTINCT FROM %s",
                (action.new_round_id, action.row_id, action.old_round_id),
            )
            changed += cur.rowcount
        if changed != stats["wrong_count"]:
            conn.rollback()
            print(
                f"\nABORTED - UPDATE changed {changed} rows, "
                f"expected {stats['wrong_count']}; rolled back."
            )
            return 1

        residual = measure(cur)
        if residual["wrong_count"] or residual["current_duplicate_groups"]:
            conn.rollback()
            print(
                "\nABORTED - postcondition failed: "
                f"wrong={residual['wrong_count']} "
                f"duplicate_groups={residual['current_duplicate_groups']}; rolled back."
            )
            return 1

        conn.commit()
        print(f"\nCommitted {changed} guarded link repair(s); all postconditions are clean.")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
