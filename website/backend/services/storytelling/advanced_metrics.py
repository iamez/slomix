"""StorytellingService mixin: advanced_metrics methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    DEATH_TRADE_WINDOW_MS,
    LURKER_MIN_DURATION_MS,
    TRADE_KILL_DELTA_MS,
    _to_date,
    date,
    strip_et_colors,
)


class _AdvancedMetricsMixin:
    """Advanced Metrics methods for StorytellingService."""

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

        # All kills grouped by round for temporal analysis
        kill_rows = await self.db.fetch_all("""
            SELECT victim_guid, killer_guid, kill_time, round_number, round_start_unix
            FROM proximity_kill_outcome
            WHERE session_date = $1 AND outcome IN ('gibbed', 'tapped_out')
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

        # Resolve names
        name_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, MAX(killer_name)
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        """, (sd,))
        name_map = {r[0]: strip_et_colors(r[1] or r[0]) for r in (name_rows or [])}

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

        # All kills with positions (from engagement end positions)
        eng_rows = await self.db.fetch_all("""
            SELECT target_guid, killer_guid, end_x, end_y, end_time_ms,
                   round_start_unix, num_attackers
            FROM combat_engagement
            WHERE session_date = $1 AND outcome = 'killed'
              AND end_x IS NOT NULL AND end_y IS NOT NULL
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

        # Resolve names + compute score
        name_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, MAX(killer_name)
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        """, (sd,))
        name_map = {r[0]: strip_et_colors(r[1] or r[0]) for r in (name_rows or [])}

        # Alive time for normalization
        alive_rows = await self.db.fetch_all("""
            SELECT player_guid, SUM(GREATEST(duration_ms, 1)) AS alive_ms
            FROM player_track WHERE session_date = $1 AND duration_ms > 0
            GROUP BY player_guid
        """, (sd,))
        alive_map = {r[0][:8]: int(r[1] or 1) for r in (alive_rows or [])}

        players = []
        for guid, stats in player_stats.items():
            alive_min = alive_map.get(guid, 60000) / 60000
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
        SOLO_RADIUS = 500  # units from nearest teammate = "solo"
        DOWNSAMPLE_MS = 1000  # 1s intervals for performance

        import math
        from collections import defaultdict

        track_rows = await self.db.fetch_all("""
            SELECT player_guid, player_name, team, round_start_unix,
                   spawn_time_ms, death_time_ms, duration_ms, path
            FROM player_track
            WHERE session_date = $1 AND duration_ms > $2 AND path IS NOT NULL
            ORDER BY round_start_unix, player_guid
        """, (sd, LURKER_MIN_DURATION_MS))

        if not track_rows:
            return {"status": "ok", "session_date": str(sd), "players": []}

        # Group tracks by round, downsample paths to 1s
        round_tracks: dict[int, list] = defaultdict(list)
        for r in track_rows:
            rsu = int(r[3] or 0)
            path_data = r[7]
            if not path_data:
                continue
            if isinstance(path_data, str):
                import json as _json
                try:
                    path_data = _json.loads(path_data)
                except (ValueError, TypeError):
                    # Unparseable JSON (legacy rows / corrupted data) — skip the track.
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
            round_tracks[rsu].append({
                "guid": r[0], "name": r[1], "team": r[2],
                "duration_ms": int(r[6] or 0), "points": points,
            })

        # For each track: compute solo time (no teammate within SOLO_RADIUS)
        player_stats: dict[str, dict] = defaultdict(lambda: {
            "total_samples": 0, "solo_samples": 0, "alive_ms": 0, "tracks": 0,
        })

        for rsu, tracks in round_tracks.items():
            # Pre-index teammate points by time bucket for fast lookup
            for track in tracks:
                guid_short = track["guid"][:8]
                team = track["team"]
                teammates = [
                    t for t in tracks
                    if t["team"] == team and t["guid"][:8] != guid_short
                ]
                if not teammates:
                    # Solo player (no teammates in this life) — all samples are solo
                    player_stats[guid_short]["solo_samples"] += len(track["points"])
                    player_stats[guid_short]["total_samples"] += len(track["points"])
                    player_stats[guid_short]["alive_ms"] += track["duration_ms"]
                    player_stats[guid_short]["tracks"] += 1
                    continue

                # Build time-indexed arrays for each teammate (sorted)
                tm_arrays = [tm["points"] for tm in teammates]

                solo_count = 0
                for t_ms, px, py in track["points"]:
                    min_dist = float("inf")
                    for tm_pts in tm_arrays:
                        # Linear scan with early exit (points are time-sorted)
                        best_d = float("inf")
                        for tt, tx, ty in tm_pts:
                            if abs(tt - t_ms) <= DOWNSAMPLE_MS * 2:
                                dx = px - tx
                                dy = py - ty
                                d = math.sqrt(dx * dx + dy * dy)
                                if d < best_d:
                                    best_d = d
                            elif tt > t_ms + DOWNSAMPLE_MS * 2:
                                break
                        if best_d < min_dist:
                            min_dist = best_d
                    if min_dist > SOLO_RADIUS:
                        solo_count += 1

                player_stats[guid_short]["total_samples"] += len(track["points"])
                player_stats[guid_short]["solo_samples"] += solo_count
                player_stats[guid_short]["alive_ms"] += track["duration_ms"]
                player_stats[guid_short]["tracks"] += 1

        # Resolve names
        name_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, MAX(killer_name)
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical
        """, (sd,))
        name_map = {r[0]: strip_et_colors(r[1] or r[0]) for r in (name_rows or [])}

        players = []
        for guid, stats in player_stats.items():
            total = max(stats["total_samples"], 1)
            solo_pct = (stats["solo_samples"] / total) * 100
            players.append({
                "guid_short": guid,
                "name": name_map.get(guid, f"#{guid}"),
                "solo_pct": round(solo_pct, 1),
                "solo_samples": stats["solo_samples"],
                "total_samples": stats["total_samples"],
                "alive_ms": stats["alive_ms"],
                "tracks": stats["tracks"],
                "solo_time_est_s": round(stats["solo_samples"] * DOWNSAMPLE_MS / 1000, 0),
            })

        players.sort(key=lambda p: p["solo_pct"], reverse=True)

        return {
            "status": "ok",
            "session_date": str(sd),
            "metric": "lurker_profile",
            "description": f"Percentage of alive time spent >={SOLO_RADIUS}u from nearest teammate.",
            "solo_radius": SOLO_RADIUS,
            "downsample_ms": DOWNSAMPLE_MS,
            "players": players,
        }

