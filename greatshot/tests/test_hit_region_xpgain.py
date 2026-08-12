"""G3: revive hit_region on kills from xpgain '<region>shot kill'.

The obituary path can only read causeOfDeath (weapon-only), so the headshot
detector saw 0 head hits across 613 kills. The engine's real per-kill hit
region lives in POV-only xpgain raw commands; the scanner correlates each to
the nearest kill by server time.
"""
from __future__ import annotations

from greatshot.scanner.api import _normalize_timeline, _parse_hitregion_xpgain


class _Profile:
    def canonical_weapon(self, w):
        return w

    def canonical_team(self, t):
        return t


def _obit(t_ms, attacker="vid", victim="lgz"):
    return {"serverTime": t_ms, "attackerCleanName": attacker,
            "targetCleanName": victim, "causeOfDeath": "MOD_MP40"}


def _xp(t_ms, reason):
    return {"serverTime": t_ms, "rawCommand": f'xpgain 4 3.000000 "{reason}"\n'}


def test_parse_hitregion_xpgain_extracts_region_and_time():
    rows = _parse_hitregion_xpgain([
        _xp(1000, "headshot kill"),
        _xp(2000, "bodyshot kill"),
        {"serverTime": 3000, "rawCommand": 'xpgain 2 4.0 "revive"\n'},  # not a hit
        {"serverTime": 4000, "rawCommand": 'xpgain 0 5.0 "^7|garbage"\n'},  # colour junk
    ])
    assert rows == [(1000, "head"), (2000, "body")]


def test_headshot_xpgain_stamps_nearest_kill():
    obits = [_obit(10_000), _obit(10_500)]
    cmds = [_xp(10_480, "headshot kill")]  # ~20 ms from the 2nd kill
    tl = _normalize_timeline([], obits, _Profile(), cmds)
    kills = [e for e in tl if e.type == "kill"]
    heads = [e for e in kills if e.hit_region == "head"]
    assert len(heads) == 1
    assert heads[0].t_ms == 10_500
    assert heads[0].meta.get("hit_region_source") == "xpgain"


def test_far_xpgain_does_not_match():
    obits = [_obit(10_000)]
    cmds = [_xp(20_000, "headshot kill")]  # 10 s away → outside 1500 ms window
    tl = _normalize_timeline([], obits, _Profile(), cmds)
    assert all(e.hit_region is None for e in tl if e.type == "kill")


def test_no_xpgain_leaves_hit_region_none():
    tl = _normalize_timeline([], [_obit(10_000)], _Profile(), [])
    assert all(e.hit_region is None for e in tl if e.type == "kill")
