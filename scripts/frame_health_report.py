#!/usr/bin/env python3
"""Read the game server's frame_health.log (as pulled by the collector into
~/slomix-server-logs/frame_health-YYYY-MM-DD.log) and say who owned the
stalls.

Lines (proximity_tracker.lua v6.13 and the shared block in every module):
  FH init wall=<ms> version=<v> mod=<name>          per-module map-load proof
  FH watcher wall=<ms> version=<v>                  the gap watcher's own proof
  FH wall=<ms> gap=<ms> self=<ms> gs=<n> players=<n> [lt=<ms> paused=<0|1>]
  FM wall=<ms> mod=<name> self=<ms> top=<section>:<ms>

Attribution: for a gap line at wall W with gap G, the frame the gap
measures ran in (W - G, W]; every FM line whose wall falls in that window
is a module's cost inside it. sum(self) is "our Lua", G - sum is the
residual (engine or host). `top` names the costliest section per module.

Usage:
  scripts/frame_health_report.py ~/slomix-server-logs/frame_health-2026-09-02.log [...]
  scripts/frame_health_report.py --burst-gap-ms 30000 --min-gap 500 <files>
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

GAP_RE = re.compile(r"^FH wall=(\d+) gap=(\d+) self=(-?\d+) gs=(-?\d+) players=(\d+)(?: lt=(-?\d+) paused=(\d))?")
FM_RE = re.compile(r"^FM wall=(\d+) mod=(\S+) self=(\d+) top=(\S+):(\d+)")
INIT_RE = re.compile(r"^FH init wall=(\d+) version=(\S+)(?: mod=(\S+))?")


@dataclass
class Gap:
    wall: int
    gap: int
    self_ms: int
    gs: int
    players: int
    lt: int | None
    paused: bool
    modules: dict[str, int] = field(default_factory=dict)
    tops: dict[str, str] = field(default_factory=dict)

    @property
    def lua_ms(self) -> int:
        # The tracker's own self is on the gap line; FM lines of the tracker
        # for the same frame would double it, so the tracker is taken from
        # whichever is larger, never summed twice.
        others = sum(v for k, v in self.modules.items() if k != "proximity_tracker")
        tracker = max(self.self_ms if self.self_ms > 0 else 0, self.modules.get("proximity_tracker", 0))
        return others + tracker

    @property
    def residual_ms(self) -> int:
        return max(0, self.gap - self.lua_ms)


@dataclass
class Report:
    gaps: list[Gap]
    fm: list[tuple[int, str, int, str, int]]
    inits: list[tuple[int, str, str | None]]


def parse(lines: list[str]) -> Report:
    gaps: list[Gap] = []
    fm: list[tuple[int, str, int, str, int]] = []
    inits: list[tuple[int, str, str | None]] = []
    for line in lines:
        m = GAP_RE.match(line)
        if m:
            wall, gap, self_ms, gs, players, lt, paused = m.groups()
            gaps.append(Gap(int(wall), int(gap), int(self_ms), int(gs), int(players),
                            int(lt) if lt is not None else None, paused == "1"))
            continue
        m = FM_RE.match(line)
        if m:
            wall, mod, self_ms, top, top_ms = m.groups()
            fm.append((int(wall), mod, int(self_ms), top, int(top_ms)))
            continue
        m = INIT_RE.match(line)
        if m:
            wall, version, mod = m.groups()
            inits.append((int(wall), version, mod))
    return Report(gaps, fm, inits)


def attribute(report: Report) -> None:
    """Attach every FM line to the gap whose frame window contains it.

    The window is (wall - gap, wall]: the gap line is written at the START
    of the frame after the slow one, so the slow frame ENDED at `wall` and
    began `gap` ms earlier. An FM line is written at the end of its own
    frame, so a module's cost inside the slow frame has wall in that window.
    """
    by_wall = sorted(report.gaps, key=lambda g: g.wall)
    for wall, mod, self_ms, top, top_ms in report.fm:
        for g in by_wall:
            if g.wall - g.gap < wall <= g.wall:
                g.modules[mod] = max(g.modules.get(mod, 0), self_ms)
                g.tops[mod] = f"{top}:{top_ms}"
                break


def bursts(gaps: list[Gap], burst_gap_ms: int) -> list[list[Gap]]:
    out: list[list[Gap]] = []
    cur: list[Gap] = []
    for g in sorted(gaps, key=lambda x: x.wall):
        if cur and g.wall - cur[-1].wall > burst_gap_ms:
            out.append(cur)
            cur = []
        cur.append(g)
    if cur:
        out.append(cur)
    return out


def render(report: Report, *, burst_gap_ms: int, min_gap: int) -> str:
    attribute(report)
    lines: list[str] = []
    gaps = [g for g in report.gaps if g.gap >= min_gap]
    lines.append(f"gap lines: {len(report.gaps)} (>= {min_gap} ms: {len(gaps)}) · FM lines: {len(report.fm)} · init lines: {len(report.inits)}")
    mods = sorted({m for _, _, m in report.inits if m})
    if mods:
        lines.append("modules that proved their write path: " + ", ".join(mods))
    total_gap = sum(g.gap for g in gaps)
    total_lua = sum(g.lua_ms for g in gaps)
    paused = [g for g in gaps if g.paused]
    empty = [g for g in gaps if g.players == 0]
    lines.append(f"stall time: {total_gap} ms · our Lua: {total_lua} ms ({(total_lua / total_gap * 100) if total_gap else 0:.0f} %) · residual (engine/host): {total_gap - total_lua} ms")
    lines.append(f"stalls while paused: {len(paused)} · on an empty server: {len(empty)}")
    per_mod: dict[str, list[int]] = defaultdict(list)
    for g in gaps:
        for m, v in g.modules.items():
            per_mod[m].append(v)
    if per_mod:
        lines.append("per module (inside stalls): " + " · ".join(
            f"{m} n={len(v)} sum={sum(v)} max={max(v)}" for m, v in sorted(per_mod.items())))
    tops: dict[str, int] = defaultdict(int)
    for g in gaps:
        for m, t in g.tops.items():
            section = t.split(":")[0]
            tops[f"{m}/{section}"] += 1
    if tops:
        lines.append("costliest sections named: " + ", ".join(f"{k}×{v}" for k, v in sorted(tops.items(), key=lambda kv: -kv[1])[:10]))
    lines.append("")
    lines.append(f"bursts (stalls closer than {burst_gap_ms} ms):")
    for b in bursts(gaps, burst_gap_ms):
        span = (b[-1].wall - b[0].wall) / 1000
        gsum = sum(g.gap for g in b)
        lsum = sum(g.lua_ms for g in b)
        mx = max(g.gap for g in b)
        who = defaultdict(int)
        for g in b:
            for m, v in g.modules.items():
                who[m] += v
        who_s = ", ".join(f"{m}={v}" for m, v in sorted(who.items(), key=lambda kv: -kv[1])[:3]) or "-"
        lines.append(f"  wall={b[0].wall:>10} n={len(b):>4} span={span:8.1f}s max_gap={mx:6} gap_sum={gsum:7} lua={lsum:7} ({(lsum / gsum * 100) if gsum else 0:3.0f} %) players={b[0].players} paused={'y' if any(g.paused for g in b) else 'n'} top={who_s}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--burst-gap-ms", type=int, default=30000)
    ap.add_argument("--min-gap", type=int, default=100)
    args = ap.parse_args(argv)
    lines: list[str] = []
    for f in args.files:
        lines.extend(f.read_text(encoding="utf-8", errors="replace").splitlines())
    print(render(parse(lines), burst_gap_ms=args.burst_gap_ms, min_gap=args.min_gap))
    return 0


if __name__ == "__main__":
    sys.exit(main())
