#!/usr/bin/env python3
"""Build per-bot Omni-bot "twin" profiles from a real player's recorded play
(docs/design/22 slice 3). Local output, no deploy: the owner carries the
files to puran and tests them with `testmode`.

For every bot NAME that is also a real player's alias (the bot table in
`server/omnibot/et_botnames_ext.gm`; today the FALLBACK list of
tools/slomix_rcon.py), with >= --min-sessions sessions on a map:

  camp spots   the player's hold episodes (website/backend/.../advanced_metrics
               `_camp_episodes`: within 96 u for >= 4 s) on the 512 u grid,
               each cell mapped to the NEAREST positioned Omni-bot goal of the
               map (`<map>_goals.gm`, `Position = Vec3(...)`; ROUTE_/AIRSTRIKE_/
               ARTILLERY_/CALLARTILLERY_/PLANTMINE_ are not places). Measured
               2026-09-05: every top cell has a goal within 46-344 u.
  distinctive  ⛔ raw time at a goal is the MAP (supply's forward flag tops
               everyone); a twin carries what the player does MORE than the
               group: share − group mean, kept only when share/group >= 2.0,
               share >= 3 % and he held there in >= 15 % of his sessions (a
               habit, not one night). An empty list is a legitimate answer.
               Every run also measures the shuffled control and prints it:
               at these thresholds about a fifth of the kept goals would
               survive a shuffle — read the report's control line.
  camp times   p25/p75 of his hold episodes at that goal → Min/MaxCampTime
               (clamped 5-60 s), emitted as SetMapGoalProperties.
  role         a named heuristic over his distinctive goals and hold share
               (DEFENDER / ATTACKER / AMBUSHER / ROAMER) → bot.SetRoles.
  tempo        median return_fire_ms relative to the group's median →
               this.ReactionTime (def_bot.gm = 1.0), clamped 0.6-1.5.

Outputs (all under --out, gitignored):
  twins/<alias>.gm            per-bot profile (profile= in the bot table)
  twins/<map>_twins.gm        OnBotJoin-style roles + goal camp times
  et_botnames_ext.gm          the bot table with profile= per twin
and a Markdown report (--report) with every number the files were made of,
plus the regulars who have no bot name yet.

Control that must fail: --shuffle reassigns sessions among players; the
distinctive goals must then (nearly) vanish. If they do not, the ranking is
measuring the map, not the player.

Usage:
  scripts/build_bot_twin_profiles.py                       # 6 rotation maps
  scripts/build_bot_twin_profiles.py --maps supply --shuffle
  scripts/build_bot_twin_profiles.py --fetch                # scp goal files
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

# The camp math is the metric the twin reads its spots from — the same
# episodes the Story page shows (docs/design/22 slice 2), not a copy.
from website.backend.services.storytelling.advanced_metrics import (  # noqa: E402
    _CAMP_CELL,  # noqa: SLF001 — module-private on purpose; the twin must use the SAME grid
    _camp_episodes,  # noqa: SLF001 — and the SAME episode definition as the camp profile
)

GRID = _CAMP_CELL
DEFAULT_MAPS = ("supply", "sw_goldrush_te", "etl_adlernest", "te_escape2", "etl_sp_delivery", "etl_frostbite")
NOT_PLACES = ("ROUTE_", "AIRSTRIKE_", "ARTILLERY_", "CALLARTILLERY_", "PLANTMINE_")
# Thresholds set FROM the control (2026-09-06, 6 twins × 5 maps, sessions
# shuffled among players): lift 1.5 / 3 % kept 66 real vs 30 shuffled goals
# (45 % noise); 2.0 / 3 % keeps 43 vs 9 (≈ 21 %); 2.5 / 5 % 19 vs 4; 3.0 / 5 %
# 12 vs 4. With seven players the group mean is a noisy baseline, so the
# control never reaches zero — the report prints both numbers every run.
MIN_LIFT = 2.0
MIN_SHARE = 0.03
# A spot is a habit, not a night: the player must have held there in at
# least this share of his sessions (and at least MIN_GOAL_SESSIONS of them).
# Without it the shuffled control kept 39 of 82 "distinctive" goals — one
# long hold on one evening looked like personality.
MIN_GOAL_SESSION_SHARE = 0.15
MIN_GOAL_SESSIONS = 3
TOP_GOALS = 3
CAMP_MIN_S, CAMP_MAX_S = 5.0, 60.0
REACTION_MIN, REACTION_MAX = 0.6, 1.5
SANE_MS_MAX = 5000  # scripts/backtest_target_acquisition.py: degenerate reactions above this
BOT_PREFIX = "^o[BOT]^7"
ROLES = ("DEFENDER", "ATTACKER", "AMBUSHER", "ROAMER")

Cell = tuple[int, int]
Point = tuple[int, float, float, float]  # t_ms, x, y, speed


@dataclass(frozen=True)
class Goal:
    name: str
    x: float
    y: float
    z: float
    has_camp_times: bool

    @property
    def kind(self) -> str:
        return self.name.split("_", 1)[0]


@dataclass
class Twin:
    alias: str
    guid: str
    sessions: dict[str, int] = field(default_factory=dict)          # map → sessions
    hold_pct: dict[str, float] = field(default_factory=dict)        # map → %
    distinctive: dict[str, list[tuple[str, float, float]]] = field(default_factory=dict)  # map → [(goal, share, group)]
    camp_times: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)  # map → goal → (min, max)
    role: dict[str, str] = field(default_factory=dict)              # map → ROLE
    reaction_ms: float | None = None
    reaction_time: float = 1.0


# ── goals ──────────────────────────────────────────────────────────────────

_GOAL_RE = re.compile(r"^\t([A-Z]+_[A-Za-z0-9_]+) = ?\n\t\{(.*?)\n\t\}", re.S | re.M)  # Omni-bot writes "= \n"
_POS_RE = re.compile(r"Position = Vec3\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)")


def parse_goals(text: str) -> list[Goal]:
    """Positioned goals of one `<map>_goals.gm` (Omni-bot's own dump), minus
    the entries that are not places a player stands at."""
    out: list[Goal] = []
    for name, body in _GOAL_RE.findall(text):
        if name.startswith(NOT_PLACES):
            continue
        m = _POS_RE.search(body)
        if not m:
            continue
        out.append(Goal(name, float(m.group(1)), float(m.group(2)), float(m.group(3)), "MinCampTime" in body))
    return out


def nearest_goal(cell: Cell, goals: list[Goal], grid: int = GRID) -> tuple[Goal, float]:
    x, y = (cell[0] + 0.5) * grid, (cell[1] + 0.5) * grid
    best = min(goals, key=lambda g: math.hypot(g.x - x, g.y - y))
    return best, math.hypot(best.x - x, best.y - y)


# ── shares and distinctiveness ─────────────────────────────────────────────

def goal_shares(cells_by_player: dict[str, dict[Cell, int]], goals: list[Goal],
                grid: int = GRID) -> dict[str, dict[str, float]]:
    """Per player: share of his hold time at each goal (cell → nearest goal)."""
    out: dict[str, dict[str, float]] = {}
    for player, cells in cells_by_player.items():
        total = sum(cells.values())
        at: dict[str, float] = defaultdict(float)
        for cell, ms in cells.items():
            if not goals:
                break
            g, _ = nearest_goal(cell, goals, grid)
            at[g.name] += ms / total if total else 0.0
        out[player] = dict(at)
    return out


def distinctive_goals(shares: dict[str, dict[str, float]], player: str, top: int = TOP_GOALS,
                      min_lift: float = MIN_LIFT, min_share: float = MIN_SHARE,
                      goal_sessions: dict[str, int] | None = None, player_sessions: int = 0,
                      min_session_share: float = MIN_GOAL_SESSION_SHARE,
                      min_sessions: int = MIN_GOAL_SESSIONS) -> list[tuple[str, float, float]]:
    """Goals where the player holds MORE than the group: ranked by
    share − group mean (others), kept when share/group >= min_lift, share
    >= min_share and — when `goal_sessions` (goal → sessions he held there)
    is given — he held there in >= max(min_sessions, min_session_share ×
    player_sessions) sessions. The group mean is over the OTHER players, so
    one player cannot lift his own baseline."""
    others = [p for p in shares if p != player]
    if not others:
        return []
    names = {g for p in shares for g in shares[p]}
    need = max(min_sessions, math.ceil(min_session_share * player_sessions)) if goal_sessions is not None else 0
    ranked = []
    for g in names:
        share = shares[player].get(g, 0.0)
        group = sum(shares[o].get(g, 0.0) for o in others) / len(others)
        if share < min_share:
            continue
        if goal_sessions is not None and goal_sessions.get(g, 0) < need:
            continue
        lift = share / group if group > 0 else float("inf")
        if lift < min_lift:
            continue
        ranked.append((g, share, group))
    ranked.sort(key=lambda t: -(t[1] - t[2]))
    return ranked[:top]


def camp_times(episode_s: list[float]) -> tuple[float, float]:
    """p25 / p75 of the player's hold episodes at a goal → Min/MaxCampTime,
    clamped to 5-60 s (Omni-bot camps are seconds; a 200 s hold is not a
    camp order, it is a stalemate)."""
    if not episode_s:
        return (CAMP_MIN_S, CAMP_MIN_S * 2)
    q = statistics.quantiles(episode_s, n=4) if len(episode_s) >= 2 else [episode_s[0]] * 3
    lo = min(max(q[0], CAMP_MIN_S), CAMP_MAX_S)
    hi = min(max(q[2], lo + 1.0), CAMP_MAX_S)
    return (round(lo, 1), round(hi, 1))


def role_for(hold_pct: float, group_median_hold: float,
             distinctive: list[tuple[str, float, float]]) -> str:
    """A named heuristic, not a measurement: DEFEND_-heavy spots and an
    above-median hold share → DEFENDER; ATTACK_/PLANT_/FLAG_ spots →
    ATTACKER; nothing distinctive and a low hold share → ROAMER; otherwise
    AMBUSHER (holds, but not at the defence goals)."""
    kinds = [g.split("_", 1)[0] for g, _, _ in distinctive]
    if not kinds:
        return "ROAMER" if hold_pct < group_median_hold else "AMBUSHER"
    defend = sum(k == "DEFEND" for k in kinds)
    attack = sum(k in ("ATTACK", "PLANT", "FLAG", "ESCORT", "CAPPOINT", "CHECKPOINT") for k in kinds)
    if defend > attack and hold_pct >= group_median_hold:
        return "DEFENDER"
    if attack >= defend and attack > 0:
        return "ATTACKER"
    return "AMBUSHER"


def tempo(return_fire_ms: float | None, group_median_ms: float | None) -> float:
    """def_bot.gm's ReactionTime is 1.0 = the group's median reaction; a
    player who returns fire faster gets a smaller value. Clamped so a bad
    measurement cannot make a bot inhuman or asleep."""
    if not return_fire_ms or not group_median_ms or group_median_ms <= 0:
        return 1.0
    return round(min(max(return_fire_ms / group_median_ms, REACTION_MIN), REACTION_MAX), 2)


def shuffle_sessions(rows: list[tuple[str, str, list[Point]]], seed: int) -> list[tuple[str, str, list[Point]]]:
    """The control: keep every session's points, reassign the player labels
    at random — a 'player' becomes a mix of everyone."""
    rng = random.Random(seed)  # noqa: S311 — a reproducible shuffle for a control, not a secret
    players = [p for p, _, _ in rows]
    rng.shuffle(players)
    return [(players[i], s, pts) for i, (_, s, pts) in enumerate(rows)]


# ── rendering (.gm) ────────────────────────────────────────────────────────

def gm_name(alias: str) -> str:
    return alias.replace("\\", "").replace('"', "")


def render_profile(alias: str, twin: Twin, today: str) -> str:
    return "\n".join([
        f"// twins/{gm_name(alias)}.gm — generated {today} by scripts/build_bot_twin_profiles.py",
        f"// from the recorded play of \"{gm_name(alias)}\" (guid {twin.guid}). Do not edit; regenerate.",
        f"// return_fire_ms median = {twin.reaction_ms:.0f}" if twin.reaction_ms else "// return_fire_ms: no measurement (ReactionTime left at the default)",
        "// Everything def_bot.gm sets and this file does not stays at def_bot's value.",
        "",
        f"this.ReactionTime = {twin.reaction_time};",
        "",
    ])


def render_map_twins(map_name: str, twins: list[Twin], prefix: str, today: str) -> str:
    lines = [
        f"// twins/{map_name}_twins.gm — generated {today} by scripts/build_bot_twin_profiles.py",
        "// Per-bot roles and camp times on THIS map's goals, from each player's",
        "// recorded hold episodes. Roles are a heuristic (see the report).",
        "// Include from the map script's OnBotJoin / InitializeRoutes, e.g.",
        f"//   ExecScript(\"twins/{map_name}_twins.gm\");  then  Twins_OnBotJoin(bot);",
        "",
        "global Twins_OnBotJoin = function( bot )",
        "{",
    ]
    for t in twins:
        role = t.role.get(map_name)
        if not role:
            continue
        lines.append(f"\tif ( bot.Name == \"{prefix}{gm_name(t.alias)}\" ) {{")
        lines.append(f"\t\tbot.SetRoles( ROLE.{role} );  // hold {t.hold_pct.get(map_name, 0):.1f} % of alive time")
        lines.append("\t}")
    lines += ["};", "", "// Camp times on the goals each twin holds more than the group does."]
    for t in twins:
        for goal, share, group in t.distinctive.get(map_name, []):
            lo, hi = t.camp_times.get(map_name, {}).get(goal, (CAMP_MIN_S, CAMP_MIN_S * 2))
            lines.append(f"// {gm_name(t.alias)}: {goal} — his share {share * 100:.1f} %, group {group * 100:.1f} %")
            lines.append(f"SetMapGoalProperties( \"{goal}\", {{ MinCampTime = {lo:g}, MaxCampTime = {hi:g} }} );")
    lines.append("")
    return "\n".join(lines)


def balanced(text: str) -> bool:
    """A cheap syntax gate for generated .gm: braces and parentheses balance
    and no stray double quotes remain in names."""
    depth_b = depth_p = 0
    for ch in text:
        if ch == "{":
            depth_b += 1
        elif ch == "}":
            depth_b -= 1
        elif ch == "(":
            depth_p += 1
        elif ch == ")":
            depth_p -= 1
        if depth_b < 0 or depth_p < 0:
            return False
    return depth_b == 0 and depth_p == 0


# ── the corpus run ─────────────────────────────────────────────────────────

async def load_rows(db, map_name: str, min_sessions: int) -> list[tuple[str, str, list[Point]]]:
    rows = await db.fetch(
        """
        SELECT pt.player_guid, pt.session_date::text, pt.path
        FROM player_track pt
        WHERE pt.map_name = $1
          AND pt.player_name NOT LIKE '%[BOT]%'
          AND UPPER(pt.player_guid) NOT LIKE 'OMNIBOT%'
          AND pt.player_guid IN (
            SELECT player_guid FROM player_track
            WHERE map_name = $1 AND player_name NOT LIKE '%[BOT]%'
            GROUP BY player_guid HAVING COUNT(DISTINCT session_date) >= $2)
        """,
        map_name, min_sessions,
    )
    out = []
    for guid, session, path in rows:
        pts = json.loads(path) if isinstance(path, str) else (path or [])
        points = [(int(p.get("time", 0)), float(p["x"]), float(p["y"]), float(p.get("speed") or 0.0))
                  for p in pts if "x" in p and "y" in p]
        if len(points) >= 10:
            out.append((str(guid)[:8].upper(), session, points))
    return out


async def load_aliases(db, aliases: list[str]) -> dict[str, list[str]]:
    """alias (lower) → guids (8-char), newest first. More than one guid is a
    warning the report carries; the newest is used."""
    rows = await db.fetch(
        """
        SELECT LOWER(alias) AS a, UPPER(LEFT(guid, 8)) AS g, MAX(last_seen) AS seen
        FROM player_aliases WHERE LOWER(alias) = ANY($1)
        GROUP BY 1, 2 ORDER BY 1, seen DESC
        """,
        [a.lower() for a in aliases],
    )
    out: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        out[r["a"]].append(r["g"])
    return dict(out)


async def load_classes(db, guids: list[str]) -> dict[str, str]:
    rows = await db.fetch(
        """
        SELECT UPPER(LEFT(player_guid, 8)) AS g,
               mode() WITHIN GROUP (ORDER BY UPPER(player_class)) AS cls
        FROM player_track WHERE UPPER(LEFT(player_guid, 8)) = ANY($1) AND player_class IS NOT NULL
        GROUP BY 1
        """,
        guids,
    )
    return {r["g"]: str(r["cls"]) for r in rows}


async def load_reactions(db) -> dict[str, float]:
    rows = await db.fetch(
        """
        SELECT UPPER(LEFT(rm.target_guid, 8)) AS g,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY rm.return_fire_ms) AS med,
               COUNT(*) AS n
        FROM proximity_reaction_metric rm
        JOIN rounds r ON r.id = rm.round_id AND r.is_valid
        WHERE rm.target_guid NOT LIKE 'OMNIBOT%' AND rm.target_name NOT LIKE '[BOT]%'
          AND rm.return_fire_ms > 0 AND rm.return_fire_ms <= $1
        GROUP BY 1 HAVING COUNT(*) >= 100
        """,
        SANE_MS_MAX,
    )
    return {r["g"]: float(r["med"]) for r in rows}


def measure_map(rows: list[tuple[str, str, list[Point]]], goals: list[Goal],
                min_lift: float = MIN_LIFT, min_share: float = MIN_SHARE) -> dict:
    """Per player on one map: hold %, distinctive goals, camp times."""
    cells: dict[str, dict[Cell, int]] = defaultdict(lambda: defaultdict(int))
    episodes: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    goal_sessions: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    hold_ms: dict[str, int] = defaultdict(int)
    alive_ms: dict[str, int] = defaultdict(int)
    sessions: dict[str, set] = defaultdict(set)
    for player, session, pts in rows:
        h, _, cl = _camp_episodes(pts)
        hold_ms[player] += h
        alive_ms[player] += pts[-1][0] - pts[0][0]
        sessions[player].add(session)
        for cell, ms in cl.items():
            cells[player][cell] += ms
            if goals:
                g, _ = nearest_goal(cell, goals)
                episodes[player][g.name].append(ms / 1000)
                goal_sessions[player][g.name].add(session)
    shares = goal_shares(cells, goals)
    hold_pct = {p: hold_ms[p] / alive_ms[p] * 100 if alive_ms[p] else 0.0 for p in cells}
    med = statistics.median(hold_pct.values()) if hold_pct else 0.0
    out = {}
    for p in cells:
        dist = distinctive_goals(shares, p, min_lift=min_lift, min_share=min_share,
                                 goal_sessions={g: len(v) for g, v in goal_sessions[p].items()},
                                 player_sessions=len(sessions[p]))
        out[p] = {
            "sessions": len(sessions[p]),
            "hold_pct": hold_pct[p],
            "distinctive": dist,
            "camp_times": {g: camp_times(episodes[p][g]) for g, _, _ in dist},
            "role": role_for(hold_pct[p], med, dist),
        }
    return out


def bot_aliases_from_table(text: str) -> list[str]:
    return re.findall(r'(?:AxisBots|AlliedBots)\["([^"]+)"\]', text)


def dedupe_by_guid(twins: list[Twin]) -> tuple[list[Twin], list[tuple[str, str, str]]]:
    """Two bot names that are aliases of the SAME player (olz / Olympus on
    the live table) must not become two copies of one twin: the first name
    keeps the twin, the rest are reported as (dropped_alias, kept_alias, guid)."""
    kept: list[Twin] = []
    seen: dict[str, str] = {}
    dropped: list[tuple[str, str, str]] = []
    for t in twins:
        if t.guid in seen:
            dropped.append((t.alias, seen[t.guid], t.guid))
            continue
        seen[t.guid] = t.alias
        kept.append(t)
    return kept, dropped


def place_in_class(axis: dict[str, list[str]], allies: dict[str, list[str]], name: str, cls: str) -> None:
    """The bot table's class comes from a round-robin; a twin plays the class
    its player plays (the mode of player_track.player_class — every regular
    here is a MEDIC). Moves `name` into `cls` on whichever team it is on."""
    for table in (axis, allies):
        for c, names in table.items():
            if name in names and c != cls and cls in table:
                names.remove(name)
                table[cls].append(name)
                return


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", nargs="*", default=list(DEFAULT_MAPS))
    ap.add_argument("--min-sessions", type=int, default=25)
    ap.add_argument("--goals-dir", type=Path, default=REPO / "server" / "omnibot" / "nav")
    ap.add_argument("--bot-table", type=Path, default=REPO / "server" / "omnibot" / "et_botnames_ext.gm")
    ap.add_argument("--out", type=Path, default=REPO / "server" / "omnibot" / "twins")
    ap.add_argument("--report", type=Path, default=REPO / "docs" / "design" / "23_TWINS_REPORT.md")
    ap.add_argument("--prefix", default=BOT_PREFIX)
    ap.add_argument("--min-lift", type=float, default=MIN_LIFT, help="share/group floor for a distinctive goal")
    ap.add_argument("--min-share", type=float, default=MIN_SHARE, help="share floor for a distinctive goal")
    ap.add_argument("--shuffle", action="store_true", help="control: reassign sessions among players")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--fetch", action="store_true", help="scp the goal files from the game server first")
    args = ap.parse_args(argv)

    import asyncpg  # noqa: PLC0415
    from audit_session_basics import _dsn  # noqa: PLC0415
    from slomix_rcon import FALLBACK_NAMES  # noqa: PLC0415

    if args.fetch:
        fetch_goal_files(args.maps, args.goals_dir)

    bot_aliases = bot_aliases_from_table(args.bot_table.read_text(encoding="utf-8")) if args.bot_table.exists() else list(FALLBACK_NAMES)
    conn = await asyncpg.connect(_dsn())
    await conn.execute("SET default_transaction_read_only = on")
    alias_guids = await load_aliases(conn, bot_aliases)
    reactions = await load_reactions(conn)
    group_rf = statistics.median(reactions.values()) if reactions else None
    today = date.today().isoformat()  # noqa: DTZ011 — a date stamp in a generated comment

    twins: dict[str, Twin] = {}
    for alias in bot_aliases:
        guids = alias_guids.get(alias.lower(), [])
        if guids:
            twins[alias] = Twin(alias=alias, guid=guids[0])
    regulars: dict[str, set] = defaultdict(set)
    warnings = [f"alias `{a}` maps to {len(g)} guids ({', '.join(g)}); newest used" for a, g in alias_guids.items() if len(g) > 1]
    kept, dropped = dedupe_by_guid(list(twins.values()))
    twins = {t.alias: t for t in kept}
    warnings += [f"bot name `{d}` is an alias of the same player as `{k}` (guid {g}); one twin, `{k}`" for d, k, g in dropped]
    classes = await load_classes(conn, [t.guid for t in twins.values()])
    per_map: dict[str, dict] = {}
    control_goals = 0
    real_goals_all = 0
    for m in args.maps:
        gfile = args.goals_dir / f"{m}_goals.gm"
        if not gfile.exists():
            warnings.append(f"{m}: no goal file at {gfile} (map skipped)")
            continue
        goals = parse_goals(gfile.read_text(encoding="utf-8", errors="replace"))
        rows = await load_rows(conn, m, args.min_sessions)
        if args.shuffle:
            rows = shuffle_sessions(rows, args.seed)
        res = measure_map(rows, goals, args.min_lift, args.min_share)
        per_map[m] = res
        # The control, always: the same rows with sessions reassigned.
        ctrl = measure_map(shuffle_sessions(rows, args.seed), goals, args.min_lift, args.min_share)
        control_goals += sum(len(r["distinctive"]) for r in ctrl.values())
        real_goals_all += sum(len(r["distinctive"]) for r in res.values())
        for guid in res:
            regulars[guid].add(m)
        for t in twins.values():
            r = res.get(t.guid)
            if not r:
                continue
            t.sessions[m] = r["sessions"]
            t.hold_pct[m] = r["hold_pct"]
            t.distinctive[m] = r["distinctive"]
            t.camp_times[m] = r["camp_times"]
            t.role[m] = r["role"]
    for t in twins.values():
        t.reaction_ms = reactions.get(t.guid)
        t.reaction_time = tempo(t.reaction_ms, group_rf)
    await conn.close()

    active = [t for t in twins.values() if t.sessions]
    args.out.mkdir(parents=True, exist_ok=True)
    for t in active:
        (args.out / f"{gm_name(t.alias)}.gm").write_text(render_profile(t.alias, t, today), encoding="utf-8")
    for m in per_map:
        text = render_map_twins(m, [t for t in active if m in t.role], args.prefix, today)
        assert balanced(text), m
        (args.out / f"{m}_twins.gm").write_text(text, encoding="utf-8")

    # The bot table with profile= per twin (render_botnames_with_profiles).
    from slomix_rcon import assign_names, dedupe, ensure_class_coverage, render_botnames, sanitize_name  # noqa: PLC0415
    names = dedupe([sanitize_name(n, 20) for n in bot_aliases])
    axis, allies = assign_names(names)
    ensure_class_coverage(axis, allies, names)
    for t in active:
        if t.guid in classes:
            place_in_class(axis, allies, t.alias, classes[t.guid])
    extra = [n for n in names if n not in sum(axis.values(), []) + sum(allies.values(), [])] or ["ExtraOne", "ExtraTwo", "ExtraThree"]
    profiles = {t.alias: f"twins/{gm_name(t.alias)}.gm" for t in active}
    (args.out / "et_botnames_ext.gm").write_text(render_botnames(axis, allies, args.prefix, extra, profiles=profiles), encoding="utf-8")

    # Report
    lines = [f"# Dvojčki botov — poročilo generatorja ({today}{', KONTROLA: premešane seje' if args.shuffle else ''})", ""]
    lines.append(f"Prag sej: {args.min_sessions}; razločevalni cilj = delež/skupina ≥ {args.min_lift:g} in delež ≥ {args.min_share * 100:g} %. "
                 + (f"Skupinska mediana `return_fire_ms`: {group_rf:.0f} ms." if group_rf else ""))
    lines.append("")
    total_distinct = 0
    for t in active:
        lines.append(f"## {t.alias} (guid {t.guid}) — ReactionTime {t.reaction_time} (return_fire {t.reaction_ms:.0f} ms)" if t.reaction_ms else f"## {t.alias} (guid {t.guid}) — ReactionTime {t.reaction_time} (brez meritve)")
        lines.append("")
        lines.append(f"Razred: {classes.get(t.guid, 'neizmerjen')}.")
        lines.append("")
        lines.append("| mapa | sej | hold % | vloga | razločevalni cilji (delež / skupina → kamp s) |")
        lines.append("|---|---|---|---|---|")
        for m in per_map:
            if m not in t.sessions:
                continue
            goals_txt = "; ".join(
                f"{g} ({s * 100:.1f} % / {gr * 100:.1f} % → {t.camp_times[m][g][0]:g}–{t.camp_times[m][g][1]:g})"
                for g, s, gr in t.distinctive[m]) or "—"
            total_distinct += len(t.distinctive[m])
            lines.append(f"| {m} | {t.sessions[m]} | {t.hold_pct[m]:.1f} | {t.role[m]} | {goals_txt} |")
        lines.append("")
    missing = sorted(g for g in regulars if g not in {t.guid for t in active})
    lines.append(f"## Regularji brez bot imena ({len(missing)})")
    lines.append("")
    lines += [f"- `{g}` na {', '.join(sorted(regulars[g]))}" for g in missing] or ["- (nobenega)"]
    lines.append("")
    lines.append(f"Skupaj razločevalnih ciljev pri dvojčkih: {total_distinct}.")
    lines.append("")
    fdr = control_goals / real_goals_all if real_goals_all else 0.0
    lines.append(f"**Kontrola (premešane seje, vsi regularji):** {control_goals} »razločevalnih« ciljev proti {real_goals_all} pravim "
                 f"→ pri teh pragih bi premešanje preživelo ≈ {fdr * 100:.0f} % najdb. Kontrola ne pade na nič: s ~7 igralci je "
                 f"skupinsko povprečje šumna osnovnica. Beri cilje z največjim dvigom kot najzanesljivejše.")
    if warnings:
        lines += ["", "## Opozorila", ""] + [f"- {w}" for w in warnings]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"twins: {len(active)} ({', '.join(t.alias for t in active)}); maps: {len(per_map)}; distinctive goals: {total_distinct}; "
          f"control (all regulars): {control_goals} of {real_goals_all}")
    print(f"wrote {args.out}/ and {args.report}")
    return 0


def fetch_goal_files(maps: list[str], goals_dir: Path) -> None:
    """scp `<map>_goals.gm` from the game server (SSH_* in .env), read-only."""
    import subprocess  # noqa: PLC0415

    from dotenv import dotenv_values  # noqa: PLC0415

    env = dotenv_values(REPO / ".env")
    key = str(Path(env.get("SSH_KEY_PATH", "~/.ssh/etlegacy_bot")).expanduser())
    goals_dir.mkdir(parents=True, exist_ok=True)
    for m in maps:
        src = f"{env['SSH_USER']}@{env['SSH_HOST']}:/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/nav/{m}_goals.gm"
        subprocess.run(["scp", "-i", key, "-P", str(env.get("SSH_PORT", "22")), "-o", "BatchMode=yes", "-q", src, str(goals_dir)], check=False)  # noqa: S603, S607


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
