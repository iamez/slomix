#!/usr/bin/env python3
"""
Cleanup duplicate round_correlations rows.

Najde grupe (date, map) z >1 correlation row, izbere "canonical" (najpopolnejši
+ najstarejši row z r1+r2_round_id), v njega merge-a vse has_* flage iz
ne-canonical rows, recalculate completeness, IZBRIŠE ne-canonical rows.

DRY-RUN by default. Pass --apply za actual writes.
Backup PRED runom: tools/cleanup_correlation_duplicates.py --backup-check

Glej docs/PLAN_correlation_orphan_remediation.md (Phase D) za context.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

# Naloži .env iz repo root pred uvozom
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

import asyncpg  # type: ignore

FLAG_COLS = [
    "has_r1_stats", "has_r2_stats",
    "has_r1_lua_teams", "has_r2_lua_teams",
    "has_r1_gametime", "has_r2_gametime",
    "has_r1_endstats", "has_r2_endstats",
    "has_r1_proximity", "has_r2_proximity",
]

ID_COLS = ["r1_round_id", "r2_round_id", "summary_round_id", "r1_lua_teams_id", "r2_lua_teams_id"]


def completeness(flags: dict) -> int:
    """Re-implementacija _recalculate_completeness logike za canonical izbiro."""
    pct = 0
    if flags.get("has_r1_stats"): pct += 25
    if flags.get("has_r2_stats"): pct += 25
    if flags.get("has_r1_lua_teams"): pct += 10
    if flags.get("has_r2_lua_teams"): pct += 10
    if flags.get("has_r1_gametime"): pct += 5
    if flags.get("has_r2_gametime"): pct += 5
    if flags.get("has_r1_endstats"): pct += 10
    if flags.get("has_r2_endstats"): pct += 10
    if flags.get("has_r1_proximity"): pct += 5
    if flags.get("has_r2_proximity"): pct += 5
    return min(pct, 100)


def status_from_flags(flags: dict) -> str:
    if flags.get("has_r1_stats") and flags.get("has_r2_stats"):
        return "complete"
    if flags.get("has_r1_stats") or flags.get("has_r2_stats"):
        return "partial"
    return "pending"


async def get_conn():
    user = os.getenv("DB_USER", "etlegacy_user")
    password = os.getenv("DB_PASSWORD", "etlegacy_secure_2025")
    db = os.getenv("DB_NAME", "etlegacy")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    return await asyncpg.connect(host=host, port=port, user=user, password=password, database=db)


async def find_dup_groups(conn) -> list[dict]:
    """Vrne sezname grup (date, map_name, list of correlation row dicts).

    Grupiranje po (date_part_of_match_id, map_name).
    """
    rows = await conn.fetch(
        """
        SELECT id, correlation_id, match_id, map_name, status, completeness_pct,
               r1_round_id, r2_round_id, summary_round_id,
               r1_lua_teams_id, r2_lua_teams_id,
               has_r1_stats, has_r2_stats,
               has_r1_lua_teams, has_r2_lua_teams,
               has_r1_gametime, has_r2_gametime,
               has_r1_endstats, has_r2_endstats,
               has_r1_proximity, has_r2_proximity,
               r1_arrived_at, r2_arrived_at, completed_at, created_at,
               SUBSTRING(match_id FROM 1 FOR 10) AS match_date
        FROM round_correlations
        ORDER BY match_id
        """
    )
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows:
        groups[(r["match_date"], r["map_name"])].append(dict(r))
    return [
        {"key": k, "rows": v}
        for k, v in groups.items()
        if len(v) > 1
    ]


def choose_canonical(rows: list[dict]) -> dict | None:
    """Izberi canonical row.

    Pravila:
    1. Vsaj eden mora imeti r1_round_id ALI r2_round_id (ker bo postal canonical
       — ostali so orphani brez round_id-jev).
    2. Najpopolnejši (highest completeness_pct).
    3. Tie-breaker: najstarejši (najmanjši id).

    Vrne None če ni primernega canonical row-a (vse so orphani).
    """
    candidates = [r for r in rows if r["r1_round_id"] is not None or r["r2_round_id"] is not None]
    if not candidates:
        return None
    # Sort: completeness DESC, id ASC
    candidates.sort(key=lambda r: (-r["completeness_pct"], r["id"]))
    return candidates[0]


def merge_flags(canonical: dict, others: list[dict]) -> dict:
    """Vrne dict s spremenjenimi flag-i (samo tisti, ki bi se dejansko spremenili)."""
    merged: dict = {}
    for col in FLAG_COLS:
        cur = canonical.get(col) or False
        new = cur
        for o in others:
            if o.get(col):
                new = True
                break
        if new != cur:
            merged[col] = True

    # ID columns: če canonical jih nima ampak drugi jih ima, vzemi (samo če None)
    for col in ID_COLS:
        if canonical.get(col) is None:
            for o in others:
                v = o.get(col)
                if v is not None:
                    merged[col] = v
                    break

    return merged


async def execute_cleanup(conn, groups: list[dict], apply: bool, summary_only: bool = False):
    stats = {
        "groups_total": len(groups),
        "groups_actionable": 0,
        "groups_skipped_no_canonical": 0,
        "groups_skipped_too_many": 0,
        "rows_to_delete": 0,
        "flags_to_merge": 0,
    }
    actions = []

    for g in groups:
        rows = g["rows"]
        date, map_name = g["key"]

        # Safety: skip clusters s ≥6 rows (suspekt — 9-row outlier itd.)
        if len(rows) > 5:
            stats["groups_skipped_too_many"] += 1
            actions.append({
                "kind": "SKIP",
                "reason": f"too_many_rows({len(rows)})",
                "key": (date, map_name),
                "rows": [r["id"] for r in rows],
            })
            continue

        canonical = choose_canonical(rows)
        if canonical is None:
            stats["groups_skipped_no_canonical"] += 1
            actions.append({
                "kind": "SKIP",
                "reason": "no_canonical",
                "key": (date, map_name),
                "rows": [r["id"] for r in rows],
            })
            continue

        others = [r for r in rows if r["id"] != canonical["id"]]
        merged_changes = merge_flags(canonical, others)

        stats["groups_actionable"] += 1
        stats["rows_to_delete"] += len(others)
        stats["flags_to_merge"] += len(merged_changes)

        actions.append({
            "kind": "MERGE",
            "key": (date, map_name),
            "canonical_id": canonical["id"],
            "canonical_correlation_id": canonical["correlation_id"],
            "delete_ids": [r["id"] for r in others],
            "delete_correlation_ids": [r["correlation_id"] for r in others],
            "flag_changes": merged_changes,
        })

        if apply:
            # 1. Update canonical with merged flags + ID columns
            if merged_changes:
                set_parts = []
                params = []
                for col, val in merged_changes.items():
                    set_parts.append(f"{col} = ${len(params)+1}")
                    params.append(val)
                params.append(canonical["id"])
                await conn.execute(
                    f"UPDATE round_correlations SET {', '.join(set_parts)} WHERE id = ${len(params)}",
                    *params,
                )

            # 2. Recalculate completeness on canonical
            row = await conn.fetchrow(
                "SELECT " + ", ".join(FLAG_COLS) + " FROM round_correlations WHERE id = $1",
                canonical["id"],
            )
            flags = dict(row)
            new_pct = completeness(flags)
            new_status = status_from_flags(flags)
            await conn.execute(
                "UPDATE round_correlations SET completeness_pct = $1, status = $2 WHERE id = $3",
                new_pct, new_status, canonical["id"],
            )

            # 3. Delete the others
            ids_to_delete = [r["id"] for r in others]
            await conn.execute(
                "DELETE FROM round_correlations WHERE id = ANY($1::int[])",
                ids_to_delete,
            )

    return stats, actions


def print_summary(stats: dict, actions: list, verbose: bool):
    print("\n=== Cleanup summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if verbose:
        # Print SKIP first (always relevant), then sample of MERGE
        skips = [a for a in actions if a["kind"] == "SKIP"]
        merges = [a for a in actions if a["kind"] == "MERGE"]

        if skips:
            print("\n=== SKIPPED groups (all) ===")
            for a in skips:
                print(f"  SKIP {a['key']}: {a['reason']} rows={a['rows']}")

        merges_with_flags = [a for a in merges if a["flag_changes"]]
        if merges_with_flags:
            print(f"\n=== MERGE z flag changes ({len(merges_with_flags)} of {len(merges)}) ===")
            for a in merges_with_flags[:30]:
                date, mn = a["key"]
                print(f"  MERGE {date} {mn}: keep={a['canonical_id']} "
                      f"delete={a['delete_ids']} flags+={list(a['flag_changes'].keys())}")
            if len(merges_with_flags) > 30:
                print(f"  ... +{len(merges_with_flags)-30} more z flag changes")

        merges_no_flags = [a for a in merges if not a["flag_changes"]]
        if merges_no_flags:
            print(f"\n=== MERGE brez flag changes ({len(merges_no_flags)} grup, samo deletes) ===")
            for a in merges_no_flags[:5]:
                date, mn = a["key"]
                print(f"  MERGE {date} {mn}: keep={a['canonical_id']} delete={a['delete_ids']}")
            if len(merges_no_flags) > 5:
                print(f"  ... +{len(merges_no_flags)-5} more brez flag changes")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default dry-run)")
    parser.add_argument("--verbose", action="store_true", help="Print all actions")
    parser.add_argument("--limit", type=int, default=0, help="Cap to N groups for testing")
    args = parser.parse_args()

    conn = await get_conn()
    try:
        groups = await find_dup_groups(conn)
        if args.limit:
            groups = groups[:args.limit]

        print(f"Found {len(groups)} duplicate groups in round_correlations.")
        if args.apply:
            print("⚠️  APPLY MODE — writes will be performed.")
        else:
            print("DRY-RUN mode (no writes). Use --apply to execute.")

        stats, actions = await execute_cleanup(conn, groups, apply=args.apply)
        print_summary(stats, actions, verbose=args.verbose or not args.apply)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
