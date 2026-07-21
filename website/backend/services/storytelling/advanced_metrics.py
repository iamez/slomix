"""StorytellingService mixin: advanced_metrics methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

import asyncio
import json as _json
import math
from collections import defaultdict
from typing import TYPE_CHECKING

from .base import (
    DEATH_TRADE_WINDOW_MS,
    LURKER_MIN_DURATION_MS,
    TRADE_KILL_DELTA_MS,
    _compute_locks,
    _to_date,
    date,
    strip_et_colors,
)

if TYPE_CHECKING:
    from website.backend.services.session_scope import GamingSessionScope

# Lurker-profile tuning (module constants so the sync worker + the async wrapper
# agree on them).
_LURKER_SOLO_RADIUS = 500     # units from nearest teammate = "solo"
_LURKER_DOWNSAMPLE_MS = 1000  # 1s sampling for performance


def _compute_lurker_solo(track_rows: list) -> tuple[dict, dict]:
    """CPU-heavy solo-time computation — runs in a worker thread.

    Pure function over pre-fetched ``player_track`` rows
    (player_guid, player_name, team, round_start_unix, spawn_time_ms,
    death_time_ms, duration_ms, path). Returns ``(player_stats, name_by_guid)``.

    Offloaded via ``asyncio.to_thread`` so its O(samples × teammates × points)
    triple loop never blocks the asyncio event loop (it was a ~13s freeze of all
    requests). Behaviour is identical to the previous inline implementation.
    The name map is built here from ``player_name`` keyed by the 8-char prefix —
    the same key as ``player_stats`` — so names always resolve (the old
    canonical-keyed map missed 32-char bot guids).
    """
    SOLO_RADIUS = _LURKER_SOLO_RADIUS
    DOWNSAMPLE_MS = _LURKER_DOWNSAMPLE_MS

    round_tracks: dict[int, list] = defaultdict(list)
    name_by_guid: dict[str, str] = {}
    for r in track_rows:
        rsu = int(r[3] or 0)
        path_data = r[7]
        if not path_data:
            continue
        if isinstance(path_data, str):
            try:
                path_data = _json.loads(path_data)
            except (ValueError, TypeError):
                # Unparseable JSON (legacy / corrupted rows) — skip the track.
                continue
        points = []
        last_t = -DOWNSAMPLE_MS
        for p in path_data:
            t = int(p.get("time", 0))
            if t - last_t >= DOWNSAMPLE_MS:
                points.append((t, float(p.get("x", 0)), float(p.get("y", 0))))
                last_t = t
        if not points:
            continue
        gshort = (r[0] or "")[:8]
        if r[1] and gshort not in name_by_guid:
            name_by_guid[gshort] = strip_et_colors(r[1])
        round_tracks[rsu].append({
            "guid": r[0], "name": r[1], "team": r[2],
            "duration_ms": int(r[6] or 0), "points": points,
        })

    player_stats: dict[str, dict] = defaultdict(lambda: {
        "total_samples": 0, "solo_samples": 0, "alive_ms": 0, "tracks": 0,
    })
    for tracks in round_tracks.values():
        for track in tracks:
            guid_short = track["guid"][:8]
            team = track["team"]
            teammates = [
                t for t in tracks
                if t["team"] == team and t["guid"][:8] != guid_short
            ]
            if not teammates:
                # Solo player (no teammates this life) — all samples are solo.
                player_stats[guid_short]["solo_samples"] += len(track["points"])
                player_stats[guid_short]["total_samples"] += len(track["points"])
                player_stats[guid_short]["alive_ms"] += track["duration_ms"]
                player_stats[guid_short]["tracks"] += 1
                continue

            # Pre-bucket each teammate's points by 1s key once (points are
            # time-sorted). The ±2s window for a sample at t_ms only touches
            # buckets [(t_ms-2s)//1s .. (t_ms+2s)//1s], so we probe ~5 buckets
            # instead of scanning the whole track — byte-identical result, far
            # fewer comparisons. WINDOW = DOWNSAMPLE_MS*2.
            window = DOWNSAMPLE_MS * 2
            tm_bucket_list = []
            for tm in teammates:
                buckets: dict[int, list] = defaultdict(list)
                for tt, tx, ty in tm["points"]:
                    buckets[tt // DOWNSAMPLE_MS].append((tt, tx, ty))
                tm_bucket_list.append(buckets)

            solo_count = 0
            for t_ms, px, py in track["points"]:
                lo = (t_ms - window) // DOWNSAMPLE_MS
                hi = (t_ms + window) // DOWNSAMPLE_MS
                min_dist = float("inf")
                for buckets in tm_bucket_list:
                    best_d = float("inf")
                    for b in range(lo, hi + 1):
                        for tt, tx, ty in buckets.get(b, ()):
                            if abs(tt - t_ms) <= window:
                                # hypot: numerically robust (CodeQL).
                                d = math.hypot(px - tx, py - ty)
                                if d < best_d:
                                    best_d = d
                    if best_d < min_dist:
                        min_dist = best_d
                if min_dist > SOLO_RADIUS:
                    solo_count += 1

            player_stats[guid_short]["total_samples"] += len(track["points"])
            player_stats[guid_short]["solo_samples"] += solo_count
            player_stats[guid_short]["alive_ms"] += track["duration_ms"]
            player_stats[guid_short]["tracks"] += 1

    return player_stats, name_by_guid


class _AdvancedMetricsMixin:
    """Advanced Metrics methods for StorytellingService."""

    async def _fallback_canonical_names(self, sd: date) -> dict[str, str]:
        """Names keyed by 8-char canonical guid, sourced from combat_engagement.

        ``compute_space_created``/``compute_enabler`` resolve names from
        ``storytelling_kill_impact``, but that table is populated lazily (first
        KIS request for the session). Until then every player rendered as
        ``#GUID8``. This fallback uses the same always-present source as
        ``compute_gravity`` so names resolve regardless of KIS state.

        Covers both sides of an engagement: a player who only ever appears as
        a killer (never engaged as a target) still resolves.
        """
        rows = await self.db.fetch_all("""
            SELECT LEFT(target_guid, 8) AS g8, MAX(target_name) AS nm
            FROM combat_engagement
            WHERE session_date = $1 AND target_guid IS NOT NULL
            GROUP BY LEFT(target_guid, 8)
            UNION ALL
            SELECT LEFT(killer_guid, 8) AS g8, MAX(killer_name) AS nm
            FROM combat_engagement
            WHERE session_date = $1
              AND killer_guid IS NOT NULL AND killer_name IS NOT NULL
            GROUP BY LEFT(killer_guid, 8)
        """, (sd,))
        names: dict[str, str] = {}
        for r in (rows or []):
            if r[0] and r[0] not in names:
                names[r[0]] = strip_et_colors(r[1] or r[0])
        return names

    async def compute_gravity(self, session_date: str | date) -> dict:
        """Compute Gravity Score: how much enemy attention each player attracts.

        Higher gravity = more enemies focused on you = more space for teammates.
        Formula: total_attention_ms / alive_time_ms (normalized per minute alive).
        """
        sd = _to_date(session_date)

        rows = await self.db.fetch_all("""
            SELECT target_guid, MAX(target_name) AS name,
                   COUNT(*) AS engagements,
                   AVG(num_attackers) AS avg_attackers,
                   SUM(num_attackers * duration_ms) AS total_attention_ms,
                   SUM(duration_ms) AS total_engaged_ms
            FROM combat_engagement
            WHERE session_date = $1
            GROUP BY target_guid
            HAVING COUNT(*) >= 5
            ORDER BY SUM(num_attackers * duration_ms) DESC
        """, (sd,))

        alive_rows = await self.db.fetch_all("""
            SELECT player_guid,
                   SUM(GREATEST(duration_ms, 1)) AS total_alive_ms,
                   COUNT(*) AS tracks
            FROM player_track
            WHERE session_date = $1 AND duration_ms > 0
            GROUP BY player_guid
        """, (sd,))
        alive_map = {r[0]: int(r[1] or 1) for r in (alive_rows or [])}

        players = []
        for r in (rows or []):
            guid = r[0]
            total_attention = int(r[4] or 0)
            alive_ms = alive_map.get(guid)
            if not alive_ms:
                continue  # Skip players without track data
            # Gravity = attention per minute alive (higher = more hunted)
            gravity = (total_attention / max(alive_ms, 1)) * 60000

            players.append({
                "guid": guid,
                "guid_short": guid[:8],
                "name": strip_et_colors(r[1] or guid[:8]),
                "gravity_score": round(gravity, 1),
                "engagements": int(r[2]),
                "avg_attackers": round(float(r[3] or 1), 2),
                "total_attention_ms": total_attention,
                "total_engaged_ms": int(r[5] or 0),
                "alive_ms": alive_ms,
            })

        players.sort(key=lambda p: p["gravity_score"], reverse=True)

        return {
            "status": "ok",
            "session_date": str(sd),
            "metric": "gravity",
            "description": "Enemy attention attracted per minute alive. Higher = more space created for teammates.",
            "players": players,
        }

    async def compute_space_created(self, session_date: str | date) -> dict:
        """Compute Space Created: what happens after your death?

        Productive death = teammate gets a kill within 10s after you die.
        Formula: productive_deaths / total_deaths
        """
        sd = _to_date(session_date)
        WINDOW_MS = DEATH_TRADE_WINDOW_MS

        # All kills grouped by round for temporal analysis.
        # round_start_unix > 0 filter: orphaned rows with NULL/0 rsu would
        # collapse into bucket 0 and mix unrelated kills into the same
        # temporal window, producing spurious teammate-trade matches.
        kill_rows = await self.db.fetch_all("""
            SELECT victim_guid, killer_guid, kill_time, round_number, round_start_unix
            FROM proximity_kill_outcome
            WHERE session_date = $1
              AND outcome IN ('gibbed', 'tapped_out')
              AND round_start_unix IS NOT NULL
              AND round_start_unix > 0
            ORDER BY round_start_unix, kill_time
        """, (sd,))

        if not kill_rows:
            return {"status": "ok", "session_date": str(sd), "players": []}

        # Build team mapping from storytelling_kill_impact (has guid_canonical)
        team_rows = await self.db.fetch_all("""
            SELECT DISTINCT killer_guid, killer_guid_canonical
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
        """, (sd,))
        guid_to_short = {r[0]: r[1] for r in (team_rows or [])}

        # Group kills by (round_start_unix) for same-round temporal queries
        from collections import defaultdict
        round_kills: dict[int, list] = defaultdict(list)
        for r in kill_rows:
            rsu = int(r[4] or 0)
            round_kills[rsu].append({
                "victim": r[0], "killer": r[1],
                "time": int(r[2] or 0), "round": r[3],
            })

        # Build player groups to know who is teammate
        groups = await self._build_player_groups(sd)
        g2g = groups["guid_to_group"] if groups else {}

        # For each death: check if teammates got kills in next 10s
        player_stats: dict[str, dict] = defaultdict(lambda: {
            "deaths": 0, "productive": 0, "teammate_kills_after": 0,
        })

        for rsu, kills in round_kills.items():
            for i, death in enumerate(kills):
                victim_short = guid_to_short.get(death["victim"], death["victim"][:8])
                victim_group = g2g.get(victim_short)
                if not victim_group:
                    continue

                player_stats[victim_short]["deaths"] += 1

                # Look for teammate kills in next WINDOW_MS
                teammate_kills = 0
                for j in range(i + 1, len(kills)):
                    k = kills[j]
                    dt = k["time"] - death["time"]
                    if dt > WINDOW_MS:
                        break
                    if dt < 0:
                        continue
                    killer_short = guid_to_short.get(k["killer"], k["killer"][:8])
                    if g2g.get(killer_short) == victim_group and killer_short != victim_short:
                        teammate_kills += 1

                if teammate_kills > 0:
                    player_stats[victim_short]["productive"] += 1
                    player_stats[victim_short]["teammate_kills_after"] += teammate_kills

        # Resolve names (KIS table first, combat_engagement fallback — KIS is
        # lazily populated, see _fallback_canonical_names)
        name_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, MAX(killer_name)
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        """, (sd,))
        name_map = await self._fallback_canonical_names(sd)
        name_map.update({r[0]: strip_et_colors(r[1] or r[0]) for r in (name_rows or [])})

        players = []
        for guid, stats in player_stats.items():
            deaths = max(stats["deaths"], 1)
            players.append({
                "guid_short": guid,
                "name": name_map.get(guid, f"#{guid}"),
                "space_score": round(stats["productive"] / deaths, 2),
                "productive_deaths": stats["productive"],
                "wasted_deaths": stats["deaths"] - stats["productive"],
                "total_deaths": stats["deaths"],
                "teammate_kills_after": stats["teammate_kills_after"],
            })

        players.sort(key=lambda p: p["space_score"], reverse=True)

        return {
            "status": "ok",
            "session_date": str(sd),
            "metric": "space_created",
            "description": "Fraction of deaths where teammates capitalized within 10s. Higher = more productive deaths.",
            "window_ms": WINDOW_MS,
            "players": players,
        }

    async def compute_enabler(self, session_date: str | date) -> dict:
        """Compute Enabler Score: teammate kills near your engagements.

        For each player's engagements, count teammate kills within ±5s
        and ≤500 game units. Includes crossfire assists and trade assists.
        """
        sd = _to_date(session_date)
        TIME_WINDOW_MS = TRADE_KILL_DELTA_MS
        DISTANCE_THRESHOLD = 500

        # round_start_unix > 0 filter: orphaned rows with NULL/0 rsu would
        # collapse into bucket 0 and mix unrelated rounds' temporal windows
        # (same pattern as compute_space_created fix in PR #210).
        eng_rows = await self.db.fetch_all("""
            SELECT target_guid, killer_guid, end_x, end_y, end_time_ms,
                   round_start_unix, num_attackers
            FROM combat_engagement
            WHERE session_date = $1
              AND outcome = 'killed'
              AND end_x IS NOT NULL AND end_y IS NOT NULL
              AND round_start_unix IS NOT NULL
              AND round_start_unix > 0
            ORDER BY round_start_unix, end_time_ms
        """, (sd,))

        if not eng_rows:
            return {"status": "ok", "session_date": str(sd), "players": []}

        # Build team mapping
        groups = await self._build_player_groups(sd)
        g2g = groups["guid_to_group"] if groups else {}

        # guid_canonical lookup
        team_rows = await self.db.fetch_all("""
            SELECT DISTINCT killer_guid, killer_guid_canonical
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
        """, (sd,))
        g2short = {r[0]: r[1] for r in (team_rows or [])}

        import math

        # Group kills by round_start_unix
        from collections import defaultdict
        round_kills: dict[int, list] = defaultdict(list)
        for r in eng_rows:
            rsu = int(r[5] or 0)
            round_kills[rsu].append({
                "victim": r[0], "killer": r[1],
                "x": float(r[2] or 0), "y": float(r[3] or 0),
                "time": int(r[4] or 0), "attackers": int(r[6] or 1),
            })

        # For each kill by player X: count same-team kills nearby in time+space
        player_stats: dict[str, dict] = defaultdict(lambda: {
            "kills": 0, "enabled_kills": 0,
            "crossfire_assists": 0, "trade_assists": 0,
        })

        for rsu, kills in round_kills.items():
            for i, kill_a in enumerate(kills):
                if not kill_a["killer"]:
                    continue
                killer_short = g2short.get(kill_a["killer"], kill_a["killer"][:8])
                killer_group = g2g.get(killer_short)
                if not killer_group:
                    continue
                player_stats[killer_short]["kills"] += 1

                # Look for teammate kills near this kill (time + space)
                # Kills sorted by time — scan outward, break when too far
                for j in range(max(0, i - 30), min(len(kills), i + 30)):
                    if i == j:
                        continue
                    kill_b = kills[j]
                    dt = kill_b["time"] - kill_a["time"]
                    if dt > TIME_WINDOW_MS:
                        break  # Sorted: all further kills are even later
                    if dt < -TIME_WINDOW_MS:
                        continue  # Earlier kill, keep scanning forward
                    if not kill_b["killer"]:
                        continue
                    other_short = g2short.get(kill_b["killer"], kill_b["killer"][:8])
                    if g2g.get(other_short) != killer_group or other_short == killer_short:
                        continue
                    dx = kill_a["x"] - kill_b["x"]
                    dy = kill_a["y"] - kill_b["y"]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= DISTANCE_THRESHOLD:
                        player_stats[killer_short]["enabled_kills"] += 1
                        break  # Count each kill_a as enabling once

        # Add crossfire + trade counts from existing tables
        xf_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, COUNT(*)
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND is_crossfire = true AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        """, (sd,))
        for r in (xf_rows or []):
            if r[0] in player_stats:
                player_stats[r[0]]["crossfire_assists"] = int(r[1] or 0)

        tr_rows = await self.db.fetch_all("""
            SELECT trader_guid_canonical, COUNT(*)
            FROM proximity_lua_trade_kill
            WHERE session_date = $1 AND trader_guid_canonical IS NOT NULL
            GROUP BY trader_guid_canonical
        """, (sd,))
        for r in (tr_rows or []):
            if r[0] in player_stats:
                player_stats[r[0]]["trade_assists"] = int(r[1] or 0)

        # Resolve names + compute score (KIS table first, combat_engagement
        # fallback — KIS is lazily populated, see _fallback_canonical_names)
        name_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, MAX(killer_name)
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        """, (sd,))
        name_map = await self._fallback_canonical_names(sd)
        name_map.update({r[0]: strip_et_colors(r[1] or r[0]) for r in (name_rows or [])})

        # Alive time for normalization
        alive_rows = await self.db.fetch_all("""
            SELECT player_guid, SUM(GREATEST(duration_ms, 1)) AS alive_ms
            FROM player_track WHERE session_date = $1 AND duration_ms > 0
            GROUP BY player_guid
        """, (sd,))
        alive_map = {r[0][:8]: int(r[1] or 1) for r in (alive_rows or [])}

        players = []
        for guid, stats in player_stats.items():
            # Skip players with no track data instead of falling back to a
            # 60_000 ms (1-minute) baseline — the previous fallback inflated
            # enabler_score for players whose tracks weren't logged (a bot,
            # an early-leaver, or a missing-data session). compute_gravity()
            # uses the same skip pattern; mismatch caused per-metric players
            # to be ranked against each other on different denominators.
            alive_ms = alive_map.get(guid)
            if not alive_ms:
                continue
            alive_min = alive_ms / 60000
            # crossfire_assists are a spatial subset of enabled_kills — don't double-count
            total_assists = stats["enabled_kills"] + stats["trade_assists"]
            players.append({
                "guid_short": guid,
                "name": name_map.get(guid, f"#{guid}"),
                "enabler_score": round(total_assists / max(alive_min, 0.1), 1),
                "enabled_kills": stats["enabled_kills"],
                "crossfire_assists": stats["crossfire_assists"],
                "trade_assists": stats["trade_assists"],
                "total_assists": total_assists,
                "own_kills": stats["kills"],
            })

        players.sort(key=lambda p: p["enabler_score"], reverse=True)

        return {
            "status": "ok",
            "session_date": str(sd),
            "metric": "enabler",
            "description": "Teammate kills enabled per minute alive (nearby kills ±5s ≤500u + crossfire + trades).",
            "time_window_ms": TIME_WINDOW_MS,
            "distance_threshold": DISTANCE_THRESHOLD,
            "players": players,
        }

    async def compute_lurker_profile(self, session_date: str | date) -> dict:
        """Compute Lurker Profile: solo time away from teammates.

        Uses player_track.path (200ms samples, spawn-to-death) to calculate
        how much time each player spends away from teammates.
        Downsampled to 1s intervals for performance (~20k points vs 100k).
        """
        sd = _to_date(session_date)
        SOLO_RADIUS = _LURKER_SOLO_RADIUS
        DOWNSAMPLE_MS = _LURKER_DOWNSAMPLE_MS

        # round_start_unix > 0 filter: orphaned rows with NULL/0 rsu would
        # collapse into bucket 0 and mix unrelated rounds' tracks together
        # (same pattern as compute_space_created fix in PR #210).
        track_rows = await self.db.fetch_all("""
            SELECT player_guid, player_name, team, round_start_unix,
                   spawn_time_ms, death_time_ms, duration_ms, path
            FROM player_track
            WHERE session_date = $1
              AND duration_ms > $2
              AND path IS NOT NULL
              AND round_start_unix IS NOT NULL
              AND round_start_unix > 0
            ORDER BY round_start_unix, player_guid
        """, (sd, LURKER_MIN_DURATION_MS))

        if not track_rows:
            return {"status": "ok", "session_date": str(sd), "players": []}

        # The solo-time math is a heavy pure-Python triple loop. Offload it to a
        # worker thread so it can't block the event loop (~13s freeze), and hold
        # a per-session lock so concurrent cold requests don't thrash the CPU.
        # Names are resolved inside the worker from player_track.player_name,
        # keyed by the same 8-char prefix as player_stats (no separate query).
        async with _compute_locks.get(f"lurker:{sd}"):
            player_stats, name_by_guid = await asyncio.to_thread(
                _compute_lurker_solo, track_rows,
            )

        players = []
        for guid, stats in player_stats.items():
            total = max(stats["total_samples"], 1)
            solo_pct = (stats["solo_samples"] / total) * 100
            players.append({
                "guid_short": guid,
                "name": name_by_guid.get(guid, f"#{guid}"),
                "solo_pct": round(solo_pct, 1),
                "solo_samples": stats["solo_samples"],
                "total_samples": stats["total_samples"],
                "alive_ms": stats["alive_ms"],
                "tracks": stats["tracks"],
                "solo_time_est_s": round(stats["solo_samples"] * DOWNSAMPLE_MS / 1000, 0),
            })

        players.sort(key=lambda p: p["solo_pct"], reverse=True)

        # Coverage: the worker silently skips tracks with unparseable/empty
        # paths — surface how much data actually fed the metric so the UI can
        # show confidence (0 skips today per E2E verification 2026-06-10).
        tracks_used = sum(s["tracks"] for s in player_stats.values())
        return {
            "status": "ok",
            "session_date": str(sd),
            "metric": "lurker_profile",
            "description": f"Percentage of alive time spent >={SOLO_RADIUS}u from nearest teammate.",
            "solo_radius": SOLO_RADIUS,
            "downsample_ms": DOWNSAMPLE_MS,
            "coverage": {
                "tracks_fetched": len(track_rows),
                "tracks_used": tracks_used,
                "tracks_skipped": len(track_rows) - tracks_used,
            },
            "players": players,
        }

    async def compute_useless_defense_deaths(
        self,
        scope: GamingSessionScope,
        min_killer_health: int = 80,
        min_reinf_seconds: int = 25,
    ) -> dict:
        """Compute "useless deaths in defense" — panic deaths the team can't afford.

        A defending player who dies while (a) the killer was barely scratched
        (killer_health >= min_killer_health) and (b) their own next spawn is
        far away (victim_reinf >= min_reinf_seconds) handed the attackers free
        time on the objective without trading damage. This is the metric the
        Discord community asked for on 2026-05-07 (olympus + superboyy ask:
        "kolkrat si na relativno full mrtu v obrambi 25+ sekund").

        Defending team is detected via ``rounds.defender_team`` (1=axis, 2=allies)
        joined to the victim's PCS row for the same round. Rounds with
        ``defender_team = 0`` (unknown) contribute no candidates.

        Returns per-player ranking with absolute count, total defensive deaths,
        and rate (rate = useless / total_def_deaths). Rate is the stable signal:
        a 1/2 player is worse than a 5/50 player even though absolute count is
        lower.

        This relies on the storytelling_kill_impact pre-compute (which carries
        ``victim_reinf`` and ``killer_health``); the caller is expected to have
        triggered ``compute_session_kis_for_gsid(scope.gaming_session_id)``
        (the gsid-native KIS entrypoint this metric now scopes by) already if
        it wants fresh KIS coverage. We do NOT trigger it here — keeps this
        metric independent of the KIS code path.
        """
        sd_str = scope.dates[0]

        rows = await self.db.fetch_all(
            """
            WITH defender_pcs AS (
                -- Scoped by gaming_session_id (deep SS-C): PCS.round_id ->
                -- rounds is reliable, so the joined round's gsid is the
                -- precise, multi-date-safe session filter. round_start_unix
                -- still joins us back to a specific round so two sessions on
                -- the same calendar date with the same map+R1 don't collide.
                SELECT pcs.round_id, pcs.player_guid, pcs.team, r.defender_team,
                       r.round_date::date AS round_date_d,
                       r.map_name, r.round_number, r.round_start_unix
                FROM player_comprehensive_stats pcs
                JOIN rounds r ON r.id = pcs.round_id
                WHERE r.gaming_session_id = $1
                  AND r.defender_team IN (1, 2)
                  AND pcs.team = r.defender_team
            ),
            defense_deaths AS (
                -- GROUP BY victim_guid only; MAX(victim_name) avoids
                -- splitting the same player into multiple rows when
                -- their displayed name changes mid-session (color codes,
                -- clan tag swaps). storytelling_kill_impact carries gsid
                -- (SS-B migration 063), so scope by it too.
                SELECT ski.victim_guid,
                       MAX(ski.victim_name) AS victim_name,
                       COUNT(*) FILTER (
                           WHERE ski.victim_reinf >= $2
                             AND ski.killer_health >= $3
                       ) AS useless_deaths,
                       COUNT(*) AS total_def_deaths
                FROM storytelling_kill_impact ski
                JOIN defender_pcs dp
                  ON dp.round_date_d = ski.session_date
                 AND dp.round_start_unix = ski.round_start_unix
                 -- PCS stores 8-char short_guid; storytelling_kill_impact
                 -- stores the full 32-char Lua GUID. Match on prefix.
                 AND dp.player_guid = LEFT(ski.victim_guid, 8)
                WHERE ski.gaming_session_id = $1
                GROUP BY ski.victim_guid
            )
            SELECT victim_guid, victim_name, useless_deaths, total_def_deaths
            FROM defense_deaths
            WHERE useless_deaths > 0
            -- Tie-break favors stable players (more total def deaths) over
            -- single-incident outliers when the absolute useless count ties.
            -- A player with 3/100 ranks above 3/5 — the latter is small
            -- sample. Previously this used ASC and inverted the intent.
            ORDER BY useless_deaths DESC, total_def_deaths DESC
            """,
            (scope.gaming_session_id, min_reinf_seconds, min_killer_health),
        )

        players = []
        for r in (rows or []):
            guid = r[0]
            useless = int(r[2] or 0)
            total = int(r[3] or 0)
            rate = (useless / total) if total > 0 else 0.0
            players.append({
                "guid": guid,
                "guid_short": guid[:8],
                "name": strip_et_colors(r[1] or guid[:8]),
                "useless_deaths": useless,
                "total_defense_deaths": total,
                "rate": round(rate, 3),
            })

        return {
            "status": "ok",
            "session_date": sd_str,
            "metric": "useless_defense_deaths",
            "description": (
                "Defenders who died with their next spawn far away "
                f"(>= {min_reinf_seconds}s) and the killer barely scratched "
                f"(>= {min_killer_health} HP). Hands the attackers free time "
                "on the objective without trading damage."
            ),
            "thresholds": {
                "min_reinf_seconds": min_reinf_seconds,
                "min_killer_health": min_killer_health,
            },
            "players": players,
        }

