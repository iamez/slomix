#!/usr/bin/env python3
"""check_live_kill_coverage.py — do the engine and the live stream agree on kills?

The Live page's K/D columns and alive dots are fed by `K` lines that
`live_events.lua` writes from `et_Obituary`. Those lines stopped arriving the
day live_events shipped (2026-08-12) and nobody noticed for eight days, because
the same module kept writing damage, movement and map lines — the feed looked
alive. Nothing compared it against a second source.

This is that second source. The engine's own console log records every scored
kill as `Kill: <killer> <victim> <mod>:`; the Lua stream records the same event
as a `K` line. Over one round they must agree within a small margin (a kill at
the very edge of a log rotation can land on either side).

    python scripts/check_live_kill_coverage.py \\
        --console ~/.etlegacy/legacy/etconsole.log \\
        --live    ~/.etlegacy/legacy/slomix-live.log

Exit code 0 = the two agree, 1 = the live stream is missing kills (the failure
this exists to catch), 2 = bad arguments / unreadable input.

Read-only. Safe to run on the game server while a round is in progress —
`slomix-live.log` is truncated on map load, so run it DURING the round you care
about, not after.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# `  35725 Kill: 3 6 8: <killer> killed <victim> by MOD_MP40`
_ENGINE_KILL = re.compile(rb"^\s*\d+\s+Kill:\s")
# `K <ms> <killer> <victim> <mod> <x,y,z> <x,y,z> <health> <dist>`
_LIVE_KILL = re.compile(rb"^K\s")
# The engine's own restart marker — everything before the last one belongs to a
# previous round and would inflate the engine side against a truncated live log.
_INIT_GAME = re.compile(rb"InitGame")


def count_engine_kills(path: Path) -> int:
    """Kills since the last InitGame — the window the live log also covers."""
    kills = 0
    with path.open("rb") as fh:
        for raw in fh:
            if _INIT_GAME.search(raw):
                kills = 0
            elif _ENGINE_KILL.match(raw):
                kills += 1
    return kills


def count_live_kills(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for raw in fh if _LIVE_KILL.match(raw))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--console", required=True, type=Path, help="etconsole.log")
    ap.add_argument("--live", required=True, type=Path, help="slomix-live.log")
    ap.add_argument("--tolerance", type=int, default=2,
                    help="kills the live stream may miss before this fails "
                         "(default 2 — covers a kill landing across a rotation)")
    ap.add_argument("--min-kills", type=int, default=5,
                    help="below this many engine kills the comparison is noise "
                         "and the check reports nothing (default 5)")
    args = ap.parse_args()

    for p in (args.console, args.live):
        if not p.is_file():
            print(f"not a readable file: {p}", file=sys.stderr)
            return 2

    engine = count_engine_kills(args.console)
    live = count_live_kills(args.live)

    if engine < args.min_kills:
        print(f"engine kills {engine} < --min-kills {args.min_kills}: too early to judge")
        return 0

    missing = engine - live
    print(f"engine kills: {engine}   live-stream K lines: {live}   missing: {missing}")

    if missing > args.tolerance:
        pct = 100.0 * missing / engine
        print(
            f"\nFAIL: the live stream is missing {missing} kills ({pct:.0f}%).\n"
            "The Live page's K/D columns and alive dots are fed by these lines, "
            "so they are wrong right now.\n"
            "First thing to check: does any Lua module ahead of live_events.lua "
            "in `lua_modules` return a value from et_Obituary? Any value — 0 "
            "included — stops the engine's module walk "
            "(see docs/GAMESERVER_LIVE_LUA_MAP.md).",
            file=sys.stderr,
        )
        return 1

    print("OK: the live stream carries the engine's kills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
