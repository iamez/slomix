"""StorytellingService mixin: narrative methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    _to_date,
    _to_date_str,
    asyncio,
    date,
    strip_et_colors,
)


class _NarrativeMixin:
    """Narrative methods for StorytellingService."""

    async def generate_narrative(self, session_date: str | date) -> dict:
        """Generate a human-readable paragraph summarizing the session.

        Uses KIS, moments, synergy, archetypes, and PWC data.
        """
        sd = _to_date(session_date)
        sd_str = _to_date_str(sd)

        # 1. Ensure KIS is computed, then fetch leaderboard + archetypes
        await self.compute_session_kis(sd)
        kis_board = await self.get_kis_leaderboard(sd, limit=50)
        archetypes, stats = await self.classify_players(sd, kis_board)

        if not kis_board:
            return {"status": "no_data", "narrative": ""}

        # 2. Maps played
        map_rows = await self.db.fetch_all(
            "SELECT DISTINCT map_name FROM proximity_kill_outcome WHERE session_date = $1",
            (sd,))
        maps_played = ", ".join(strip_et_colors(r[0]) for r in (map_rows or []) if r[0])

        # 3. MVP (top KIS player)
        mvp = kis_board[0]
        mvp_name = strip_et_colors(mvp.get("name", "Unknown"))
        mvp_archetype = (archetypes.get(mvp["guid"], "frontline_warrior")).replace("_", " ")
        mvp_guid = mvp["guid"]
        mvp_stats = stats.get(mvp_guid, {})
        mvp_dpm = round(mvp_stats.get("dpm", 0), 1)
        mvp_kis = mvp.get("total_kis", 0)

        # 4. Medic anchor (most revives)
        medic_name = ""
        medic_revives = 0
        for guid, s in stats.items():
            rev = s.get("revives_given", 0)
            if rev > medic_revives:
                medic_revives = rev
                # Find name from kis_board
                entry = next((e for e in kis_board if e["guid"] == guid), None)
                medic_name = strip_et_colors(entry["name"]) if entry else guid[:8]

        # 5. Top moment
        moments = await self.detect_moments(sd, limit=1)
        top_moment_time = ""
        top_moment_narrative = ""
        if moments:
            m = moments[0]
            top_moment_time = m.get("time_formatted", "")
            top_moment_narrative = strip_et_colors(m.get("narrative", "an intense play"))

        # 6. Team synergy
        synergy = await self.compute_team_synergy(sd)
        better_team = ""
        better_composite = 0.0
        worse_composite = 0.0
        best_axis_name = ""
        best_axis_val = 0.0
        teams = synergy.get("groups", {})
        if teams:
            composites = {t: d.get("composite", 0) for t, d in teams.items()}
            if composites:
                better_team = max(composites, key=composites.get)
                worse_team = min(composites, key=composites.get)
                better_composite = composites.get(better_team, 0)
                worse_composite = composites.get(worse_team, 0)
                # Find the best synergy axis for the better team
                better_data = teams.get(better_team, {})
                for axis in ('crossfire', 'trade', 'cohesion', 'push', 'medic'):
                    val = better_data.get(axis, 0)
                    if val > best_axis_val:
                        best_axis_val = val
                        best_axis_name = axis

        # 7. Session ID from gaming sessions
        session_id_row = await self.db.fetch_one(
            "SELECT gaming_session_id FROM rounds "
            "WHERE round_date = $1 LIMIT 1",
            (sd_str,))
        session_id = session_id_row[0] if session_id_row else "?"

        # 8. Build narrative
        parts = [f"Session {session_id} on {maps_played}"]

        parts.append(
            f" was defined by {mvp_name}'s {mvp_archetype} performance "
            f"({mvp_dpm} DPM, {mvp_kis:.0f} KIS)"
        )

        if medic_name and medic_revives > 0:
            parts.append(f". {medic_name} anchored the team with {medic_revives} revives")

        if top_moment_narrative:
            parts.append(
                f". The session's defining moment came at {top_moment_time} "
                f"when {top_moment_narrative}"
            )

        if better_team and better_composite > 0:
            parts.append(
                f". Team synergy favored {better_team} "
                f"({better_composite:.0f} vs {worse_composite:.0f}), "
                f"driven by superior {best_axis_name} ({best_axis_val:.0f})"
            )

        narrative = "".join(parts) + "."

        return {
            "status": "ok",
            "session_date": sd_str,
            "narrative": narrative,
        }

    async def generate_player_narratives(self, session_date: str | date) -> dict:
        """Generate per-player micro-narratives using gravity, space, enabler, lurker.

        Each player gets a 1-2 sentence story describing their invisible value,
        not just their K/D.
        """
        sd = _to_date(session_date)

        # Compute all metrics in parallel
        gravity, space, enabler, lurker = await asyncio.gather(
            self.compute_gravity(sd),
            self.compute_space_created(sd),
            self.compute_enabler(sd),
            self.compute_lurker_profile(sd),
        )

        # Also get KIS for archetype + kills context
        await self.compute_session_kis(sd)
        kis_board = await self.get_kis_leaderboard(sd, limit=50)

        # Index by guid_short
        g_map = {p["guid_short"]: p for p in gravity.get("players", [])}
        s_map = {p["guid_short"]: p for p in space.get("players", [])}
        e_map = {p["guid_short"]: p for p in enabler.get("players", [])}
        l_map = {p["guid_short"]: p for p in lurker.get("players", [])}

        kis_map = {}
        for p in kis_board:
            short = p.get("guid", "")[:8]
            kis_map[short] = p

        # Build narratives
        narratives = []
        all_guids = set(g_map) | set(s_map) | set(e_map) | set(l_map)

        # Collect raw values for percentile normalization (different scales!)
        raw_vals: dict[str, list[float]] = {
            "gravity": [p.get("gravity_score", 0) for p in gravity.get("players", [])],
            "space": [p.get("space_score", 0) for p in space.get("players", [])],
            "enabler": [p.get("enabler_score", 0) for p in enabler.get("players", [])],
            "solo": [p.get("solo_pct", 0) for p in lurker.get("players", [])],
        }

        def _pct_rank(val: float, values: list[float]) -> float:
            """Percentile rank of val within values (0.0 to 1.0)."""
            if not values or max(values) == min(values):
                return 0.5
            below = sum(1 for v in values if v < val)
            return below / max(len(values) - 1, 1)

        # Helper: relative context string ("40% more than average")
        def _rel_ctx(val: float, values: list[float]) -> str:
            avg = sum(values) / max(len(values), 1)
            if avg <= 0 or val <= avg:
                return ""
            pct_above = ((val - avg) / avg) * 100
            if pct_above >= 80:
                return f" ({pct_above:.0f}% above session avg)"
            if pct_above >= 30:
                return f" ({pct_above:.0f}% more than avg)"
            return ""

        for guid in sorted(all_guids):
            g = g_map.get(guid, {})
            s = s_map.get(guid, {})
            e = e_map.get(guid, {})
            lk = l_map.get(guid, {})
            k = kis_map.get(guid, {})

            name = (g.get("name") or s.get("name") or e.get("name")
                    or lk.get("name") or f"#{guid}")
            gravity_score = g.get("gravity_score", 0)
            avg_attackers = g.get("avg_attackers", 1)
            space_score = s.get("space_score", 0)
            productive = s.get("productive_deaths", 0)
            total_deaths = s.get("total_deaths", 0)
            enabler_score = e.get("enabler_score", 0)
            solo_pct = lk.get("solo_pct", 0)
            kills = k.get("kills", 0)
            archetype = (k.get("archetype", "unknown")).replace("_", " ")
            total_kis = k.get("total_kis", 0)

            # KIS secondary stats
            clutch_kills = k.get("clutch_kills", 0) + k.get("solo_clutch_kills", 0)
            outnumbered = k.get("outnumbered_kills", 0)
            carrier_kills = k.get("carrier_kills", 0)
            denied_time = k.get("denied_time", 0)
            revives = k.get("revives_given", 0)

            parts = []

            # Normalize to percentile rank (0-1) before comparing across metrics
            traits = [
                ("gravity", _pct_rank(gravity_score, raw_vals["gravity"])),
                ("space", _pct_rank(space_score, raw_vals["space"])),
                ("enabler", _pct_rank(enabler_score, raw_vals["enabler"])),
                ("solo", _pct_rank(solo_pct, raw_vals["solo"])),
            ]
            top_trait = max(traits, key=lambda t: t[1])
            pct = top_trait[1]  # How dominant is this trait (0.0-1.0)

            # ── Gravity: drew enemy heat ──
            if top_trait[0] == "gravity" and gravity_score > 0:
                ctx = _rel_ctx(gravity_score, raw_vals["gravity"])
                if pct >= 0.9:
                    parts.append(
                        f"{name}: Attention magnet — drew the most heat, "
                        f"avg {avg_attackers:.1f} enemies per fight{ctx}. "
                    )
                elif pct >= 0.6:
                    parts.append(
                        f"{name}: Enemy focus target — consistently drew "
                        f"{avg_attackers:.1f} attackers{ctx}. "
                    )
                else:
                    parts.append(
                        f"{name}: Drew solid enemy attention "
                        f"({avg_attackers:.1f} avg attackers). "
                    )
                if space_score > 0.3:
                    parts.append(
                        f"{productive}/{total_deaths} deaths were productive "
                        f"— team capitalized within 10s."
                    )
                elif enabler_score > 1:
                    parts.append(
                        f"Set up {e.get('total_assists', 0)} teammate frags "
                        f"through pressure."
                    )

            # ── Solo: behind enemy lines ──
            elif top_trait[0] == "solo" and solo_pct > 30:
                solo_s = lk.get("solo_time_est_s", 0)
                if pct >= 0.9:
                    parts.append(
                        f"{name}: Deep lurker — {solo_pct:.0f}% of alive time "
                        f"behind enemy lines ({solo_s:.0f}s solo). "
                    )
                elif pct >= 0.6:
                    parts.append(
                        f"{name}: Flanker — operated solo {solo_pct:.0f}% "
                        f"of the time ({solo_s:.0f}s). "
                    )
                else:
                    parts.append(
                        f"{name}: Spent {solo_pct:.0f}% of alive time "
                        f"away from the pack. "
                    )
                if enabler_score > 0.5:
                    parts.append(
                        f"Despite going solo, set up "
                        f"{e.get('total_assists', 0)} teammate frags."
                    )
                elif kills > 0:
                    parts.append(
                        f"Fragged {kills} ({total_kis:.0f} KIS) as {archetype}."
                    )

            # ── Enabler: made teammates look good ──
            elif top_trait[0] == "enabler" and enabler_score > 0:
                total_assists = e.get("total_assists", 0)
                ctx = _rel_ctx(enabler_score, raw_vals["enabler"])
                if pct >= 0.9:
                    parts.append(
                        f"{name}: Made teammates look good — "
                        f"{total_assists} teammate frags created{ctx}. "
                    )
                elif pct >= 0.6:
                    parts.append(
                        f"{name}: Set up kills for the team — "
                        f"{total_assists} assists "
                        f"({e.get('trade_assists', 0)} trades){ctx}. "
                    )
                else:
                    parts.append(
                        f"{name}: Enabled {total_assists} teammate frags "
                        f"through positioning. "
                    )
                if gravity_score > 0:
                    parts.append(
                        f"Also drew heat (gravity {gravity_score:.0f})."
                    )

            # ── Space: dying forward ──
            elif top_trait[0] == "space" and space_score > 0:
                if pct >= 0.9:
                    parts.append(
                        f"{name}: Dying forward — "
                        f"{productive}/{total_deaths} deaths opened space, "
                        f"team fragged within 10s each time. "
                    )
                elif pct >= 0.6:
                    parts.append(
                        f"{name}: Created space — "
                        f"{productive}/{total_deaths} deaths led to "
                        f"teammate frags. "
                    )
                else:
                    parts.append(
                        f"{name}: {productive} productive deaths "
                        f"out of {total_deaths}. "
                    )
                if solo_pct > 15:
                    parts.append(
                        f"Often solo ({solo_pct:.0f}% of alive time)."
                    )

            else:
                # Fallback: basic stats
                parts.append(
                    f"{name} ({archetype}): Fragged {kills}, "
                    f"{total_kis:.0f} KIS."
                )

            # ── Secondary facts (1-2 extra lines from KIS/PCS data) ──
            secondary = []
            if clutch_kills >= 2:
                secondary.append(f"pulled off {clutch_kills} clutch kills")
            if outnumbered >= 3:
                secondary.append(f"{outnumbered} outnumbered frags")
            if carrier_kills >= 2:
                secondary.append(f"intercepted {carrier_kills} objective carriers")
            if denied_time >= 30:
                secondary.append(f"locked out {denied_time:.0f}s of enemy playtime")
            if revives >= 3:
                secondary.append(f"kept the team alive with {revives} revives")
            if secondary:
                parts.append(" " + ", ".join(secondary[:2]).capitalize() + ".")

            narratives.append({
                "guid_short": guid,
                "name": name,
                "narrative": "".join(parts).strip(),
                "archetype": archetype,
                "top_trait": top_trait[0],
                "metrics": {
                    "gravity": gravity_score,
                    "space_score": space_score,
                    "enabler_score": enabler_score,
                    "solo_pct": solo_pct,
                    "kills": kills,
                    "total_kis": round(total_kis, 1),
                    "archetype": archetype,
                    "clutch_kills": clutch_kills,
                    "carrier_kills": carrier_kills,
                    "denied_time": denied_time,
                    "revives": revives,
                },
            })

        # Sort by KIS descending
        narratives.sort(key=lambda n: n["metrics"].get("total_kis", 0), reverse=True)

        return {
            "status": "ok",
            "session_date": str(sd),
            "player_narratives": narratives,
        }

