#!/usr/bin/env python3
"""Compare a supastats screenshot against our database. Read-only.

Supa posts a screenshot of his sheet the morning after a gather. That sheet is
an independent measurement of the same night, so comparing it with our numbers
is the strongest data check available while the project is still a prototype —
a manual run of exactly this comparison on 2026-08-14 cleared a suspected
scoring regression AND found 17 genuinely inverted historical rounds.

The bot cog runs the same two services automatically; this CLI is the dev path,
so old screenshots can be re-checked at any time.

Usage:
    python scripts/supastats_check.py screenshots/supastats12-8-2026.png
    python scripts/supastats_check.py <image> --date 2026-08-11
    python scripts/supastats_check.py <image> --gsid 144

Exit code: 0 all good, 1 discrepancies found, 2 could not run.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.config import load_config  # noqa: E402
from bot.core.database_adapter import create_adapter  # noqa: E402
from bot.services.session_data_service import SessionDataService  # noqa: E402
from bot.services.stopwatch_scoring_service import StopwatchScoringService  # noqa: E402
from bot.services.supastats_image_reader import (  # noqa: E402
    UnsupportedScreenshot,
    read_supastats_image,
)
from bot.services.supastats_reconcile_service import (  # noqa: E402
    format_report,
    load_our_session,
    load_our_teams,
    reconcile,
)


async def run(image: Path, date: str | None, gsid: int | None) -> int:
    print(f"1/5 reading {image.name} ...")
    try:
        sheet = read_supastats_image(image.read_bytes())
    except UnsupportedScreenshot as exc:
        print(f"    cannot read this screenshot: {exc}")
        return 2
    print(f"    {sheet.map_count} maps, {len(sheet.kills)} players, "
          f"winners {sheet.winners}, checksum {'ok' if sheet.kills_checksum_ok else 'FAILED'}")
    for warning in sheet.warnings:
        print(f"    warning: {warning}")

    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    try:
        data_service = SessionDataService(adapter, getattr(config, "sqlite_db_path", None))

        session_date = date or sheet.session_date
        if not session_date and not gsid:
            session_date = await data_service.get_latest_session_date()
            print(f"2/5 no date given or readable — using the latest session ({session_date})")
        else:
            print(f"2/5 session date: {session_date or f'(from --gsid {gsid})'}")

        # Resolve the date the same way every other surface does (PR #730): a
        # date belongs to exactly ONE session — the one that started that day —
        # never a blend of the previous night's midnight tail and this one.
        sessions, session_ids, _, _ = (
            await data_service.fetch_session_data_by_date(session_date)
            if session_date else (None, None, None, 0)
        )
        if gsid is None:
            if not session_ids:
                print(f"    no gaming session found for {session_date}")
                return 2
            row = await adapter.fetch_one(
                "SELECT gaming_session_id FROM rounds WHERE id = ?", (session_ids[0],)
            )
            gsid = int(row[0]) if row and row[0] is not None else None
            if gsid is None:
                print(f"    rounds for {session_date} carry no gaming_session_id")
                return 2
            touching = await data_service.get_gaming_session_ids_for_date(session_date)
            if touching and len(touching) > 1:
                print(f"    note: {session_date} also touches {sorted(set(touching) - {gsid})}"
                      " (midnight tail) — comparing only the session that started that day")
        print(f"3/5 gaming session #{gsid}")

        ours = await load_our_session(adapter, gsid)
        print(f"    our side: {ours['map_count']} maps, {len(ours['kills'])} players")

        # Map winners in our own team vocabulary, via the same scorer the bot
        # and the website use.
        our_winners: list[str] = []
        our_teams: dict[str, list[str]] = {}
        if session_ids:
            hardcoded = await data_service.get_hardcoded_teams(session_ids)
            rosters = {name: info.get("guids", []) for name, info in (hardcoded or {}).items()}
            if len(rosters) >= 2:
                scoring = await StopwatchScoringService(adapter).calculate_session_scores_with_teams(
                    session_date, session_ids, rosters
                )
                if scoring:
                    a_name = scoring.get("team_a_name", "Team A")
                    b_name = scoring.get("team_b_name", "Team B")
                    for entry in scoring.get("maps", []) or []:
                        a_points = entry.get("team_a_points") or 0
                        b_points = entry.get("team_b_points") or 0
                        our_winners.append(
                            a_name if a_points > b_points else (b_name if b_points > a_points else "draw")
                        )
                    # Team -> player names from the SAME rosters the scorer
                    # used, so the colour binding cannot come out swapped.
                    our_teams = await load_our_teams(adapter, gsid, rosters)
        print(f"4/5 our map winners: {our_winners or '(unavailable)'}")

        report = reconcile(
            sheet,
            session_date=session_date or "",
            gaming_session_id=gsid,
            our_kills=ours["kills"],
            our_dpm=ours["dpm"],
            our_durations=ours["durations"],
            our_map_winners=our_winners,
            our_teams=our_teams,
        )
        print("5/5 comparison\n")
        print(format_report(report, sheet))
        return 0 if report.ok else 1
    finally:
        close = getattr(adapter, "close", None)
        if close:
            await close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--date", help="session date the sheet describes (YYYY-MM-DD)")
    parser.add_argument("--gsid", type=int, help="gaming session id, if you already know it")
    args = parser.parse_args()
    if not args.image.exists():
        print(f"no such file: {args.image}")
        return 2
    return asyncio.run(run(args.image, args.date, args.gsid))


if __name__ == "__main__":
    raise SystemExit(main())
