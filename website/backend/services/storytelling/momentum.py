"""StorytellingService mixin: momentum methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import (
    date,
)

if TYPE_CHECKING:
    from website.backend.services.session_scope import GamingSessionScope


class _MomentumMixin:
    """Momentum methods for StorytellingService."""

    async def compute_momentum(self, scope: GamingSessionScope) -> dict:
        """Compute per-round team momentum in 30-second windows.

        Momentum decays each window (×0.85) and gains from kills and objectives.
        Returns dual-line data (AXIS vs ALLIES) normalized to 0-100 per round.

        Scoped by the full gaming session (deep SS-C): a midnight-crossing
        session charts momentum for ALL its rounds, not just one date.
        """
        internal = await self._momentum_rounds(scope)
        sd_str = scope.dates[0]
        if internal is None:
            return {"status": "no_data", "session_date": sd_str, "rounds": []}
        return {
            "status": "ok",
            "session_date": sd_str,
            "rounds": [
                {
                    "round_number": r["round_number"],
                    "map_name": r["map_name"],
                    "points": r["points"],
                }
                for r in internal
            ],
        }

    async def _momentum_rounds(self, scope: GamingSessionScope) -> list[dict] | None:
        """Per-round momentum series, with round_start_unix kept for stitching.

        Proximity tables (kill_outcome, carrier_event, construction_event)
        carry no gaming_session_id, so they filter by session dates + the
        canonical round key (deep SS-C). Shared with compute_momentum and
        compute_momentum_session.
        """
        dates = [date.fromisoformat(d) for d in scope.dates]
        starts, maps, rnums = scope.round_key_arrays()

        # 1. Get all kills with team info
        kills = await self.db.fetch_all(f"""
            SELECT ko.round_number, ko.round_start_unix, ko.map_name,
                   ko.kill_time, ko.killer_guid, ko.victim_guid
            FROM proximity_kill_outcome ko
            WHERE ko.session_date = ANY($1) AND {scope.round_key_filter_sql(2, alias="ko")}
            ORDER BY ko.round_start_unix, ko.kill_time
        """, (dates, starts, maps, rnums))

        if not kills:
            return None

        # 2. Build team map from PCS
        rtm = await self._build_round_team_map(scope)

        # Fallback: majority-vote per GUID
        guid_teams: dict[str, list[str]] = {}
        for (g, _rn), faction in rtm.items():
            guid_teams.setdefault(g, []).append(faction)
        guid_majority: dict[str, str] = {}
        for g, teams in guid_teams.items():
            if teams.count('AXIS') > teams.count('ALLIES'):
                guid_majority[g] = 'AXIS'
            elif teams.count('ALLIES') > teams.count('AXIS'):
                guid_majority[g] = 'ALLIES'
            # tied → skip, lookup returns None

        # Build short→long for PCS 8-char to proximity 32-char
        all_guids = set()
        for k in kills:
            all_guids.add(k[4])
            all_guids.add(k[5])
        short_to_long = {g[:8]: g for g in all_guids}

        def _get_team(guid: str, rn: int) -> str | None:
            """Resolve team for a GUID in a round. Try PCS 8-char lookup, then majority."""
            t = rtm.get((guid[:8], rn)) or rtm.get((guid, rn))
            if t:
                return t
            long = short_to_long.get(guid[:8], guid)
            t = rtm.get((long[:8], rn))
            if t:
                return t
            return guid_majority.get(guid[:8]) or guid_majority.get(guid)

        # 3. Get objective events: carrier pickups/secured
        carrier_events = await self.db.fetch_all(f"""
            SELECT round_number, round_start_unix, map_name,
                   carrier_team, pickup_time, outcome
            FROM proximity_carrier_event
            WHERE session_date = ANY($1) AND {scope.round_key_filter_sql(2)}
        """, (dates, starts, maps, rnums))

        # Construction events
        construction_events = await self.db.fetch_all(f"""
            SELECT round_number, round_start_unix, map_name,
                   player_team, event_time, event_type
            FROM proximity_construction_event
            WHERE session_date = ANY($1) AND {scope.round_key_filter_sql(2)}
        """, (dates, starts, maps, rnums))

        # 4. Group kills by round
        rounds_data: dict[tuple[int, int], dict] = {}  # (rn, start_unix) -> {map, kills, objs}
        for k in kills:
            rn, start_unix, map_name = k[0], k[1], k[2]
            key = (rn, start_unix)
            if key not in rounds_data:
                rounds_data[key] = {"map_name": map_name, "kills": [], "objectives": []}
            kill_time_ms = k[3] or 0
            killer_guid = k[4]
            killer_team = _get_team(killer_guid, rn)
            if killer_team is None:
                continue
            rounds_data[key]["kills"].append({
                "t_ms": kill_time_ms,
                "team": killer_team,
            })

        # Add carrier objectives
        for ce in (carrier_events or []):
            rn, start_unix = ce[0], ce[1]
            key = (rn, start_unix)
            if key not in rounds_data:
                rounds_data[key] = {"map_name": ce[2], "kills": [], "objectives": []}
            team = ce[3]
            if not team:
                continue
            pickup_ms = (ce[4] or 0)
            outcome = ce[5] or ''
            bonus = 15 if outcome != 'secured' else 30
            rounds_data[key]["objectives"].append({
                "t_ms": pickup_ms,
                "team": team,
                "bonus": bonus,
            })

        # Add construction objectives
        for ce in (construction_events or []):
            rn, start_unix = ce[0], ce[1]
            key = (rn, start_unix)
            if key not in rounds_data:
                rounds_data[key] = {"map_name": ce[2], "kills": [], "objectives": []}
            team = ce[3]
            if not team:
                continue
            event_time_ms = (ce[4] or 0)
            rounds_data[key]["objectives"].append({
                "t_ms": event_time_ms,
                "team": team,
                "bonus": 20,
            })

        # 5. Compute momentum per round
        WINDOW_MS = 30_000
        DECAY = 0.85
        KILL_IMPACT = 5.0
        result_rounds = []

        for (rn, start_unix), rd in sorted(rounds_data.items(), key=lambda x: (x[0][1], x[0][0])):
            # Find max time in this round
            all_times = [k["t_ms"] for k in rd["kills"]]
            all_times += [o["t_ms"] for o in rd["objectives"]]
            if not all_times:
                continue
            max_time = max(all_times)

            # Build windows
            axis_raw = 0.0
            allies_raw = 0.0
            points = []

            n_windows = max(1, (max_time // WINDOW_MS) + 2)
            for w in range(n_windows):
                t_start = w * WINDOW_MS
                t_end = t_start + WINDOW_MS

                # Decay previous momentum
                axis_raw *= DECAY
                allies_raw *= DECAY

                # Sum kill impacts in this window
                for k in rd["kills"]:
                    if t_start <= k["t_ms"] < t_end:
                        if k["team"] == 'AXIS':
                            axis_raw += KILL_IMPACT
                            allies_raw -= KILL_IMPACT * 0.3
                        else:
                            allies_raw += KILL_IMPACT
                            axis_raw -= KILL_IMPACT * 0.3

                # Sum objective bonuses
                for o in rd["objectives"]:
                    if t_start <= o["t_ms"] < t_end:
                        if o["team"] == 'AXIS':
                            axis_raw += o["bonus"]
                        else:
                            allies_raw += o["bonus"]

                points.append({
                    "t_ms": t_start,
                    "axis_raw": axis_raw,
                    "allies_raw": allies_raw,
                })

            # 6. Normalize to 0-100 range
            all_vals = [abs(p["axis_raw"]) for p in points] + [abs(p["allies_raw"]) for p in points]
            max_val = max(all_vals) if all_vals else 1.0
            if max_val < 0.01:
                max_val = 1.0

            normalized = []
            for p in points:
                # Map from raw to 0-100 centered at 50
                axis_norm = 50 + (p["axis_raw"] / max_val) * 50
                allies_norm = 50 + (p["allies_raw"] / max_val) * 50
                # Clamp
                axis_norm = max(0, min(100, axis_norm))
                allies_norm = max(0, min(100, allies_norm))
                normalized.append({
                    "t_ms": p["t_ms"],
                    "axis": round(axis_norm, 1),
                    "allies": round(allies_norm, 1),
                })

            result_rounds.append({
                "round_number": rn,
                "map_name": rd["map_name"],
                "round_start_unix": start_unix,
                "points": normalized,
            })

        return result_rounds

    async def compute_momentum_session(self, scope: GamingSessionScope) -> dict:
        """Whole-session momentum by LOGICAL team (stopwatch-aware).

        Faction lines are meaningless across a session — rosters swap sides
        between R1 and R2 — so each round's axis/allies series is remapped to
        team_a/team_b via the synergy player-group round_map (first-R1 anchor
        + per-round guid-overlap voting), then stitched onto one cumulative
        timeline (sum of round durations, not wall clock — map breaks would
        stretch the chart).

        Deep SS-C transitional: `_momentum_rounds` is now full-gaming-session
        scoped (multi-date), but the player-group mapping (`_build_player_groups`
        / `_team_labels`) still keys off the representative first date until
        the shared `_build_player_groups` cluster converts (next batch). For a
        midnight-crossing session the after-midnight rounds therefore surface
        as `unmapped_rounds` rather than mislabeled — honest, and finalized
        when the cluster lands.
        """
        sd = date.fromisoformat(scope.dates[0])
        internal = await self._momentum_rounds(scope)
        if internal is None:
            return {"status": "no_data", "session_date": str(sd), "points": []}

        groups = await self._build_player_groups(sd)
        if not groups or groups.get("_status") == "partial_data":
            return {
                "status": "no_team_data",
                "session_date": str(sd),
                "reason": (groups or {}).get("_reason", "no_pcs_rows"),
                "points": [],
            }

        round_map = groups["round_map"]
        labels = await self._team_labels(sd, groups)

        WINDOW_MS = 30_000
        points: list[dict] = []
        boundaries: list[dict] = []
        unmapped_rounds = 0
        offset = 0
        for r in sorted(internal, key=lambda x: (x["round_start_unix"], x["round_number"])):
            rsu = r["round_start_unix"]
            axis_group = round_map.get((rsu, "AXIS"))
            if axis_group is None:
                # Round exists in proximity data but not in PCS (orphan) —
                # skip rather than guess, and report it.
                unmapped_rounds += 1
                continue
            axis_is_a = axis_group == "group_a"
            boundaries.append({
                "x_ms": offset,
                "map_name": r["map_name"],
                "round_number": r["round_number"],
            })
            points.extend(
                {
                    "t_ms": offset + p["t_ms"],
                    "team_a": p["axis"] if axis_is_a else p["allies"],
                    "team_b": p["allies"] if axis_is_a else p["axis"],
                }
                for p in r["points"]
            )
            duration = (r["points"][-1]["t_ms"] + WINDOW_MS) if r["points"] else 0
            offset += duration

        return {
            "status": "ok",
            "session_date": str(sd),
            "teams": {
                "team_a": {"label": labels["team_a"], "players": groups["group_a_players"]},
                "team_b": {"label": labels["team_b"], "players": groups["group_b_players"]},
            },
            "points": points,
            "round_boundaries": boundaries,
            "meta": {
                "rounds": len(boundaries),
                "unmapped_rounds": unmapped_rounds,
                "defaulted_players_count": groups.get("defaulted_players_count", 0),
            },
        }

    async def _team_labels(self, sd: date, groups: dict) -> dict[str, str]:
        """Name each logical team after its two highest-kill players."""
        rows = await self.db.fetch_all(
            """
            SELECT pcs.player_guid, MAX(pcs.player_name), SUM(pcs.kills) AS kills
            FROM player_comprehensive_stats pcs
            WHERE pcs.round_date = $1
            GROUP BY pcs.player_guid
            ORDER BY kills DESC NULLS LAST
            """,
            (str(sd),),
        )
        guid_to_group = groups.get("guid_to_group", {})
        top: dict[str, list[str]] = {"group_a": [], "group_b": []}
        for guid, name, _kills in (rows or []):
            grp = guid_to_group.get(guid)
            if grp and len(top[grp]) < 2:
                top[grp].append(name or guid[:8])
        return {
            "team_a": " & ".join(top["group_a"]) or "Team A",
            "team_b": " & ".join(top["group_b"]) or "Team B",
        }

