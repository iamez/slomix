"""Good Night Index v0 — rate the EVENING, not the players.

Phase 1 of the Good Night Engine plan (docs/SLOMIX_GOOD_NIGHT_ENGINE_PLAN,
algorithm family 1), productized from scripts/backtest_good_night.py after
the owner tone review (2026-07-05; backtested range 46-88 over 20 sessions,
close multi-player nights on top, stomps at the bottom).

    good_night = .25*balance + .20*tension + .15*attendance + .15*story
               + .10*flow + .10*variety + .05*participation

Computed on read — no schema. Copy is neutral English (owner decision).
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class GoodNightService:
    def __init__(self, db):
        self.db = db

    async def compute(self, gaming_session_id: int) -> dict[str, Any] | None:
        rounds = await self.db.fetch_all(
            """
            SELECT round_number, match_id, map_name,
                   COALESCE(actual_duration_seconds, 0), round_start_unix
            FROM rounds
            WHERE gaming_session_id = $1 AND is_valid
              -- same legal-round predicate as the session-detail endpoints:
              -- 'substitution' rounds and legacy NULL statuses still count
              AND (round_status IN ('completed', 'substitution')
                   OR round_status IS NULL)
              AND round_number IN (1, 2)
            ORDER BY round_start_unix
            """,
            (gaming_session_id,),
        )
        pairs: dict[str, dict[int, tuple]] = {}
        stamped = []
        for rn, match_id, map_name, secs, start_unix in rounds or []:
            if start_unix:
                stamped.append((int(start_unix), int(secs or 0)))
            if match_id:
                pairs.setdefault(match_id, {})[int(rn)] = (map_name, int(secs or 0))
        matches = [p for p in pairs.values() if 1 in p and 2 in p]
        if not matches or not stamped:
            return None

        sr = await self.db.fetch_one(
            "SELECT round_details FROM session_results "
            "WHERE gaming_session_id = $1 ORDER BY id DESC LIMIT 1",
            (gaming_session_id,),
        )
        wins_a = wins_b = draws = 0
        has_details = bool(sr and sr[0])
        if has_details:
            try:
                for m in json.loads(sr[0]) if isinstance(sr[0], str) else sr[0]:
                    if m.get("counted") is False:
                        continue
                    pa = int(m.get("team_a_points", m.get("team1_points", 0)) or 0)
                    pb = int(m.get("team_b_points", m.get("team2_points", 0)) or 0)
                    if pa > pb:
                        wins_a += 1
                    elif pb > pa:
                        wins_b += 1
                    else:
                        draws += 1
            except (TypeError, ValueError):
                has_details = False

        # balance (neutral 50 when the win/loss signal is unavailable)
        map_closeness = (100 - min(100, abs(wins_a - wins_b) * 25)) if has_details else 50
        diffs = [abs(p[1][1] - p[2][1]) for p in matches]
        round_closeness = sum(100 - min(100, d / 6) for d in diffs) / len(diffs)
        balance = 0.6 * map_closeness + 0.4 * round_closeness

        # tension
        close_maps = sum(1 for d in diffs if d <= 30)
        stomp_maps = sum(1 for d in diffs if d >= 240)
        decider = 15 if (has_details and abs(wins_a - wins_b) <= 1) else 0
        tension = _clamp(close_maps * 18 + draws * 22 + decider - stomp_maps * 12)

        # attendance
        players = await self.db.fetch_one(
            """
            SELECT COUNT(DISTINCT p.player_guid)
            FROM player_comprehensive_stats p
            JOIN rounds r ON r.id = p.round_id
            WHERE r.gaming_session_id = $1 AND r.is_valid
              AND p.player_guid NOT LIKE 'OMNIBOT%'
              AND p.player_name NOT LIKE '[BOT]%'
            """,
            (gaming_session_id,),
        )
        n_players = int(players[0] or 0) if players else 0
        attendance = 100 if n_players >= 10 else 85 if n_players >= 8 else 70 if n_players >= 6 else 45

        t0 = min(s for s, _ in stamped)
        t1 = max(s + d for s, d in stamped)
        hours = max(0.5, (t1 - t0) / 3600.0)

        # story density — KIS spikes + carrier kills per hour (v0 proxy;
        # midnight-safe via round_start_unix, bots excluded)
        # portable IN(...) placeholders instead of PG-only ANY($1) — the
        # local SQLite adapter executes SQL verbatim
        starts = [s for s, _ in stamped]
        ph = ", ".join(f"${i + 2}" for i in range(len(starts)))
        mom = await self.db.fetch_one(
            f"""
            SELECT COUNT(*) FROM storytelling_kill_impact
            WHERE (total_impact >= $1 OR is_carrier_kill)
              AND round_start_unix IN ({ph})
              AND killer_guid NOT LIKE 'OMNIBOT%'
              AND killer_name NOT LIKE '[BOT]%'
            """,
            (3.0, *starts),
        )
        moments = int(mom[0] or 0) if mom else 0
        story = _clamp(moments / hours * 18 / 4)

        # flow — invalid rounds + long between-round gaps (end -> next start)
        inv = await self.db.fetch_one(
            "SELECT COUNT(*) FROM rounds WHERE gaming_session_id = $1 AND is_valid IS FALSE",
            (gaming_session_id,),
        )
        spans = sorted((s, s + d) for s, d in stamped)
        long_gaps = sum(1 for a, b in zip(spans, spans[1:]) if b[0] - a[1] > 25 * 60)
        flow = _clamp(100 - int(inv[0] or 0) * 20 - long_gaps * 10)

        # variety
        distinct_maps = len({p[1][0] for p in matches})
        both_won = 10 if (wins_a > 0 and wins_b > 0) else 0
        variety = _clamp(distinct_maps * 18 + both_won)

        # participation (MVP votes + bets)
        votes = await self.db.fetch_one(
            "SELECT COUNT(*) FROM session_mvp_votes WHERE gaming_session_id = $1",
            (gaming_session_id,),
        )
        bets = await self.db.fetch_one(
            "SELECT COUNT(*) FROM parimutuel_bets b "
            "JOIN parimutuel_markets m ON m.id = b.market_id "
            "WHERE m.gaming_session_id = $1",
            (gaming_session_id,),
        )
        participation = _clamp((int(votes[0] or 0) + int(bets[0] or 0)) * 10)

        score = (0.25 * balance + 0.20 * tension + 0.15 * attendance
                 + 0.15 * story + 0.10 * flow + 0.10 * variety
                 + 0.05 * participation)

        # Friendship-safe reason chips: positive or neutral facts only
        reasons: list[str] = []
        if has_details and abs(wins_a - wins_b) <= 1:
            reasons.append("close teams")
        if draws:
            reasons.append(f"{draws} drawn map{'s' if draws != 1 else ''}")
        if close_maps:
            reasons.append(f"{close_maps} tight finish{'es' if close_maps != 1 else ''}")
        reasons.append(f"{n_players} players")
        reasons.append(f"{len(matches)} maps in {hours:.1f}h")
        if moments >= 40:
            reasons.append("plenty of big moments")
        if distinct_maps >= 5:
            reasons.append("good map variety")

        return {
            "gaming_session_id": gaming_session_id,
            "score": round(score),
            "components": {
                "balance": round(balance), "tension": round(tension),
                "attendance": round(attendance), "story": round(story),
                "flow": round(flow), "variety": round(variety),
                "participation": round(participation),
            },
            "reasons": reasons[:5],
            "maps": len(matches),
            "players": n_players,
            "hours": round(hours, 1),
        }
