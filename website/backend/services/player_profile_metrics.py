"""Pure, DB-free helper formulas for the unified player profile.

These functions are deliberately side-effect free so they can be unit-tested
without a database. The composite profile endpoint
(``players_profile_router.py``) feeds them rows already fetched from PostgreSQL.

Three gibhub.gg-parity metrics live here:

* **UTRO** — respawn-weighted kill value. Reuses the graduated reinforcement
  tiers from :mod:`website.backend.services.storytelling.base`
  (``REINF_MULT_TIERS``) so a kill that caught an enemy at a long respawn wait
  is worth more than one near a fresh spawn. The tier lookup MUST match
  ``kis.py`` (``if r <= upper``) — see the base.py comment block.
* **bait_score** — trade-involvement index from ``proximity_lua_trade_kill``.
* **streaks** — current/longest win & loss runs from an ordered W/L sequence.

Plus a ``weapon_t`` (WP_*) id → display-name map, because the proximity tables
store the engine ``weapon_t`` enum (NOT the ``kill_mod``/MOD_* enum that
``et_constants.weapon_name`` maps).
"""

from __future__ import annotations

import math

from website.backend.services.storytelling.base import REINF_MULT_TIERS

__all__ = [
    "WP_WEAPON_NAMES",
    "bait_score",
    "compute_streaks",
    "reinf_multiplier",
    "utro_from_waits",
    "weapon_t_name",
]


# ── UTRO (respawn-weighted kills) ──────────────────────────────────────────

def reinf_multiplier(wait_seconds: float) -> float:
    """Map a victim's reinforcement wait (seconds) to its UTRO multiplier.

    Matches ``kis.py``: the first tier whose inclusive ceiling the wait does
    not exceed wins (``if r <= upper``). ``REINF_MULT_TIERS`` ends with an
    ``inf`` ceiling, so every non-negative wait maps to exactly one tier.
    Negative / NaN-ish inputs are clamped to 0 (treated as a fresh spawn).
    """
    try:
        r = float(wait_seconds)
    except (TypeError, ValueError):
        return REINF_MULT_TIERS[0][1]
    if math.isnan(r):
        return REINF_MULT_TIERS[0][1]
    if r < 0.0:
        r = 0.0
    for upper, mult in REINF_MULT_TIERS:
        if r <= upper:
            return mult
    return REINF_MULT_TIERS[-1][1]  # unreachable (inf tier), defensive


def utro_from_waits(waits_seconds: list[float | int | None]) -> dict:
    """Aggregate UTRO over a list of victim reinforcement waits (seconds).

    Returns a dict with the summed value, the count of weighted kills, and the
    per-kill average. ``None`` waits are skipped (no reliable timing) rather
    than counted as fresh spawns, so they don't deflate the average.
    """
    total = 0.0
    n = 0
    for w in waits_seconds or []:
        if w is None:
            continue
        total += reinf_multiplier(w)
        n += 1
    return {
        "utro": round(total, 2),
        "weighted_kills": n,
        "utro_per_kill": round(total / n, 3) if n else 0.0,
    }


# ── bait_score (trade involvement) ─────────────────────────────────────────

def bait_score(trades_made: int, untraded_deaths: int) -> dict:
    """Trade-involvement / bait index.

    * ``trades_made`` — kills where the player avenged a teammate's death
      within the trade window (player is ``trader_guid`` in
      ``proximity_lua_trade_kill``). Good teamplay.
    * ``untraded_deaths`` — the player's own deaths that no teammate avenged
      (over-extension / getting baited). Derived as
      ``total_deaths − deaths_avenged_for_player`` by the caller.

    Score = ``trades_made / (trades_made + untraded_deaths) * 100``. Higher =
    more involved in trades and less often left hanging. Returns
    ``available: False`` when there's no trade-relevant situation at all.
    """
    t = max(0, int(trades_made or 0))
    u = max(0, int(untraded_deaths or 0))
    denom = t + u
    if denom == 0:
        return {"available": False, "trades_made": 0, "untraded_deaths": 0, "score": 0.0}
    return {
        "available": True,
        "trades_made": t,
        "untraded_deaths": u,
        "score": round(t / denom * 100.0, 1),
    }


# ── W/L streaks ────────────────────────────────────────────────────────────

def compute_streaks(results: list[str]) -> dict:
    """Current & longest win/loss streaks from an ordered result sequence.

    ``results`` is oldest → newest, each item one of ``"W"`` / ``"L"`` (any
    other token, e.g. a draw, breaks both streaks without extending either).
    The *current* streak is read from the newest end.
    """
    longest_win = 0
    longest_loss = 0
    run_win = 0
    run_loss = 0
    for r in results or []:
        if r == "W":
            run_win += 1
            run_loss = 0
            longest_win = max(longest_win, run_win)
        elif r == "L":
            run_loss += 1
            run_win = 0
            longest_loss = max(longest_loss, run_loss)
        else:
            run_win = 0
            run_loss = 0

    current_type = ""
    current_streak = 0
    for r in reversed(results or []):
        if not current_type:
            if r in ("W", "L"):
                current_type = r
                current_streak = 1
            else:
                break
        elif r == current_type:
            current_streak += 1
        else:
            break

    return {
        "current_streak": current_streak,
        "current_type": current_type,
        "longest_win": longest_win,
        "longest_loss": longest_loss,
    }


# ── weapon_t (WP_*) id → name ──────────────────────────────────────────────
# The proximity tables (proximity_shot_fired, proximity_hit_region) store the
# ET:Legacy engine ``weapon_t`` enum, confirmed empirically: ids 3 (MP40) and
# 8 (Thompson) dominate the data — the two standard SMGs. Source: bg_public.h
# weapon_t. ``et_constants.weapon_name`` maps the DIFFERENT kill_mod/MOD_* enum
# (used by player kill rows), so it is NOT reusable here.
WP_WEAPON_NAMES: dict[int, str] = {
    1: "Knife",
    2: "Luger",
    3: "MP40",
    4: "Grenade Launcher",
    5: "Panzerfaust",
    6: "Flamethrower",
    7: "Colt",
    8: "Thompson",
    9: "Grenade",
    10: "Sten",
    11: "Syringe",
    12: "Ammo Pack",
    13: "Artillery",
    14: "Silenced Luger",
    15: "Dynamite",
    17: "Map Mortar",
    19: "Medkit",
    20: "Binoculars",
    21: "Pliers",
    23: "Kar98",
    24: "M1 Garand (Carbine)",
    25: "Garand",
    26: "Landmine",
    27: "Satchel",
    29: "Smoke Bomb",
    30: "Mobile MG42",
    31: "K43",
    32: "FG42",
    34: "Mortar",
    35: "Akimbo Colt",
    36: "Akimbo Luger",
    37: "GPG40",
    38: "M7",
    39: "Silenced Colt",
    40: "Scoped Garand",
    41: "Scoped K43",
    42: "Scoped FG42",
    43: "Mortar",
    44: "Adrenaline",
    45: "Akimbo Silenced Colt",
    46: "Akimbo Silenced Luger",
    47: "Mobile MG42 (Set)",
    48: "Ka-Bar Knife",
    49: "Mobile Browning",
    50: "Mobile Browning (Set)",
    51: "Mortar",
    52: "Mortar (Set)",
    53: "Bazooka",
    54: "MP34",
    55: "Airstrike",
}


def weapon_t_name(weapon_id: int | None) -> str:
    """Human-readable name for a ``weapon_t`` (WP_*) id; fallback for unknowns."""
    if weapon_id is None:
        return "Unknown"
    return WP_WEAPON_NAMES.get(int(weapon_id), f"Weapon {int(weapon_id)}")
