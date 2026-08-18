"""Player-card composite endpoint helpers (SUPER LIVE 2.0 Val C)."""
from __future__ import annotations

from website.backend.routers.players_profile_router import _percentile


def test_percentile_basics():
    pool = [100.0, 200.0, 300.0, 400.0]
    assert _percentile(pool, 400.0) == 100
    assert _percentile(pool, 250.0) == 50
    assert _percentile(pool, 50.0) == 0
    assert _percentile([], 100.0) is None
