"""Phase-5 checklist item 7 as a test, not a hand (docs/design/17 §3):
the intersection of the proximity inventory against what the app actually
calls, recomputed on every run.

The inventory (docs/parity/proximity_inventory.json) carries the 92 paths
of the proximity/storytelling/replay family with a disposition each:
covered / pending / dropped. Dispositions are CLAIMS, and this test is the
measurement they answer to, in both directions:

- a `pending` row the app now calls fails as STALE — flip it to covered,
  which is how phase 5's remaining-surface number ratchets down in review;
- a `covered` row the app no longer calls fails as a REGRESSION;
- the `dropped` set must equal O9's decision exactly (owner, 24. 8.):
  dashboard and the three replay duplicates, nothing else — a path
  quietly demoted to dropped is the "nothing left silent" failure O9
  exists to prevent;
- the pending COUNT is pinned, so the phase's surface only moves in a
  reviewed edit of this file.

Coverage reuses the endpoint-gap extractor (the same one H1 trusts), so
"the app calls it" means the same thing in both guards.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.integration.test_endpoint_gap import (  # noqa: E402
    _extract_new_frontend_paths,
    _template_matches,
)

INVENTORY = REPO / "docs" / "parity" / "proximity_inventory.json"

# Phase 5's remaining surface. Started at 67 on 2026-08-31; now 65
# proximity rows (trades/player-stats among them) + 1 replay row (the
# spider-web /web path — the other three replay rows are dropped, and
# every storytelling row is covered). Every page PR that adopts paths
# lowers it together with the flipped dispositions.
PENDING_BUDGET = 20

O9_DROPPED = {
    "/api/proximity/dashboard",
    "/api/replay/round/{round_id}/timeline",
    "/api/replay/round/{round_id}/positions",
    "/api/replay/round/{round_id}/paths",
}


def _load() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def _covered_now(path: str, spa_calls: set[str]) -> bool:
    return any(call == path or _template_matches(path, call) or _template_matches(call, path) for call in spa_calls)


def test_dispositions_match_what_the_app_actually_calls():
    exact, dynamic = _extract_new_frontend_paths()
    spa_calls = exact | dynamic
    problems: list[str] = []
    for row in _load()["rows"]:
        path, disp = row["path"], row["disposition"]
        if disp == "dropped":
            continue
        now = _covered_now(path, spa_calls)
        if disp == "pending" and now:
            problems.append(f"STALE: {path} is called by the app — flip it to covered")
        elif disp == "covered" and not now:
            problems.append(f"REGRESSION: {path} is marked covered but nothing calls it")
        elif disp not in ("pending", "covered"):
            problems.append(f"{path}: unknown disposition {disp!r}")
    assert not problems, "\n".join(problems)


def test_the_dropped_set_is_exactly_o9s_decision():
    dropped = {r["path"] for r in _load()["rows"] if r["disposition"] == "dropped"}
    assert dropped == O9_DROPPED, (
        f"quietly added: {sorted(dropped - O9_DROPPED)}; "
        f"quietly revived: {sorted(O9_DROPPED - dropped)} — "
        "either way it is an owner decision, not an edit"
    )
    for row in _load()["rows"]:
        if row["disposition"] == "dropped":
            assert row.get("reason"), f"{row['path']}: a dropped row needs its reason"


def test_the_pending_surface_is_pinned():
    pending = [r["path"] for r in _load()["rows"] if r["disposition"] == "pending"]
    assert len(pending) == PENDING_BUDGET, (
        f"pending surface is {len(pending)}, pinned at {PENDING_BUDGET} — "
        "a page PR that adopts paths lowers both together; anything else "
        "is a reviewed decision, not drift"
    )


def test_all_ten_leaderboard_tabs_are_still_named():
    # Checklist item 3: the ten LB_TABS must survive into the new page by
    # NAME; losing one here would lose it silently at build time.
    tabs = _load()["lb_tabs"]
    assert tabs == [
        "power",
        "spawn",
        "crossfire",
        "trades",
        "reactions",
        "survivors",
        "movement",
        "focus_fire",
        "krogt",
        "comp_skill",
    ]
