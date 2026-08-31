"""The 200-with-`{"status": "error"}` convention is pinned here on purpose.

25 handlers across 11 routers answer a not-found / could-not-compute with
**HTTP 200** and a body of `{"status": "error", "detail": …}`. That reads like
a bug — a caller checking the status code sees success — and it was reported as
one (`/api/skill/player/{id}`, 2026-08-30). It is not being fixed, and this
file is why, so that the next person to notice does not spend the afternoon
re-deriving it.

⛔ WHY A LONE 404 WOULD MAKE THINGS WORSE. The legacy pages fetch through
`fetchJSON` (`website/js/utils.js:120`), which **throws on any non-2xx**. Every
call site wraps that in `try { … } catch { return; }`. So a route switched to
404 stops rendering "not rated" and starts rendering *nothing at all* — the
failure becomes invisible instead of explicit, which is the opposite of the
intent. Changing one route also leaves the API with two vocabularies for one
situation, which is the drift these guards exist to catch.

Owner's decision, 2026-08-30: keep the convention, document it. Revisit when
the legacy pages are retired, and then for all of them at once.

⚠️ THE ONE THAT IS NOT SETTLED, and the reason this list is worth keeping
current: the new SPA's `apiGet` (`src/app/lib/api.ts:113`) also throws only on
`!res.ok`, so one of these bodies arrives as ordinary data. Today that reaches
2 routes it calls. **20 of the 25 below are proximity handlers — that is phase
5.** When those pages are built, every one of them can hand the new SPA an
error dressed as a payload, which is exactly the class of the outage that read
as an empty database. The frontend needs one place that recognises the shape.

This test is an inventory, not a prohibition: adding a handler is fine, it just
has to be a decision someone made rather than one that happened.
"""

import ast
from pathlib import Path

import pytest

ROUTERS = Path(__file__).resolve().parents[2] / "website" / "backend" / "routers"

# (file, function) for every handler that answers with status "error" under a
# 200. Frozen 2026-08-30 against the tree at that date.
KNOWN = {
    ("proximity_combat.py", "get_proximity_engagements"),
    ("proximity_combat.py", "get_proximity_hotzones"),
    ("proximity_combat.py", "get_proximity_duos"),
    ("proximity_combat.py", "get_proximity_classes"),
    ("proximity_dashboard.py", "get_proximity_dashboard"),
    ("proximity_dashboard.py", "get_proximity_scopes"),
    ("proximity_dashboard.py", "get_proximity_summary"),
    ("proximity_events.py", "get_proximity_events"),
    ("proximity_helpers.py", "_timed_section"),
    ("proximity_movement.py", "get_proximity_movers"),
    ("proximity_movement.py", "get_proximity_reactions"),
    ("proximity_positions.py", "get_proximity_hit_regions_by_weapon"),
    ("proximity_quality.py", "_collect_signal"),
    ("proximity_quality.py", "_collect_round_correlation"),
    ("proximity_quality.py", "get_proximity_quality"),
    ("proximity_scoring.py", "get_proximity_leaderboards"),
    ("proximity_teamplay.py", "get_proximity_teamplay"),
    ("proximity_trades.py", "get_proximity_trades_summary"),
    ("proximity_trades.py", "get_proximity_trades_player_stats"),
    ("proximity_trades.py", "get_proximity_trade_events"),
    # ("records_maps.py", "get_map_objective_records") left the convention
    # with #830: the handler no longer answers status:"error" — its own
    # docstring records the change. Removed here in the same merge, exactly
    # the ceremony this inventory demands.
    ("skill_router.py", "get_player_skill"),
    ("skill_router.py", "get_player_skill_history"),
    ("skill_router.py", "get_et_performance_v3_shadow"),
    ("skill_router.py", "get_player_form"),
}


def _handlers_returning_status_error() -> set[tuple[str, str]]:
    """⚠️ Structural, never textual.

    A grep for `"status": "error"` matches this module's own docstring, every
    comment that mentions the convention, and any unrelated string — it would
    report agreement that was never measured. This walks the dict LITERALS in
    each function and looks for the key/value pair itself.
    """
    found: set[tuple[str, str]] = set()
    for path in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Dict):
                    continue
                for key, value in zip(inner.keys, inner.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "status"
                        and isinstance(value, ast.Constant)
                        and value.value == "error"
                    ):
                        found.add((path.name, node.name))
    return found


def test_the_inventory_is_current():
    found = _handlers_returning_status_error()
    added, removed = found - KNOWN, KNOWN - found
    assert not added and not removed, (
        "the 200-with-status-error inventory moved.\n"
        f"  new handlers using it: {sorted(added)}\n"
        f"  handlers that stopped: {sorted(removed)}\n"
        "If you switched one route to a real status code, read this module's "
        "docstring first: the legacy pages throw on non-2xx and render nothing, "
        "and one route changed leaves two vocabularies for one situation. If "
        "the change is deliberate, update KNOWN in the same commit."
    )


def test_the_convention_is_still_concentrated_in_proximity():
    """The number that decides when this has to be dealt with.

    Phase 5 builds the proximity pages against the new SPA, whose `apiGet`
    throws only on `!res.ok`. Every proximity handler in this list is one that
    can hand those pages an error dressed as a payload.
    """
    proximity = {h for h in KNOWN if h[0].startswith("proximity_")}
    assert len(proximity) >= 18, (
        f"only {len(proximity)} of {len(KNOWN)} are proximity handlers — the "
        "docstring's reasoning about phase 5 no longer matches the code"
    )


def test_the_reader_can_fail():
    """A control: an AST reader that finds nothing agrees with any inventory."""
    found = _handlers_returning_status_error()
    assert found, "the reader found no handlers at all — it is not measuring"
    assert ("skill_router.py", "get_player_skill") in found, (
        "the reader missed the handler this convention was reported against, "
        "so it cannot be trusted to notice one leaving"
    )
    assert found != KNOWN | {("nonexistent.py", "nope")}, "the comparison cannot distinguish an extra entry"


@pytest.mark.parametrize("path", ["get_player_skill", "get_proximity_scopes"])
def test_these_handlers_still_answer_200(path):
    """The convention is about the STATUS CODE, so pin that too — an inventory
    of source shapes alone would pass if someone kept the body and added
    `status_code=404` to the decorator."""
    from website.backend.routers import proximity_dashboard, skill_router

    module = skill_router if path == "get_player_skill" else proximity_dashboard
    for route in module.router.routes:
        if getattr(route, "endpoint", None) is getattr(module, path):
            assert route.status_code in (None, 200), (
                f"{path} now declares status_code={route.status_code}; that is "
                "the contract change this file records as not made"
            )
            return
    pytest.fail(f"{path} is no longer registered on its router")
