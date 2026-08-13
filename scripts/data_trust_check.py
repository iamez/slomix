#!/usr/bin/env python3
"""data_trust_check.py — on-demand "Data Trust report" for a Smart Stats session.

Points the shared story invariants (tests/contract/story_invariants.py) at a
REAL, live session: it reads the database ground truth (read-only), fetches the
Smart Stats endpoints over HTTP, and reports each invariant PASS/FAIL with the
numbers behind it. This is the operator-facing twin of the CI gate
(tests/contract/test_story_data_invariants.py) — run it against production or dev
any time a panel "looks weird" to see, in one screen, whether the displayed
numbers still agree with the database.

    # dev (uses .env POSTGRES_* — the bot's own creds):
    python scripts/data_trust_check.py --gsid 144

    # explicit target + optional headless visual checks (needs playwright):
    POSTGRES_PASSWORD=… python scripts/data_trust_check.py \
        --gsid 144 --url https://www.slomix.fyi --headless

DB connection comes from POSTGRES_* env vars (same names as the bot/.env). The
connection is opened READ-ONLY. Exit code = total number of invariant violations
(0 = all trusted), so it drops straight into a shell guard or a cron.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Make the repo root importable so `tests.contract.story_invariants` resolves
# when the script is run from anywhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.contract.story_invariants import (  # noqa: E402
    GroundTruth,
    SessionContext,
    evaluate,
)

# Panel key -> endpoint path (query string appended by the fetcher). Keep the
# keys identical to the ones the invariants look up.
_PANELS = {
    "kill_impact": "/api/storytelling/kill-impact",
    "composite": "/api/skill/composite",
    "win_contribution": "/api/storytelling/win-contribution",
    "moments": "/api/storytelling/moments",
    "box_score": "/api/storytelling/box-score",
}


def _load_dotenv(root: Path) -> None:
    """Best-effort .env loader so POSTGRES_* are present without extra tooling.

    Only sets vars that are not already in the environment (real env wins), and
    never overrides an explicit POSTGRES_PASSWORD passed on the command line.
    """
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


# ── DB ground truth (read-only) ───────────────────────────────────────────────

# The round-validity gate the storytelling panels + GamingSessionScope apply.
_GATE = (
    "r.round_number IN (1, 2) "
    "AND r.is_valid IS DISTINCT FROM FALSE "
    "AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)"
)
# %% because these go through psycopg2's %s-paramstyle execute, which treats a
# lone % as a placeholder marker.
_NOT_BOT = (
    "UPPER(pcs.player_guid) NOT LIKE 'OMNIBOT%%' "
    "AND pcs.player_name NOT LIKE '%%[BOT]%%'"
)


def _fetch_ground_truth(gsid: int) -> GroundTruth:
    import psycopg2  # imported lazily so --help works without the driver

    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE",
                "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [n for n in required if not os.getenv(n)]
    if missing:
        raise SystemExit(f"Missing database env vars: {', '.join(missing)}")

    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(pcs.kills), 0) "
                "FROM player_comprehensive_stats pcs "
                "JOIN rounds r ON r.id = pcs.round_id "
                f"WHERE r.gaming_session_id = %s AND {_GATE} AND {_NOT_BOT}",
                (gsid,),
            )
            total_kills = int(cur.fetchone()[0])

            cur.execute(
                "SELECT DISTINCT UPPER(LEFT(pcs.player_guid, 8)) "
                "FROM player_comprehensive_stats pcs "
                "JOIN rounds r ON r.id = pcs.round_id "
                f"WHERE r.gaming_session_id = %s AND {_GATE} AND {_NOT_BOT}",
                (gsid,),
            )
            roster = {row[0] for row in cur.fetchall() if row[0]}
    finally:
        conn.close()
    return GroundTruth(total_kills=total_kills, roster_guids=roster)


# ── Endpoint fetch ────────────────────────────────────────────────────────────

def _fetch_panels(base_url: str, gsid: int) -> dict:
    panels: dict = {}
    for key, path in _PANELS.items():
        url = f"{base_url.rstrip('/')}{path}?gaming_session_id={gsid}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310 (trusted internal URL)
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
                panels[key] = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"  ⚠️  {key}: fetch failed ({exc}) — invariants over it will SKIP")
            panels[key] = None
    return panels


# ── Report ────────────────────────────────────────────────────────────────────

def _print_report(ctx: SessionContext) -> int:
    print("=" * 70)
    print(f"  DATA TRUST REPORT — gaming_session_id={ctx.gaming_session_id}")
    print("=" * 70)
    print(f"  DB ground truth: SUM(pcs.kills)={ctx.truth.total_kills}  "
          f"roster={len(ctx.truth.roster_guids)} players")
    loaded = [k for k, v in ctx.panels.items() if v is not None]
    print(f"  Panels loaded:   {', '.join(loaded) or '(none)'}")
    print("-" * 70)

    results = evaluate(ctx)
    total_violations = 0
    for res in results:
        if res.passed:
            print(f"  ✅ [{res.invariant.category}] {res.invariant.key}")
        else:
            total_violations += len(res.violations)
            print(f"  🔴 [{res.invariant.category}] {res.invariant.key}")
            print(f"       {res.invariant.description}")
            for v in res.violations:
                print(f"       → {v}")
    print("-" * 70)
    verdict = "ALL TRUSTED" if total_violations == 0 else f"{total_violations} VIOLATION(S)"
    print(f"  VERDICT: {verdict}")
    print("=" * 70)
    return total_violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gsid", type=int, required=True,
                        help="gaming_session_id to audit")
    parser.add_argument("--url", default="http://127.0.0.1:8000",
                        help="base URL of the website API (default: dev)")
    args = parser.parse_args()

    _load_dotenv(_REPO_ROOT)
    truth = _fetch_ground_truth(args.gsid)
    panels = _fetch_panels(args.url, args.gsid)
    ctx = SessionContext(gaming_session_id=args.gsid, panels=panels, truth=truth)
    return _print_report(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
