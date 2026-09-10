#!/usr/bin/env python3
"""W6: join the engine's answer to ours, segment by segment. READ-ONLY.

This is the comparison the whole geometry toolchain has been waiting for. The
2026-08-20 kill validation could only bound our error from above (90.4%),
because a bullet and our trace are not the same question: G_HistoricalTrace with
MASK_SHOT against antilag positions with entities clipped, versus CONTENTS_SOLID
through world brushes at a quantised position. Here both sides are asked the
identical question about the identical geometry with the identical float32
coordinates, so there is nothing left to explain a disagreement with.

⭐ THE BAR IS ~100%, NOT 90.4%. Every mismatch is a defect in our tracer and
this script's job is to hand over the segment that proves it.

The engine's own answer carries the diagnosis with it: `surfaceFlags` and
`contents` say WHAT stopped the trace, which separates a brush-reader bug
(bsp.py) from a patch-tessellation bug (patch.py) without further guessing.

Four things fail the run outright rather than being averaged away:
  * a control answering wrong (DOWN must block, TINY must be clear) — the
    capture is broken and no other number in it means anything;
  * an entityNum that is not 1022/1023 — entNum=-2 did not do what
    sv_world.c:749 says, so the comparison is not world-against-world;
  * an ERROR row — a trace that did not run must not read as a shorter sample;
  * a capture whose row set differs from the fixture's — a missing row is
    dropped from the denominator, and the controls are written last so that a
    truncation loses them first.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

ENTITYNUM_WORLD = 1022
ENTITYNUM_NONE = 1023

#: What each control MUST answer, known before the engine is asked.
#:
#: DOWN traces 10,000 units straight down from a point a player occupied — they
#: were standing on something, so it must block. TINY traces one unit sideways
#: inside the space they already filled, so it must be clear. A control that
#: does not carry its own expected answer cannot fail, and a check that cannot
#: fail is decoration.
CONTROL_EXPECTATIONS = {"control_down": "blocked", "control_tiny": "clear"}


def read_fixture(path: Path) -> tuple[dict, dict[str, tuple]]:
    meta: dict[str, str] = {}
    rows: dict[str, tuple] = {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            if "=" in line:
                for part in line.lstrip("# ").split():
                    if "=" in part:
                        k, _, v = part.partition("=")
                        meta.setdefault(k, v)
            continue
        f = line.split()
        if len(f) >= 10:
            rows[f[0]] = (f[1], f[8], f[9])   # kind, offline_status, offline_startsolid
    return meta, rows


def read_capture(path: Path) -> tuple[dict, dict[str, tuple]]:
    meta: dict[str, str] = {}
    rows: dict[str, tuple] = {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            for part in line.lstrip("# ").split():
                if "=" in part:
                    k, _, v = part.partition("=")
                    meta.setdefault(k, v)
            continue
        f = line.split()
        if len(f) >= 7:
            rows[f[0]] = tuple(f[1:7])   # fraction, startsolid, allsolid, entnum, surf, contents
    return meta, rows


def engine_status(fraction: str) -> str:
    """The engine reports a fraction; we report a verdict. fraction == 1 means
    nothing was hit along the whole segment, anything less means something was."""
    return "clear" if float(fraction) >= 1.0 else "blocked"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--show", type=int, default=8, help="mismatches to print")
    args = ap.parse_args()

    fmeta, fixture = read_fixture(args.fixture)
    cmeta, capture = read_capture(args.capture)

    print(f"  mapa: {fmeta.get('map')}   BSP sha={str(fmeta.get('bsp_sha256'))[:16]}  "
          f"pk3={fmeta.get('pk3')}")
    print(f"  motor: {cmeta.get('us_per_trace')} us/sled, {cmeta.get('batches')} serij")

    missing = set(fixture) - set(capture)
    extra = set(capture) - set(fixture)
    if missing or extra:
        print(f"  ⚠️ manjka v zajemu: {len(missing)}   odveč: {len(extra)}")
        # ⛔ These fail the run rather than being noted. A missing row is simply
        # dropped from `total_n`, so a truncated capture reports a clean rate
        # over whatever survived — and the controls are written LAST precisely
        # so that a truncation loses them. That combination turns the one thing
        # designed to catch a broken capture into the first casualty of one
        # (CodeRabbit, PR #797).
        for idx in sorted(missing, key=int)[:5]:
            print(f"      manjka idx={idx} ({fixture[idx][0]})")

    hard_fail: list[str] = []
    by_kind: dict[str, Counter[str]] = {}
    mismatches: list[tuple] = []
    entnum_bad = 0
    errors = 0

    for idx, (kind, off_status, off_ss) in sorted(fixture.items(), key=lambda kv: int(kv[0])):
        cap = capture.get(idx)
        if cap is None:
            continue
        frac, ss, _all, entnum, surf, contents = cap
        if frac == "ERROR":
            errors += 1
            continue
        if entnum not in (str(ENTITYNUM_WORLD), str(ENTITYNUM_NONE)):
            entnum_bad += 1

        eng = engine_status(frac)
        counter = by_kind.setdefault(kind, Counter())
        counter["n"] += 1
        if eng == off_status:
            counter["agree"] += 1
        else:
            counter["disagree"] += 1
            mismatches.append((idx, kind, off_status, eng, frac, surf, contents))
        if ss != off_ss:
            counter["startsolid_differs"] += 1

        # Controls carry their own answer; a wrong one invalidates the capture.
        #
        # ⭐ The expected value comes from CONTROL_EXPECTATIONS — the control's
        # design — not from what was observed. The previous version derived it
        # from the measured fraction, which made it unfalsifiable, and then
        # `del`eted it without ever comparing. Codacy saw the unused variable;
        # the real defect was a control that could not fail.
        #
        # Both sides are checked against it, not against each other: two sides
        # that agree DOWN is clear is precisely the breakage a control exists
        # to catch, and an agreement test passes it.
        expected = CONTROL_EXPECTATIONS.get(kind)
        if expected is not None:
            if off_status != expected:
                hard_fail.append(
                    f"{kind} idx={idx}: offline={off_status}, must be {expected}"
                )
            if eng != expected:
                hard_fail.append(
                    f"{kind} idx={idx}: engine={eng} (frac={frac}), "
                    f"must be {expected}"
                )

    print("\n  === ujemanje po vrsti daljice ===")
    total_n = total_agree = 0
    for kind in ("blocked", "clear", "random", "control_down", "control_tiny"):
        c = by_kind.get(kind)
        if not c:
            continue
        n, a = c["n"], c["agree"]
        total_n += n
        total_agree += a
        print(f"    {kind:8s} n={n:5d}  ujemanje {100.0 * a / max(n, 1):6.2f} %"
              f"   startsolid razlik: {c['startsolid_differs']}")
    print(f"    {'SKUPAJ':8s} n={total_n:5d}  ⭐ ujemanje "
          f"{100.0 * total_agree / max(total_n, 1):6.2f} %")

    # ⭐ Presence, not only value. Both sides now enforce what a control must
    # ANSWER, but nothing required a control to BE THERE — so a run with zero
    # controls passed at exit 0 with no falsifier at all (CodeRabbit, #797).
    # Recorded before the report below, so a missing control is printed as the
    # hard failure it is rather than only changing the exit code.
    hard_fail.extend(
        f"{kind}: no rows compared — the run has no falsifier"
        for kind in CONTROL_EXPECTATIONS
        if not by_kind.get(kind, {}).get("n")
    )

    print("\n  === trde napake (vsaka razveljavi tek) ===")
    print(f"    ERROR vrstic:                 {errors}")
    print(f"    entityNum ni 1022/1023:       {entnum_bad}")
    print(f"    napačna kontrola:             {len(hard_fail)}")
    for h in hard_fail[:5]:
        print(f"      {h}")

    if mismatches:
        print(f"\n  === prvih {min(args.show, len(mismatches))} neujemanj "
              f"(surfaceFlags pove, kaj je motor zadel) ===")
        for idx, kind, off, eng, frac, surf, contents in mismatches[:args.show]:
            print(f"    idx={idx:5s} {kind:8s} offline={off:8s} motor={eng:8s} "
                  f"frac={frac:12s} surf={surf} contents={contents}")

    print("\n  === celovitost zajema ===")
    print(f"    manjka v zajemu:              {len(missing)}")
    print(f"    odveč v zajemu:               {len(extra)}")

    ok = (errors == 0 and entnum_bad == 0 and not hard_fail
          and total_agree == total_n
          and not missing and not extra)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
