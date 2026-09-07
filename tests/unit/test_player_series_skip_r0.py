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

SOURCE = Path(__file__).resolve().parents[2] / "website" / "backend" / "routers" / "players_router.py"
HANDLERS = ("get_player_form", "get_player_rounds")


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
