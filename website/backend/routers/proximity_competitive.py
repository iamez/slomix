"""Stopwatch competitive analytics — Phase 4 of the proximity-vision plan.

Implements the top S/M items from docs/ANALYTICS_BENCHMARK_2026-06.md:

- /proximity/competitive/stagger        — stagger index (kills that cost the
  victim >=80% of their spawn wave; ET's native "spawn denial" sharpened into
  a Leetify-style per-player rate).
- /proximity/competitive/first-blood    — first blood -> round conversion %
  (OW fight-analytics staple) + per-player first-pick/first-death rates.
- /proximity/competitive/wave-cycles    — the wave-cycle fight ledger: one
  round segmented by both teams' reinforcement-wave landings, each cycle
  scored (kills, denial, first blood) like Winston's Lab fight ledgers.
- /proximity/competitive/personal-bests — Leetify-style PB session cards
  (new per-session records vs the player's own history).

killer_reinf is deliberately NOT used (historical rows lack the CS_REINFSEEDS
offset — bug F1, docs/PROXIMITY_E2E_AUDIT_2026-06-10.md). Wave clocks are
derived from victim-side fields, which are correct: for the victim's team
offset = (interval - time_to_next_spawn - kill_time) mod interval, constant
per round (numerically verified in the E2E audit).
"""

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Query

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _parse_iso_date,
    logger,
)
from website.backend.utils.et_constants import strip_et_colors

router = APIRouter()

# A kill is a "stagger" when the victim's wait is >=80% of their wave
# interval — i.e. the kill landed just after the victim's wave, the costliest
# moment of the cycle (Quake "spawn control" / OW "stagger" concept).
STAGGER_THRESHOLD = 0.8

_TEAM_BY_NUM = {1: "AXIS", 2: "ALLIES"}


@router.get("/proximity/competitive/stagger")
async def get_stagger_index(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player stagger kills, stagger rate and total denied wave time."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    rows = await db.fetch_all(
        f"""
        SELECT killer_guid, MAX(killer_name), MAX(killer_team),
               COUNT(*) AS kills,
               COUNT(*) FILTER (
                   WHERE enemy_spawn_interval > 0
                     AND time_to_next_spawn >= {STAGGER_THRESHOLD} * enemy_spawn_interval
               ) AS stagger_kills,
               SUM(time_to_next_spawn) AS denied_ms,
               AVG(spawn_timing_score) AS avg_score
        FROM proximity_spawn_timing
        {where_sql} AND killer_guid <> victim_guid
        GROUP BY killer_guid
        HAVING COUNT(*) >= 3
        ORDER BY 5 DESC, 6 DESC
        """,
        tuple(params),
    )
    players = [
        {
            "guid": r[0],
            "name": strip_et_colors(r[1] or r[0][:8]),
            "team": r[2],
            "kills": int(r[3]),
            "stagger_kills": int(r[4]),
            "stagger_rate": round(int(r[4]) / max(int(r[3]), 1) * 100, 1),
            "denied_s": round(int(r[5] or 0) / 1000, 1),
            "avg_score": round(float(r[6] or 0), 3),
        }
        for r in (rows or [])
    ]
    return {
        "status": "ok",
        "scope": scope,
        "threshold": STAGGER_THRESHOLD,
        "description": (
            "Stagger kill = victim loses >=80% of their spawn wave. "
            "denied_s = total enemy respawn time removed by this player's kills."
        ),
        "players": players,
    }


@router.get("/proximity/competitive/first-blood")
async def get_first_blood_conversion(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """First blood -> round conversion + per-player first-pick/first-death."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    # First kill of every round in scope (round identity = round_start_unix).
    rows = await db.fetch_all(
        f"""
        SELECT DISTINCT ON (round_start_unix)
               round_start_unix, killer_guid, killer_name, killer_team,
               victim_guid, victim_name, kill_time
        FROM proximity_spawn_timing
        {where_sql} AND round_start_unix > 0 AND killer_guid <> victim_guid
        ORDER BY round_start_unix, kill_time
        """,
        tuple(params),
    )
    first_bloods = {int(r[0]): r for r in (rows or [])}
    if not first_bloods:
        return {"status": "ok", "scope": scope, "rounds": 0, "players": []}

    # Round winners for the same scope (exclude filler/invalid + draws).
    win_params: list = [list(first_bloods.keys())]
    win_sql = "SELECT round_start_unix, winner_team FROM rounds WHERE round_start_unix = ANY($1)"
    win_sql += " AND is_valid IS DISTINCT FROM FALSE AND winner_team IN (1, 2)"
    win_rows = await db.fetch_all(win_sql, tuple(win_params))
    winner_by_rsu = {int(r[0]): _TEAM_BY_NUM.get(int(r[1])) for r in (win_rows or [])}

    converted = 0
    decided = 0
    picks: dict[str, dict] = defaultdict(lambda: {"name": "", "first_picks": 0, "first_deaths": 0, "fp_converted": 0})
    for rsu, fb in first_bloods.items():
        killer_guid, killer_name, killer_team = fb[1], fb[2], fb[3]
        victim_guid, victim_name = fb[4], fb[5]
        picks[killer_guid]["name"] = strip_et_colors(killer_name or killer_guid[:8])
        picks[killer_guid]["first_picks"] += 1
        picks[victim_guid]["name"] = strip_et_colors(victim_name or victim_guid[:8])
        picks[victim_guid]["first_deaths"] += 1
        winner = winner_by_rsu.get(rsu)
        if winner is None:
            continue
        decided += 1
        if winner == killer_team:
            converted += 1
            picks[killer_guid]["fp_converted"] += 1

    players = [
        {"guid": g, **stats}
        for g, stats in sorted(
            picks.items(),
            key=lambda kv: (kv[1]["first_picks"], -kv[1]["first_deaths"]),
            reverse=True,
        )
    ]
    return {
        "status": "ok",
        "scope": scope,
        "rounds": len(first_bloods),
        "decided_rounds": decided,
        "converted": converted,
        "conversion_pct": round(converted / decided * 100, 1) if decided else None,
        "description": (
            "How often the side drawing first blood goes on to win the round "
            "(decided rounds only; draws/filler excluded)."
        ),
        "players": players,
    }


def _implied_offsets(st_rows: list) -> dict[str, tuple[int, int]]:
    """Per-team (offset_ms, interval_ms) derived from victim-side clocks.

    offset = (interval - time_to_next_spawn - kill_time) mod interval is
    constant per round per team (E2E audit, section 3). Uses the modal value
    to be robust against the 0.1s rounding in stored fields.
    """
    candidates: dict[str, Counter] = defaultdict(Counter)
    intervals: dict[str, int] = {}
    for r in st_rows:
        team, interval = r[3], int(r[7] or 0)
        if interval <= 0:
            continue
        kill_time, ttn = int(r[6] or 0), int(r[8] or 0)
        offset = (interval - ttn - kill_time) % interval
        # quantize to 25ms grid (storage rounding) before voting
        candidates[team][round(offset / 25) * 25] += 1
        intervals[team] = interval
    return {
        team: (counter.most_common(1)[0][0], intervals[team])
        for team, counter in candidates.items()
        if counter
    }


@router.get("/proximity/competitive/wave-cycles")
async def get_wave_cycles(
    session_date: str = Query(...),
    map_name: str = Query(...),
    round_number: int = Query(..., ge=0),
    round_start_unix: int | None = Query(default=None, ge=0),
    range_days: int = 30,
    db: DatabaseAdapter = Depends(get_db),
):
    """Wave-cycle fight ledger for one round.

    Segments the round at every reinforcement-wave landing (either team) and
    scores each segment: kills per team, denied wave time, first blood.
    """
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    st_rows = await db.fetch_all(
        f"""
        SELECT killer_guid, killer_name, killer_team, victim_team,
               victim_guid, victim_name, kill_time,
               enemy_spawn_interval, time_to_next_spawn
        FROM proximity_spawn_timing
        {where_sql} AND killer_guid <> victim_guid
        ORDER BY kill_time
        """,
        tuple(params),
    )
    if not st_rows:
        return {"status": "ok", "scope": scope, "cycles": [], "message": "No kills in scope."}

    round_len_ms = max(int(r[6] or 0) for r in st_rows) + 1
    offsets = _implied_offsets(st_rows)

    # Wave landing times for each team: t = k*interval - offset (>0).
    boundaries: list[tuple[int, str]] = []
    for team, (offset, interval) in offsets.items():
        t = interval - offset
        while t < round_len_ms + interval:
            if t > 0:
                boundaries.append((t, team))
            t += interval
    boundaries.sort()

    edges = [0] + [b[0] for b in boundaries]
    wave_team_at_edge = {b[0]: b[1] for b in boundaries}

    cycles = []
    axis_won = allies_won = 0
    for i in range(len(edges)):
        start = edges[i]
        end = edges[i + 1] if i + 1 < len(edges) else round_len_ms
        if end <= start:
            continue
        seg_kills = [r for r in st_rows if start <= int(r[6] or 0) < end]
        kills_axis = sum(1 for r in seg_kills if r[2] == "AXIS")
        kills_allies = sum(1 for r in seg_kills if r[2] == "ALLIES")
        denied_axis = sum(int(r[8] or 0) for r in seg_kills if r[2] == "AXIS")
        denied_allies = sum(int(r[8] or 0) for r in seg_kills if r[2] == "ALLIES")
        first_blood = seg_kills[0][2] if seg_kills else None
        if kills_axis > kills_allies:
            winner = "AXIS"
        elif kills_allies > kills_axis:
            winner = "ALLIES"
        elif denied_axis != denied_allies:
            winner = "AXIS" if denied_axis > denied_allies else "ALLIES"
        else:
            winner = None
        if winner == "AXIS":
            axis_won += 1
        elif winner == "ALLIES":
            allies_won += 1
        cycles.append({
            "start_ms": start,
            "end_ms": end,
            "wave": wave_team_at_edge.get(start),  # whose wave opened this cycle
            "kills_axis": kills_axis,
            "kills_allies": kills_allies,
            "denied_axis_s": round(denied_axis / 1000, 1),
            "denied_allies_s": round(denied_allies / 1000, 1),
            "first_blood": first_blood,
            "winner": winner,
        })

    return {
        "status": "ok",
        "scope": scope,
        "round_len_ms": round_len_ms,
        "clocks": {
            team: {"offset_ms": off, "interval_ms": iv}
            for team, (off, iv) in offsets.items()
        },
        "summary": {
            "cycles": len(cycles),
            "axis_won": axis_won,
            "allies_won": allies_won,
            "contested": len(cycles) - axis_won - allies_won,
        },
        "cycles": cycles,
    }


# Personal-best metrics: key -> (label, higher_is_better)
_PB_METRICS = {
    "kills": "Kills in a session",
    "stagger_kills": "Stagger kills in a session",
    "denied_s": "Enemy respawn time denied (s)",
    "best_denial_s": "Single biggest spawn denial (s)",
}


@router.get("/proximity/competitive/personal-bests")
async def get_personal_bests(
    session_date: str = Query(...),
    db: DatabaseAdapter = Depends(get_db),
):
    """Leetify-style PB cards: new per-session records vs the player's history."""
    sd = _parse_iso_date(session_date)
    rows = await db.fetch_all(
        f"""
        SELECT killer_guid, MAX(killer_name) AS name, session_date,
               COUNT(*) AS kills,
               COUNT(*) FILTER (
                   WHERE enemy_spawn_interval > 0
                     AND time_to_next_spawn >= {STAGGER_THRESHOLD} * enemy_spawn_interval
               ) AS stagger_kills,
               SUM(time_to_next_spawn) AS denied_ms,
               MAX(time_to_next_spawn) AS best_denial_ms
        FROM proximity_spawn_timing
        WHERE killer_guid <> victim_guid
        GROUP BY killer_guid, session_date
        """,
        (),
    )
    by_player: dict[str, list] = defaultdict(list)
    for r in (rows or []):
        by_player[r[0]].append(r)

    cards = []
    for guid, sessions in by_player.items():
        current = next((s for s in sessions if s[2] == sd), None)
        if current is None:
            continue
        history = [s for s in sessions if s[2] < sd]
        if not history:
            continue  # first session — everything is a PB, skip the noise
        name = strip_et_colors(current[1] or guid[:8])
        cur_vals = {
            "kills": int(current[3]),
            "stagger_kills": int(current[4]),
            "denied_s": round(int(current[5] or 0) / 1000, 1),
            "best_denial_s": round(int(current[6] or 0) / 1000, 1),
        }
        idx = {"kills": 3, "stagger_kills": 4, "denied_s": 5, "best_denial_s": 6}
        for key, label in _PB_METRICS.items():
            i = idx[key]
            prev_best_row = max(history, key=lambda s: int(s[i] or 0))
            prev_best = int(prev_best_row[i] or 0)
            cur_raw = int(current[i] or 0)
            if cur_raw > prev_best and cur_raw > 0:
                scale = 1000 if key.endswith("_s") else 1
                cards.append({
                    "guid": guid,
                    "name": name,
                    "metric": key,
                    "label": label,
                    "value": cur_vals[key],
                    "prev_best": round(prev_best / scale, 1) if scale > 1 else prev_best,
                    "prev_best_date": str(prev_best_row[2]),
                    "sessions_played": len(history) + 1,
                })

    cards.sort(key=lambda c: (c["name"], c["metric"]))
    if not cards:
        logger.debug("personal-bests: no new PBs for %s", sd)
    return {
        "status": "ok",
        "session_date": str(sd),
        "description": "New personal records set this session (players with prior history only).",
        "cards": cards,
    }
