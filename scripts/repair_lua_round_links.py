#!/usr/bin/env python3
"""Repair wrong Lua team/spawn ``round_id`` values without guessing.

Dry-run is the default. It fingerprints the exact action set:

* one exact source-key target -> rebind to that round;
* no/multiple exact targets -> set round_id NULL;
* spawn rows inherit only the projected identity of their matching team row;
* any duplicate non-NULL team round_id remaining in the projection -> refuse.

``--apply`` requires the dry-run counts, fingerprint, target database identity,
and a verified manifest emitted by ``scripts/db_backup.sh`` for that same
database. The candidate set is re-measured after write-blocking locks on both
the source and target tables, and all postconditions are checked before commit.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.apply_migrations import (  # noqa: E402
    get_connection_kwargs,
    get_target_dsn_parts,
)

try:
    import psycopg2 as _pg
except ImportError:  # pragma: no cover
    try:
        import psycopg as _pg  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover
        _pg = None  # type: ignore[assignment]


@dataclass(frozen=True)
class RepairAction:
    row_id: int
    old_round_id: int | None
    new_round_id: int | None
    candidate_count: int
    table: str = "lua_round_teams"

    @property
    def kind(self) -> str:
        return "rebind" if self.new_round_id is not None else "quarantine"


def _connect():
    if _pg is None:
        raise SystemExit(
            "This script needs a PostgreSQL driver: pip install psycopg2-binary"
        )
    return _pg.connect(**get_connection_kwargs())


def fingerprint_actions(actions: list[RepairAction]) -> str:
    payload = "\n".join(
        f"{a.table}:{a.row_id}:{a.old_round_id}:"
        f"{a.new_round_id if a.new_round_id is not None else 'NULL'}"
        for a in sorted(actions, key=lambda item: (item.table, item.row_id))
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def backup_manifest_problems(
    manifest_path: str | Path | None,
    expected_db_identity: str,
) -> list[str]:
    """Verify that a completed backup belongs to this exact repair target."""
    if not manifest_path:
        return ["--backup-manifest is required with --apply"]

    path = Path(manifest_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [f"cannot read backup manifest {path}: {exc}"]

    values: dict[str, str] = {}
    problems = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            problems.append(f"invalid backup manifest line: {line!r}")
            continue
        key, value = line.split("=", 1)
        if key in values:
            problems.append(f"duplicate backup manifest key: {key}")
        values[key] = value

    required = ("db_identity", "dump_file", "sha256", "created_unix")
    problems.extend(
        f"backup manifest missing {key}" for key in required if not values.get(key)
    )
    if problems:
        return problems

    if values["db_identity"] != expected_db_identity:
        problems.append(
            "backup database mismatch: "
            f"manifest {values['db_identity']}, repair {expected_db_identity}"
        )

    dump_path = Path(values["dump_file"])
    if not dump_path.is_absolute():
        dump_path = path.parent / dump_path
    try:
        if dump_path.stat().st_size <= 0:
            problems.append(f"backup dump is empty: {dump_path}")
        else:
            digest = hashlib.sha256()
            with dump_path.open("rb") as dump_file:
                for chunk in iter(lambda: dump_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != values["sha256"]:
                problems.append(f"backup checksum mismatch: {dump_path}")
    except OSError as exc:
        problems.append(f"cannot verify backup dump {dump_path}: {exc}")

    try:
        int(values["created_unix"])
    except ValueError:
        problems.append("backup manifest created_unix is not an integer")
    return problems


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
        LEFT JOIN rounds linked ON linked.id = l.round_id
        LEFT JOIN rounds target
          ON target.round_start_unix = l.round_start_unix
         AND LOWER(BTRIM(target.map_name)) = LOWER(BTRIM(l.map_name))
         AND target.round_number = l.round_number
        WHERE l.round_id IS NOT NULL
          AND (
              l.round_start_unix IS NULL
              OR l.round_start_unix <= 0
              OR linked.id IS NULL
              OR linked.round_start_unix IS DISTINCT FROM l.round_start_unix
              OR LOWER(BTRIM(linked.map_name))
                    IS DISTINCT FROM LOWER(BTRIM(l.map_name))
              OR linked.round_number IS DISTINCT FROM l.round_number
          )
        GROUP BY l.id, l.round_id, l.captured_at
        ORDER BY l.id
        """
    )
    rows = cur.fetchall()
    team_actions = [
        RepairAction(
            row_id=int(row[0]),
            old_round_id=int(row[1]),
            new_round_id=int(row[3]) if int(row[2]) == 1 else None,
            candidate_count=int(row[2]),
        )
        for row in rows
    ]

    cur.execute(
        "SELECT id, match_id, round_number, map_name, round_id, "
        "captured_at::date FROM lua_round_teams ORDER BY id"
    )
    all_team_rows = cur.fetchall()
    projected_by_id = {
        int(row[0]): int(row[4]) if row[4] is not None else None
        for row in all_team_rows
    }
    for action in team_actions:
        projected_by_id[action.row_id] = action.new_round_id

    def source_key(row) -> tuple[str, int, str | None]:
        return (
            str(row[1]),
            int(row[2]),
            None if row[3] is None else str(row[3]).strip().lower(),
        )

    projected_team_links: dict[
        tuple[str, int, str | None], list[int | None]
    ] = {}
    for row in all_team_rows:
        projected_team_links.setdefault(source_key(row), []).append(
            projected_by_id[int(row[0])]
        )

    cur.execute(
        "SELECT id, match_id, round_number, map_name, round_id, "
        "captured_at::date FROM lua_spawn_stats ORDER BY id"
    )
    spawn_rows = cur.fetchall()
    spawn_actions: list[RepairAction] = []
    spawn_action_dates = []
    for row in spawn_rows:
        candidates = projected_team_links.get(source_key(row), [])
        projected_round_id = candidates[0] if len(candidates) == 1 else None
        old_round_id = int(row[4]) if row[4] is not None else None
        if old_round_id != projected_round_id:
            spawn_actions.append(
                RepairAction(
                    row_id=int(row[0]),
                    old_round_id=old_round_id,
                    new_round_id=projected_round_id,
                    candidate_count=len(candidates),
                    table="lua_spawn_stats",
                )
            )
            if row[5] is not None:
                spawn_action_dates.append(row[5])

    actions = [*team_actions, *spawn_actions]

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
    captured_dates.extend(spawn_action_dates)

    return {
        "actions": actions,
        "wrong_count": len(actions),
        "rebind_count": sum(action.kind == "rebind" for action in actions),
        "quarantine_count": sum(action.kind == "quarantine" for action in actions),
        "team_rebind_count": sum(a.kind == "rebind" for a in team_actions),
        "team_quarantine_count": sum(a.kind == "quarantine" for a in team_actions),
        "spawn_rebind_count": sum(a.kind == "rebind" for a in spawn_actions),
        "spawn_quarantine_count": sum(a.kind == "quarantine" for a in spawn_actions),
        "ambiguous_count": sum(a.candidate_count > 1 for a in team_actions),
        "missing_count": sum(a.candidate_count == 0 for a in team_actions),
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
    print(f"planned repair rows: {stats['wrong_count']}")
    print(f"  rebind to proven round: {stats['rebind_count']}")
    print(f"  quarantine to NULL: {stats['quarantine_count']}")
    print(
        "  team rows: "
        f"{stats['team_rebind_count']} rebind, "
        f"{stats['team_quarantine_count']} quarantine"
    )
    print(
        "  spawn rows: "
        f"{stats['spawn_rebind_count']} rebind, "
        f"{stats['spawn_quarantine_count']} quarantine"
    )
    print(f"    missing exact target: {stats['missing_count']}")
    print(f"    ambiguous exact target: {stats['ambiguous_count']}")
    print(f"current duplicate round_id groups: {stats['current_duplicate_groups']}")
    print(f"projected duplicate round_id groups: {stats['projected_duplicate_groups']}")
    print(f"latest affected date: {stats['latest_date']}")
    print(f"action fingerprint: {stats['fingerprint']}")


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument(
        "--backup-manifest",
        help="verified .manifest path printed by scripts/db_backup.sh; required with --apply",
    )
    parser.add_argument("--expect-rebind-count", type=int)
    parser.add_argument("--expect-quarantine-count", type=int)
    parser.add_argument("--expect-current-duplicate-groups", type=int)
    parser.add_argument("--expect-latest-date")
    parser.add_argument("--expect-fingerprint")
    parser.add_argument("--expect-db")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.apply and not args.backup_manifest:
        print("Refusing --apply without --backup-manifest (run scripts/db_backup.sh first).")
        return 1

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("SELECT current_database()")
        db_name = cur.fetchone()[0]
        target = get_target_dsn_parts()
        db_identity = "{}:{}/{}".format(
            target["host"],
            target["port"],
            db_name,
        )

        if args.apply:
            backup_problems = backup_manifest_problems(
                args.backup_manifest,
                db_identity,
            )
            if backup_problems:
                conn.rollback()
                print("\nABORTED - backup verification failed, nothing written:")
                for problem in backup_problems:
                    print(f"  - {problem}")
                return 1
            print(f"verified backup manifest: {args.backup_manifest}")
            cur.execute("LOCK TABLE rounds IN SHARE MODE")
            cur.execute(
                "LOCK TABLE lua_round_teams, lua_spawn_stats "
                "IN SHARE ROW EXCLUSIVE MODE"
            )

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
                f"  --apply --backup-manifest <path-printed-by-db_backup.sh> "
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
        update_sql = {
            "lua_round_teams": (
                "UPDATE lua_round_teams SET round_id = %s "
                "WHERE id = %s AND round_id IS NOT DISTINCT FROM %s"
            ),
            "lua_spawn_stats": (
                "UPDATE lua_spawn_stats SET round_id = %s "
                "WHERE id = %s AND round_id IS NOT DISTINCT FROM %s"
            ),
        }
        for action in stats["actions"]:
            if action.table not in update_sql:
                raise RuntimeError(f"unsupported repair table: {action.table}")
            cur.execute(
                update_sql[action.table],
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
