#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "== WS7 Kill-Assists Smoke Snapshot =="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo

echo "[1] Frontend syntax check"
node --check website/js/sessions.js
echo "frontend_syntax=OK"
echo

echo "[2] API + Discord path smoke"
python3 - <<'PY'
import asyncio
import json
import sys

from bot.config import load_config
from bot.core.database_adapter import create_adapter
from bot.services.session_data_service import SessionDataService
from bot.services.session_view_handlers import SessionViewHandlers
from website.backend.routers.api import get_last_session, get_session_graph_stats


class _CaptureCtx:
    def __init__(self):
        self.embeds = []

    async def send(self, *args, **kwargs):
        embed = kwargs.get("embed")
        if embed is not None:
            self.embeds.append(embed)


async def main():
    cfg = load_config()
    db = create_adapter(**cfg.get_database_adapter_kwargs())
    await db.connect()
    try:
        last = await get_last_session(db=db)
        last_players = [
            p
            for team in (last.get("teams") or [])
            for p in (team.get("players") or [])
        ]
        last_has_kill_assists = bool(last_players) and all(
            "kill_assists" in p for p in last_players
        )
        last_kill_assists_sum = sum(int(p.get("kill_assists") or 0) for p in last_players)

        graphs = await get_session_graph_stats(
            last["date"], gaming_session_id=last.get("gaming_session_id"), db=db
        )
        graph_players = graphs.get("players") or []
        graph_has_kill_assists = bool(graph_players) and all(
            "kill_assists" in (p.get("combat_defense") or {}) for p in graph_players
        )
        graph_kill_assists_sum = sum(
            int((p.get("combat_defense") or {}).get("kill_assists") or 0)
            for p in graph_players
        )

        data_service = SessionDataService(db)
        latest_date = await data_service.get_latest_session_date()
        _, session_ids, session_ids_str, player_count = await data_service.fetch_session_data(latest_date)

        ctx = _CaptureCtx()
        view = SessionViewHandlers(db_adapter=db, stats_calculator=None)
        await view.show_objectives_view(
            ctx=ctx,
            latest_date=latest_date,
            session_ids=session_ids,
            session_ids_str=session_ids_str,
            player_count=player_count,
        )

        first_field = ""
        objectives_has_ka = False
        if ctx.embeds and ctx.embeds[0].fields:
            first_field = ctx.embeds[0].fields[0].value
            objectives_has_ka = "Kill Assists:" in first_field

        checks = {
            "last_session_ka_field_present": bool(last_has_kill_assists),
            "graphs_ka_field_present": bool(graph_has_kill_assists),
            "objectives_embed_has_ka_line": bool(objectives_has_ka),
            "ka_sums_match": int(last_kill_assists_sum) == int(graph_kill_assists_sum),
        }
        overall_ok = all(checks.values())

        print(f"last_session_date={last['date']}")
        print(f"last_session_gaming_session_id={last.get('gaming_session_id')}")
        print(f"last_session_players={len(last_players)}")
        print(f"last_session_ka_sum={last_kill_assists_sum}")
        print(f"graphs_players={len(graph_players)}")
        print(f"graphs_ka_sum={graph_kill_assists_sum}")
        print(f"objectives_embed_sent={len(ctx.embeds)}")
        print(f"objectives_embed_first_field_has_ka={objectives_has_ka}")
        print("checks_json=" + json.dumps(checks, sort_keys=True))
        print(f"overall_ok={overall_ok}")
        if first_field:
            preview = first_field.replace("\n", " | ")
            print(f"objectives_first_field_preview={preview}")

        if not overall_ok:
            sys.exit(1)
    finally:
        await db.close()


asyncio.run(main())
PY

echo
echo "WS7 smoke check: PASS"
