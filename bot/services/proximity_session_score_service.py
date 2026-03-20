"""
Proximity Session Score Service

Computes per-player composite combat scores from proximity analytics data
for a given session_date. Aggregates 7 categories into a 0-100 score.

Used by both the Discord bot (!psession) and the website API (/proximity/session-scores).
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Category weights (must sum to 1.0)
WEIGHTS = {
    "kill_timing": 0.25,
    "crossfire": 0.15,
    "focus_fire": 0.10,
    "trades": 0.15,
    "survivability": 0.15,
    "movement": 0.10,
    "reactions": 0.10,
}

MIN_ENGAGEMENTS = 3  # exclude players with fewer engagements


class ProximitySessionScoreService:
    def __init__(self, db_adapter):
        self.db = db_adapter

    async def get_latest_session_date(self) -> Optional[str]:
        row = await self.db.fetch_one(
            "SELECT MAX(session_date)::TEXT FROM combat_engagement"
        )
        return row[0] if row and row[0] else None

    async def compute_session_scores(self, session_date: str) -> List[Dict]:
        names: Dict[str, str] = {}
        scores: Dict[str, Dict] = {}  # guid -> {category: raw_value, ...}

        def ensure(guid, name=None):
            if guid not in scores:
                scores[guid] = {}
            if name and (guid not in names or names[guid] in ("", None)):
                names[guid] = name

        # ── 1. Engagement base (survivability + player roster) ───────────
        eng_rows = await self.db.fetch_all(
            """
            SELECT target_guid, MAX(target_name) AS name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) AS escapes
            FROM combat_engagement
            WHERE session_date = $1
            GROUP BY target_guid
            HAVING COUNT(*) >= $2
            """,
            (session_date, MIN_ENGAGEMENTS),
        )
        guid_set = set()
        for r in (eng_rows or []):
            guid, name, total, escapes = r[0], r[1], int(r[2] or 0), int(r[3] or 0)
            guid_set.add(guid)
            ensure(guid, name)
            escape_rate = (escapes / max(total, 1)) * 100
            scores[guid]["survivability"] = min(escape_rate, 100)
            scores[guid]["_engagements"] = total
            scores[guid]["_escapes"] = escapes

        if not guid_set:
            return []

        # ── 2. Kill timing (with impact breakdown) ─────────────────────
        timing_rows = await self.db.fetch_all(
            """
            SELECT killer_guid, MAX(killer_name),
                   AVG(spawn_timing_score) AS avg_score,
                   COUNT(*) AS kills,
                   SUM(CASE WHEN spawn_timing_score >= 0.7 THEN 1 ELSE 0 END) AS high_impact,
                   SUM(CASE WHEN spawn_timing_score < 0.3 THEN 1 ELSE 0 END) AS low_impact
            FROM proximity_spawn_timing
            WHERE session_date = $1
            GROUP BY killer_guid
            """,
            (session_date,),
        )
        for r in (timing_rows or []):
            guid, name = r[0], r[1]
            if guid not in guid_set:
                continue
            ensure(guid, name)
            avg_s = float(r[2] or 0)
            kills = int(r[3] or 0)
            high = int(r[4] or 0)
            low = int(r[5] or 0)
            dampener = min(kills / 5.0, 1.0)
            scores[guid]["kill_timing"] = avg_s * 100 * dampener
            scores[guid]["_timing_kills"] = kills
            scores[guid]["_timing_avg"] = round(avg_s, 3)
            scores[guid]["_timing_high"] = high
            scores[guid]["_timing_low"] = low

        # ── 3. Crossfire execution ───────────────────────────────────────
        cf_rows = await self.db.fetch_all(
            """
            SELECT guid, SUM(cnt) AS total FROM (
                SELECT teammate1_guid AS guid, COUNT(*) AS cnt
                FROM proximity_crossfire_opportunity
                WHERE was_executed = true AND session_date = $1
                GROUP BY teammate1_guid
                UNION ALL
                SELECT teammate2_guid AS guid, COUNT(*) AS cnt
                FROM proximity_crossfire_opportunity
                WHERE was_executed = true AND session_date = $1
                GROUP BY teammate2_guid
            ) sub GROUP BY guid
            """,
            (session_date,),
        )
        for r in (cf_rows or []):
            guid = r[0]
            if guid not in guid_set:
                continue
            count = int(r[1] or 0)
            scores[guid]["crossfire"] = min(count / 5.0, 1.0) * 100
            scores[guid]["_cf_count"] = count

        # ── 4. Focus fire ────────────────────────────────────────────────
        try:
            ff_rows = await self.db.fetch_all(
                """
                SELECT target_guid, MAX(target_name),
                       AVG(focus_score) AS avg_score,
                       COUNT(*) AS events
                FROM proximity_focus_fire
                WHERE session_date = $1
                GROUP BY target_guid
                """,
                (session_date,),
            )
            for r in (ff_rows or []):
                guid = r[0]
                if guid not in guid_set:
                    continue
                ensure(guid, r[1])
                avg_ff = float(r[2] or 0)
                events = int(r[3] or 0)
                dampener = min(events / 3.0, 1.0)
                scores[guid]["focus_fire"] = avg_ff * 100 * dampener
                scores[guid]["_ff_events"] = events
        except Exception:
            pass  # table may not exist yet

        # ── 5. Trade kills (spawn-timing-weighted) ────────────────────
        # Cross-join trade kills with spawn timing to weight each trade
        # by how long the killed enemy will be out (high score = impactful trade)
        trade_rows = await self.db.fetch_all(
            """
            SELECT tk.trader_guid, MAX(tk.trader_name),
                   COUNT(*) AS trade_count,
                   AVG(COALESCE(NULLIF(st.spawn_timing_score, 0), 0.5)) AS avg_trade_timing,
                   SUM(CASE WHEN st.spawn_timing_score >= 0.7 THEN 1 ELSE 0 END) AS high_impact,
                   SUM(CASE WHEN st.spawn_timing_score < 0.3 AND st.spawn_timing_score > 0 THEN 1 ELSE 0 END) AS low_impact
            FROM proximity_lua_trade_kill tk
            LEFT JOIN proximity_spawn_timing st
              ON st.session_date = tk.session_date
              AND st.round_number = tk.round_number
              AND st.round_start_unix = tk.round_start_unix
              AND st.killer_guid = tk.trader_guid
              AND st.kill_time = tk.traded_kill_time
            WHERE tk.session_date = $1
            GROUP BY tk.trader_guid
            """,
            (session_date,),
        )
        for r in (trade_rows or []):
            guid, name = r[0], r[1]
            if guid not in guid_set:
                continue
            ensure(guid, name)
            count = int(r[2] or 0)
            avg_timing = float(r[3] or 0.5)
            high = int(r[4] or 0)
            low = int(r[5] or 0)
            # Weighted score: count matters, but quality (spawn timing) amplifies
            # A player with 2 high-impact trades scores higher than 5 useless trades
            quantity_score = min(count / 3.0, 1.0)  # 0-1 based on count
            quality_score = avg_timing               # 0-1 based on avg spawn timing
            scores[guid]["trades"] = (quantity_score * 0.4 + quality_score * 0.6) * 100
            scores[guid]["_trade_count"] = count
            scores[guid]["_trade_timing"] = round(avg_timing, 3)
            scores[guid]["_trade_high"] = high
            scores[guid]["_trade_low"] = low

        # ── 6. Movement ──────────────────────────────────────────────────
        move_rows = await self.db.fetch_all(
            """
            SELECT player_guid, MAX(player_name),
                   AVG(sprint_percentage) AS sp,
                   AVG(avg_speed) AS spd
            FROM player_track
            WHERE session_date = $1
            GROUP BY player_guid
            """,
            (session_date,),
        )
        for r in (move_rows or []):
            guid, name = r[0], r[1]
            if guid not in guid_set:
                continue
            ensure(guid, name)
            sp = float(r[2] or 0)
            spd = float(r[3] or 0)
            raw = sp * 0.6 + min(spd / 300, 1.0) * 100 * 0.4
            scores[guid]["movement"] = min(raw, 100)
            scores[guid]["_sprint_pct"] = round(sp, 1)
            scores[guid]["_avg_speed"] = round(spd, 1)

        # ── 7. Reactions ─────────────────────────────────────────────────
        react_rows = await self.db.fetch_all(
            """
            SELECT target_guid, MAX(target_name),
                   AVG(return_fire_ms) AS avg_rf
            FROM proximity_reaction_metric
            WHERE return_fire_ms IS NOT NULL AND session_date = $1
            GROUP BY target_guid
            """,
            (session_date,),
        )
        for r in (react_rows or []):
            guid, name = r[0], r[1]
            if guid not in guid_set:
                continue
            ensure(guid, name)
            avg_rf = float(r[2] or 3000)
            raw = max(0, 100 - avg_rf / 30)
            scores[guid]["reactions"] = min(raw, 100)
            scores[guid]["_avg_rf_ms"] = round(avg_rf)

        # ── Composite scoring ────────────────────────────────────────────
        results = []
        for guid in guid_set:
            ps = scores.get(guid, {})
            categories = {}
            total = 0.0

            for cat, weight in WEIGHTS.items():
                raw = ps.get(cat, 0.0)
                weighted = round(raw * weight, 1)
                total += weighted
                categories[cat] = {"raw": round(raw, 1), "weighted": weighted}

            # Add detail strings
            eng_total = ps.get("_engagements", 0)
            eng_esc = ps.get("_escapes", 0)
            tk = ps.get('_timing_kills', 0)
            th = ps.get('_timing_high', 0)
            tl = ps.get('_timing_low', 0)
            categories["kill_timing"]["detail"] = f"avg {ps.get('_timing_avg', 0)}, {tk} kills ({th} high/{tl} low impact)"
            categories["crossfire"]["detail"] = f"{ps.get('_cf_count', 0)} executed"
            categories["focus_fire"]["detail"] = f"{ps.get('_ff_events', 0)} events" if ps.get("_ff_events") else "no data"
            tc = ps.get('_trade_count', 0)
            trh = ps.get('_trade_high', 0)
            trl = ps.get('_trade_low', 0)
            categories["trades"]["detail"] = f"{tc} trades (timing {ps.get('_trade_timing', 0)}, {trh} high/{trl} useless)"
            categories["survivability"]["detail"] = f"{eng_esc}/{eng_total} escaped"
            categories["movement"]["detail"] = f"sprint {ps.get('_sprint_pct', 0)}%, {ps.get('_avg_speed', 0)} u/s"
            categories["reactions"]["detail"] = f"{ps.get('_avg_rf_ms', 0)}ms avg"

            results.append({
                "guid": guid,
                "name": names.get(guid, guid[:8]),
                "total_score": round(total, 1),
                "categories": categories,
                "engagement_count": eng_total,
            })

        results.sort(key=lambda x: x["total_score"], reverse=True)
        return results
