#!/usr/bin/env python3
"""liveview_replay — S0 harness: replay a recorded ``legacy3.log`` slice
through the live-view parser.

The game server is empty most of the day and the dev box is LAN
outbound-only, so every downstream slice (S1 ingest, S3 panel) develops
against THIS harness instead of live traffic (research: "S0 ni pogajalski").

Usage:
  python scripts/liveview_replay.py <log-file> [--types POPUP,KILL]
      [--speed 60] [--summary]

  --types    emit only these event types (comma-separated)
  --speed    replay pacing: 0 = instant dump (default); N = N× real time,
             derived from level-time deltas (map restarts reset the clock)
  --summary  per-round synthesis instead of the JSONL stream
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vps_scripts.liveview_parser import parse_line  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logfile", type=Path)
    ap.add_argument("--types", default="")
    ap.add_argument("--speed", type=float, default=0.0)
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    wanted = {t.strip().upper() for t in args.types.split(",") if t.strip()}
    rounds: list[Counter] = [Counter()]
    prev_ms: int | None = None
    total = 0

    for line in args.logfile.read_text(encoding="utf-8", errors="ignore").splitlines():
        ev = parse_line(line)
        if ev is None:
            continue
        total += 1

        if args.summary:
            rounds[-1][ev.type] += 1
            if ev.type == "ROUND_END":
                rounds.append(Counter())
            continue

        if wanted and ev.type not in wanted:
            continue
        if args.speed > 0 and ev.level_ms is not None:
            if prev_ms is not None and ev.level_ms > prev_ms:
                time.sleep(min((ev.level_ms - prev_ms) / 1000.0 / args.speed, 5.0))
            prev_ms = ev.level_ms
        print(json.dumps({"type": ev.type, "level_ms": ev.level_ms, **ev.fields},
                         ensure_ascii=False))

    if args.summary:
        done = [r for r in rounds if r]
        print(f"dogodkov skupaj: {total} · zaključenih rund: "
              f"{sum(1 for r in done if r.get('ROUND_END'))}", file=sys.stderr)
        for i, r in enumerate(done, 1):
            top = ", ".join(f"{t}×{c}" for t, c in sorted(r.items(), key=lambda x: -x[1])[:8])
            print(f"  runda-blok {i}: {top}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
