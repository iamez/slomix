#!/usr/bin/env python3
"""rescore_session_results.py — recompute one session's BOX result in place.

For the times a session_results row is wrong for a reason that is now fixed:
the session-144 incident (2026-08-11) left a human gather night scored 0:0
with OMNIBOT rosters, because a stale bot roster in session_teams poisoned
the scorer. With the stale-roster guard in StopwatchScoringService this
recompute produces the correct rosters and score, and the extended
ON CONFLICT list makes it overwrite everything the scorer computes.

    python scripts/rescore_session_results.py 2026-08-11 --gsid 144
    python scripts/rescore_session_results.py 2026-08-11            # by date

Prints the session_results row before and after, so the run itself is the
evidence. Uses the bot's own scoring service — no scoring logic lives here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bot.config import load_config  # noqa: E402
from bot.core.database_adapter import create_adapter  # noqa: E402
from bot.services.stopwatch_scoring_service import (  # noqa: E402
    StopwatchScoringService,
)


async def _show_row(adapter, session_date: str, gsid: int | None) -> None:
    if gsid is not None:
        row = await adapter.fetch_one(
            "SELECT team_1_name, team_1_score, team_2_score, team_2_name, "
            "       team_1_guids, team_2_guids, updated_at "
            "FROM session_results WHERE gaming_session_id = ? AND map_name = 'ALL'",
            (gsid,),
        )
    else:
        row = await adapter.fetch_one(
            "SELECT team_1_name, team_1_score, team_2_score, team_2_name, "
            "       team_1_guids, team_2_guids, updated_at "
            "FROM session_results "
            "WHERE SUBSTRING(CAST(session_date AS TEXT), 1, 10) = ? AND map_name = 'ALL'",
            (session_date,),
        )
    if not row:
        print("  (no session_results row)")
        return
    t1n, t1s, t2s, t2n, g1, g2, upd = row
    g1 = json.loads(g1) if isinstance(g1, str) else (g1 or [])
    g2 = json.loads(g2) if isinstance(g2, str) else (g2 or [])
    print(f"  {t1n} {t1s} : {t2s} {t2n}   (updated_at {upd})")
    print(f"  team_1_guids: {g1}")
    print(f"  team_2_guids: {g2}")


async def _run(session_date: str, gsid: int | None) -> int:
    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    try:
        print(f"BEFORE ({session_date}, gsid={gsid}):")
        await _show_row(adapter, session_date, gsid)

        scorer = StopwatchScoringService(adapter)
        scores = await scorer.calculate_session_scores(session_date)
        if not scores:
            print("Scorer returned nothing — no valid rounds or no roster; "
                  "nothing written.")
            return 1
        if gsid is not None and scores.get('_gaming_session_id') != gsid:
            print(f"Scorer resolved gaming_session_id="
                  f"{scores.get('_gaming_session_id')}, expected {gsid} — "
                  "refusing to write.")
            return 1
        saved = await scorer.save_session_results(scores)
        if not saved:
            print("save_session_results reported failure.")
            return 1

        print(f"AFTER ({session_date}, gsid={gsid}):")
        await _show_row(adapter, session_date, gsid)
        return 0
    finally:
        await adapter.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session_date", help="YYYY-MM-DD of the session to re-score")
    ap.add_argument("--gsid", type=int, default=None,
                    help="expected gaming_session_id (safety check + row display)")
    args = ap.parse_args()
    return asyncio.run(_run(args.session_date, args.gsid))


if __name__ == "__main__":
    raise SystemExit(main())
