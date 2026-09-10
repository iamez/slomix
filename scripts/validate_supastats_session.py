from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot.config import load_config
from bot.core.database_adapter import create_adapter
from bot.services.session_data_service import SessionDataService
from website.backend.routers import sessions_router as api_router

UNRESOLVED_FIELDS = ["A", "EFFORT", "EXPECTED", "PERF"]


def build_player_snapshot_rows(players: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for player in sorted(players, key=lambda row: str(row.get("player_name", "")).lower()):
        rows.append(
            {
                "player_name": player.get("player_name"),
                "player_guid": player.get("player_guid"),
                "damage_given": int(player.get("damage_given") or 0),
                "damage_received": int(player.get("damage_received") or 0),
                "kills": int(player.get("kills") or 0),
                "kill_assists": int(player.get("kill_assists") or 0),
                "gibs": int(player.get("gibs") or 0),
                "self_kills": int(player.get("self_kills") or 0),
                "deaths": int(player.get("deaths") or 0),
                "kd": float(player.get("kd") or 0.0),
                "supastats_tmp_pct": _round_float(player.get("supastats_tmp_pct")),
                "supastats_tmp_ratio": _round_float(player.get("supastats_tmp_ratio"), digits=3),
            }
        )
    return rows


def build_team_snapshot_rows(
    players: Iterable[dict[str, Any]], teams: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if not teams:
        return []

    by_guid = {str(player.get("player_guid")): player for player in players}
    rows = []
    for team_name in sorted(teams):
        total = {
            "team_name": team_name,
            "damage_given": 0,
            "damage_received": 0,
            "kills": 0,
            "kill_assists": 0,
            "gibs": 0,
            "self_kills": 0,
            "deaths": 0,
        }
        for guid in teams[team_name].get("guids", []):
            player = by_guid.get(str(guid))
            if not player:
                continue
            total["damage_given"] += int(player.get("damage_given") or 0)
            total["damage_received"] += int(player.get("damage_received") or 0)
            total["kills"] += int(player.get("kills") or 0)
            total["kill_assists"] += int(player.get("kill_assists") or 0)
            total["gibs"] += int(player.get("gibs") or 0)
            total["self_kills"] += int(player.get("self_kills") or 0)
            total["deaths"] += int(player.get("deaths") or 0)
        rows.append(total)
    return rows


def build_match_pair_rows(round_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_rows = sorted(
        round_rows,
        key=lambda row: (
            int(row.get("round_start_unix") or 0),
            int(row.get("round_number") or 0),
            int(row.get("round_id") or 0),
        ),
    )
    match_pairs = []
    current_pair: list[dict[str, Any]] = []

    for row in ordered_rows:
        current_pair.append(row)
        if len(current_pair) == 2:
            match_pairs.append(_pair_to_snapshot(len(match_pairs) + 1, current_pair))
            current_pair = []

    if current_pair:
        match_pairs.append(_pair_to_snapshot(len(match_pairs) + 1, current_pair))

    return match_pairs


def compare_snapshots(actual: Any, expected: Any, path: str = "root") -> list[str]:
    mismatches: list[str] = []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected dict, got {type(actual).__name__}"]
        for key in sorted(expected.keys() - actual.keys()):
            mismatches.append(f"{path}.{key}: missing key")
        for key in sorted(actual.keys() - expected.keys()):
            mismatches.append(f"{path}.{key}: unexpected key")
        for key in sorted(expected.keys() & actual.keys()):
            mismatches.extend(compare_snapshots(actual[key], expected[key], f"{path}.{key}"))
        return mismatches

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if len(actual) != len(expected):
            mismatches.append(f"{path}: expected {len(expected)} items, got {len(actual)}")
        for idx, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            mismatches.extend(compare_snapshots(actual_item, expected_item, f"{path}[{idx}]"))
        return mismatches

    if _is_number(actual) and _is_number(expected):
        if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-6):
            mismatches.append(f"{path}: expected {expected}, got {actual}")
        return mismatches

    if actual != expected:
        mismatches.append(f"{path}: expected {expected!r}, got {actual!r}")
    return mismatches


async def fetch_session_snapshot(
    *, session_date: str | None = None, gaming_session_id: int | None = None
) -> dict[str, Any]:
    adapter = await _connect_adapter()
    try:
        resolved_session_id = gaming_session_id
        if resolved_session_id is None:
            if not session_date:
                raise ValueError("Provide --session-date or --gaming-session-id")
            resolved_session_id = await _resolve_gaming_session_id(adapter, session_date)

        payload = await api_router.get_stats_session_detail(
            gaming_session_id=resolved_session_id,
            db=adapter,
        )
        round_rows = await _fetch_round_rows(adapter, resolved_session_id)
        round_ids = [row["round_id"] for row in round_rows]
        team_service = SessionDataService(adapter, None)
        teams = await team_service.get_hardcoded_teams(round_ids)

        return {
            "session_date": payload["date"],
            "gaming_session_id": payload["session_id"],
            "unresolved_fields": list(UNRESOLVED_FIELDS),
            "players": build_player_snapshot_rows(payload["players"]),
            "teams": build_team_snapshot_rows(payload["players"], teams),
            "match_pairs": build_match_pair_rows(round_rows),
        }
    finally:
        await adapter.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate canonical Slomix session data against a stored supastats fixture."
    )
    parser.add_argument("--session-date", help="Session date in YYYY-MM-DD format")
    parser.add_argument("--gaming-session-id", type=int, help="Gaming session id")
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Optional JSON fixture path. If provided, compare live snapshot against it.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path for the generated snapshot JSON.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the generated snapshot JSON to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        snapshot = asyncio.run(
            fetch_session_snapshot(
                session_date=args.session_date,
                gaming_session_id=args.gaming_session_id,
            )
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"session={snapshot['session_date']} "
        f"gaming_session_id={snapshot['gaming_session_id']} "
        f"players={len(snapshot['players'])} "
        f"teams={len(snapshot['teams'])} "
        f"match_pairs={len(snapshot['match_pairs'])}"
    )

    if args.fixture:
        expected = json.loads(args.fixture.read_text(encoding="utf-8"))
        mismatches = compare_snapshots(snapshot, expected)
        if mismatches:
            print("fixture comparison failed:")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
            return 1
        print(f"fixture comparison ok: {args.fixture}")

    if args.json or (not args.fixture and not args.output):
        print(json.dumps(snapshot, indent=2, sort_keys=True))

    return 0


async def _connect_adapter():
    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    return adapter


async def _resolve_gaming_session_id(adapter, session_date: str) -> int:
    rows = await adapter.fetch_all(
        """
        SELECT DISTINCT r.gaming_session_id
        FROM rounds r
        WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) = $1
          AND r.gaming_session_id IS NOT NULL
          AND r.round_number IN (1, 2)
          AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
          AND EXISTS (
              SELECT 1
              FROM player_comprehensive_stats pcs
              WHERE pcs.round_id = r.id
          )
        ORDER BY r.gaming_session_id
        """,
        (session_date,),
    )
    session_ids = [int(row[0]) for row in rows]
    if not session_ids:
        raise ValueError(f"no linked gaming session found for {session_date}")
    if len(session_ids) > 1:
        raise ValueError(
            f"multiple gaming sessions found for {session_date}: {session_ids}. "
            "Use --gaming-session-id."
        )
    return session_ids[0]


async def _fetch_round_rows(adapter, gaming_session_id: int) -> list[dict[str, Any]]:
    rows = await adapter.fetch_all(
        """
        SELECT
            r.id,
            r.map_name,
            r.round_number,
            r.round_start_unix,
            COALESCE(
                l.actual_duration_seconds,
                CASE
                    WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                        SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                        SPLIT_PART(r.actual_time, ':', 2)::int
                    ELSE 0
                END
            ) AS duration_seconds
        FROM rounds r
        LEFT JOIN lua_round_teams l ON l.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND r.round_number IN (1, 2)
          AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
        ORDER BY r.round_start_unix, r.round_number, r.id
        """,
        (gaming_session_id,),
    )

    return [
        {
            "round_id": int(row[0]),
            "map_name": str(row[1]),
            "round_number": int(row[2]),
            "round_start_unix": int(row[3] or 0),
            "duration_seconds": int(row[4] or 0),
        }
        for row in rows
    ]


def _pair_to_snapshot(order: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "order": order,
        "map_name": rows[0]["map_name"] if rows else None,
        "round_ids": [row["round_id"] for row in rows],
        "round_numbers": [row["round_number"] for row in rows],
        "durations": [row["duration_seconds"] for row in rows],
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _round_float(value: Any, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


if __name__ == "__main__":
    raise SystemExit(main())
