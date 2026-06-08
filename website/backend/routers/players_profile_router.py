"""Unified player profile endpoint — gibhub.gg parity.

``GET /api/players/{identifier}/profile`` assembles every profile section in a
single round-trip-parallel call (``asyncio.gather``), mirroring the composite
pattern in :mod:`website.backend.routers.proximity_player`.

Each section is its own ``_fetch_*`` coroutine that returns either its data or
``{"available": False, "reason": ...}`` — proximity coverage is uneven (only
~26 % of players have ``proximity_shot_fired`` rows, ~50 % have ``player_track``),
so every section degrades gracefully instead of failing the whole endpoint.

GUID handling (verified against live schema):
* ``player_comprehensive_stats.player_guid``        → 8-char
* ``proximity_shot_fired.guid_canonical``           → 8-char (``guid`` is 32)
* ``proximity_spawn_timing.killer_guid_canonical``  → 8-char
* ``proximity_lua_trade_kill.trader_guid_canonical``→ 8-char
* ``proximity_hit_region.attacker_guid`` / ``player_track.player_guid`` /
  ``combat_engagement.target_guid``                 → 32-char → match ``LEFT(col,8)``
* ``proximity_kill_outcome.killer_guid``            → 32-char (RivalriesService key)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.routers.api_helpers import (
    resolve_display_name,
    resolve_player_guid,
)
from website.backend.routers.proximity_positions import _circular_yaw_stats
from website.backend.services.player_profile_metrics import (
    bait_score,
    compute_streaks,
    locale_to_flag,
    utro_from_waits,
    weapon_t_name,
)
from website.backend.services.rivalries_service import RivalriesService
from website.backend.services.skill_rating_service import get_tier
from website.backend.utils.et_constants import strip_et_colors

logger = logging.getLogger(__name__)
router = APIRouter()

_MIN_WEAPON_SHOTS = 30      # per-weapon aim needs a usable sample
_MIN_FLICK_PAIRS = 20       # flick index needs enough consecutive shot pairs
_MIN_ENEMY_REL = 25         # enemy-relative crosshair sample floor
_FLICK_DEG = 30.0           # |Δyaw| above this between quick shots = a flick
_FLICK_MAX_DT_MS = 600      # only count pairs fired within this gap
_SPREAD_TIGHT_DEG = 5.0     # |Δyaw| below this between quick shots = tight control
_BURST_GAP_MS = 500         # shots within this gap belong to the same burst
_MIN_BURST_SHOTS = 50       # need this many shots before burst stats are meaningful


# ── helpers ────────────────────────────────────────────────────────────────

def _f(v, default=0.0) -> float:
    try:
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def _i(v, default=0) -> int:
    try:
        return int(v) if v is not None else int(default)
    except (TypeError, ValueError):
        return int(default)


# ── section fetchers ─────────────────────────────────────────────────────────

async def _fetch_identity(db, guid8: str, fallback: str) -> dict:
    name = await resolve_display_name(db, guid8, fallback)
    rows = await db.fetch_all(
        """
        SELECT DISTINCT player_name FROM player_comprehensive_stats
        WHERE player_guid = $1 ORDER BY player_name LIMIT 25
        """,
        (guid8,),
    )
    # Strip ET color codes (^1name) for consistency with identity.name, which
    # is already normalized via resolve_display_name. De-dup post-strip.
    aliases = list(dict.fromkeys(
        strip_et_colors(r[0]) for r in (rows or []) if r and r[0]
    ))
    seen = await db.fetch_one(
        """
        SELECT MIN(round_date) AS first_seen, MAX(round_date) AS last_seen,
               COUNT(DISTINCT round_id) AS rounds
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND round_number IN (1, 2)
        """,
        (guid8,),
    )
    # Discord link + optional identity enrichment (locale→flag, twitch handle).
    # Guarded: the locale/twitch columns may not exist until migration 056 is
    # applied — fall back to the plain link check so identity never errors.
    discord_linked = False
    country = None
    twitch = None
    try:
        link = await db.fetch_one(
            "SELECT discord_locale, twitch_login FROM player_links WHERE player_guid = $1 LIMIT 1",
            (guid8,),
        )
        if link is not None:
            discord_linked = True
            country = locale_to_flag(link[0])
            if link[1]:
                handle = str(link[1]).strip().lstrip("@")
                if handle:
                    twitch = {"login": handle, "url": f"https://twitch.tv/{handle}"}
    except Exception:
        link = await db.fetch_one(
            "SELECT 1 FROM player_links WHERE player_guid = $1 LIMIT 1", (guid8,),
        )
        discord_linked = bool(link)
    return {
        "available": True,
        "guid": guid8,
        "name": name,
        "aliases": aliases,
        "first_seen": str(seen[0]) if seen and seen[0] else None,
        "last_seen": str(seen[1]) if seen and seen[1] else None,
        "rounds": _i(seen[2]) if seen else 0,
        "discord_linked": discord_linked,
        "country": country,   # {flag, country, locale} or None (locale≠verified country)
        "twitch": twitch,     # {login, url} or None (live status = future, needs Helix creds)
    }


async def _fetch_lifetime(db, guid8: str) -> dict:
    row = await db.fetch_one(
        """
        SELECT
            COUNT(p.round_id)                       AS rounds,
            SUM(p.kills)                            AS kills,
            SUM(p.deaths)                           AS deaths,
            SUM(p.gibs)                             AS gibs,
            SUM(p.headshots)                        AS headshots,
            SUM(p.headshot_kills)                   AS headshot_kills,
            SUM(p.damage_given)                     AS dmg_given,
            SUM(p.damage_received)                  AS dmg_received,
            SUM(p.team_damage_given)                AS team_dmg_given,
            SUM(p.team_kills)                       AS team_kills,
            SUM(p.self_kills)                       AS self_kills,
            SUM(p.bullets_fired)                    AS shots,
            SUM(p.xp)                               AS xp,
            SUM(p.time_played_seconds)              AS time_played,
            SUM(p.revives_given)                    AS revives_given,
            SUM(p.times_revived)                    AS times_revived,
            SUM(p.kill_assists)                     AS assists,
            SUM(p.most_useful_kills)                AS useful_kills,
            SUM(p.objectives_completed)             AS obj_completed,
            SUM(p.objectives_destroyed)             AS obj_destroyed,
            SUM(p.objectives_stolen)                AS obj_stolen,
            SUM(p.objectives_returned)              AS obj_returned,
            SUM(p.dynamites_planted)                AS dyn_planted,
            SUM(p.dynamites_defused)                AS dyn_defused,
            SUM(p.double_kills)                     AS double_kills,
            SUM(p.triple_kills)                     AS triple_kills,
            SUM(p.quad_kills)                       AS quad_kills,
            SUM(p.multi_kills)                      AS multi_kills,
            SUM(p.mega_kills)                       AS mega_kills,
            MAX(p.killing_spree_best)               AS best_spree,
            -- winner_team: 0 = draw/no-winner, 1 = AXIS, 2 = ALLIES. Only
            -- decided rounds (1/2) count toward W/L so draws don't deflate win_rate.
            SUM(CASE WHEN r.winner_team IN (1, 2) AND p.team = r.winner_team
                     THEN 1 ELSE 0 END)            AS wins,
            SUM(CASE WHEN r.winner_team IN (1, 2) AND p.team <> r.winner_team
                     THEN 1 ELSE 0 END)            AS losses
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1 AND p.round_number IN (1, 2)
        """,
        (guid8,),
    )
    if not row or not row[0]:
        return {"available": False, "reason": "no stats"}

    (rounds, kills, deaths, gibs, headshots, hs_kills, dmg_g, dmg_r, tdmg_g,
     tkills, selfk, shots, xp, time_played, rev_g, rev_t, assists, useful,
     obj_c, obj_d, obj_s, obj_r, dyn_p, dyn_d, dk, tk2, qk, mk, megak,
     best_spree, wins, losses) = row

    kills = _i(kills)
    deaths = _i(deaths)
    time_played = _i(time_played)
    wins = _i(wins)
    losses = _i(losses)
    games = wins + losses
    return {
        "available": True,
        "rounds": _i(rounds),
        "wins": wins, "losses": losses,
        "win_rate": round(wins / games * 100, 1) if games else 0.0,
        "kills": kills, "deaths": deaths,
        "kd": round(kills / deaths, 2) if deaths else float(kills),
        "gibs": _i(gibs),
        "headshots": _i(headshots), "headshot_kills": _i(hs_kills),
        "damage_given": _i(dmg_g), "damage_received": _i(dmg_r),
        "team_damage_given": _i(tdmg_g),
        "team_kills": _i(tkills), "self_kills": _i(selfk),
        "shots": _i(shots),
        "xp": _i(xp),
        "time_played_seconds": time_played,
        "hours_played": round(time_played / 3600, 1),
        "dpm": round(_i(dmg_g) / (time_played / 60), 1) if time_played else 0.0,
        "revives_given": _i(rev_g), "times_revived": _i(rev_t),
        "kill_assists": _i(assists), "useful_kills": _i(useful),
        "objectives_completed": _i(obj_c), "objectives_destroyed": _i(obj_d),
        "objectives_stolen": _i(obj_s), "objectives_returned": _i(obj_r),
        "dynamites_planted": _i(dyn_p), "dynamites_defused": _i(dyn_d),
        "double_kills": _i(dk), "triple_kills": _i(tk2), "quad_kills": _i(qk),
        "multi_kills": _i(mk), "mega_kills": _i(megak),
        "best_killing_spree": _i(best_spree),
    }


async def _fetch_streaks(db, guid8: str) -> dict:
    rows = await db.fetch_all(
        """
        SELECT CASE WHEN p.team = r.winner_team THEN 'W' ELSE 'L' END AS res
        FROM player_comprehensive_stats p
        JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1 AND p.round_number IN (1, 2)
          AND r.winner_team IN (1, 2)   -- exclude draws (0) so W/L streaks stay clean
        ORDER BY p.round_date ASC, p.round_id ASC
        """,
        (guid8,),
    )
    results = [r[0] for r in (rows or []) if r and r[0]]
    if not results:
        return {"available": False}
    out = compute_streaks(results)
    out["available"] = True
    return out


async def _fetch_advanced(db, guid8: str, lifetime_deaths: int) -> dict:
    """UTRO + bait_score (proximity-derived; degrades if no proximity rows)."""
    waits_rows = await db.fetch_all(
        """
        SELECT victim_reinf FROM proximity_spawn_timing
        WHERE killer_guid_canonical = $1 AND victim_reinf IS NOT NULL
        """,
        (guid8,),
    )
    waits = [r[0] for r in (waits_rows or []) if r]
    utro = utro_from_waits(waits) if waits else {"available": False}
    if waits:
        utro["available"] = True

    trades_row = await db.fetch_one(
        "SELECT COUNT(*) FROM proximity_lua_trade_kill WHERE trader_guid_canonical = $1",
        (guid8,),
    )
    avenged_row = await db.fetch_one(
        # Player's own deaths that a teammate avenged (player is the original victim)
        "SELECT COUNT(*) FROM proximity_lua_trade_kill WHERE LEFT(original_victim_guid, 8) = $1",
        (guid8,),
    )
    trades_made = _i(trades_row[0]) if trades_row else 0
    avenged = _i(avenged_row[0]) if avenged_row else 0
    untraded = max(0, lifetime_deaths - avenged)
    bait = bait_score(trades_made, untraded)
    return {"available": True, "utro": utro, "bait": bait}


async def _fetch_movement(db, guid8: str) -> dict:
    row = await db.fetch_one(
        """
        SELECT COUNT(*) AS tracks,
               ROUND(AVG(avg_speed)::numeric, 1)            AS avg_speed,
               ROUND(MAX(peak_speed)::numeric, 1)           AS peak_speed,
               ROUND(AVG(sprint_percentage)::numeric, 1)    AS sprint_pct,
               ROUND(AVG(total_distance)::numeric, 0)       AS avg_distance,
               ROUND(AVG(post_spawn_distance)::numeric, 0)  AS avg_spawn_distance,
               SUM(stance_standing_sec)                     AS standing,
               SUM(stance_crouching_sec)                    AS crouching,
               SUM(stance_prone_sec)                        AS prone,
               SUM(sprint_sec)                              AS sprint_sec
        FROM player_track
        WHERE LEFT(player_guid, 8) = $1
        """,
        (guid8,),
    )
    if not row or not _i(row[0]):
        return {"available": False, "reason": "no movement data"}
    standing = _f(row[6])
    crouching = _f(row[7])
    prone = _f(row[8])
    total_stance = standing + crouching + prone
    return {
        "available": True,
        "tracks": _i(row[0]),
        "avg_speed": _f(row[1]), "peak_speed": _f(row[2]),
        "sprint_pct": _f(row[3]),
        "avg_distance_per_life": _i(row[4]),
        "avg_post_spawn_distance": _i(row[5]),
        "stance": {
            "standing_sec": round(standing, 1),
            "crouching_sec": round(crouching, 1),
            "prone_sec": round(prone, 1),
            "standing_pct": round(standing / total_stance * 100, 1) if total_stance else 0.0,
            "crouching_pct": round(crouching / total_stance * 100, 1) if total_stance else 0.0,
            "prone_pct": round(prone / total_stance * 100, 1) if total_stance else 0.0,
        },
        "sprint_sec": round(_f(row[9]), 1),
    }


async def _fetch_weapons(db, guid8: str) -> dict:
    rows = await db.fetch_all(
        """
        SELECT weapon_name,
               SUM(kills)      AS kills,
               SUM(deaths)     AS deaths,
               SUM(headshots)  AS headshots,
               SUM(shots)      AS shots,
               SUM(hits)       AS hits
        FROM weapon_comprehensive_stats
        WHERE player_guid = $1 AND round_number IN (1, 2)
        GROUP BY weapon_name
        HAVING SUM(kills) > 0 OR SUM(shots) > 0
        ORDER BY SUM(kills) DESC
        """,
        (guid8,),
    )
    if not rows:
        return {"available": False, "reason": "no weapon data"}
    weapons = []
    tot_shots = tot_hits = tot_hs = 0
    for r in rows:
        shots = _i(r[4])
        hits = _i(r[5])
        hs = _i(r[3])
        tot_shots += shots
        tot_hits += hits
        tot_hs += hs
        name = (r[0] or "").strip()
        if name.lower().startswith(("ws ", "ws_")):
            name = name[3:]
        weapons.append({
            "weapon": name.replace("_", " ").title() or "Unknown",
            "kills": _i(r[1]), "deaths": _i(r[2]),
            "headshots": hs, "shots": shots, "hits": hits,
            "accuracy": round(hits / shots * 100, 1) if shots else 0.0,
            "hs_accuracy": round(hs / hits * 100, 1) if hits else 0.0,
        })
    return {
        "available": True,
        "weapons": weapons[:25],
        "overall_accuracy": round(tot_hits / tot_shots * 100, 1) if tot_shots else 0.0,
        "overall_hs_accuracy": round(tot_hs / tot_hits * 100, 1) if tot_hits else 0.0,
        "total_shots": tot_shots,
        "total_hits": tot_hits,
    }


async def _fetch_hit_regions(db, guid8: str) -> dict:
    """Body-region hit distribution from raw proximity_hit_region (weapon_t)."""
    rows = await db.fetch_all(
        """
        SELECT weapon_id,
               SUM(CASE WHEN hit_region = 0 THEN 1 ELSE 0 END) AS head,
               SUM(CASE WHEN hit_region = 1 THEN 1 ELSE 0 END) AS arms,
               SUM(CASE WHEN hit_region = 2 THEN 1 ELSE 0 END) AS body,
               SUM(CASE WHEN hit_region = 3 THEN 1 ELSE 0 END) AS legs,
               COUNT(*) AS total
        FROM proximity_hit_region
        WHERE LEFT(attacker_guid, 8) = $1
        GROUP BY weapon_id
        ORDER BY total DESC
        """,
        (guid8,),
    )
    if not rows:
        return {"available": False, "reason": "no hit-region data"}
    tot_head = tot_arms = tot_body = tot_legs = 0
    per_weapon = []
    for r in rows:
        head = _i(r[1])
        arms = _i(r[2])
        body = _i(r[3])
        legs = _i(r[4])
        total = _i(r[5])
        tot_head += head
        tot_arms += arms
        tot_body += body
        tot_legs += legs
        if total >= _MIN_WEAPON_SHOTS:
            per_weapon.append({
                "weapon": weapon_t_name(r[0]),
                "head": head, "arms": arms, "body": body, "legs": legs,
                "total": total,
                "head_pct": round(head / total * 100, 1) if total else 0.0,
            })
    grand = tot_head + tot_arms + tot_body + tot_legs
    if grand == 0:
        return {"available": False, "reason": "no hits"}
    return {
        "available": True,
        "totals": {
            "head": tot_head, "arms": tot_arms, "body": tot_body, "legs": tot_legs,
            "head_pct": round(tot_head / grand * 100, 1),
            "arms_pct": round(tot_arms / grand * 100, 1),
            "body_pct": round(tot_body / grand * 100, 1),
            "legs_pct": round(tot_legs / grand * 100, 1),
        },
        "per_weapon": per_weapon[:15],
    }


async def _fetch_relationships(db, guid8: str, guid32: str | None) -> dict:
    out: dict = {"available": False}
    # top_killers / top_victims / hardest / easiest from RivalriesService (32-char key)
    if guid32:
        try:
            riv = await RivalriesService(db).get_player_rivalries(guid32)
            pairs = [p for p in riv.get("all_pairs", []) if p.get("total_encounters", 0) >= 3]
            top_killers = sorted(pairs, key=lambda p: p["kills_on_player"], reverse=True)[:5]
            top_victims = sorted(pairs, key=lambda p: p["kills_by_player"], reverse=True)[:5]
            ranked = [p for p in pairs if p["total_encounters"] >= 5]
            hardest = sorted(ranked, key=lambda p: p["win_rate"])[:5]
            easiest = sorted(ranked, key=lambda p: p["win_rate"], reverse=True)[:5]
            out.update({
                "available": True,
                "top_killers": top_killers,
                "top_victims": top_victims,
                "hardest_opponents": hardest,
                "easiest_opponents": easiest,
            })
        except Exception:
            logger.warning("rivalries fetch failed for %s", guid8, exc_info=True)

    # best/worst teammates — round co-play DPM delta (self-contained, 8-char)
    try:
        baseline_row = await db.fetch_one(
            """
            SELECT AVG(damage_given * 60.0 / NULLIF(time_played_seconds, 0))
            FROM player_comprehensive_stats
            WHERE player_guid = $1 AND round_number IN (1, 2) AND time_played_seconds > 60
            """,
            (guid8,),
        )
        baseline = _f(baseline_row[0]) if baseline_row else 0.0
        tm_rows = await db.fetch_all(
            """
            WITH my_rounds AS (
                SELECT round_id, team FROM player_comprehensive_stats
                WHERE player_guid = $1 AND round_number IN (1, 2)
            )
            SELECT tm.player_guid,
                   MAX(tm.player_name)                                          AS name,
                   COUNT(*)                                                     AS rounds_together,
                   AVG(me.damage_given * 60.0 / NULLIF(me.time_played_seconds, 0)) AS my_dpm_with
            FROM my_rounds mr
            JOIN player_comprehensive_stats tm
                 ON tm.round_id = mr.round_id AND tm.team = mr.team
                 AND tm.player_guid <> $1 AND tm.round_number IN (1, 2)
            JOIN player_comprehensive_stats me
                 ON me.round_id = mr.round_id AND me.player_guid = $1
                 AND me.round_number IN (1, 2) AND me.time_played_seconds > 60
            WHERE tm.player_guid NOT LIKE 'OMNIBOT%'
            GROUP BY tm.player_guid
            HAVING COUNT(*) >= 5
            """,
            (guid8,),
        )
        mates = []
        for r in (tm_rows or []):
            dpm_with = _f(r[3])
            mates.append({
                "guid": r[0],
                "name": (r[1] or r[0][:8]),
                "rounds_together": _i(r[2]),
                "dpm_with": round(dpm_with, 1),
                "synergy": round(dpm_with - baseline, 1),
            })
        mates.sort(key=lambda m: m["synergy"], reverse=True)
        out["best_teammates"] = mates[:5]
        out["worst_teammates"] = list(reversed(mates[-5:])) if len(mates) > 5 else []
        out["baseline_dpm"] = round(baseline, 1)
        if mates:
            out["available"] = True
    except Exception:
        logger.warning("teammate synergy fetch failed for %s", guid8, exc_info=True)
    return out


async def _fetch_skill(db, guid8: str) -> dict:
    # Window-rank over all rated players (rank 1 = best), same source as
    # /api/skill/leaderboard, so the profile shows a leaderboard position.
    row = await db.fetch_one(
        """
        WITH ranked AS (
            SELECT player_guid, et_rating, games_rated, components,
                   ROW_NUMBER() OVER (ORDER BY et_rating DESC) AS rnk,
                   COUNT(*) OVER () AS total
            FROM player_skill_ratings
            WHERE games_rated > 0
        )
        SELECT et_rating, games_rated, components, rnk, total
        FROM ranked WHERE player_guid = $1
        """,
        (guid8,),
    )
    if not row or row[0] is None:
        return {"available": False, "reason": "not rated"}
    rating = _f(row[0])
    rank = _i(row[3])
    total = _i(row[4])
    return {
        "available": True,
        "et_rating": round(rating, 3),
        "tier": get_tier(rating),
        "games_rated": _i(row[1]),
        "components": row[2],
        "rank": rank,
        "total_rated": total,
        "percentile": round((total - rank) / total * 100, 1) if total else 0.0,
    }


async def _fetch_gather_summary(db, guid8: str) -> dict:
    """Per-gather (gaming-session) W/L/D + win% + streaks.

    Uses `session_results` (one stopwatch-correct row per gaming session, with
    `winning_team` 0=draw/1/2 from the map score). This is the gather-level
    record (gibhub gather_summary granularity), distinct from the round-level
    streaks already shown. GUIDs are stored as quoted 8-char JSON elements, so
    match on `%"guid"%` to avoid prefix collisions.
    """
    rows = await db.fetch_all(
        """
        SELECT session_date, gaming_session_id, winning_team, team_1_guids, team_2_guids
        FROM session_results
        WHERE team_1_guids LIKE $1 OR team_2_guids LIKE $1
        ORDER BY session_date ASC, gaming_session_id ASC
        """,
        (f'%"{guid8}"%',),
    )
    if not rows:
        return {"available": False}
    needle = f'"{guid8}"'
    results = []
    wins = losses = draws = 0
    for r in rows:
        winner = _i(r[2])
        in_t1 = needle in (r[3] or "")
        my_team = 1 if in_t1 else 2
        if winner == 0:
            results.append("D")
            draws += 1
        elif winner == my_team:
            results.append("W")
            wins += 1
        else:
            results.append("L")
            losses += 1
    decided = wins + losses
    streaks = compute_streaks(results)
    return {
        "available": True,
        "gathers": len(results),
        "wins": wins, "losses": losses, "draws": draws,
        "win_rate": round(wins / decided * 100, 1) if decided else 0.0,
        "current_streak": streaks["current_streak"],
        "current_type": streaks["current_type"],
        "longest_win": streaks["longest_win"],
        "longest_loss": streaks["longest_loss"],
    }


async def _fetch_nick_history(db, guid8: str) -> dict:
    """Names this GUID has used, with date ranges (gibhub nick_history)."""
    rows = await db.fetch_all(
        """
        SELECT player_name, MIN(round_date) AS first_seen, MAX(round_date) AS last_seen,
               COUNT(DISTINCT round_id) AS uses
        FROM player_comprehensive_stats
        WHERE player_guid = $1 AND round_number IN (1, 2) AND player_name IS NOT NULL
        GROUP BY player_name
        ORDER BY MAX(round_date) DESC
        LIMIT 25
        """,
        (guid8,),
    )
    if not rows:
        return {"available": False}
    names = [{
        "name": strip_et_colors(r[0]),
        "first_seen": str(r[1]) if r[1] else None,
        "last_seen": str(r[2]) if r[2] else None,
        "uses": _i(r[3]),
    } for r in rows if r and r[0]]
    return {"available": True, "names": names}


async def _fetch_maps(db, guid8: str) -> dict:
    rows = await db.fetch_all(
        """
        SELECT p.map_name,
               COUNT(p.round_id)                                            AS rounds,
               SUM(CASE WHEN r.winner_team IN (1, 2) AND p.team = r.winner_team
                        THEN 1 ELSE 0 END)                                  AS wins,
               SUM(CASE WHEN r.winner_team IN (1, 2) THEN 1 ELSE 0 END)     AS decided,
               SUM(p.kills)                                                 AS kills,
               SUM(p.deaths)                                                AS deaths,
               SUM(p.damage_given)                                          AS dmg,
               SUM(p.time_played_seconds)                                   AS time_played
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1 AND p.round_number IN (1, 2)
        GROUP BY p.map_name
        ORDER BY rounds DESC
        """,
        (guid8,),
    )
    if not rows:
        return {"available": False}
    maps = []
    for r in rows:
        rounds = _i(r[1])
        wins = _i(r[2])
        decided = _i(r[3])
        kills = _i(r[4])
        deaths = _i(r[5])
        tp = _i(r[7])
        name = (r[0] or "").replace("maps/", "").rsplit(".", 1)[0]
        maps.append({
            "map": name,
            "rounds": rounds,
            "wins": wins,
            # win_rate over DECIDED games (exclude draws) — consistent with lifetime
            "win_rate": round(wins / decided * 100, 1) if decided else 0.0,
            "kd": round(kills / deaths, 2) if deaths else float(kills),
            "dpm": round(_i(r[6]) / (tp / 60), 1) if tp else 0.0,
        })
    return {"available": True, "maps": maps}


async def _fetch_recent_matches(db, guid8: str, limit: int = 10) -> dict:
    rows = await db.fetch_all(
        """
        SELECT p.round_id, p.round_date, p.map_name, p.round_number,
               p.kills, p.deaths, p.damage_given, p.time_played_seconds,
               p.team, r.winner_team
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1 AND p.round_number IN (1, 2)
        ORDER BY p.round_date DESC, p.round_id DESC
        LIMIT $2
        """,  # round_id is monotonic with time → correct order on multi-match days
        (guid8, limit),
    )
    if not rows:
        return {"available": False}
    matches = []
    for r in rows:
        tp = _i(r[7])
        kills = _i(r[4])
        deaths = _i(r[5])
        winner = r[9]
        result = None
        if winner in (1, 2):
            result = "W" if r[8] == winner else "L"
        elif winner == 0:
            result = "D"
        matches.append({
            "round_id": _i(r[0]),
            "date": str(r[1]) if r[1] else None,
            "map": (r[2] or "").replace("maps/", "").rsplit(".", 1)[0],
            "round_number": _i(r[3]),
            "kills": kills, "deaths": deaths,
            "kd": round(kills / deaths, 2) if deaths else float(kills),
            "dpm": round(_i(r[6]) / (tp / 60), 1) if tp else 0.0,
            "result": result,
        })
    return {"available": True, "matches": matches}


# ── aim summary + improvements ──────────────────────────────────────────────

async def _fetch_aim_summary(db, guid8: str) -> dict:
    """True-aim lifetime summary + per-weapon + flick + enemy-relative.

    Map-agnostic (origin coords differ per map, so no rose here — the frontend
    map dropdown calls /proximity/player-aim for the spatial rose). Reuses
    ``_circular_yaw_stats`` for wrap-safe yaw aggregation.
    """
    # lifetime circular aggregate over all maps
    circ_row = await db.fetch_one(
        """
        SELECT COUNT(*) AS n,
               AVG(SIN(RADIANS(view_yaw::float8)))  AS sbar,
               AVG(COS(RADIANS(view_yaw::float8)))  AS cbar,
               AVG(view_pitch::float8)              AS pmean,
               COALESCE(STDDEV_POP(view_pitch::float8), 0) AS pstd
        FROM proximity_shot_fired
        WHERE guid_canonical = $1
        """,
        (guid8,),
    )
    n_total = _i(circ_row[0]) if circ_row else 0
    if n_total == 0:
        return {"available": False, "reason": "no true-aim data"}
    circ = _circular_yaw_stats(_f(circ_row[1]), _f(circ_row[2]), n_total)
    circ["pitch_mean_deg"] = round(_f(circ_row[3]), 2)
    circ["pitch_std_deg"] = round(_f(circ_row[4]), 2)

    # per-weapon circular consistency
    wpn_rows = await db.fetch_all(
        """
        SELECT weapon_id, COUNT(*) AS n,
               AVG(SIN(RADIANS(view_yaw::float8))) AS sbar,
               AVG(COS(RADIANS(view_yaw::float8))) AS cbar,
               AVG(view_pitch::float8) AS pmean
        FROM proximity_shot_fired
        WHERE guid_canonical = $1
        GROUP BY weapon_id
        HAVING COUNT(*) >= $2
        ORDER BY n DESC
        """,
        (guid8, _MIN_WEAPON_SHOTS),
    )
    per_weapon = []
    for r in (wpn_rows or []):
        wn = _i(r[1])
        wc = _circular_yaw_stats(_f(r[2]), _f(r[3]), wn)
        per_weapon.append({
            "weapon": weapon_t_name(r[0]),
            "shots": wn,
            # NOT an aim-quality metric: this is the resultant length of ABSOLUTE
            # world yaw across all maps (≈0 for everyone, since a player faces
            # every direction over a career). Kept as a neutral diagnostic only;
            # real aim signals are flick%, enemy-relative error, and pitch spread.
            "yaw_resultant_length": wc["resultant_length"],
            "circular_std_deg": wc["circular_std_deg"],
            "pitch_mean_deg": round(_f(r[4]), 2),
        })

    # flick index — |Δyaw| between consecutive shots fired within a short gap.
    # Static SQL (no interpolation); thresholds + guid are $N-bound. The window
    # tie-breaks on id so tied event_time values give a deterministic LAG order.
    flick_row = await db.fetch_one(
        """
        WITH ordered AS (
            SELECT view_yaw,
                   LAG(view_yaw)   OVER (PARTITION BY round_id ORDER BY event_time, id) AS prev_yaw,
                   LAG(event_time) OVER (PARTITION BY round_id ORDER BY event_time, id) AS prev_t,
                   event_time
            FROM proximity_shot_fired
            WHERE guid_canonical = $1
        ),
        deltas AS (
            SELECT abs( ((((view_yaw - prev_yaw)::numeric + 180.0)
                        - floor(((view_yaw - prev_yaw)::numeric + 180.0)/360.0)*360.0) - 180.0) ) AS d
            FROM ordered
            WHERE prev_yaw IS NOT NULL
              AND (event_time - prev_t) BETWEEN 1 AND $2
        )
        SELECT COUNT(*) AS pairs,
               SUM(CASE WHEN d > $3 THEN 1 ELSE 0 END) AS flicks,
               ROUND(AVG(d)::numeric, 1) AS avg_delta,
               SUM(CASE WHEN d <= $4 THEN 1 ELSE 0 END) AS tight,
               ROUND((percentile_cont(0.5)  WITHIN GROUP (ORDER BY d))::numeric, 1) AS p50,
               ROUND((percentile_cont(0.95) WITHIN GROUP (ORDER BY d))::numeric, 1) AS p95,
               ROUND(MIN(d)::numeric, 1) AS min_d,
               ROUND(MAX(d)::numeric, 1) AS max_d
        FROM deltas
        """,
        (guid8, _FLICK_MAX_DT_MS, _FLICK_DEG, _SPREAD_TIGHT_DEG),
    )
    flick = {"available": False}
    spread = {"available": False}
    if flick_row and _i(flick_row[0]) >= _MIN_FLICK_PAIRS:
        pairs = _i(flick_row[0])
        flicks = _i(flick_row[1])
        tight = _i(flick_row[3])
        flick = {
            "available": True,
            "pairs": pairs,
            "flick_pct": round(flicks / pairs * 100, 1),
            "track_pct": round((pairs - flicks) / pairs * 100, 1),
            "avg_delta_yaw_deg": _f(flick_row[2]),
        }
        # Spread control: how tightly consecutive quick shots cluster in aim
        # angle. Lower = better control. Derived from the same Δyaw pairs.
        spread = {
            "available": True,
            "control_pct": round(tight / pairs * 100, 1),   # % within ±tight°
            "min_spread_deg": _f(flick_row[6]),             # tightest consecutive move
            "median_spread_deg": _f(flick_row[4]),          # typical
            "max_spread_deg": _f(flick_row[7]),             # widest swing
            "p95_spread_deg": _f(flick_row[5]),             # near-worst (robust)
        }

    burst = await _fetch_burst_stats(db, guid8)
    enemy_rel = await _fetch_enemy_relative(db, guid8)

    return {
        "available": True,
        "lifetime": circ,
        "per_weapon": per_weapon,
        "flick": flick,
        "spread": spread,
        "burst": burst,
        "enemy_relative": enemy_rel,
    }


async def _fetch_burst_stats(db, guid8: str) -> dict:
    """Burst-fire profile: sessionize each round's shots into bursts (gaps
    > _BURST_GAP_MS start a new burst) and summarize. Static SQL; $N-bound."""
    row = await db.fetch_one(
        """
        WITH ordered AS (
            SELECT round_id, id, event_time,
                   event_time - LAG(event_time)
                       OVER (PARTITION BY round_id ORDER BY event_time, id) AS gap
            FROM proximity_shot_fired
            WHERE guid_canonical = $1
        ),
        marked AS (
            SELECT round_id, id, event_time,
                   CASE WHEN gap IS NULL OR gap > $2 THEN 1 ELSE 0 END AS new_burst
            FROM ordered
        ),
        grouped AS (
            -- burst_no must accumulate in the SAME (event_time, id) order the
            -- gap/new_burst flags were computed in, else tied timestamps split
            -- or merge bursts non-deterministically.
            SELECT round_id,
                   SUM(new_burst) OVER (PARTITION BY round_id ORDER BY event_time, id
                                        ROWS UNBOUNDED PRECEDING) AS burst_no
            FROM marked
        ),
        sizes AS (
            SELECT round_id, burst_no, COUNT(*) AS shots
            FROM grouped GROUP BY round_id, burst_no
        )
        SELECT COUNT(*) AS bursts,
               SUM(shots) AS total_shots,
               ROUND(AVG(shots)::numeric, 2) AS avg_burst,
               MAX(shots) AS max_burst,
               SUM(CASE WHEN shots = 1 THEN 1 ELSE 0 END) AS taps,
               SUM(CASE WHEN shots >= 2 THEN 1 ELSE 0 END) AS multi_bursts
        FROM sizes
        """,
        (guid8, _BURST_GAP_MS),
    )
    if not row or _i(row[1]) < _MIN_BURST_SHOTS:
        return {"available": False}
    bursts = _i(row[0])
    return {
        "available": True,
        "bursts": bursts,
        "avg_burst_len": _f(row[2]),
        "max_burst_len": _i(row[3]),
        "tap_pct": round(_i(row[4]) / bursts * 100, 1) if bursts else 0.0,
        "burst_pct": round(_i(row[5]) / bursts * 100, 1) if bursts else 0.0,
    }


async def _fetch_enemy_relative(db, guid8: str) -> dict:
    """EXPERIMENTAL crosshair-placement error vs the enemy in an engagement.

    Approximate: joins each shot to a combat_engagement the player was an
    attacker in (same round, shot time inside the engagement window) and uses
    the engagement's end position as the enemy reference. The error is the
    wrap-safe angle between the player's view_yaw and the bearing to the enemy.
    Heavily guarded — returns ``available: False`` on any failure or low sample
    rather than emitting an unreliable number.
    """
    try:
        # Static SQL (no interpolation); guid is $1-bound. The crosshair-error
        # is the wrap-safe angle between view_yaw and the bearing to the enemy.
        # combat_engagement windows overlap, so one shot can fall in several;
        # DISTINCT ON keeps ONE engagement per shot (tightest window = most
        # specific enemy reference), preventing the same shot from being counted
        # up to 5x with conflicting enemy positions (inflated sample + biased avg).
        row = await db.fetch_one(
            """
            SELECT COUNT(*) AS n,
                   ROUND(AVG(err)::numeric, 1) AS avg_err,
                   ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY err))::numeric, 1) AS median_err
            FROM (
                SELECT DISTINCT ON (s.id)
                    abs( (((s.view_yaw - degrees(atan2(e.end_y - s.origin_y, e.end_x - s.origin_x)))::numeric + 180.0)
                        - floor(((s.view_yaw - degrees(atan2(e.end_y - s.origin_y, e.end_x - s.origin_x)))::numeric + 180.0)/360.0)*360.0 - 180.0) ) AS err
                FROM proximity_shot_fired s
                JOIN combat_engagement e
                  ON e.round_id = s.round_id
                 AND e.map_name = s.map_name
                 AND s.event_time BETWEEN e.start_time_ms AND e.end_time_ms
                 AND (e.end_x <> s.origin_x OR e.end_y <> s.origin_y)
                 AND EXISTS (
                     SELECT 1 FROM jsonb_array_elements(COALESCE(e.attackers, '[]'::jsonb)) a
                     WHERE LEFT(a->>'guid', 8) = $1
                 )
                WHERE s.guid_canonical = $1
                ORDER BY s.id, (e.end_time_ms - e.start_time_ms) ASC
            ) q
            """,
            (guid8,),
        )
    except Exception:
        logger.warning("enemy-relative aim fetch failed for %s", guid8, exc_info=True)
        return {"available": False, "reason": "query failed"}
    if not row or _i(row[0]) < _MIN_ENEMY_REL:
        return {"available": False, "reason": "insufficient matched shots"}
    return {
        "available": True,
        "approximate": True,
        "matched_shots": _i(row[0]),
        "avg_error_deg": _f(row[1]),
        "median_error_deg": _f(row[2]),
    }


async def _fetch_combat_timing(db, guid8: str) -> dict:
    """Leetify-style combat timing — independent of shot_fired (uses
    combat_engagement ~48% coverage + proximity_reaction_metric).

    - Time-to-Kill: median engagement duration (first contact → kill) on the
      player's kills. (Leetify Time-to-Damage is NOT computable: our
      combat_engagement.start_time_ms IS the first-hit time, so time-to-first-hit
      is ~0 — there's no 'enemy spotted' signal, so we omit TTD.)
    - Return-fire reaction: median ms from being hit to firing back, with the
      populated-coverage % shown (the metric is ~50% populated, so be honest).
    All stats use the MEDIAN to drop outliers (Leetify practice).
    """
    row = await db.fetch_one(
        """
        WITH ttk AS (
            SELECT (end_time_ms - start_time_ms) AS v
            FROM combat_engagement
            WHERE outcome = 'killed' AND LEFT(killer_guid, 8) = $1
              AND end_time_ms >= start_time_ms
        ),
        rf AS (
            SELECT return_fire_ms FROM proximity_reaction_metric
            WHERE LEFT(target_guid, 8) = $1
        )
        SELECT
            (SELECT COUNT(*) FROM ttk) AS ttk_n,
            (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY v)) FROM ttk) AS ttk_median,
            (SELECT COUNT(*) FILTER (WHERE return_fire_ms IS NOT NULL) FROM rf) AS rf_n,
            (SELECT COUNT(*) FROM rf) AS rf_total,
            (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY return_fire_ms))
             FROM rf WHERE return_fire_ms IS NOT NULL) AS rf_median
        """,
        (guid8,),
    )
    if not row:
        return {"available": False}
    ttk_n = _i(row[0])
    rf_n = _i(row[2])
    rf_total = _i(row[3])
    if ttk_n < 10 and rf_n < 10:
        return {"available": False, "reason": "insufficient combat data"}
    out: dict = {"available": True}
    if ttk_n >= 10:
        out["time_to_kill"] = {"median_ms": _i(row[1]), "kills": ttk_n}
    if rf_n >= 10:
        out["return_fire"] = {
            "median_ms": _i(row[4]),
            "samples": rf_n,
            "coverage_pct": round(rf_n / rf_total * 100, 1) if rf_total else 0.0,
        }
    return out


async def _resolve_guid32(db, guid8: str) -> str | None:
    """Best-effort 32-char proximity GUID for RivalriesService (kill_outcome key)."""
    row = await db.fetch_one(
        "SELECT MAX(killer_guid) FROM proximity_kill_outcome WHERE killer_guid_canonical = $1",
        (guid8,),
    )
    if row and row[0]:
        return row[0]
    row = await db.fetch_one(
        "SELECT MAX(victim_guid) FROM proximity_kill_outcome WHERE LEFT(victim_guid, 8) = $1",
        (guid8,),
    )
    return row[0] if row and row[0] else None


# ── endpoint ────────────────────────────────────────────────────────────────

@router.get("/players/{identifier}/profile")
async def get_player_profile(
    identifier: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Composite gibhub.gg-parity player profile in one parallel round-trip."""
    guid8 = await resolve_player_guid(db, identifier)
    if not guid8:
        raise HTTPException(status_code=404, detail="Player not found")

    guid32 = await _resolve_guid32(db, guid8)

    # Lifetime first (advanced bait_score needs its death total); the rest fan out.
    lifetime = await _fetch_lifetime(db, guid8)
    if not lifetime.get("available"):
        raise HTTPException(status_code=404, detail="Player not found")
    deaths = _i(lifetime.get("deaths"))

    # Bound per-request DB concurrency: each section may run several queries on
    # the shared asyncpg pool, so 11 unbounded sections × N concurrent requests
    # could saturate the pool and starve other endpoints. Cap at 5 in-flight
    # sections (pattern from records_awards.py).
    sem = asyncio.Semaphore(5)

    async def _guard(coro):
        async with sem:
            return await coro

    (identity, streaks, advanced, movement, weapons, hit_regions,
     relationships, skill, maps, recent, aim,
     gather_summary, nick_history, combat_timing) = await asyncio.gather(
        _guard(_fetch_identity(db, guid8, identifier)),
        _guard(_fetch_streaks(db, guid8)),
        _guard(_fetch_advanced(db, guid8, deaths)),
        _guard(_fetch_movement(db, guid8)),
        _guard(_fetch_weapons(db, guid8)),
        _guard(_fetch_hit_regions(db, guid8)),
        _guard(_fetch_relationships(db, guid8, guid32)),
        _guard(_fetch_skill(db, guid8)),
        _guard(_fetch_maps(db, guid8)),
        _guard(_fetch_recent_matches(db, guid8)),
        _guard(_fetch_aim_summary(db, guid8)),
        _guard(_fetch_gather_summary(db, guid8)),
        _guard(_fetch_nick_history(db, guid8)),
        _guard(_fetch_combat_timing(db, guid8)),
        return_exceptions=True,
    )

    def _ok(section, label):
        if isinstance(section, Exception):
            logger.warning("profile section %s failed for %s", label, guid8, exc_info=section)
            return {"available": False, "reason": "error"}
        return section

    return {
        "guid": guid8,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": _ok(identity, "identity"),
        "lifetime": lifetime,
        "streaks": _ok(streaks, "streaks"),
        "advanced": _ok(advanced, "advanced"),
        "movement": _ok(movement, "movement"),
        "weapons": _ok(weapons, "weapons"),
        "hit_regions": _ok(hit_regions, "hit_regions"),
        "relationships": _ok(relationships, "relationships"),
        "skill": _ok(skill, "skill"),
        "maps": _ok(maps, "maps"),
        "recent_matches": _ok(recent, "recent_matches"),
        "aim": _ok(aim, "aim"),
        "gather_summary": _ok(gather_summary, "gather_summary"),
        "nick_history": _ok(nick_history, "nick_history"),
        "combat_timing": _ok(combat_timing, "combat_timing"),
    }
