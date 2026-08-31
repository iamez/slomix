"""The published spawn_timing range must be DERIVED from the constant.

`"range": "1.0 - 2.0"` in /storytelling/formula was a hand-written copy of
`SPAWN_TIMING_BONUS = 1.0` (base.py even says so in the constant's comment:
"so range 1.0-2.0 based on score 0-1"). Two spellings of one fact drift the
day someone tunes the bonus: the transparency endpoint would keep publishing
the old range beside the new coefficient. The multiplier really is
1 + bonus x denial (kis.py `spawn_mult = 1.0 + best_score`), so the range's
upper end IS 1.0 + SPAWN_TIMING_BONUS and the endpoint must compute it.

Seen failing before the fix: with the range still hardcoded, moving the
constant left the published range at "1.0 - 2.0" and the first test below
failed on "1.0 - 2.5" (Codex on #842, PR run 2026-08-31).
"""
from __future__ import annotations

import pytest

from website.backend.routers import storytelling_router


@pytest.mark.asyncio
async def test_spawn_range_follows_the_bonus_constant(monkeypatch):
    # Patch the ROUTER's binding — the handler must read the module global at
    # request time for the published range to track the constant at all.
    monkeypatch.setattr(storytelling_router, "SPAWN_TIMING_BONUS", 1.5)
    payload = await storytelling_router.get_kis_formula()
    st = payload["multipliers"]["spawn_timing"]
    assert st["bonus"] == 1.5
    assert st["range"] == "1.0 - 2.5"


@pytest.mark.asyncio
async def test_spawn_range_today_is_the_documented_one():
    # The derivation must reproduce the value every consumer has on record
    # (the SPA fixture pins "1.0 - 2.0") while the constant is 1.0.
    payload = await storytelling_router.get_kis_formula()
    st = payload["multipliers"]["spawn_timing"]
    assert st["range"] == f"1.0 - {1.0 + storytelling_router.SPAWN_TIMING_BONUS}"
    assert st["range"] == "1.0 - 2.0"
