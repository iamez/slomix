"""The per-player form and rounds series count halves, never the R0 copy.

docs/CLAUDE.md: `round_number = 0` rows are still written and their damage is
the two halves added again. Measured 2026-09-07 for one regular's rows with
time_played_seconds > 60: R0 26 rows / 96,970 damage, R1 27 / 51,899, R2 29 /
47,637 — an unfiltered sum doubles the damage while the time only grows ~1.3x,
so the DPM the profile draws was ~1.9x too high. This pins the filter on both
queries by reading the SQL the handlers carry, so the next edit that drops it
fails here rather than on the page.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[2] / "website" / "backend" / "routers"
SOURCE = ROUTERS / "players_router.py"
HANDLERS = ("get_player_form", "get_player_rounds")
# skill_router._form_rows feeds /api/skill/player/{}/form (profile header,
# FormPage, Home form movers): same table, same missing filter, and R0 rounds
# are is_valid = TRUE (249 of 257 since June 2026), so the join did not save it.
SKILL_SOURCE = ROUTERS / "skill_router.py"
SKILL_HANDLERS = ("_form_rows",)


def _sql_of(func: ast.FunctionDef) -> str:
    return "\n".join(
        node.value
        for node in ast.walk(func)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "FROM player_comprehensive_stats" in node.value
    )


def test_form_and_rounds_series_count_only_the_two_halves():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    seen = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in HANDLERS:
            seen[node.name] = _sql_of(node)
    assert set(seen) == set(HANDLERS), f"handlers moved: found {sorted(seen)}"
    for name, sql in seen.items():
        assert "player_comprehensive_stats" in sql, f"{name}: query not found"
        assert "p.round_number IN (1, 2)" in sql, f"{name}: the R0 summary rows are counted again (docs/CLAUDE.md)"


def test_skill_form_rows_count_only_the_two_halves():
    tree = ast.parse(SKILL_SOURCE.read_text(encoding="utf-8"))
    seen = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in SKILL_HANDLERS:
            # The query is an f-string: its literal segments are Constants
            # inside a JoinedStr, so join every string constant of the body.
            seen[node.name] = "\n".join(
                n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            )
    assert set(seen) == set(SKILL_HANDLERS), f"handlers moved: found {sorted(seen)}"
    for name, sql in seen.items():
        assert "FROM player_comprehensive_stats" in sql, f"{name}: query not found"
        assert "pcs.round_number IN (1, 2)" in sql, f"{name}: the R0 summary rows are counted again (docs/CLAUDE.md)"
