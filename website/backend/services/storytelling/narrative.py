"""StorytellingService mixin: narrative methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.

Narrative style note (2026-05-09 overhaul): we follow the
"wordalisation" pattern from sports NLG research — flow numbers into
sentences with context rather than emit "(N% / N vs N)" parenthetical
data dumps. Where a single template would feel formulaic across many
sessions, three phrasing variants are picked deterministically by
session_id hash so back-to-back sessions don't read identically.
"""
from __future__ import annotations

import re

from .base import (
    _to_date,
    _to_date_str,
    asyncio,
    date,
    strip_et_colors,
)

# ---------------------------------------------------------------------------
# Map name humanization
# ---------------------------------------------------------------------------

# Strip common ET:Legacy map prefixes/suffixes that mean nothing to a
# human reader. ``etl_adlernest`` → ``Adlernest``; ``sw_goldrush_te`` →
# ``Goldrush``. Versioned tails like ``_b3``, ``_t2`` are also dropped.
_MAP_PREFIX_RE = re.compile(r'^(etl?_|sw_|te_)+', re.IGNORECASE)
_MAP_SUFFIX_RE = re.compile(r'(_te|_b\d+|_t\d+|_v\d+)$', re.IGNORECASE)


def _humanize_map_name(raw: str) -> str:
    if not raw:
        return ""
    cleaned = _MAP_PREFIX_RE.sub("", raw)
    cleaned = _MAP_SUFFIX_RE.sub("", cleaned)
    return cleaned.replace('_', ' ').strip().title() or raw


def _format_maps_list(maps: list[str]) -> str:
    """Render a friendly map list. Truncates aggressively past 4 entries.

    Returns just the names (no "N maps" prefix) — the caller decides
    whether to wrap with a count. Avoids doubled "across N maps — N maps
    including ..." when the opener already mentions the count.
    """
    # Sort on the humanized form (post-prefix-strip) so the visible
    # order is alphabetical to a reader: "Adlernest, Brewdog, ..." not
    # the raw-name order ("et_brewdog" < "etl_adlernest" lexically).
    pretty = sorted({_humanize_map_name(m) for m in maps if m})
    pretty = [p for p in pretty if p]
    if not pretty:
        return "no map data"
    if len(pretty) == 1:
        return pretty[0]
    if len(pretty) == 2:
        return f"{pretty[0]} and {pretty[1]}"
    if len(pretty) <= 4:
        return ", ".join(pretty[:-1]) + f", and {pretty[-1]}"
    # >4 maps: list the first 3 + how many more remain
    return f"{', '.join(pretty[:3])} (+{len(pretty) - 3} more)"


# ---------------------------------------------------------------------------
# Variant phrasing (deterministic pick by session_id)
# ---------------------------------------------------------------------------
# Three variants per slot avoids same-template fatigue across back-to-back
# sessions while staying maintainable (no LLM, no per-style branches).

_MVP_LEADS = (
    "{name} led the leaderboard as {archetype} with {dpm} DPM (damage/min) and {kis:.0f} KIS",
    "{name} took the top spot — {archetype} with {dpm} DPM and {kis:.0f} KIS",
    "{name} carried the session as {archetype}, posting {dpm} DPM and {kis:.0f} KIS",
)

_MEDIC_LEADS = (
    "{name} kept the squad alive with {revives} revives",
    "{name} patched the team back together {revives} times",
    "{name} held down medic duty ({revives} revives)",
)

_MOMENT_LEADS = (
    "The defining moment came {when} — {what}",
    "The session pivoted {when}: {what}",
    "Standout play of the day {when}: {what}",
)

_SYNERGY_LEADS = (
    "{winner} edged out {loser} {win_score}–{lose_score} on team synergy, {tip}",
    "Synergy went to {winner} ({win_score}–{lose_score}), {tip}",
    "{winner} pulled ahead in coordination {win_score}–{lose_score}, {tip}",
)

_AXIS_PHRASING = {
    "crossfire": "set up by tighter crossfire angles",
    "trade": "carried by quicker trades",
    "cohesion": "anchored by tighter formation",
    "push": "driven by cleaner pushes",
    "medic": "kept upright by stronger medic play",
}


def _push_quality_phrase(quality: float | None) -> str:
    """Band the moment's `push_quality` (0..2+ range) into a human descriptor.

    Source field is `proximity_team_push.push_quality`, the same value
    the moment-detector filters at >= 0.7. (The sibling `alignment_score`
    is the raw cohesion ratio without the toward-objective weighting,
    not what we want for "how textbook was the execution".)
    """
    if quality is None:
        return "coordinated"
    if quality >= 1.5:
        return "textbook"
    if quality >= 1.0:
        return "well-coordinated"
    return "solid"


def _pick_variant(variants: tuple[str, ...], seed: int) -> str:
    return variants[seed % len(variants)]


def _format_group_label(group_data: dict, fallback: str) -> str:
    """Build a human label for a synergy group from its players list.

    Prefer real names ("bronze, qmr, vid") over the internal ``group_a``
    key. Falls back to "Side A" / "Side B" when player data is missing.
    """
    players = [strip_et_colors(p) for p in (group_data.get("players") or []) if p]
    players = [p for p in players if p]
    if not players:
        return fallback
    if len(players) <= 3:
        return ", ".join(players)
    return f"{', '.join(players[:3])} (+{len(players) - 3} more)"


class _NarrativeMixin:
    """Narrative methods for StorytellingService."""

    async def generate_narrative(self, session_date: str | date) -> dict:
        """Generate a human-readable paragraph summarizing the session.

        Uses KIS, moments, synergy, archetypes, and PWC data. Output is
        designed to read like a sports recap, not a stats dump — see
        the module docstring for the wordalisation rationale.
        """
        sd = _to_date(session_date)
        sd_str = _to_date_str(sd)

        # 1. Ensure KIS is computed, then fetch leaderboard + archetypes.
        # Routes through kis_compute_with_shadow so KIS_SHADOW_MODE_ENABLED
        # sessions get an audit-row even when narrative generation is the
        # first thing that triggers a KIS compute.
        await self.kis_compute_with_shadow(sd)
        kis_board = await self.get_kis_leaderboard(sd, limit=50)
        archetypes, stats = await self.classify_players(sd, kis_board)

        if not kis_board:
            return {"status": "no_data", "narrative": ""}

        # 2. Maps played — humanize and truncate (was a 6-entry comma sandwich).
        # Order by map_name so the rendered list is stable across re-renders.
        # Without ORDER BY, postgres can return DISTINCT rows in any order
        # and the same session would narrate "Brewdog, Adlernest, ..." one
        # time and "Adlernest, Brewdog, ..." the next — variant phrasing on
        # purpose, but map ordering shouldn't drift.
        map_rows = await self.db.fetch_all(
            "SELECT DISTINCT map_name FROM proximity_kill_outcome "
            "WHERE session_date = $1 ORDER BY map_name",
            (sd,))
        raw_maps = [strip_et_colors(r[0]) for r in (map_rows or []) if r[0]]
        maps_played = _format_maps_list(raw_maps)
        map_count = len(raw_maps)

        # 3. MVP (top KIS player)
        mvp = kis_board[0]
        mvp_name = strip_et_colors(mvp.get("name", "Unknown"))
        mvp_archetype = (archetypes.get(mvp["guid"], "frontline_warrior")).replace("_", " ")
        mvp_guid = mvp["guid"]
        mvp_stats = stats.get(mvp_guid, {})
        mvp_dpm = round(mvp_stats.get("dpm", 0))
        mvp_kis = mvp.get("total_kis", 0)

        # 4. Medic anchor (most revives)
        medic_name = ""
        medic_revives = 0
        for guid, s in stats.items():
            rev = s.get("revives_given", 0)
            if rev > medic_revives:
                medic_revives = rev
                entry = next((e for e in kis_board if e["guid"] == guid), None)
                medic_name = strip_et_colors(entry["name"]) if entry else guid[:8]

        # 5. Top moment — include map+round context, drop raw quality%
        moments = await self.detect_moments(sd, limit=1)
        top_moment_when = ""
        top_moment_what = ""
        if moments:
            m = moments[0]
            map_label = _humanize_map_name(m.get("map_name") or "")
            round_num = m.get("round_number")
            if map_label and round_num:
                top_moment_when = f"on {map_label} R{round_num}"
            elif map_label:
                top_moment_when = f"on {map_label}"
            elif m.get("time_formatted"):
                top_moment_when = f"at {m['time_formatted']}"

            # For push_success moments, replace the noisy
            # "(quality 174%)" tail with a descriptive adjective and
            # keep the rest of the moment narrative intact.
            raw = strip_et_colors(m.get("narrative", "an intense play"))
            if m.get("type") == "push_success":
                detail = m.get("detail") or {}
                quality = detail.get("push_quality")
                count = detail.get("participant_count")
                team = detail.get("team", "Unknown")
                # Title-case the objective the same way moments.py does
                # for its own card narrative — "flag_room" → "Flag Room"
                # rather than the previous lowercase "flag room" mid-sentence.
                obj = (detail.get("objective") or "the objective").replace('_', ' ').title()
                top_moment_what = (
                    f"{team} pulled off a {_push_quality_phrase(quality)} "
                    f"{count}-player {obj} push" if count
                    else f"{team} put together a {_push_quality_phrase(quality)} push toward {obj}"
                )
            else:
                top_moment_what = raw

        # 6. Team synergy — humanize labels, drop raw axis number
        synergy = await self.compute_team_synergy(sd)
        winner_label = ""
        loser_label = ""
        win_score = 0
        lose_score = 0
        axis_tip = ""
        teams = synergy.get("groups", {})
        if teams:
            composites = {t: d.get("composite", 0) for t, d in teams.items()}
            if composites:
                winner_key = max(composites, key=composites.get)
                loser_key = min(composites, key=composites.get)
                if winner_key != loser_key:
                    winner_label = _format_group_label(
                        teams.get(winner_key, {}),
                        fallback=winner_key.replace('group_', 'Side ').upper(),
                    )
                    loser_label = _format_group_label(
                        teams.get(loser_key, {}),
                        fallback=loser_key.replace('group_', 'Side ').upper(),
                    )
                    win_score = round(composites[winner_key])
                    lose_score = round(composites[loser_key])

                    # Find the axis where the winner was strongest
                    winner_data = teams.get(winner_key, {})
                    best_axis = ""
                    best_axis_val = 0.0
                    for axis in ('crossfire', 'trade', 'cohesion', 'push', 'medic'):
                        val = winner_data.get(axis, 0)
                        if val > best_axis_val:
                            best_axis_val = val
                            best_axis = axis
                    axis_tip = _AXIS_PHRASING.get(best_axis, "with the edge across the board")

        # 7. Session ID for variant seed.
        # Legacy rows may have NULL gaming_session_id; render as "?" and
        # derive a stable seed from the session_date string. Avoid Python's
        # built-in `hash()` because it's PYTHONHASHSEED-dependent and
        # would shuffle variant pickup across uvicorn restarts.
        session_id_row = await self.db.fetch_one(
            "SELECT gaming_session_id FROM rounds "
            "WHERE round_date = $1 LIMIT 1",
            (sd_str,))
        raw_id = session_id_row[0] if session_id_row else None
        if isinstance(raw_id, int):
            session_label = str(raw_id)
            seed = raw_id
        else:
            session_label = "?"
            # Stable across processes: sum of date character codes is
            # deterministic and good enough for variant pickup over a
            # 4-element variant pool.
            seed = sum(ord(c) for c in sd_str)

        # 8. Build narrative — variant phrasings, flowed numbers
        if map_count >= 2:
            opener = f"Session {session_label} played out across {map_count} maps — {maps_played}."
        elif map_count == 1:
            opener = f"Session {session_label} on {maps_played}."
        else:
            opener = f"Session {session_label}."

        parts = [opener]

        parts.append(" " + _pick_variant(_MVP_LEADS, seed).format(
            name=mvp_name, archetype=mvp_archetype, dpm=mvp_dpm, kis=mvp_kis,
        ) + ".")

        if medic_name and medic_revives > 0:
            parts.append(" " + _pick_variant(_MEDIC_LEADS, seed + 1).format(
                name=medic_name, revives=medic_revives,
            ) + ".")

        if top_moment_what and top_moment_when:
            parts.append(" " + _pick_variant(_MOMENT_LEADS, seed + 2).format(
                when=top_moment_when, what=top_moment_what,
            ) + ".")

        if winner_label and loser_label and win_score > 0 and axis_tip:
            parts.append(" " + _pick_variant(_SYNERGY_LEADS, seed + 3).format(
                winner=winner_label, loser=loser_label,
                win_score=win_score, lose_score=lose_score,
                tip=axis_tip,
            ) + ".")

        narrative = "".join(parts).strip()

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

        # Also get KIS for archetype + kills context (shadow-aware — see
        # generate_narrative for rationale).
        await self.kis_compute_with_shadow(sd)
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

        # Own-history baselines (VISION_2026 writing rule: numbers carry
        # their delta vs the player's usual, not just the session avg).
        from .baseline import format_with_baseline, trailing_averages
        guid_list = sorted(all_guids)
        # Resolve the narrated night's earliest gaming_session_id so the
        # baseline strictly PRECEDES it. Without this the trailing average
        # would (a) include tonight in "your usual" and (b) for a historical
        # session_date draw the baseline from sessions played AFTER it.
        # A single calendar date can hold >1 gaming_session_id, so use MIN()
        # as the cutoff to exclude every session of that night.
        gsid_row = await self.db.fetch_one(
            "SELECT MIN(gaming_session_id) FROM rounds "
            "WHERE round_date = $1 AND gaming_session_id IS NOT NULL",
            (_to_date_str(sd),))
        before_gsid = gsid_row[0] if gsid_row else None
        baseline_results = await asyncio.gather(
            *(trailing_averages(self.db, g[:8], before_session_id=before_gsid)
              for g in guid_list),
            return_exceptions=True,
        )
        own_baseline: dict[str, dict] = {
            g: (res if isinstance(res, dict) else {})
            for g, res in zip(guid_list, baseline_results)
        }

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
                    kills_txt = format_with_baseline(
                        kills, own_baseline.get(guid, {}).get("kills")
                    )
                    parts.append(
                        f"Fragged {kills_txt} ({total_kis:.0f} KIS) as {archetype}."
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

