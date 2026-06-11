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

import re
from collections import Counter, defaultdict
from itertools import groupby

from fastapi import APIRouter, Depends, HTTPException, Query

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
    params.append(STAGGER_THRESHOLD)
    threshold_param = len(params)
    rows = await db.fetch_all(
        f"""
        SELECT killer_guid, MAX(killer_name), MAX(killer_team),
               COUNT(*) AS kills,
               COUNT(*) FILTER (
                   WHERE enemy_spawn_interval > 0
                     AND time_to_next_spawn >= ${threshold_param}::float8 * enemy_spawn_interval
               ) AS stagger_kills,
               SUM(time_to_next_spawn) AS denied_ms,
               AVG(spawn_timing_score) AS avg_score
        FROM proximity_spawn_timing
        {where_sql} AND killer_guid <> victim_guid
        GROUP BY killer_guid
        HAVING COUNT(*) >= 3
        ORDER BY 5 DESC, 6 DESC
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
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
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
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


def _implied_offsets(victim_clocks: list) -> dict[str, tuple[int, int]]:
    """Per-team (offset_ms, interval_ms) derived from victim-side clocks.

    victim_clocks: (victim_team, kill_time, interval, time_to_next_spawn).
    offset = (interval - time_to_next_spawn - kill_time) mod interval is
    constant per round per team (E2E audit, section 3). Uses the modal value
    to be robust against the 0.1s rounding in stored fields.
    """
    candidates: dict[str, Counter] = defaultdict(Counter)
    intervals: dict[str, int] = {}
    for team, kill_time, interval, ttn in victim_clocks:
        interval = int(interval or 0)
        if interval <= 0:
            continue
        kill_time, ttn = int(kill_time or 0), int(ttn or 0)
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
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )
    if not st_rows:
        return {"status": "ok", "scope": scope, "cycles": [], "message": "No kills in scope."}

    round_len_ms = max(int(r[6] or 0) for r in st_rows) + 1
    offsets = _implied_offsets([(r[3], r[6], r[7], r[8]) for r in st_rows])

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
        """
        SELECT killer_guid, MAX(killer_name) AS name, session_date,
               COUNT(*) AS kills,
               COUNT(*) FILTER (
                   WHERE enemy_spawn_interval > 0
                     AND time_to_next_spawn >= $1::float8 * enemy_spawn_interval
               ) AS stagger_kills,
               SUM(time_to_next_spawn) AS denied_ms,
               MAX(time_to_next_spawn) AS best_denial_ms
        FROM proximity_spawn_timing
        WHERE killer_guid <> victim_guid
        GROUP BY killer_guid, session_date
        """,
        (STAGGER_THRESHOLD,),
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


# v7 capture capabilities (Lua 6.10 draft, dormant) — shown on the website as
# a roadmap card; counts flip live once the owner enables a flag + deploys.
_V7_CAPABILITIES = [
    {
        "key": "aim_lock",
        "table": "proximity_aim_lock",
        "title": "Aim Lock",
        "what": "Crosshair-on-enemy windows — who tracks targets, for how long, at what range. Closes the loop between shot data and real targets.",
        "api": "et.trap_Trace + ps.viewangles (runtime-proven)",
    },
    {
        "key": "spawn_select",
        "table": "proximity_spawn_select",
        "title": "Spawn Selection",
        "what": "Which spawn point each player picked, every life — spawn discipline and rotation reads become measurable.",
        "api": "sess.spawnObjectiveIndex + pers.lastSpawnTime",
    },
    {
        "key": "skill_snapshot",
        "table": "proximity_skill_snapshot",
        "title": "Skill Context",
        "what": "The in-game XP skill array per player per round — correlate behavior with class skill levels.",
        "api": "sess.skill (SK_* 0-6)",
    },
    {
        "key": "comm_events",
        "table": "proximity_comm_event",
        "title": "Comms",
        "what": "Voice-macro usage frequency (vsay 'Medic!' etc.) — a communication proxy. No chat text captured.",
        "api": "et_ClientCommand + trap_Argv",
    },
]

_V7_TABLES = {c["table"] for c in _V7_CAPABILITIES}


@router.get("/proximity/v7-status")
async def get_v7_status(db: DatabaseAdapter = Depends(get_db)):
    """Live status of the dormant v7 capture tables (roadmap panel)."""
    capabilities = []
    for cap in _V7_CAPABILITIES:
        table = cap["table"]
        if table not in _V7_TABLES:  # defensive: identifiers come from the literal list above
            continue
        rows = 0
        rounds = 0
        try:
            row = await db.fetch_one(
                f"SELECT COUNT(*), COUNT(DISTINCT round_start_unix) FROM {table}"  # noqa: S608 # nosec B608 - table from module-literal _V7_CAPABILITIES with membership guard; no user data
            )
            rows, rounds = int(row[0] or 0), int(row[1] or 0)
        except Exception:
            logger.debug("v7-status: table %s missing", table)
        capabilities.append({
            **{k: cap[k] for k in ("key", "title", "what", "api")},
            "rows": rows,
            "rounds": rounds,
            "live": rows > 0,
        })
    return {
        "status": "ok",
        "lua_version_draft": "6.10",
        "deployed": any(c["live"] for c in capabilities),
        "doc": "docs/LUA_V7_CAPTURE_RESEARCH_2026-06.md",
        "capabilities": capabilities,
    }


# ===== Wave 2: man-advantage / clutch / side splits =====
# (docs/ANALYTICS_BENCHMARK_2026-06.md proposals #4, #5, #6)

# A window only counts once both teams have spawned at least once (filters
# the spurious "advantage" of staggered initial spawns).
ADV_KILL_EPSILON_MS = 100  # the window-opening kill itself is not a conversion
CLUTCH_MIN_ENEMIES = 2
CLUTCH_MIN_WAVE_WAIT_MS = 5000

_OTHER_TEAM = {"AXIS": "ALLIES", "ALLIES": "AXIS"}


def _advantage_windows(lives: list, kills: list, round_end_ms: int) -> list[dict]:
    """Man-advantage windows from the alive-count differential timeline.

    lives: (guid, team, spawn_ms, death_ms_or_None)
    kills: (kill_time, killer_team, killer_guid, killer_name, victim_team)
    Window = contiguous span where one team has more players alive; converted
    when the advantaged team lands a further kill inside the window.
    """
    events: list[tuple[int, int, str]] = []
    first_spawn: dict[str, int] = {}
    for _guid, team, spawn_ms, death_ms in lives:
        if team not in _OTHER_TEAM:
            continue
        end = death_ms if death_ms and death_ms > spawn_ms else round_end_ms
        events.append((int(spawn_ms), 0, team))
        events.append((int(end), 1, team))
        if team not in first_spawn or spawn_ms < first_spawn[team]:
            first_spawn[team] = int(spawn_ms)
    if len(first_spawn) < 2:
        return []
    ready_ms = max(first_spawn.values())
    events.sort()

    alive = {"AXIS": 0, "ALLIES": 0}
    windows: list[dict] = []
    current: dict | None = None
    # Evaluate the differential once per timestamp — simultaneous events
    # (paired wave spawns, multikills) must not create transient windows.
    for t, group in groupby(events, key=lambda e: e[0]):
        for _, kind, team in group:
            alive[team] += 1 if kind == 0 else -1
        diff = alive["AXIS"] - alive["ALLIES"]
        leader = "AXIS" if diff > 0 else ("ALLIES" if diff < 0 else None)
        if current is not None and leader != current["team"]:
            current["end"] = t
            windows.append(current)
            current = None
        if current is None and leader is not None and t >= ready_ms:
            current = {"team": leader, "start": t, "max_size": abs(diff)}
        elif current is not None:
            current["max_size"] = max(current["max_size"], abs(diff))
    if current is not None:
        current["end"] = round_end_ms
        windows.append(current)

    for w in windows:
        # Half-open [start, end): events at `end` are what removed the edge,
        # so a kill at exactly `end` happened with the edge already gone.
        converter = next(
            (
                k for k in kills
                if k[1] == w["team"]
                and k[4] == _OTHER_TEAM[w["team"]]
                and w["start"] + ADV_KILL_EPSILON_MS < k[0] < w["end"]
            ),
            None,
        )
        w["converted"] = converter is not None
        w["converter_guid"] = converter[2] if converter else None
        w["converter_name"] = converter[3] if converter else None
    return windows


def _detect_clutches(
    lives: list, kills: list, clocks: dict, round_end_ms: int,
) -> list[dict]:
    """Fight-scoped 1vN clutches (no round-end elimination state in ET).

    Situation: a death leaves exactly one player alive on their team while
    >=CLUTCH_MIN_ENEMIES enemies live and the friendly wave is
    >=CLUTCH_MIN_WAVE_WAIT_MS away. Won if the survivor gets a kill and
    lives to the wave, or trades up (kills >= enemies - 1).
    """
    events: list[tuple[int, int, str, str]] = []
    for guid, team, spawn_ms, death_ms in lives:
        if team not in _OTHER_TEAM:
            continue
        end = death_ms if death_ms and death_ms > spawn_ms else round_end_ms
        events.append((int(spawn_ms), 0, team, guid))
        events.append((int(end), 1, team, guid))
    events.sort(key=lambda e: (e[0], e[1]))

    alive: dict[str, set] = {"AXIS": set(), "ALLIES": set()}
    situations: list[dict] = []
    busy_until: dict[str, int] = {}
    # Evaluate once per timestamp (a multikill must not fire intermediate
    # "last alive" states mid-group).
    for t, group in groupby(events, key=lambda e: e[0]):
        died_teams: set[str] = set()
        for _, kind, team, guid in group:
            if kind == 0:
                alive[team].add(guid)
            else:
                alive[team].discard(guid)
                died_teams.add(team)
        for team in died_teams:
            if len(alive[team]) != 1:
                continue
            survivor = next(iter(alive[team]))
            enemies = len(alive[_OTHER_TEAM[team]])
            clock = clocks.get(team)
            if enemies < CLUTCH_MIN_ENEMIES or clock is None:
                continue
            if t < busy_until.get(survivor, 0):
                continue
            offset, interval = clock
            # Ceiling wave landing (>= t): a death exactly on a wave landing
            # means reinforcements are immediate, not a full interval away.
            t_wave = -((-(t + offset)) // interval) * interval - offset
            if t_wave - t < CLUTCH_MIN_WAVE_WAIT_MS:
                continue
            t_wave = min(t_wave, round_end_ms)
            # The survivor's current life bounds the situation.
            life_end = round_end_ms
            for life_guid, life_team, spawn_ms, death_ms in lives:
                d = death_ms if death_ms and death_ms > spawn_ms else round_end_ms
                if life_guid == survivor and life_team == team and spawn_ms <= t < d:
                    life_end = d
                    break
            end = min(t_wave, life_end)
            sit_kills = sum(
                1 for k in kills
                if k[2] == survivor and k[4] == _OTHER_TEAM[team] and t < k[0] <= end
            )
            survived = life_end >= t_wave
            won = (sit_kills >= 1 and survived) or sit_kills >= enemies - 1
            situations.append({
                "guid": survivor,
                "team": team,
                "start": t,
                "enemies": enemies,
                "kills": sit_kills,
                "survived": survived,
                "won": won,
            })
            busy_until[survivor] = end
    return situations


async def _fetch_round_lives_and_kills(
    db: DatabaseAdapter, where_sql: str, params: list,
) -> dict[tuple, dict]:
    """Group player_track lives + spawn_timing kills by round identity."""
    track_rows = await db.fetch_all(
        f"""
        SELECT session_date, map_name, round_number, round_start_unix,
               player_guid, team, spawn_time_ms, death_time_ms
        FROM player_track
        {where_sql}
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )
    kill_rows = await db.fetch_all(
        f"""
        SELECT session_date, map_name, round_number, round_start_unix,
               kill_time, killer_team, killer_guid, killer_name,
               victim_team, enemy_spawn_interval, time_to_next_spawn
        FROM proximity_spawn_timing
        {where_sql} AND killer_guid <> victim_guid
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )
    rounds: dict[tuple, dict] = defaultdict(lambda: {"lives": [], "kills": [], "st": []})
    for r in (track_rows or []):
        key = (r[0], r[1], int(r[2] or 0), int(r[3] or 0))
        rounds[key]["lives"].append((r[4], r[5], int(r[6] or 0), r[7]))
    for r in (kill_rows or []):
        key = (r[0], r[1], int(r[2] or 0), int(r[3] or 0))
        rounds[key]["kills"].append(
            (int(r[4] or 0), r[5], r[6], r[7], r[8])
        )
        rounds[key]["st"].append(r)
    for data in rounds.values():
        # Round end from spawns AND deaths (a survivor's death_ms is None) AND
        # kill times — death-only would truncate windows on survivor-heavy
        # rounds. Kills sorted so the converter pick is deterministic.
        data["kills"].sort(key=lambda k: k[0])
        ends = (
            [s for _, _, s, _ in data["lives"]]
            + [d for _, _, _, d in data["lives"] if d]
            + [k[0] for k in data["kills"]]
        )
        data["end_ms"] = max(ends) if ends else 0
        data["clocks"] = _implied_offsets([
            (r[8], r[4], r[9], r[10]) for r in data["st"]
        ])
    return rounds


@router.get("/proximity/competitive/man-advantage")
async def get_man_advantage(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Man-advantage conversion: who cashes in a numbers edge (benchmark #4)."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    rounds = await _fetch_round_lives_and_kills(db, where_sql, params)

    teams = {
        t: {"windows": 0, "converted": 0, "by_size": {"1": [0, 0], "2": [0, 0], "3+": [0, 0]}}
        for t in ("AXIS", "ALLIES")
    }
    converters: dict[str, dict] = defaultdict(lambda: {"name": "", "conversions": 0})
    total_windows = 0
    for data in rounds.values():
        if not data["lives"]:
            continue
        for w in _advantage_windows(data["lives"], data["kills"], data["end_ms"]):
            team = teams[w["team"]]
            bucket = "1" if w["max_size"] == 1 else ("2" if w["max_size"] == 2 else "3+")
            team["windows"] += 1
            team["by_size"][bucket][0] += 1
            total_windows += 1
            if w["converted"]:
                team["converted"] += 1
                team["by_size"][bucket][1] += 1
                c = converters[w["converter_guid"]]
                c["name"] = strip_et_colors(w["converter_name"] or w["converter_guid"][:8])
                c["conversions"] += 1
    for t in teams.values():
        t["conversion_pct"] = round(t["converted"] / t["windows"] * 100, 1) if t["windows"] else 0.0
        t["by_size"] = {
            k: {"windows": v[0], "converted": v[1]} for k, v in t["by_size"].items()
        }
    top = sorted(
        ({"guid": g, **c} for g, c in converters.items()),
        key=lambda x: -x["conversions"],
    )[:10]
    return {
        "status": "ok",
        "scope": scope,
        "rounds": len(rounds),
        "description": (
            "Advantage window = one team has more players alive (counted once "
            "both teams have spawned). Converted = a further kill lands while "
            "the edge holds."
        ),
        "teams": teams,
        "total_windows": total_windows,
        "top_converters": top,
    }


@router.get("/proximity/competitive/clutch")
async def get_clutches(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Fight-scoped 1vN clutch situations (benchmark #5)."""
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix,
    )
    rounds = await _fetch_round_lives_and_kills(db, where_sql, params)

    names: dict[str, str] = {}
    for data in rounds.values():
        for k in data["kills"]:
            names.setdefault(k[2], k[3])
    players: dict[str, dict] = defaultdict(
        lambda: {"situations": 0, "wins": 0, "best": None}
    )
    skipped_no_clock = 0
    for data in rounds.values():
        if not data["lives"]:
            continue
        if not data["clocks"]:
            skipped_no_clock += 1
            continue
        for sit in _detect_clutches(
            data["lives"], data["kills"], data["clocks"], data["end_ms"]
        ):
            p = players[sit["guid"]]
            p["situations"] += 1
            if sit["won"]:
                p["wins"] += 1
                best = p["best"]
                if best is None or (sit["enemies"], sit["kills"]) > (best["enemies"], best["kills"]):
                    p["best"] = {"enemies": sit["enemies"], "kills": sit["kills"], "survived": sit["survived"]}
    out = [
        {
            "guid": g,
            "name": strip_et_colors(names.get(g) or g[:8]),
            "situations": p["situations"],
            "wins": p["wins"],
            "win_pct": round(p["wins"] / p["situations"] * 100, 1),
            "best": p["best"],
        }
        for g, p in players.items()
        if p["situations"] > 0
    ]
    out.sort(key=lambda x: (-x["wins"], -x["win_pct"]))
    return {
        "status": "ok",
        "scope": scope,
        "rounds": len(rounds),
        "skipped_rounds_no_clock": skipped_no_clock,
        "description": (
            "Clutch = last player alive of their wave group vs 2+ enemies with "
            ">=5s to the friendly wave. Won = a kill + survive to the wave, or "
            "trade up (kills >= enemies-1)."
        ),
        "players": out,
    }


@router.get("/proximity/competitive/side-splits")
async def get_side_splits(
    range_days: int = 30,
    session_date: str | None = None,
    map_name: str | None = None,
    round_number: int | None = None,
    round_start_unix: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Attack/defense re-cut of kill metrics (benchmark #6, Opta-style).

    Side comes from rounds.defender_team via the round_id link; rows on
    unlinked rounds or rounds with unknown defender are skipped (reported).
    """
    where_sql, params, scope = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix, alias="st",
    )
    params.append(STAGGER_THRESHOLD)
    thr = len(params)
    kill_rows = await db.fetch_all(
        f"""
        SELECT st.killer_guid, MAX(st.killer_name),
               CASE WHEN (CASE st.killer_team WHEN 'AXIS' THEN 1 WHEN 'ALLIES' THEN 2 END) = r.defender_team
                    THEN 'defense' ELSE 'attack' END AS side,
               COUNT(*) AS kills,
               COUNT(*) FILTER (
                   WHERE st.enemy_spawn_interval > 0
                     AND st.time_to_next_spawn >= ${thr}::float8 * st.enemy_spawn_interval
               ) AS stagger_kills,
               SUM(st.time_to_next_spawn) AS denied_ms
        FROM proximity_spawn_timing st
        JOIN rounds r ON r.id = st.round_id
        {where_sql} AND st.killer_guid <> st.victim_guid AND r.defender_team IN (1, 2)
        GROUP BY st.killer_guid, side
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )
    time_where, time_params, _ = _build_proximity_where_clause(
        range_days, session_date, map_name, round_number, round_start_unix, alias="pt",
    )
    time_rows = await db.fetch_all(
        f"""
        SELECT pt.player_guid,
               CASE WHEN (CASE pt.team WHEN 'AXIS' THEN 1 WHEN 'ALLIES' THEN 2 END) = r.defender_team
                    THEN 'defense' ELSE 'attack' END AS side,
               SUM(COALESCE(pt.duration_ms, 0)) AS played_ms
        FROM player_track pt
        JOIN rounds r ON r.id = pt.round_id
        {time_where} AND r.defender_team IN (1, 2)
        GROUP BY pt.player_guid, side
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(time_params),
    )
    minutes: dict[tuple, float] = {
        (r[0], r[1]): int(r[2] or 0) / 60000 for r in (time_rows or [])
    }
    players: dict[str, dict] = {}
    for r in (kill_rows or []):
        guid, name, side = r[0], r[1], r[2]
        p = players.setdefault(guid, {
            "guid": guid,
            "name": strip_et_colors(name or guid[:8]),
            "attack": None,
            "defense": None,
        })
        mins = minutes.get((guid, side), 0.0)
        kills = int(r[3])
        p[side] = {
            "kills": kills,
            "stagger_kills": int(r[4]),
            "denied_s": round(int(r[5] or 0) / 1000, 1),
            "minutes": round(mins, 1),
            "kpm": round(kills / mins, 2) if mins >= 1 else None,
        }
    out = sorted(
        players.values(),
        key=lambda p: -(((p["attack"] or {}).get("kills", 0)) + ((p["defense"] or {}).get("kills", 0))),
    )
    return {
        "status": "ok",
        "scope": scope,
        "description": (
            "Side from rounds.defender_team (1=AXIS defends, 2=ALLIES defend); "
            "kpm = kills per minute actually played on that side. Unlinked "
            "rounds and unknown defenders are excluded."
        ),
        "players": out,
    }


@router.get("/proximity/competitive/player-card")
async def get_player_card(
    player_guid: str = Query(..., min_length=8, max_length=32),
    range_days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """Player passport card: one player's competitive profile in one call.

    Stagger and side splits cover range_days; clutch and man-advantage are
    computed over the last 30 days (they need full-round timelines, which is
    the expensive part — 30 days bounds it).
    """
    guid = player_guid.strip().upper()
    # Alphanumeric only (ET guids are hex, bot guids OMNIBOT...) — also keeps
    # LIKE wildcards (%/_) out of the prefix pattern below.
    if not re.fullmatch(r"[A-Z0-9]{8,32}", guid):
        raise HTTPException(status_code=400, detail="player_guid must be 8-32 alphanumeric chars")

    where_sql, params, scope = _build_proximity_where_clause(
        range_days, None, None, None, None,
    )
    params.append(STAGGER_THRESHOLD)
    thr = len(params)
    params.append(guid + "%")
    g = len(params)
    stagger_row = await db.fetch_one(
        f"""
        SELECT MAX(killer_name), COUNT(*),
               COUNT(*) FILTER (
                   WHERE enemy_spawn_interval > 0
                     AND time_to_next_spawn >= ${thr}::float8 * enemy_spawn_interval
               ),
               SUM(time_to_next_spawn), AVG(spawn_timing_score)
        FROM proximity_spawn_timing
        {where_sql} AND killer_guid LIKE ${g} AND killer_guid <> victim_guid
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(params),
    )
    kills = int(stagger_row[1] or 0) if stagger_row else 0
    if not kills:
        return {
            "status": "ok", "player": None, "scope": scope,
            "message": "No competitive data for this player in range.",
        }
    name = strip_et_colors(stagger_row[0] or guid[:8])
    stagger = {
        "kills": kills,
        "stagger_kills": int(stagger_row[2] or 0),
        "stagger_rate": round(int(stagger_row[2] or 0) / kills * 100, 1),
        "denied_s": round(int(stagger_row[3] or 0) / 1000, 1),
        "avg_score": round(float(stagger_row[4] or 0), 3),
    }

    side_where, side_params, _ = _build_proximity_where_clause(
        range_days, None, None, None, None, alias="st",
    )
    side_params.append(guid + "%")
    sg = len(side_params)
    side_rows = await db.fetch_all(
        f"""
        SELECT CASE WHEN (CASE st.killer_team WHEN 'AXIS' THEN 1 WHEN 'ALLIES' THEN 2 END) = r.defender_team
                    THEN 'defense' ELSE 'attack' END AS side,
               COUNT(*), SUM(st.time_to_next_spawn)
        FROM proximity_spawn_timing st
        JOIN rounds r ON r.id = st.round_id
        {side_where} AND st.killer_guid LIKE ${sg}
          AND st.killer_guid <> st.victim_guid AND r.defender_team IN (1, 2)
        GROUP BY side
        """,  # nosec B608 - where_sql is $N-parameterized by _build_proximity_where_clause; no user data interpolated
        tuple(side_params),
    )
    sides = {
        r[0]: {"kills": int(r[1]), "denied_s": round(int(r[2] or 0) / 1000, 1)}
        for r in (side_rows or [])
    }

    # Full-round timelines for clutch + man-advantage (bounded to 30 days).
    tl_where, tl_params, _ = _build_proximity_where_clause(30, None, None, None, None)
    rounds = await _fetch_round_lives_and_kills(db, tl_where, tl_params)
    clutch = {"situations": 0, "wins": 0, "best": None}
    ma_conversions = 0
    for data in rounds.values():
        if not data["lives"]:
            continue
        for w in _advantage_windows(data["lives"], data["kills"], data["end_ms"]):
            if w["converted"] and (w["converter_guid"] or "").upper().startswith(guid):
                ma_conversions += 1
        if not data["clocks"]:
            continue
        for sit in _detect_clutches(
            data["lives"], data["kills"], data["clocks"], data["end_ms"]
        ):
            if not sit["guid"].upper().startswith(guid):
                continue
            clutch["situations"] += 1
            if sit["won"]:
                clutch["wins"] += 1
                best = clutch["best"]
                if best is None or (sit["enemies"], sit["kills"]) > (best["enemies"], best["kills"]):
                    clutch["best"] = {
                        "enemies": sit["enemies"], "kills": sit["kills"],
                        "survived": sit["survived"],
                    }
    clutch["win_pct"] = (
        round(clutch["wins"] / clutch["situations"] * 100, 1)
        if clutch["situations"] else 0.0
    )

    return {
        "status": "ok",
        "scope": scope,
        "player": {"guid": guid, "name": name},
        "range_days": range_days,
        "timeline_range_days": 30,
        "stagger": stagger,
        "sides": sides,
        "clutch": clutch,
        "man_advantage": {"conversions": ma_conversions},
    }
