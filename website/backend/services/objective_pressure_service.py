"""Objective Pressure — "real pressure seconds" (Good Night plan rank 6, §F).

Rewards the part of ET that raw K/D misses: time a player spends applying REAL,
contested, coordinated objective pressure. Computed from the 200ms player_track
samples against the objective zones in objective_zones.json.

A track sample earns pressure time (v0.2 definition) only when ALL hold:
  - the player is inside a specific objective's sphere (full 3D distance, so a
    different floor doesn't count),
  - an ENEMY is inside that same objective in the same ~200ms bucket (§F.1 —
    the objective is actually contested), and
  - at least one TEAMMATE is in it too (>=2 of the player's team => not "empty
    pressure", §F.2 — lone loitering near an objective doesn't count).

"Alive" is implicit: a track exists only between spawn and death. Bots are
excluded. Proven with scripts/backtest_objective_pressure.py before shipping.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from website.backend.logging_config import get_app_logger
from website.backend.utils.et_constants import strip_et_colors

logger = get_app_logger("services.objective_pressure")

# Time granularity for the contested/support cross-check, and the per-sample
# credit cap so a gap in a track (e.g. a missed poll) can't inflate the total.
BUCKET_MS = 200
SAMPLE_CAP_MS = 400

_ZONES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "assets" / "maps" / "proximity" / "objective_zones.json"
)

# session_date -> (result, monotonic_ts). Pressure is a pure function of the
# session's tracks; Session Detail can request it repeatedly, so memoize briefly.
_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 300
_CACHE_MAX = 32

_zones_by_map: dict[str, list] | None = None


def _load_zones() -> dict[str, list]:
    """map_name (and aliases), lowercased -> list of (x, y, z, radius). Cached."""
    global _zones_by_map
    if _zones_by_map is not None:
        return _zones_by_map
    out: dict[str, list] = {}
    try:
        raw = json.loads(_ZONES_PATH.read_text(encoding="utf-8"))
        for m in raw.get("maps", {}).values():
            objs = [(o["x"], o["y"], o.get("z", 0.0), o.get("radius", 500))
                    for o in m.get("objectives", [])]
            if not objs:
                continue
            for key in [m.get("map_name", ""), *m.get("aliases", [])]:
                if key:
                    out[key.lower()] = objs
    except (OSError, ValueError, KeyError):
        logger.exception("objective_pressure: failed to load objective zones")
    _zones_by_map = out
    return out


def _zone_index(x: float, y: float, z: float, zones: list) -> int:
    """Index of the first objective whose 3D sphere contains the point, else -1."""
    for i, (zx, zy, zz, r) in enumerate(zones):
        if (x - zx) ** 2 + (y - zy) ** 2 + (z - zz) ** 2 <= r * r:
            return i
    return -1


def _accumulate_round(rtracks: list, zones: list, pressure: dict) -> None:
    """Add each player's contested+supported objective seconds for one round.

    rtracks: list of (team, name, samples) where samples is a sorted list of
    (time_ms, x, y, z). Mutates `pressure` (name -> seconds).
    """
    # Pass 1: presence per (bucket, zone_idx) -> {team: count}.
    presence: dict[tuple, dict] = defaultdict(lambda: defaultdict(int))
    marked = []
    for team, name, samples in rtracks:
        zis = []
        for tm, x, y, z in samples:
            zi = _zone_index(x, y, z, zones)
            zis.append(zi)
            if zi >= 0:
                presence[(tm // BUCKET_MS, zi)][team] += 1
        marked.append((team, name, samples, zis))

    # Pass 2: credit samples that are in a contested, supported objective.
    for team, name, samples, zis in marked:
        for i, zi in enumerate(zis):
            if zi < 0:
                continue
            counts = presence[(samples[i][0] // BUCKET_MS, zi)]
            enemy = any(c > 0 for tm2, c in counts.items() if tm2 != team)
            mates = counts.get(team, 0)
            if not enemy or mates < 2:
                continue
            tm = samples[i][0]
            dt = (samples[i + 1][0] - tm) if i + 1 < len(samples) else BUCKET_MS
            pressure[name] += min(max(dt, 0), SAMPLE_CAP_MS) / 1000.0


def _evict_oldest() -> None:
    if len(_CACHE) <= _CACHE_MAX:
        return
    oldest = min(_CACHE, key=lambda k: _CACHE[k][1])
    _CACHE.pop(oldest, None)


async def compute_objective_pressure(db, session_date, limit: int = 10) -> dict:
    """Objective-pressure leaderboard for one session. Read-only, cached 5 min.

    session_date may be a datetime.date (from the router's _parse_iso_date) or a
    'YYYY-MM-DD' string; it is passed straight to asyncpg for the DATE column.
    """
    cache_key = str(session_date)
    cached = _CACHE.get(cache_key)
    if cached and (time.monotonic() - cached[1]) < _CACHE_TTL:
        return cached[0]

    zones_by_map = _load_zones()

    tracks = await db.fetch_all(
        """
        SELECT round_start_unix, round_number, map_name, player_guid,
               player_name, team, path
        FROM player_track
        WHERE session_date = $1 AND path IS NOT NULL AND sample_count > 0
          AND player_guid NOT LIKE 'OMNIBOT%' AND player_name NOT LIKE '[BOT]%'
        """,
        (session_date,),
    )

    pressure: dict[str, float] = defaultdict(float)
    name_guid: dict[str, str] = {}
    maps_counted: set = set()
    by_round: dict[tuple, list] = defaultdict(list)

    for t in (tracks or []):
        zones = zones_by_map.get((t["map_name"] or "").lower())
        if not zones:
            continue
        path = t["path"] if isinstance(t["path"], list) else json.loads(t["path"])
        samples = sorted(
            (int(s["time"]), float(s["x"]), float(s["y"]), float(s.get("z", 0.0)))
            for s in path if "time" in s and "x" in s and "y" in s
        )
        if not samples:
            continue
        name = strip_et_colors(t["player_name"] or t["player_guid"][:8])
        name_guid.setdefault(name, t["player_guid"])
        maps_counted.add(t["map_name"])
        by_round[(t["round_start_unix"], t["round_number"], t["map_name"])].append(
            (t["team"], name, samples)
        )

    for (_rsu, _rnum, mapname), rtracks in by_round.items():
        _accumulate_round(rtracks, zones_by_map[(mapname or "").lower()], pressure)

    # Kills per player (same session, bots excluded) so the UI can contrast
    # objective pressure against the scoreboard — the "invisible value" framing.
    kill_rows = await db.fetch_all(
        """
        SELECT attacker_name AS name, COUNT(*) AS kills
        FROM proximity_combat_position
        WHERE session_date = $1 AND event_type = 'kill'
          AND attacker_team IS NOT NULL AND attacker_team != victim_team
          AND attacker_guid NOT LIKE 'OMNIBOT%' AND attacker_name NOT LIKE '[BOT]%'
        GROUP BY attacker_name
        """,
        (session_date,),
    )
    kills_by_name = {strip_et_colors(r["name"]): int(r["kills"]) for r in (kill_rows or [])}

    ranked = sorted(pressure.items(), key=lambda kv: -kv[1])
    players = [
        {
            "guid": name_guid.get(name),
            "name": name,
            "pressure_seconds": round(secs, 1),
            "kills": kills_by_name.get(name, 0),
        }
        for name, secs in ranked if secs > 0
    ][: max(1, min(limit, 50))]

    result = {
        "status": "ok",
        "session_date": cache_key,
        "maps_counted": len(maps_counted),
        "players": players,
    }
    _CACHE[cache_key] = (result, time.monotonic())
    _evict_oldest()
    return result
