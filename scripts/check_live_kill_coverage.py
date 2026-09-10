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


def is_usable_live_kill(raw: bytes) -> bool:
    """The minimum grammar `vps_scripts/liveview_parser.py` accepts for a K.

    Counting every line that merely starts with "K " overstates the live side:
    the parser drops a record whose timestamp is not a number, that has fewer
    than nine fields, or whose killer/victim slots are unparseable (a None slot
    would misattribute the kill). A malformed line would then stand in for a
    genuinely missing one and this check would answer OK — the exact silence it
    exists to break (CodeRabbit review, #785).

    Deliberately duplicated rather than imported: this script is meant to run
    on the game server, where the website package is not deployed. The
    duplication is held to the parser by
    tests/unit/test_live_kill_coverage_grammar.py, which feeds both the same
    lines and fails when they disagree.
    """
    tok = raw.split()
    return (
        len(tok) >= 9
        and tok[0] == b"K"
        and tok[1].isdigit()
        and tok[2].lstrip(b"-").isdigit()
        and tok[3].lstrip(b"-").isdigit()
    )


def count_live_kills(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for raw in fh if is_usable_live_kill(raw))


def _non_negative(value: str) -> int:
    """A negative threshold quietly inverts the check.

    `--tolerance -1` fails a run where the two sides agree exactly;
    `--min-kills -1` disables the "too early to judge" guard, so a round with
    two kills reports a verdict. Both are argument errors, not opinions
    (CodeRabbit review, #785).
    """
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be zero or more, got {number}")
    return number


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--console", required=True, type=Path, help="etconsole.log")
    ap.add_argument("--live", required=True, type=Path, help="slomix-live.log")
    ap.add_argument("--tolerance", type=_non_negative, default=2,
                    help="kills the live stream may miss before this fails "
                         "(default 2 — covers a kill landing across a rotation)")
    ap.add_argument("--min-kills", type=_non_negative, default=5,
                    help="below this many engine kills the comparison is noise "
                         "and the check reports nothing (default 5)")
    args = ap.parse_args()

    for p in (args.console, args.live):
        if not p.is_file():
            print(f"not a readable file: {p}", file=sys.stderr)
            return 2

    # is_file() proves the path existed a moment ago, not that the read will
    # succeed. This runs against logs that rotate under it — slomix-live.log is
    # truncated on map load — so an OSError here is an ordinary Tuesday, and the
    # docstring already promises exit 2 for unreadable input rather than a
    # traceback (CodeRabbit review, #785).
    try:
        engine = count_engine_kills(args.console)
        live = count_live_kills(args.live)
    except OSError as exc:
        print(f"could not read the logs: {exc}", file=sys.stderr)
        return 2

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
