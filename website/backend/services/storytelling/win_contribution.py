"""StorytellingService mixin: win_contribution methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    _to_date,
    _to_date_str,
    date,
    strip_et_colors,
)


class _WinContributionMixin:
    """Win Contribution methods for StorytellingService."""

    async def compute_win_contribution(self, session_date: str | date) -> dict:
        """Compute Player Win Contribution v2 for every player in a session.

        v2 adds proximity-derived components: crossfire share, trade share,
        clutch share (28% combined weight, inspired by HLTV 2.1 / FACEIT RWS).

        Returns dict with 'mvp', 'players' list (sorted by total_pwc desc),
        and 'session_date'.
        """
        sd_str = _to_date_str(session_date)
        sd_date = _to_date(session_date)

        # 1. Fetch per-player per-round stats from PCS joined with rounds
        rows = await self.db.fetch_all("""
            SELECT pcs.player_guid, pcs.player_name, pcs.round_number,
                   r.map_name, pcs.team, r.winner_team,
                   pcs.kills, pcs.damage_given,
                   COALESCE(pcs.objectives_completed, 0)
                     + COALESCE(pcs.objectives_destroyed, 0)
                     + COALESCE(pcs.objectives_stolen, 0)
                     + COALESCE(pcs.objectives_returned, 0)
                     + COALESCE(pcs.dynamites_planted, 0)
                     + COALESCE(pcs.dynamites_defused, 0)
                     + COALESCE(pcs.constructions, 0) AS objectives,
                   pcs.revives_given,
                   GREATEST(pcs.time_played_minutes - COALESCE(pcs.time_dead_minutes, 0), 0.01)
                     AS time_alive_minutes,
                   r.id AS round_id,
                   r.round_start_unix
            FROM player_comprehensive_stats pcs
            JOIN rounds r ON r.id = pcs.round_id
            WHERE pcs.round_date = $1
              AND pcs.round_number IN (1, 2)
              AND r.round_number IN (1, 2)
              AND pcs.time_played_seconds > 0
            ORDER BY r.id, pcs.player_guid
        """, (sd_str,))

        # 1b. Fetch proximity data for proximity PWC components
        # Crossfire kills per player per round (via guid_canonical)
        xf_rows = await self.db.fetch_all("""
            SELECT killer_guid_canonical, round_start_unix, COUNT(*) as xf_kills
            FROM storytelling_kill_impact
            WHERE session_date = $1 AND is_crossfire = true AND killer_guid_canonical IS NOT NULL
            GROUP BY killer_guid_canonical, round_start_unix
        """, (sd_date,))
        xf_map: dict[tuple[str, int], int] = {
            (r[0], int(r[1])): int(r[2]) for r in xf_rows
        }

        # Trade kills per player per round (via guid_canonical)
        tr_rows = await self.db.fetch_all("""
            SELECT trader_guid_canonical, round_start_unix, COUNT(*) as tr_kills
            FROM proximity_lua_trade_kill
            WHERE session_date = $1 AND trader_guid_canonical IS NOT NULL
            GROUP BY trader_guid_canonical, round_start_unix
        """, (sd_date,))
        tr_map: dict[tuple[str, int], int] = {
            (r[0], int(r[1])): int(r[2]) for r in tr_rows
        }

        # Clutch kills per player per round (via guid_canonical)
        cl_rows = await self.db.fetch_all("""
            SELECT attacker_guid_canonical, round_start_unix, COUNT(*) as cl_kills
            FROM proximity_combat_position
            WHERE session_date = $1 AND event_type = 'kill'
              AND attacker_guid_canonical IS NOT NULL
              AND ((killer_health > 0 AND killer_health < 30)
                   OR (attacker_team = 'AXIS' AND axis_alive < allies_alive)
                   OR (attacker_team = 'ALLIES' AND allies_alive < axis_alive))
            GROUP BY attacker_guid_canonical, round_start_unix
        """, (sd_date,))
        cl_map: dict[tuple[str, int], int] = {
            (r[0], int(r[1])): int(r[2]) for r in cl_rows
        }

        if not rows:
            return {"session_date": sd_str, "mvp": None, "players": []}

        # 2. Group by round_id to compute team totals
        from collections import defaultdict

        # round_id → list of player rows
        rounds_map: dict[int, list] = defaultdict(list)
        for r in rows:
            rounds_map[r[11]].append(r)  # r[11] = round_id

        # 3. Compute PWC per player per round
        # player_guid → {name, per_round: [...], total_pwc, won_pwc, lost_pwc, rounds_won, rounds_lost}
        player_data: dict[str, dict] = {}

        for round_id, round_rows in rounds_map.items():
            winner_team = round_rows[0][5]  # same for all rows in this round
            map_name = round_rows[0][3]
            round_number = round_rows[0][2]
            round_start = int(round_rows[0][12] or 0)  # round_start_unix

            # Team totals (per team integer: 1=Allies, 2=Axis)
            team_kills: dict[int, int] = defaultdict(int)
            team_damage: dict[int, int] = defaultdict(int)
            team_objectives: dict[int, int] = defaultdict(int)
            team_revives: dict[int, int] = defaultdict(int)
            team_alive: dict[int, float] = defaultdict(float)
            team_count: dict[int, int] = defaultdict(int)
            # Proximity team totals
            team_crossfire: dict[int, int] = defaultdict(int)
            team_trade: dict[int, int] = defaultdict(int)
            team_clutch: dict[int, int] = defaultdict(int)

            for r in round_rows:
                t = r[4]  # team
                guid = r[0]
                team_kills[t] += int(r[6] or 0)
                team_damage[t] += int(r[7] or 0)
                team_objectives[t] += int(r[8] or 0)
                team_revives[t] += int(r[9] or 0)
                team_alive[t] += float(r[10] or 0)
                team_count[t] += 1
                # Sum proximity per team for this round
                team_crossfire[t] += xf_map.get((guid, round_start), 0)
                team_trade[t] += tr_map.get((guid, round_start), 0)
                team_clutch[t] += cl_map.get((guid, round_start), 0)

            # Check if objectives are zero for ALL players in this round
            all_objectives_zero = all(int(r[8] or 0) == 0 for r in round_rows)

            for r in round_rows:
                guid = r[0]
                name = strip_et_colors(r[1] or guid[:8])
                t = r[4]
                p_kills = int(r[6] or 0)
                p_damage = int(r[7] or 0)
                p_objectives = int(r[8] or 0)
                p_revives = int(r[9] or 0)
                p_alive = float(r[10] or 0)

                # Proximity per-player counts for this round
                p_crossfire = xf_map.get((guid, round_start), 0)
                p_trade = tr_map.get((guid, round_start), 0)
                p_clutch = cl_map.get((guid, round_start), 0)

                tk = team_kills[t]
                td = team_damage[t]
                to = team_objectives[t]
                trev = team_revives[t]
                team_avg_alive = team_alive[t] / max(team_count[t], 1)
                txf = team_crossfire[t]
                ttr = team_trade[t]
                tcl = team_clutch[t]

                # Share = player / team; 0 when team total is 0
                # (avoids inflating score to absolute values)
                kill_share = p_kills / tk if tk > 0 else 0.0
                damage_share = p_damage / td if td > 0 else 0.0
                obj_share = p_objectives / to if to > 0 else 0.0
                revive_share = p_revives / trev if trev > 0 else 0.0
                survival_share = min(p_alive / team_avg_alive, 2.0) if team_avg_alive > 0.01 else 0.0
                crossfire_share = p_crossfire / txf if txf > 0 else 0.0
                trade_share = p_trade / ttr if ttr > 0 else 0.0
                clutch_share = p_clutch / tcl if tcl > 0 else 0.0

                # PWC v2: PCS (72%) + proximity (28%)
                if all_objectives_zero:
                    # Redistribute 0.20 objectives across kills/damage/revives
                    pwc = ((self._PWC_W_KILLS + 0.06) * kill_share
                           + (self._PWC_W_DAMAGE + 0.03) * damage_share
                           + (self._PWC_W_REVIVES + 0.03) * revive_share
                           + (self._PWC_W_SURVIVAL + 0.02) * survival_share
                           + (self._PWC_W_CROSSFIRE + 0.03) * crossfire_share
                           + (self._PWC_W_TRADE + 0.03) * trade_share
                           + self._PWC_W_CLUTCH * clutch_share)
                else:
                    pwc = (self._PWC_W_KILLS * kill_share
                           + self._PWC_W_DAMAGE * damage_share
                           + self._PWC_W_OBJECTIVES * obj_share
                           + self._PWC_W_REVIVES * revive_share
                           + self._PWC_W_SURVIVAL * survival_share
                           + self._PWC_W_CROSSFIRE * crossfire_share
                           + self._PWC_W_TRADE * trade_share
                           + self._PWC_W_CLUTCH * clutch_share)

                won = (t == winner_team and winner_team in (1, 2))

                if guid not in player_data:
                    player_data[guid] = {
                        "guid": guid,
                        "name": name,
                        "total_pwc": 0.0,
                        "won_pwc": 0.0,
                        "lost_pwc": 0.0,
                        "rounds_won": 0,
                        "rounds_lost": 0,
                        "per_round": [],
                        "components": {
                            "kills": 0.0, "damage": 0.0,
                            "objectives": 0.0, "revives": 0.0,
                            "survival": 0.0, "crossfire": 0.0,
                            "trade": 0.0, "clutch": 0.0,
                        },
                    }
                else:
                    # Update name to latest non-empty
                    if name and name != guid[:8]:
                        player_data[guid]["name"] = name

                pd = player_data[guid]
                pd["total_pwc"] += pwc
                if won:
                    pd["won_pwc"] += pwc
                    pd["rounds_won"] += 1
                else:
                    pd["lost_pwc"] += pwc
                    pd["rounds_lost"] += 1

                # Accumulate component contributions for stacked bars
                if all_objectives_zero:
                    pd["components"]["kills"] += (self._PWC_W_KILLS + 0.06) * kill_share
                    pd["components"]["damage"] += (self._PWC_W_DAMAGE + 0.03) * damage_share
                    pd["components"]["revives"] += (self._PWC_W_REVIVES + 0.03) * revive_share
                    pd["components"]["survival"] += (self._PWC_W_SURVIVAL + 0.02) * survival_share
                    pd["components"]["crossfire"] += (self._PWC_W_CROSSFIRE + 0.03) * crossfire_share
                    pd["components"]["trade"] += (self._PWC_W_TRADE + 0.03) * trade_share
                else:
                    pd["components"]["kills"] += self._PWC_W_KILLS * kill_share
                    pd["components"]["damage"] += self._PWC_W_DAMAGE * damage_share
                    pd["components"]["objectives"] += self._PWC_W_OBJECTIVES * obj_share
                    pd["components"]["revives"] += self._PWC_W_REVIVES * revive_share
                    pd["components"]["survival"] += self._PWC_W_SURVIVAL * survival_share
                    pd["components"]["crossfire"] += self._PWC_W_CROSSFIRE * crossfire_share
                    pd["components"]["trade"] += self._PWC_W_TRADE * trade_share
                pd["components"]["clutch"] += self._PWC_W_CLUTCH * clutch_share

                pd["per_round"].append({
                    "round_number": round_number,
                    "map_name": map_name,
                    "pwc": round(pwc, 4),
                    "won": won,
                    "kills": p_kills,
                    "damage": p_damage,
                    "objectives": p_objectives,
                    "revives": p_revives,
                })

        # 4. Compute WIS v2 (Win Impact Score) per player
        #    WIS = (avg_won - avg_lost) * confidence
        #    confidence = harmonic_balance of win/loss counts, so unbalanced
        #    samples (e.g. 1 win + 3 losses) get dampened WIS.
        players_list = []
        for guid, pd in player_data.items():
            total_rounds = pd["rounds_won"] + pd["rounds_lost"]
            rw = pd["rounds_won"]
            rl = pd["rounds_lost"]

            if total_rounds < 2:
                wis = 0.0  # insufficient data
            else:
                avg_won = pd["won_pwc"] / max(rw, 1)
                avg_lost = pd["lost_pwc"] / max(rl, 1)
                # Harmonic balance: 1.0 when rw==rl, lower when imbalanced
                if rw > 0 and rl > 0:
                    reliability = 2 * rw * rl / (rw + rl)
                    confidence = min(reliability / (total_rounds / 2), 1.0)
                else:
                    confidence = 0.0  # all wins or all losses → no contrast
                wis = (avg_won - avg_lost) * confidence

            waa = pd["won_pwc"] / max(total_rounds, 1)

            players_list.append({
                "guid": pd["guid"],
                "name": pd["name"],
                "total_pwc": round(pd["total_pwc"], 3),
                "wis": round(wis, 3),
                "waa": round(waa, 3),
                "rounds_won": rw,
                "rounds_lost": rl,
                "total_rounds": total_rounds,
                "components": {k: round(v, 3) for k, v in pd["components"].items()},
                "per_round": pd["per_round"],
            })

        # Sort by total_pwc descending
        players_list.sort(key=lambda p: p["total_pwc"], reverse=True)

        # 5. Session MVP — Bayesian WAA with minimum round eligibility
        #    Bayesian prior (C=2) regresses small-sample players toward
        #    session average, preventing 1-round late-joiners from MVP.
        #    Eligibility: must have played >=50% of max rounds in session
        #    and won at least 1 round.
        mvp = None
        if players_list:
            max_rounds_played = max(
                p["total_rounds"] for p in players_list
            )
            min_rounds_for_mvp = max(2, max_rounds_played // 2)

            # Session average PWC per round (prior for Bayesian)
            total_session_pwc = sum(p["total_pwc"] for p in players_list)
            total_session_rounds = sum(p["total_rounds"] for p in players_list)
            session_avg_pwc = (
                total_session_pwc / total_session_rounds
                if total_session_rounds > 0
                else 0.0
            )

            _BAYES_C = 2  # phantom rounds — prior weight

            for p in players_list:
                # Bayesian WAA: shrink toward session average
                p["waa_bayes"] = round(
                    (p["waa"] * p["total_rounds"] + _BAYES_C * session_avg_pwc)
                    / (p["total_rounds"] + _BAYES_C),
                    3,
                )

            mvp_candidates = [
                p for p in players_list
                if p["rounds_won"] > 0
                and p["total_rounds"] >= min_rounds_for_mvp
            ]
            if mvp_candidates:
                mvp_player = max(
                    mvp_candidates,
                    key=lambda p: (
                        float(p["waa_bayes"]),
                        p["total_pwc"],
                        p["rounds_won"],
                    ),
                )
            else:
                # Fallback: best total_pwc (list already sorted)
                mvp_player = players_list[0]
            mvp = {
                "guid": mvp_player["guid"],
                "name": mvp_player["name"],
                "total_pwc": mvp_player["total_pwc"],
                "wis": mvp_player["wis"],
            }

        return {
            "session_date": sd_str,
            "mvp": mvp,
            "players": players_list,
        }

