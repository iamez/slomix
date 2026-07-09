"""SSR — Situational Skill Rating v0 (owner answer A4: full green light).

Per-player aggregate of the situational-competence signals the All-Seeing Eye
phase validated, expressed as GROUP-RELATIVE percentiles (0..1) and averaged
into one number. No component mixes raw units; every input is ranked within
the rated cohort first (min {MIN_SESSIONS} valid gaming sessions, A6).

Components (each may be None when its own sample gate fails — the aggregate
averages only what exists and reports coverage):
    clutch_kis_ps      Σ KIS earned while LAST ALIVE on own side, per session
                       (alive counts valid since 2026-04, Oksii Lua)
    situational_share  share of total KIS earned in carrier/push/crossfire/
                       objective-area context
    ois_ps             Objective Impact Score per session (base values —
                       the per-event speed/contested multipliers need event
                       context and stay in OisService)
    permanence         gib rate (permanent kills / kills)
    target_acq_ms      median aim-lock onset -> kill (lower better; live
                       since 2026-06-22, min {MIN_ACQ_EVENTS} linked kills)
    spawn_ready_ms     median time-to-first-move per life (lower better,
                       min {MIN_SPAWN_LIVES} lives)

SSR = mean of available component percentiles. Research status until the
Comp Skill surface ships (registry: situational_skill_rating).
"""
from __future__ import annotations

import datetime as _dt

from website.backend.utils.et_constants import strip_et_colors

FORMULA_VERSION = "ssr-v0.2"  # v0.2: +opening_net, +trade_discipline (owner-
                              # approved tables, PR #467 merged)
MIN_SESSIONS = 5           # owner answer A6
MIN_COMPONENTS = 3         # a 1-component player must not top the board
MIN_ACQ_EVENTS = 15
MIN_SPAWN_LIVES = 50
MIN_DUEL_ROUNDS = 30
MIN_DEATHS = 30
ALIVE_CONTEXT_SINCE = "2026-04-01"
AIM_LOCK_LIVE_SINCE = "2026-06-22"

_BOTS = ("OMNIBOT%", "[BOT]%")


def _pct_ranks(values: dict[str, float], *, lower_is_better: bool = False
               ) -> dict[str, float]:
    """guid -> percentile (0..1, 1 = best); ties share the average rank."""
    items = sorted(values.items(), key=lambda kv: kv[1],
                   reverse=not lower_is_better)
    n = len(items)
    if n == 1:
        return {items[0][0]: 1.0}
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        pct = sum(1.0 - k / (n - 1) for k in range(i, j + 1)) / (j - i + 1)
        for k in range(i, j + 1):
            out[items[k][0]] = round(pct, 4)
        i = j + 1
    return out


class SsrService:
    def __init__(self, db):
        self.db = db

    async def _sessions(self) -> dict[str, tuple[str, int]]:
        rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(p.player_guid, 8)) AS g8,"
            "       MAX(p.player_name) AS name,"
            "       COUNT(DISTINCT r.gaming_session_id) AS n "
            "FROM player_comprehensive_stats p "
            "JOIN rounds r ON r.id = p.round_id "
            "WHERE r.is_valid AND r.gaming_session_id IS NOT NULL "
            "  AND p.player_guid NOT LIKE ? AND p.player_name NOT LIKE ? "
            "GROUP BY UPPER(LEFT(p.player_guid, 8))",
            _BOTS,
        )
        return {r[0]: (strip_et_colors(r[1] or r[0]), int(r[2]))
                for r in (rows or [])}

    async def _kis_shares(self) -> dict[str, float]:
        rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(killer_guid, 8)) AS g8,"
            "       SUM(total_impact) AS total,"
            "       SUM(total_impact) FILTER ("
            "           WHERE is_carrier_kill OR is_during_push"
            "              OR is_crossfire OR is_objective_area) AS situ "
            "FROM storytelling_kill_impact "
            "WHERE killer_guid NOT LIKE ? AND killer_name NOT LIKE ? "
            "GROUP BY UPPER(LEFT(killer_guid, 8)) "
            "HAVING SUM(total_impact) > 0",
            _BOTS,
        )
        return {r[0]: float(r[2] or 0) / float(r[1]) for r in (rows or [])}

    async def _clutch_kis(self) -> dict[str, float]:
        # DISTINCT ON: the combat_position join can multi-match one kill
        # within the +-300ms slack window (bursts / same-tick multi-kills).
        # Canonical round key (round_start_unix, map_name, round_number,
        # session_date) + victim match, and dropping the old "BOTH sides
        # alive" pre-filter — round_start_unix alone is not guaranteed
        # unique repo-wide, and requiring axis_alive>0 AND allies_alive>0
        # silently excluded the exact kill that wipes the enemy side to 0
        # (the actual last-man clutch payoff!). Same fixes already applied
        # in scripts/backtest_clutch_v1.py (codex, PR #474/#478 follow-up
        # audit finding #2).
        rows = await self.db.fetch_all(
            "SELECT g8, SUM(kis) FROM ("
            "  SELECT DISTINCT ON (ki.id)"
            "         UPPER(LEFT(ki.killer_guid, 8)) AS g8,"
            "         ki.total_impact AS kis "
            "  FROM storytelling_kill_impact ki "
            "  JOIN proximity_combat_position cp "
            "    ON cp.round_start_unix = ki.round_start_unix "
            "   AND cp.session_date = ki.session_date "
            "   AND cp.round_number = ki.round_number "
            "   AND cp.map_name = ki.map_name "
            "   AND UPPER(LEFT(cp.attacker_guid, 8)) = UPPER(LEFT(ki.killer_guid, 8)) "
            "   AND UPPER(LEFT(cp.victim_guid, 8)) = UPPER(LEFT(ki.victim_guid, 8)) "
            "   AND ABS(cp.event_time - ki.kill_time_ms) <= 300 "
            "  WHERE ki.session_date >= ?::date "
            "    AND ((cp.attacker_team = 'AXIS' AND cp.axis_alive = 1)"
            "      OR (cp.attacker_team = 'ALLIES' AND cp.allies_alive = 1)) "
            "    AND ki.killer_guid NOT LIKE ? AND ki.killer_name NOT LIKE ? "
            "  ORDER BY ki.id, ABS(cp.event_time - ki.kill_time_ms)"
            ") solo GROUP BY g8",
            (_dt.date.fromisoformat(ALIVE_CONTEXT_SINCE), *_BOTS),
        )
        return {r[0]: float(r[1] or 0) for r in (rows or [])}

    async def _ois_counts(self) -> dict[str, float]:
        """All-time OIS with base values (see module docstring)."""
        out: dict[str, float] = {}
        rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(returner_guid, 8)), COUNT(*) "
            "FROM proximity_carrier_return "
            "WHERE returner_guid IS NOT NULL AND returner_guid NOT LIKE ? "
            "GROUP BY 1",
            (_BOTS[0],),
        )
        for r in rows or []:
            out[r[0]] = out.get(r[0], 0.0) + 3.0 * int(r[1])
        rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(player_guid, 8)), event_type, COUNT(*) "
            "FROM proximity_construction_event "
            "WHERE event_type IN ('dynamite_defuse', 'construction_complete') "
            "  AND player_guid IS NOT NULL AND player_guid NOT LIKE ? "
            "GROUP BY 1, 2",
            (_BOTS[0],),
        )
        for r in rows or []:
            base = 2.5 if r[1] == "dynamite_defuse" else 2.0
            out[r[0]] = out.get(r[0], 0.0) + base * int(r[2])
        return out

    async def _permanence(self) -> dict[str, float]:
        rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(killer_guid, 8)) AS g8,"
            "       COUNT(*) FILTER (WHERE outcome = 'gibbed')::REAL"
            "       / NULLIF(COUNT(*), 0) AS gib "
            "FROM proximity_kill_outcome "
            "WHERE killer_guid NOT LIKE ? AND killer_name NOT LIKE ? "
            "GROUP BY UPPER(LEFT(killer_guid, 8)) HAVING COUNT(*) >= 30",
            _BOTS,
        )
        return {r[0]: float(r[1] or 0) for r in (rows or [])}

    async def _target_acq(self) -> dict[str, float]:
        rows = await self.db.fetch_all(
            "SELECT g8, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY acq_ms) "
            "FROM ("
            "  SELECT DISTINCT ON (ko.id)"
            "         UPPER(al.guid_canonical) AS g8,"
            "         (ko.kill_time - al.start_time) AS acq_ms "
            "  FROM proximity_aim_lock al "
            "  JOIN proximity_kill_outcome ko "
            "    ON ko.round_start_unix = al.round_start_unix "
            "   AND ko.session_date = al.session_date "
            "   AND ko.round_number = al.round_number "
            "   AND ko.killer_guid_canonical = al.guid_canonical "
            "   AND UPPER(SUBSTRING(ko.victim_guid, 1, 8)) ="
            "       UPPER(SUBSTRING(al.target_guid, 1, 8)) "
            "   AND ko.kill_time BETWEEN al.start_time AND al.end_time + 1000 "
            "  WHERE al.round_start_unix > 0 AND al.session_date >= ?::date "
            "    AND al.guid NOT LIKE ? AND al.player_name NOT LIKE ? "
            "    AND al.target_guid NOT LIKE ? "
            "    AND ko.kill_time > al.start_time "
            "  ORDER BY ko.id, al.start_time DESC"
            ") j GROUP BY g8 HAVING COUNT(*) >= ?",
            (_dt.date.fromisoformat(AIM_LOCK_LIVE_SINCE), *_BOTS, _BOTS[0],
             MIN_ACQ_EVENTS),
        )
        return {r[0]: float(r[1]) for r in (rows or [])}

    async def _spawn_ready(self) -> dict[str, float]:
        rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(pt.player_guid, 8)) AS g8,"
            "       PERCENTILE_CONT(0.5) WITHIN GROUP"
            "       (ORDER BY pt.time_to_first_move_ms) "
            "FROM player_track pt "
            "JOIN rounds r ON r.id = pt.round_id AND r.is_valid "
            "WHERE pt.time_to_first_move_ms > 0 "
            "  AND pt.time_to_first_move_ms <= 5000 "
            "  AND pt.spawn_time_ms >= 0 "
            "  AND pt.player_guid NOT LIKE ? AND pt.player_name NOT LIKE ? "
            "GROUP BY UPPER(LEFT(pt.player_guid, 8)) HAVING COUNT(*) >= ?",
            (*_BOTS, MIN_SPAWN_LIVES),
        )
        return {r[0]: float(r[1]) for r in (rows or [])}

    async def _opening_net(self) -> dict[str, float]:
        """Net first-kill rate per rounds PLAYED (duels-v0.1 + #467 r3 fixes:
        matched valid rounds only, ALL kills tied at the round minimum credit
        every participant, denominator from PCS presence).

        Canonical round key includes map_name (round_start_unix alone is
        not guaranteed unique repo-wide — codex, PR #478 follow-up audit
        finding #3)."""
        openings = await self.db.fetch_all(
            "WITH k AS ("
            "  SELECT ki.round_start_unix, ki.round_number, ki.map_name,"
            "         ki.kill_time_ms,"
            "         UPPER(LEFT(ki.killer_guid, 8)) AS killer,"
            "         UPPER(LEFT(ki.victim_guid, 8)) AS victim "
            "  FROM storytelling_kill_impact ki "
            "  JOIN rounds r ON r.round_start_unix = ki.round_start_unix "
            "               AND r.round_number = ki.round_number "
            "               AND r.map_name = ki.map_name "
            "               AND r.is_valid "
            "               AND NOT COALESCE(r.is_bot_round, FALSE) "
            "  WHERE ki.round_start_unix > 0 "
            "    AND ki.killer_guid NOT LIKE ? AND ki.victim_guid NOT LIKE ? "
            "    AND ki.killer_name NOT LIKE ? "
            "    AND COALESCE(ki.victim_name, '') NOT LIKE ? "
            ") "
            "SELECT killer, victim FROM k "
            "WHERE (round_start_unix, map_name, round_number, kill_time_ms) IN ("
            "    SELECT round_start_unix, map_name, round_number, MIN(kill_time_ms) "
            "    FROM k GROUP BY round_start_unix, map_name, round_number)",
            (_BOTS[0], _BOTS[0], _BOTS[1], _BOTS[1]),
        )
        presence_rows = await self.db.fetch_all(
            "SELECT UPPER(LEFT(p.player_guid, 8)) AS g8, COUNT(*) "
            "FROM player_comprehensive_stats p "
            "JOIN rounds r ON r.id = p.round_id "
            "WHERE r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE) "
            "  AND r.round_start_unix > 0 "
            "  AND p.round_number > 0 "
            "  AND p.player_guid NOT LIKE ? AND p.player_name NOT LIKE ? "
            "GROUP BY UPPER(LEFT(p.player_guid, 8))",
            _BOTS,
        )
        wins: dict[str, int] = {}
        losses: dict[str, int] = {}
        for o in openings or []:
            wins[o[0]] = wins.get(o[0], 0) + 1
            losses[o[1]] = losses.get(o[1], 0) + 1
        out = {}
        for row in presence_rows or []:
            g8, n = row[0], int(row[1])
            if n >= MIN_DUEL_ROUNDS:
                out[g8] = (wins.get(g8, 0) - losses.get(g8, 0)) / n
        return out

    async def _trade_discipline(self) -> dict[str, float]:
        """Share of own deaths avenged in the trade window (duels-v0.1)."""
        deaths = await self.db.fetch_all(
            "SELECT UPPER(LEFT(ko.victim_guid, 8)) AS g8, COUNT(*) "
            "FROM proximity_kill_outcome ko "
            "JOIN rounds r ON r.id = ko.round_id AND r.is_valid "
            "WHERE TRUE "
            "  AND ko.victim_guid NOT LIKE ? AND ko.victim_name NOT LIKE ? "
            "GROUP BY UPPER(LEFT(ko.victim_guid, 8)) HAVING COUNT(*) >= ?",
            (*_BOTS, MIN_DEATHS),
        )
        avenged = await self.db.fetch_all(
            "SELECT UPPER(LEFT(tk.original_victim_guid, 8)),"
            "       COUNT(DISTINCT (tk.round_id, tk.original_kill_time)) "
            "FROM proximity_lua_trade_kill tk "
            "JOIN rounds r ON r.id = tk.round_id AND r.is_valid "
            "WHERE TRUE "
            "  AND tk.original_victim_guid IS NOT NULL "
            "  AND tk.original_victim_guid NOT LIKE ? "
            "GROUP BY 1",
            (_BOTS[0],),
        )
        av = {r[0]: int(r[1]) for r in (avenged or [])}
        return {r[0]: min(av.get(r[0], 0), int(r[1])) / int(r[1])
                for r in (deaths or [])}

    async def compute(self) -> dict:
        """Rated SSR list + meta. Group-relative; see module docstring."""
        sessions = await self._sessions()
        rated = {g for g, (_n, cnt) in sessions.items() if cnt >= MIN_SESSIONS}

        shares = await self._kis_shares()
        clutch = await self._clutch_kis()
        ois = await self._ois_counts()
        perm = await self._permanence()
        acq = await self._target_acq()
        spawn = await self._spawn_ready()
        duels = await self._opening_net()
        trades = await self._trade_discipline()

        def _per_session(m: dict[str, float]) -> dict[str, float]:
            return {g: v / sessions[g][1] for g, v in m.items() if g in rated}

        comp_values = {
            "clutch_kis_ps": _per_session(clutch),
            "situational_share": {g: v for g, v in shares.items() if g in rated},
            "ois_ps": _per_session(ois),
            "permanence": {g: v for g, v in perm.items() if g in rated},
            "target_acq_ms": {g: v for g, v in acq.items() if g in rated},
            "spawn_ready_ms": {g: v for g, v in spawn.items() if g in rated},
            "opening_net": {g: v for g, v in duels.items() if g in rated},
            "trade_discipline": {g: v for g, v in trades.items() if g in rated},
        }
        lower_better = {"target_acq_ms", "spawn_ready_ms"}
        comp_pcts = {
            name: _pct_ranks(vals, lower_is_better=name in lower_better)
            for name, vals in comp_values.items() if vals
        }

        players = []
        for g in sorted(rated):
            comps = {}
            pcts = []
            for name in comp_values:
                raw = comp_values[name].get(g)
                pct = comp_pcts.get(name, {}).get(g)
                comps[name] = {
                    "raw": round(raw, 4) if raw is not None else None,
                    "pct": pct,
                }
                if pct is not None:
                    pcts.append(pct)
            if len(pcts) < MIN_COMPONENTS:
                continue  # insufficient coverage — component gates tell why
            players.append({
                "player_guid": g,
                "name": sessions[g][0],
                "n_sessions": sessions[g][1],
                "ssr": round(sum(pcts) / len(pcts), 4),
                "coverage": f"{len(pcts)}/{len(comp_values)}",
                "components": comps,
            })
        players.sort(key=lambda p: -p["ssr"])
        return {
            "formula_version": FORMULA_VERSION,
            "min_sessions": MIN_SESSIONS,
            "min_components": MIN_COMPONENTS,
            "rated": len(players),
            "players": players,
        }
