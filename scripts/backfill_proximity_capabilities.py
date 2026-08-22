#!/usr/bin/env python3
"""Fill `proximity_processed_files.capabilities` from the raw files. DRY-RUN BY DEFAULT.

Migration 062 added the column in 2026 and left it NULL in all 828 rows,
explicitly deferring the fill: "the v3 shadow falls back to its population-level
coverage proxy until a backfill (owner-gated) populates these". This is that
backfill.

⭐ WHAT IT MAY AND MAY NOT CONCLUDE

Every gated section in the tracker is written as `if isFeatureEnabled(x) and
#rows > 0`, so a section carrying rows PROVES its capture was on, and a missing
section proves nothing whatsoever — capture off and capture on with nothing to
report produce byte-identical files. This script therefore only ever writes
`enabled` or `unknown` for a file that predates the 6.11 declaration. It never
writes `disabled`. A `disabled` here would not be caution, it would be a claim
we cannot support, and it is precisely the claim that would let a consumer say
"no gunfire in this round" about a round where gunfire simply was not recorded.

It also fills `round_key` where it is missing, because that column is the only
bridge from a processed file to a round and 644 of the rows do not have it —
without it the manifest is stored where no consumer can reach it.

Rows whose raw file is gone stay NULL. NULL is the honest answer for a file we
cannot read, and leaving it is the point rather than a shortfall.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from proximity.parser.capability_manifest import (  # noqa: E402
    DISABLED,
    ENABLED,
    build_manifest,
    scan_file,
)


def _connect():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        dbname=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
    )


def _round_key(filename: str, scanned_header: dict) -> str | None:
    """`date|map|round|start_unix`, the shape migration 062 defined.

    The date comes from the filename (`2026-08-21-113210-map-round-1_...`) and
    the rest from the header, which is how the parser builds it too — checked
    against the 184 keys the parser has already written: 182 identical.

    ⚠️ The two that differ do so in the ROUND NUMBER, which the parser
    normalises from context this script does not have. That is why the consumer
    (`round_web_service.load_capture_policy`) matches on the last field alone:
    `round_start_unix` identifies 950 of 951 rounds by itself, so a round number
    we cannot reproduce exactly can no longer cause a mis-join. Rows that
    already carry a key are left alone regardless.
    """
    parts = filename.split("-")
    if len(parts) < 4:
        return None
    date = "-".join(parts[:3])
    map_name = scanned_header.get("map_name")
    round_num = scanned_header.get("round_num")
    start_unix = scanned_header.get("round_start_unix")
    if not map_name or round_num is None or start_unix is None:
        return None
    return f"{date}|{map_name}|{round_num}|{start_unix}"


def _read_header(path: Path) -> dict:
    """map/round/start_unix, read without parsing the whole file."""
    out: dict = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("#"):
                break
            text = line.strip()
            for prefix, key, cast in (
                ("# map=", "map_name", str),
                ("# round=", "round_num", int),
                ("# round_start_unix=", "round_start_unix", int),
            ):
                if text.startswith(prefix):
                    try:
                        out[key] = cast(text[len(prefix):])
                    except ValueError:
                        pass
            if len(out) == 3:
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--proximity-dir",
        type=Path,
        default=Path("/home/samba/share/slomix_discord/local_proximity"),
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="write. Without it nothing is modified and the report is the output.",
    )
    ap.add_argument("--backup-dir", type=Path, default=Path("."))
    ap.add_argument("--limit", type=int, default=0, help="0 = every eligible row")
    args = ap.parse_args()

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT filename, round_key, capabilities FROM proximity_processed_files "
        "ORDER BY filename"
    )
    rows = cursor.fetchall()

    planned: list[tuple[str, str, str | None]] = []
    backup: list[dict] = []
    missing_file = 0
    already = 0
    per_flag: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    key_filled = 0

    for filename, round_key, existing in rows:
        if existing is not None:
            already += 1
            continue
        path = args.proximity_dir / filename
        if not path.exists():
            missing_file += 1
            continue

        scanned = scan_file(str(path))
        manifest = build_manifest(
            sections_with_rows=scanned["sections_with_rows"],
            declared=scanned["declared"],
            test_mode=scanned["test_mode"],
            tracker_version_full=scanned["tracker_version_full"],
            position_sample_interval_ms=scanned["position_sample_interval_ms"],
        )

        # An inferred manifest must never claim a capture was off. This is the
        # script's central promise, so it is asserted per row rather than
        # trusted from the helper.
        if manifest["source"] == "sections_observed":
            assert DISABLED not in manifest["capabilities"].values(), (
                f"{filename}: inference produced `disabled`, which it cannot prove"
            )

        new_key = round_key
        if not round_key:
            new_key = _round_key(filename, _read_header(path))
            if new_key:
                key_filled += 1

        planned.append((filename, json.dumps(manifest), new_key))
        backup.append(
            {"filename": filename, "capabilities": existing, "round_key": round_key}
        )
        sources[manifest["source"]] += 1
        for flag, state in manifest["capabilities"].items():
            if state == ENABLED:
                per_flag[flag] += 1
        if args.limit and len(planned) >= args.limit:
            break

    print(f"  vrstic skupaj:            {len(rows)}")
    print(f"  že imajo manifest:        {already}")
    print(f"  ⭐ za zapis:               {len(planned)}")
    print(f"  brez surove datoteke:     {missing_file}  (ostanejo NULL — pravilno)")
    print(f"  round_key na novo:        {key_filled}")
    print(f"  viri: {dict(sources)}")
    print("\n  dokazano VKLOPLJENO (nikoli 'disabled' po tej poti):")
    for flag, count in per_flag.most_common():
        share = 100.0 * count / max(len(planned), 1)
        print(f"    {flag:24s} {count:4d}  ({share:5.1f} %)")

    if not args.apply:
        print("\n  DRY-RUN — nič ni bilo zapisano. Za zapis: --apply")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = args.backup_dir / f"capabilities-backfill-backup-{stamp}.json"
    backup_path.write_text(json.dumps(backup, indent=1))
    print(f"\n  varnostna kopija prejšnjega stanja: {backup_path} ({len(backup)} vrstic)")

    cursor.executemany(
        """UPDATE proximity_processed_files
              SET capabilities = %s::jsonb,
                  round_key = COALESCE(round_key, %s)
            WHERE filename = %s
              AND capabilities IS NULL""",
        [(payload, key, filename) for filename, payload, key in planned],
    )
    conn.commit()
    print(f"  zapisanih vrstic: {cursor.rowcount if cursor.rowcount >= 0 else len(planned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
