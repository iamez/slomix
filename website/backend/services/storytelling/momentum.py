"""StorytellingService mixin: momentum methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    _to_date,
    date,
)


class _MomentumMixin:
    """Momentum methods for StorytellingService."""

    async def compute_momentum(self, session_date: str | date) -> dict:
        """Compute per-round team momentum in 30-second windows.

        Momentum decays each window (×0.85) and gains from kills and objectives.
        Returns dual-line data (AXIS vs ALLIES) normalized to 0-100 per round.
        """
        sd = _to_date(session_date)

        # 1. Get all kills with team info
        kills = await self.db.fetch_all("""
            SELECT ko.round_number, ko.round_start_unix, ko.map_name,
                   ko.kill_time, ko.killer_guid, ko.victim_guid
            FROM proximity_kill_outcome ko
            WHERE ko.session_date = $1
            ORDER BY ko.round_start_unix, ko.kill_time
        """, (sd,))

        if not kills:
            return {"status": "no_data", "session_date": str(sd), "rounds": []}

        # 2. Build team map from PCS
        rtm = await self._build_round_team_map(sd)

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
        carrier_events = await self.db.fetch_all("""
            SELECT round_number, round_start_unix, map_name,
                   carrier_team, pickup_time, outcome
            FROM proximity_carrier_event
            WHERE session_date = $1
        """, (sd,))

        # Construction events
        construction_events = await self.db.fetch_all("""
            SELECT round_number, round_start_unix, map_name,
                   player_team, event_time, event_type
            FROM proximity_construction_event
            WHERE session_date = $1
        """, (sd,))

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
                "points": normalized,
            })

        return {
            "status": "ok",
            "session_date": str(sd),
            "rounds": result_rounds,
        }

