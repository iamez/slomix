"""The accuracy record must stand on a PROVABLE sample.

The 2025 supastats backfill carries garbage bullets_fired on 7,311 of its
9,698 rows (the old record row: 5,523 bullets in 269 s = 20.5/s where an MP40
tops out at ~11.6/s), while the 2026 live capture has zero such rows. The
sample-size gate (>50 bullets) is meaningless when the bullet count itself is
corrupted, so the accuracy category additionally requires a physically
possible fire rate — and ONLY the accuracy category: other records do not
depend on the bullet count, and a global gate would silently shrink them.
"""
from __future__ import annotations

import inspect

from website.backend.routers import records_awards


def _source() -> str:
    return inspect.getsource(records_awards.get_records)


def test_accuracy_requires_a_physically_possible_fire_rate():
    src = _source()
    i = src.index('"accuracy"')
    block = src[i:src.index('"revived"')]
    assert "bullets_fired > 50" in block
    assert "bullets_fired <= time_played_seconds * 15" in block


def test_the_physics_gate_is_specific_to_accuracy():
    """Kills/damage/gibs records must NOT inherit the bullet-count clause —
    they are independent of it, and rows with a corrupted bullet count can
    still carry a legitimate kills or damage value."""
    src = _source()
    assert src.count("time_played_seconds * 15") == 1
