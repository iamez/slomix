"""
Session Graph Generator - Creates beautiful performance graphs

This service generates 5 themed graph images:
1. Combat Stats (Offense) - Kills/Deaths grouped, Damage grouped, K/D, DPM
2. Combat Stats (Defense/Support) - Revives grouped, Time grouped, Gibs, Headshots
3. Advanced Metrics - FragPotential, Damage Efficiency, Denied Playtime, Survival Rate, Useful Kills, Self Kills, Full Selfkills
4. Playstyle Analysis - Player Playstyles + Legend
5. DPM Timeline - Performance evolution over rounds
"""

import io
import inspect
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Any, Dict, List, Optional, Tuple

from bot.core.frag_potential import FragPotentialCalculator

logger = logging.getLogger("bot.services.session_graph_generator")


class SessionGraphGenerator:
    """Service for generating beautiful performance graphs"""

    # Color palette - Discord-inspired dark theme
    COLORS = {
        'bg_dark': '#2b2d31',
        'bg_panel': '#1e1f22',
        'green': '#57F287',
        'red': '#ED4245',
        'blue': '#5865F2',
        'yellow': '#FEE75C',
        'orange': '#F39C12',
        'pink': '#EB459E',
        'purple': '#9B59B6',
        'cyan': '#3498DB',
        'teal': '#1ABC9C',
        'gray': '#95A5A6',
    }

    def __init__(
        self,
        db_adapter,
        timing_debug_service=None,
        timing_shadow_service=None,
        show_timing_dual: bool = False
    ):
        self.db_adapter = db_adapter
        self.timing_debug_service = timing_debug_service
        self.timing_shadow_service = timing_shadow_service
        self.show_timing_dual = bool(show_timing_dual)

    async def _get_player_stats_columns(self):
        """Get columns for player_comprehensive_stats (cached)."""
        if hasattr(self, "_player_stats_columns"):
            return self._player_stats_columns

        try:
            cols = await self.db_adapter.fetch_all("PRAGMA table_info(player_comprehensive_stats)")
            self._player_stats_columns = {c[1] for c in cols}
            return self._player_stats_columns
        except Exception:
            pass

        try:
            cols = await self.db_adapter.fetch_all(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'player_comprehensive_stats'
                """
            )
            self._player_stats_columns = {c[0] for c in cols}
            return self._player_stats_columns
        except Exception:
            self._player_stats_columns = set()
            return self._player_stats_columns

    @staticmethod
    def _parse_time_to_seconds(time_value: Any) -> int:
        """Parse MM:SS / HH:MM:SS / numeric to seconds."""
        if time_value is None:
            return 0
        text = str(time_value).strip()
        if not text:
            return 0
        try:
            parts = text.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            if "." in text:
                return int(float(text) * 60)
            return int(float(text))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _row_get(row: Any, idx: int, key: str, default: Any = None) -> Any:
        """Read tuple/dict row values safely."""
        if isinstance(row, dict):
            return row.get(key, default)
        try:
            return row[idx]
        except Exception:
            return default

    async def _call_service_method(self, method_name: str, *args, **kwargs) -> Tuple[bool, Any]:
        """Call timing shadow service method if it exists."""
        if not self.timing_shadow_service:
            return False, None
        method = getattr(self.timing_shadow_service, method_name, None)
        if not method:
            return False, None
        result = method(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return True, result

    def _normalize_round_factor_payload(self, payload: Any) -> Dict[int, float]:
        """Normalize service payload into round_id->factor mapping."""
        factors: Dict[int, float] = {}
        if payload is None:
            return factors

        raw = payload
        if isinstance(payload, dict):
            for key in ("round_factors", "factors", "by_round"):
                if key in payload and isinstance(payload[key], (dict, list)):
                    raw = payload[key]
                    break

        if isinstance(raw, dict):
            for round_id, factor in raw.items():
                try:
                    rid = int(round_id)
                    fval = float(factor)
                except (TypeError, ValueError):
                    continue
                if fval > 0:
                    factors[rid] = max(0.0, min(2.0, fval))
            return factors

        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                round_id = item.get("round_id") or item.get("id")
                factor = (
                    item.get("factor")
                    or item.get("correction_factor")
                    or item.get("duration_factor")
                )
                try:
                    rid = int(round_id)
                    fval = float(factor)
                except (TypeError, ValueError):
                    continue
                if fval > 0:
                    factors[rid] = max(0.0, min(2.0, fval))
        return factors

    async def _get_round_timing_shadow(self, session_ids: List[int]) -> Dict[str, Any]:
        """Build round-level timing correction factors from shadow/comparison service."""
        result: Dict[str, Any] = {
            "factors": {},
            "rounds_total": len(session_ids or []),
            "rounds_with_telemetry": 0,
            "reason": "",
            "source": "none",
        }
        if not session_ids:
            result["reason"] = "No rounds provided"
            return result
        if not self.timing_shadow_service:
            result["reason"] = "Timing shadow service unavailable"
            return result

        for method_name in (
            "get_session_round_timing_factors",
            "get_round_timing_factors_for_session",
            "get_session_round_factors",
        ):
            called, payload = await self._call_service_method(method_name, session_ids=session_ids)
            if not called:
                continue
            factors = self._normalize_round_factor_payload(payload)
            if factors:
                result["factors"] = factors
                result["rounds_with_telemetry"] = len(factors)
                if len(factors) < len(session_ids):
                    result["reason"] = f"Lua timing missing for {len(session_ids) - len(factors)}/{len(session_ids)} rounds"
                else:
                    result["reason"] = "OK"
                result["source"] = method_name
                return result

        if not hasattr(self.timing_shadow_service, "_fetch_lua_data"):
            result["reason"] = "Timing service does not expose round comparison data"
            return result

        placeholders = ",".join("?" for _ in session_ids)
        rounds_query = f"""
            SELECT r.id, r.map_name, r.round_number, r.round_date, r.round_time, r.actual_time
            FROM rounds r
            WHERE r.id IN ({placeholders})
        """
        round_rows = await self.db_adapter.fetch_all(rounds_query, tuple(session_ids))
        for row in round_rows:
            round_id = int(self._row_get(row, 0, "id", 0) or 0)
            map_name = self._row_get(row, 1, "map_name", "unknown") or "unknown"
            round_number = int(self._row_get(row, 2, "round_number", 0) or 0)
            round_date = self._row_get(row, 3, "round_date", "")
            round_time = self._row_get(row, 4, "round_time", "")
            actual_time = self._row_get(row, 5, "actual_time", "")

            stats_seconds = self._parse_time_to_seconds(actual_time)
            if hasattr(self.timing_shadow_service, "_fetch_stats_file_data"):
                try:
                    stats_data = await self.timing_shadow_service._fetch_stats_file_data(round_id)
                except Exception:  # nosec B110
                    stats_data = None
                if isinstance(stats_data, dict):
                    map_name = stats_data.get("map_name") or map_name
                    round_number = int(stats_data.get("round_number") or round_number or 0)
                    round_date = stats_data.get("round_date") or round_date
                    round_time = stats_data.get("round_time") or round_time
                    stats_seconds = int(stats_data.get("stats_duration_seconds") or stats_seconds or 0)

            try:
                lua_data = await self.timing_shadow_service._fetch_lua_data(
                    round_id,
                    map_name,
                    round_number,
                    round_date,
                    round_time,
                )
            except Exception:  # nosec B110
                lua_data = None

            lua_seconds = None
            if isinstance(lua_data, dict):
                try:
                    lua_seconds_raw = lua_data.get("lua_duration_seconds")
                    lua_seconds = int(lua_seconds_raw) if lua_seconds_raw is not None else None
                except (TypeError, ValueError):
                    lua_seconds = None

            if stats_seconds > 0 and lua_seconds and lua_seconds > 0:
                factor = max(0.0, min(2.0, float(lua_seconds) / float(stats_seconds)))
                result["factors"][round_id] = factor
                result["rounds_with_telemetry"] += 1

        missing_rounds = len(session_ids) - result["rounds_with_telemetry"]
        if result["rounds_with_telemetry"] == 0:
            result["reason"] = "No Lua timing telemetry linked to this session"
        elif missing_rounds > 0:
            result["reason"] = f"Lua timing missing for {missing_rounds}/{len(session_ids)} rounds"
        else:
            result["reason"] = "OK"
        result["source"] = "compat_fetch"
        return result

    async def _get_session_timing_dual_by_guid(self, session_ids: List[int]) -> Dict[str, Any]:
        """Build per-player old/new timing aggregates for graph dual-mode."""
        payload: Dict[str, Any] = {
            "players": {},
            "meta": {
                "rounds_total": len(session_ids or []),
                "rounds_with_telemetry": 0,
                "reason": "",
                "source": "none",
            },
        }
        if not session_ids:
            payload["meta"]["reason"] = "No rounds provided"
            return payload

        called, shadow_result = await self._call_service_method("compare_session", session_ids)
        if called and shadow_result is not None:
            players: Dict[str, Dict[str, Any]] = {}
            round_diagnostics = tuple(getattr(shadow_result, "round_diagnostics", ()) or ())
            rounds_total = len(round_diagnostics)
            rounds_with_telemetry = sum(
                1 for diag in round_diagnostics if int(getattr(diag, "players_with_lua", 0) or 0) > 0
            )

            for summary in tuple(getattr(shadow_result, "player_summaries", ()) or ()):
                guid_key = str(getattr(summary, "player_guid", "") or "")
                entry = {
                    "old_time_dead_seconds": int(getattr(summary, "old_dead_seconds", 0) or 0),
                    "new_time_dead_seconds": int(getattr(summary, "new_dead_seconds", 0) or 0),
                    "old_denied_seconds": int(getattr(summary, "old_denied_playtime", 0) or 0),
                    "new_denied_seconds": int(getattr(summary, "new_denied_playtime", 0) or 0),
                }
                players[guid_key] = entry
                guid_prefix = guid_key[:8]
                if guid_prefix and guid_prefix not in players:
                    players[guid_prefix] = entry

            if rounds_total == 0:
                reason = "No round diagnostics"
            elif rounds_with_telemetry == 0:
                reason = "No Lua telemetry linked to this session"
            elif rounds_with_telemetry < rounds_total:
                reason = f"Lua timing partial {rounds_with_telemetry}/{rounds_total} rounds"
            else:
                reason = "OK"

            payload["players"] = players
            payload["meta"] = {
                "rounds_total": rounds_total,
                "rounds_with_telemetry": rounds_with_telemetry,
                "reason": reason,
                "source": "compare_session",
                "overall_coverage_percent": float(
                    getattr(shadow_result, "overall_coverage_percent", 0.0) or 0.0
                ),
                "artifact_path": getattr(shadow_result, "artifact_path", None),
            }
            return payload

        shadow = await self._get_round_timing_shadow(session_ids)
        round_factors = shadow.get("factors", {}) or {}
        payload["meta"]["rounds_with_telemetry"] = int(shadow.get("rounds_with_telemetry") or 0)
        payload["meta"]["reason"] = shadow.get("reason") or ""
        payload["meta"]["source"] = shadow.get("source") or "none"

        placeholders = ",".join("?" for _ in session_ids)
        query = f"""
            SELECT p.player_guid,
                p.round_id,
                SUM(COALESCE(p.time_played_seconds, 0)) as time_played_seconds,
                SUM(
                    LEAST(
                        COALESCE(p.time_dead_minutes, 0) * 60,
                        COALESCE(p.time_played_seconds, 0)
                    )
                ) as time_dead_old_seconds,
                SUM(COALESCE(p.denied_playtime, 0)) as denied_old_seconds
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({placeholders})
            GROUP BY p.player_guid, p.round_id
        """
        rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

        for row in rows:
            guid = self._row_get(row, 0, "player_guid")
            if not guid:
                continue
            round_id = int(self._row_get(row, 1, "round_id", 0) or 0)
            played = int(self._row_get(row, 2, "time_played_seconds", 0) or 0)
            dead_old = int(round(float(self._row_get(row, 3, "time_dead_old_seconds", 0) or 0)))
            denied_old = int(round(float(self._row_get(row, 4, "denied_old_seconds", 0) or 0)))
            dead_old = max(0, min(dead_old, played if played > 0 else dead_old))
            denied_old = max(0, min(denied_old, played if played > 0 else denied_old))

            factor = round_factors.get(round_id)
            if factor is not None:
                dead_new = int(round(dead_old * factor))
                denied_new = int(round(denied_old * factor))
                dead_new = max(0, min(dead_new, played if played > 0 else dead_new))
                denied_new = max(0, min(denied_new, played if played > 0 else denied_new))
            else:
                dead_new = dead_old
                denied_new = denied_old

            entry = payload["players"].setdefault(
                guid,
                {
                    "old_time_dead_seconds": 0,
                    "new_time_dead_seconds": 0,
                    "old_denied_seconds": 0,
                    "new_denied_seconds": 0,
                },
            )
            entry["old_time_dead_seconds"] += dead_old
            entry["new_time_dead_seconds"] += dead_new
            entry["old_denied_seconds"] += denied_old
            entry["new_denied_seconds"] += denied_new

        return payload

    def _style_axis(self, ax, title: str, title_size: int = 13):
        """Apply beautiful dark theme styling"""
        ax.set_title(title, fontweight="bold", color='white',
                     fontsize=title_size, pad=10)
        ax.set_facecolor(self.COLORS['bg_panel'])
        ax.tick_params(colors='white', labelsize=9)
        for spine in ['bottom', 'left']:
            ax.spines[spine].set_color('#404249')
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        ax.grid(True, alpha=0.15, color='white', axis='y', linestyle='--')

    def _add_bar_labels(self, ax, bars, values, fmt="{:.0f}", offset=0):
        """Add white value labels on top of bars"""
        for bar, value in zip(bars, values):
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2., height,
                    fmt.format(value),
                    ha='center', va='bottom', color='white',
                    fontsize=8, fontweight='bold'
                )

    def _add_grouped_bar_labels(self, ax, bars1, bars2, values1, values2, 
                                 fmt="{:.0f}"):
        """Add labels for grouped bars"""
        for bar, value in zip(bars1, values1):
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        fmt.format(value), ha='center', va='bottom',
                        color='white', fontsize=7, fontweight='bold')
        for bar, value in zip(bars2, values2):
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        fmt.format(value), ha='center', va='bottom',
                        color='white', fontsize=7, fontweight='bold')

    async def generate_performance_graphs(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str
    ) -> Tuple[Optional[io.BytesIO], Optional[io.BytesIO],
               Optional[io.BytesIO], Optional[io.BytesIO],
               Optional[io.BytesIO]]:
        """
        Generate FIVE beautiful graph images:
        
        Image 1: COMBAT STATS (OFFENSE) - 2x2
            - Kills vs Deaths (grouped bars)
            - Damage Given vs Received (grouped bars)
            - K/D Ratio
            - DPM
            
        Image 2: COMBAT STATS (DEFENSE/SUPPORT) - 2x2
            - Revives Given vs Times Revived (grouped bars)
            - Time Played vs Time Dead (grouped bars)
            - Gibs
            - Headshots
            
        Image 3: ADVANCED METRICS - 3x2
            - FragPotential
            - Damage Efficiency
            - Denied Playtime
            - Survival Rate
            - Useful Kills (UK)
            - Self Kills vs Full Selfkills
            
        Image 4: PLAYSTYLE ANALYSIS
            - Player Playstyles (horizontal bars - full width)
            - Playstyle Legend
            
        Image 5: DPM TIMELINE
            - DPM evolution line graph
            - Session Form Analysis
        
        Returns: Tuple of 5 buffers
        """
        try:
            # Comprehensive query with all needed stats
            columns = await self._get_player_stats_columns()
            has_full_selfkills = "full_selfkills" in columns
            full_selfkills_select = (
                "SUM(COALESCE(p.full_selfkills, 0)) as full_selfkills"
                if has_full_selfkills
                else "0 as full_selfkills"
            )
            placeholders = ','.join(['?' for _ in session_ids])
            query = f"""
                SELECT MAX(p.player_name) as player_name,
                       SUM(p.kills) as kills,
                       SUM(p.deaths) as deaths,
                       SUM(p.damage_given) as damage_given,
                       SUM(p.damage_received) as damage_received,
                       CASE
                           WHEN SUM(p.time_played_seconds) > 0
                           THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                           ELSE 0
                       END as dpm,
                       SUM(p.time_played_seconds) as time_played,
                       -- Use stored time_dead_minutes directly (already calculated with R2 differential)
                       -- Cap at time_played to prevent edge cases where time_dead > time_played
                       SUM(
                           LEAST(
                               COALESCE(p.time_dead_minutes, 0),
                               p.time_played_seconds / 60.0
                           )
                       ) as time_dead_minutes,
                       SUM(p.revives_given) as revives_given,
                       SUM(p.times_revived) as times_revived,
                       SUM(p.gibs) as gibs,
                       SUM(COALESCE(p.headshots, p.headshot_kills, 0)) as headshots,
                       SUM(COALESCE(p.denied_playtime, 0)) as denied_playtime,
                       SUM(COALESCE(p.most_useful_kills, 0)) as useful_kills,
                       SUM(COALESCE(p.self_kills, 0)) as self_kills,
                       {full_selfkills_select},
                       p.player_guid,
                       COUNT(DISTINCT p.round_id) as rounds_played
                FROM player_comprehensive_stats p
                WHERE p.round_id IN ({placeholders})
                GROUP BY p.player_guid
                ORDER BY kills DESC
                LIMIT 16
            """
            top_players = await self.db_adapter.fetch_all(
                query, tuple(session_ids)
            )

            if not top_players:
                return None, None, None, None, None

            # Extract all data arrays (keep full names for matching)
            # Handle None names - use player_guid as fallback
            names = [(p[0] or p[16] or f"Player_{i}") for i, p in enumerate(top_players)]
            display_names = [str(n)[:12] for n in names]
            player_guids = [p[16] or "" for p in top_players]
            kills = [p[1] or 0 for p in top_players]
            deaths = [p[2] or 0 for p in top_players]
            damage_given = [p[3] or 0 for p in top_players]
            damage_received = [p[4] or 0 for p in top_players]
            dpm = [p[5] or 0 for p in top_players]
            time_played_sec = [p[6] or 0 for p in top_players]
            time_played = [t / 60 for t in time_played_sec]
            time_dead_old_minutes = [p[7] or 0 for p in top_players]
            revives_given = [p[8] or 0 for p in top_players]
            times_revived = [p[9] or 0 for p in top_players]
            gibs = [p[10] or 0 for p in top_players]
            headshots = [p[11] or 0 for p in top_players]
            denied_playtime_old_sec = [p[12] or 0 for p in top_players]
            useful_kills = [p[13] or 0 for p in top_players]
            self_kills = [p[14] or 0 for p in top_players]
            full_selfkills = [p[15] or 0 for p in top_players]
            rounds_played = [p[17] or 1 for p in top_players]

            # Shadow timing payload for dual-mode graphs
            dual_shadow_note = ""
            dual_players: Dict[str, Dict[str, Any]] = {}
            if self.show_timing_dual:
                dual_payload = await self._get_session_timing_dual_by_guid(session_ids)
                dual_players = dual_payload.get("players", {}) or {}
                dual_meta = dual_payload.get("meta", {}) or {}
                rounds_total = int(dual_meta.get("rounds_total") or len(session_ids or []))
                rounds_with_telemetry = int(dual_meta.get("rounds_with_telemetry") or 0)
                if rounds_with_telemetry <= 0:
                    dual_shadow_note = "No Lua telemetry linked; New mirrors Old."
                elif rounds_with_telemetry < rounds_total:
                    dual_shadow_note = (
                        f"Lua telemetry for {rounds_with_telemetry}/{rounds_total} rounds; "
                        "missing rounds mirror Old."
                    )

            time_dead_old_sec = [int(round((v or 0) * 60)) for v in time_dead_old_minutes]
            time_dead_new_sec = []
            denied_playtime_new_sec = []
            for idx, guid in enumerate(player_guids):
                old_dead_sec = time_dead_old_sec[idx]
                old_denied_sec = int(denied_playtime_old_sec[idx] or 0)
                played_sec = int(time_played_sec[idx] or 0)
                shadow = dual_players.get(guid, {}) if self.show_timing_dual else {}

                dead_new = int(shadow.get("new_time_dead_seconds", old_dead_sec) or 0)
                denied_new = int(shadow.get("new_denied_seconds", old_denied_sec) or 0)
                if played_sec > 0:
                    dead_new = max(0, min(dead_new, played_sec))
                    denied_new = max(0, min(denied_new, played_sec))
                else:
                    dead_new = max(0, dead_new)
                    denied_new = max(0, denied_new)

                time_dead_new_sec.append(dead_new)
                denied_playtime_new_sec.append(denied_new)

            time_dead_new_minutes = [v / 60.0 for v in time_dead_new_sec]
            denied_playtime_pct_old = [
                (dp / max(1, tp)) * 100 for dp, tp in zip(denied_playtime_old_sec, time_played_sec)
            ]
            denied_playtime_pct_new = [
                (dp / max(1, tp)) * 100 for dp, tp in zip(denied_playtime_new_sec, time_played_sec)
            ]

            # Baseline metrics keep legacy timing to preserve existing behavior when flag is off
            kd_ratios = [k / max(1, d) for k, d in zip(kills, deaths)]
            time_dead_minutes = time_dead_old_minutes
            time_dead = time_dead_minutes
            time_alive = [max(0, tp - td) for tp, td in zip(time_played, time_dead)]
            survival_rate = [
                100 - (td / max(0.01, tp) * 100) if tp > 0 else 0
                for td, tp in zip(time_dead_old_minutes, time_played)
            ]
            survival_rate_new = [
                100 - (td / max(0.01, tp) * 100) if tp > 0 else 0
                for td, tp in zip(time_dead_new_minutes, time_played)
            ]

            # ═══════════════════════════════════════════════════════════════════
            # TIME DEBUG: Validate time values are consistent
            # ═══════════════════════════════════════════════════════════════════
            logger.info("═" * 70)
            logger.info("TIME DEBUG: Graph data validation")
            logger.info("═" * 70)
            for i, name in enumerate(names):
                tp = time_played[i]
                td = time_dead[i]
                ta = time_alive[i]
                # Validate: time_alive + time_dead should equal time_played
                sum_check = ta + td
                diff = abs(sum_check - tp)
                status = "✅" if diff < 0.1 else "⚠️ MISMATCH"
                logger.info(
                    f"[TIME] {name[:15]:15} | "
                    f"played={tp:6.1f}min | dead={td:6.1f}min | alive={ta:6.1f}min | "
                    f"alive+dead={sum_check:6.1f} | {status}"
                )
                if diff >= 0.1:
                    logger.warning(
                        f"[TIME MISMATCH] {name}: time_played={tp:.2f} != alive+dead={sum_check:.2f} (diff={diff:.2f})"
                    )
            logger.info("═" * 70)

            dmg_eff = [
                dg / max(1, dr)
                for dg, dr in zip(damage_given, damage_received)
            ]

            # Calculate FragPotential and Playstyles
            frag_potentials = []
            playstyles = []
            avg_deaths = sum(deaths) / len(deaths) if deaths else 0
            avg_revives = sum(revives_given) / len(revives_given) if revives_given else 0

            from bot.core.frag_potential import PlayerMetrics
            for i, p in enumerate(top_players):
                # Calculate time_dead_ratio from time_dead_minutes and time_played
                time_dead_ratio_calc = (time_dead_minutes[i] / max(0.01, time_played[i]) * 100) if time_played[i] > 0 else 0

                fp = FragPotentialCalculator.calculate_frag_potential(
                    damage_given=damage_given[i],
                    time_played_seconds=time_played_sec[i],
                    time_dead_ratio=time_dead_ratio_calc,
                    time_dead_minutes=time_dead_minutes[i]
                )
                frag_potentials.append(fp)

                metrics = PlayerMetrics(
                    player_name=p[0],
                    player_guid=p[13] or "",
                    kills=kills[i],
                    deaths=deaths[i],
                    damage_given=damage_given[i],
                    damage_received=damage_received[i],
                    time_played_seconds=time_played_sec[i],
                    time_dead_ratio=time_dead_ratio_calc,
                    time_dead_minutes=time_dead_minutes[i],
                    revives_given=revives_given[i],
                    headshot_kills=headshots[i],
                    objectives_completed=0,
                )

                style, _ = FragPotentialCalculator.determine_playstyle(
                    metrics,
                    session_avg_deaths=avg_deaths,
                    session_avg_revives=avg_revives,
                    rounds_played=rounds_played[i]
                )
                playstyles.append(style)

            n_players = len(names)
            x = np.arange(n_players)
            bar_width = 0.35

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 1: COMBAT STATS (OFFENSE) - 2x2 with grouped bars
            # ═══════════════════════════════════════════════════════════════
            fig1, axes1 = plt.subplots(2, 2, figsize=(14, 10))
            fig1.patch.set_facecolor(self.COLORS['bg_dark'])
            fig1.suptitle(
                f"COMBAT STATS (OFFENSE)  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Kills vs Deaths (grouped)
            bars1 = axes1[0, 0].bar(x - bar_width/2, kills, bar_width,
                                     color=self.COLORS['green'], label='Kills',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes1[0, 0].bar(x + bar_width/2, deaths, bar_width,
                                     color=self.COLORS['red'], label='Deaths',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[0, 0], "KILLS vs DEATHS")
            axes1[0, 0].set_xticks(x)
            axes1[0, 0].set_xticklabels(display_names, rotation=45, ha="right")
            axes1[0, 0].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes1[0, 0], bars1, bars2, kills, deaths)

            # Damage Given vs Received (grouped)
            bars1 = axes1[0, 1].bar(x - bar_width/2, damage_given, bar_width,
                                     color=self.COLORS['blue'], label='Given',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes1[0, 1].bar(x + bar_width/2, damage_received, bar_width,
                                     color=self.COLORS['orange'], label='Received',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[0, 1], "DAMAGE GIVEN vs RECEIVED")
            axes1[0, 1].set_xticks(x)
            axes1[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
            axes1[0, 1].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes1[0, 1], bars1, bars2,
                                          damage_given, damage_received, "{:,.0f}")

            # K/D Ratio
            kd_colors = [
                self.COLORS['green'] if kd >= 1.5
                else self.COLORS['yellow'] if kd >= 1.0
                else self.COLORS['red']
                for kd in kd_ratios
            ]
            bars = axes1[1, 0].bar(x, kd_ratios, color=kd_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[1, 0], "K/D RATIO")
            axes1[1, 0].axhline(y=1.0, color="white", linestyle="--",
                                 alpha=0.5, linewidth=1)
            axes1[1, 0].set_xticks(x)
            axes1[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes1[1, 0], bars, kd_ratios, fmt="{:.2f}")

            # DPM
            bars = axes1[1, 1].bar(x, dpm, color=self.COLORS['cyan'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[1, 1], "DPM (Damage Per Minute)")
            axes1[1, 1].set_xticks(x)
            axes1[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes1[1, 1], bars, dpm)

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf1 = io.BytesIO()
            plt.savefig(buf1, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf1.seek(0)
            plt.close(fig1)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 2: COMBAT STATS (DEFENSE/SUPPORT) - 2x2 with grouped bars
            # ═══════════════════════════════════════════════════════════════
            fig2, axes2 = plt.subplots(2, 2, figsize=(14, 10))
            fig2.patch.set_facecolor(self.COLORS['bg_dark'])
            fig2.suptitle(
                f"COMBAT STATS (DEFENSE/SUPPORT)  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Revives Given vs Times Revived (grouped)
            bars1 = axes2[0, 0].bar(x - bar_width/2, revives_given, bar_width,
                                     color=self.COLORS['green'], label='Given',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes2[0, 0].bar(x + bar_width/2, times_revived, bar_width,
                                     color=self.COLORS['teal'], label='Received',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[0, 0], "REVIVES GIVEN vs RECEIVED")
            axes2[0, 0].set_xticks(x)
            axes2[0, 0].set_xticklabels(display_names, rotation=45, ha="right")
            axes2[0, 0].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes2[0, 0], bars1, bars2,
                                          revives_given, times_revived)

            if self.show_timing_dual:
                bars1 = axes2[0, 1].bar(
                    x - bar_width/2,
                    time_dead_old_minutes,
                    bar_width,
                    color=self.COLORS['pink'],
                    label='Dead (Old)',
                    edgecolor='white',
                    linewidth=0.5,
                )
                bars2 = axes2[0, 1].bar(
                    x + bar_width/2,
                    time_dead_new_minutes,
                    bar_width,
                    color=self.COLORS['cyan'],
                    label='Dead (New)',
                    edgecolor='white',
                    linewidth=0.5,
                )
                self._style_axis(axes2[0, 1], "TIME DEAD OLD vs NEW (minutes)")
                axes2[0, 1].set_xticks(x)
                axes2[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
                axes2[0, 1].legend(
                    loc='upper right',
                    facecolor=self.COLORS['bg_panel'],
                    edgecolor='white',
                    labelcolor='white',
                )
                self._add_grouped_bar_labels(
                    axes2[0, 1],
                    bars1,
                    bars2,
                    time_dead_old_minutes,
                    time_dead_new_minutes,
                    "{:.1f}",
                )
            else:
                # Legacy graph behavior (flag off): Alive vs Dead
                bars1 = axes2[0, 1].bar(x - bar_width/2, time_alive, bar_width,
                                         color=self.COLORS['cyan'], label='Alive',
                                         edgecolor='white', linewidth=0.5)
                bars2 = axes2[0, 1].bar(x + bar_width/2, time_dead, bar_width,
                                         color=self.COLORS['pink'], label='Dead',
                                         edgecolor='white', linewidth=0.5)
                self._style_axis(axes2[0, 1], "TIME ALIVE vs DEAD (minutes)")
                axes2[0, 1].set_xticks(x)
                axes2[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
                axes2[0, 1].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                                   edgecolor='white', labelcolor='white')
                self._add_grouped_bar_labels(axes2[0, 1], bars1, bars2,
                                              time_alive, time_dead, "{:.1f}")

            # Gibs
            bars = axes2[1, 0].bar(x, gibs, color=self.COLORS['red'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[1, 0], "GIBS")
            axes2[1, 0].set_xticks(x)
            axes2[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes2[1, 0], bars, gibs)

            # Headshots
            bars = axes2[1, 1].bar(x, headshots, color=self.COLORS['purple'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[1, 1], "HEADSHOTS")
            axes2[1, 1].set_xticks(x)
            axes2[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes2[1, 1], bars, headshots)
            if self.show_timing_dual and dual_shadow_note:
                fig2.text(0.01, 0.01, f"Dual timing note: {dual_shadow_note}",
                          color='#B0B0B0', fontsize=8)

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf2 = io.BytesIO()
            plt.savefig(buf2, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf2.seek(0)
            plt.close(fig2)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 3: ADVANCED METRICS - 3x2
            # ═══════════════════════════════════════════════════════════════
            fig3, axes3 = plt.subplots(3, 2, figsize=(14, 14))
            fig3.patch.set_facecolor(self.COLORS['bg_dark'])
            fig3.suptitle(
                f"ADVANCED METRICS  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # FragPotential
            fp_colors = [style.color for style in playstyles]
            bars = axes3[0, 0].bar(x, frag_potentials, color=fp_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[0, 0], "FRAGPOTENTIAL (DPM While Alive)")
            axes3[0, 0].set_xticks(x)
            axes3[0, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[0, 0], bars, frag_potentials)

            # Damage Efficiency
            eff_colors = [
                self.COLORS['green'] if e >= 1.5
                else self.COLORS['yellow'] if e >= 1.0
                else self.COLORS['red']
                for e in dmg_eff
            ]
            bars = axes3[0, 1].bar(x, dmg_eff, color=eff_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[0, 1], "DAMAGE EFFICIENCY")
            axes3[0, 1].axhline(y=1.0, color="white", linestyle="--",
                                 alpha=0.5, linewidth=1)
            axes3[0, 1].set_xticks(x)
            axes3[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[0, 1], bars, dmg_eff, fmt="{:.2f}x")

            if self.show_timing_dual:
                timing_bar_width = 0.35
                bars1 = axes3[1, 0].bar(
                    x - timing_bar_width/2,
                    denied_playtime_pct_old,
                    timing_bar_width,
                    color=self.COLORS['orange'],
                    label='Old',
                    edgecolor='white',
                    linewidth=0.5,
                )
                bars2 = axes3[1, 0].bar(
                    x + timing_bar_width/2,
                    denied_playtime_pct_new,
                    timing_bar_width,
                    color=self.COLORS['teal'],
                    label='New',
                    edgecolor='white',
                    linewidth=0.5,
                )
                self._style_axis(axes3[1, 0], "TIME DENIED % (OLD vs NEW)")
                max_denied = max(max(denied_playtime_pct_old), max(denied_playtime_pct_new), 1)
                axes3[1, 0].set_ylim(0, max(50, max_denied * 1.2))
                axes3[1, 0].set_xticks(x)
                axes3[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
                axes3[1, 0].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                                   edgecolor='white', labelcolor='white')
                self._add_grouped_bar_labels(
                    axes3[1, 0],
                    bars1,
                    bars2,
                    denied_playtime_pct_old,
                    denied_playtime_pct_new,
                    fmt="{:.1f}%",
                )
            else:
                # Denied Playtime (as percentage)
                denied_colors = [
                    self.COLORS['red'] if d >= 30
                    else self.COLORS['orange'] if d >= 15
                    else self.COLORS['green']
                    for d in denied_playtime_pct_old
                ]
                bars = axes3[1, 0].bar(x, denied_playtime_pct_old, color=denied_colors,
                                        edgecolor='white', linewidth=0.5)
                self._style_axis(axes3[1, 0], "TIME DENIED (%)")
                axes3[1, 0].set_ylim(0, max(50, max(denied_playtime_pct_old) * 1.2))
                axes3[1, 0].set_xticks(x)
                axes3[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
                self._add_bar_labels(axes3[1, 0], bars, denied_playtime_pct_old,
                                     fmt="{:.1f}%")

            if self.show_timing_dual:
                timing_bar_width = 0.35
                bars1 = axes3[1, 1].bar(
                    x - timing_bar_width/2,
                    survival_rate,
                    timing_bar_width,
                    color=self.COLORS['yellow'],
                    label='Old',
                    edgecolor='white',
                    linewidth=0.5,
                )
                bars2 = axes3[1, 1].bar(
                    x + timing_bar_width/2,
                    survival_rate_new,
                    timing_bar_width,
                    color=self.COLORS['green'],
                    label='New',
                    edgecolor='white',
                    linewidth=0.5,
                )
                self._style_axis(axes3[1, 1], "SURVIVAL RATE % (OLD vs NEW)")
                axes3[1, 1].set_ylim(0, 100)
                axes3[1, 1].axhline(y=50, color="white", linestyle="--",
                                     alpha=0.5, linewidth=1)
                axes3[1, 1].set_xticks(x)
                axes3[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
                axes3[1, 1].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                                   edgecolor='white', labelcolor='white')
                self._add_grouped_bar_labels(
                    axes3[1, 1],
                    bars1,
                    bars2,
                    survival_rate,
                    survival_rate_new,
                    fmt="{:.0f}%",
                )
            else:
                # Survival Rate
                surv_colors = [
                    self.COLORS['green'] if s >= 70
                    else self.COLORS['yellow'] if s >= 50
                    else self.COLORS['red']
                    for s in survival_rate
                ]
                bars = axes3[1, 1].bar(x, survival_rate, color=surv_colors,
                                        edgecolor='white', linewidth=0.5)
                self._style_axis(axes3[1, 1], "SURVIVAL RATE (%)")
                axes3[1, 1].set_ylim(0, 100)
                axes3[1, 1].axhline(y=50, color="white", linestyle="--",
                                     alpha=0.5, linewidth=1)
                axes3[1, 1].set_xticks(x)
                axes3[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
                self._add_bar_labels(axes3[1, 1], bars, survival_rate, fmt="{:.0f}%")

            # Useful Kills (UK)
            bars = axes3[2, 0].bar(x, useful_kills, color=self.COLORS['teal'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[2, 0], "USEFUL KILLS (UK)")
            axes3[2, 0].set_xticks(x)
            axes3[2, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[2, 0], bars, useful_kills)

            # Self Kills vs Full Selfkills
            bar_width = 0.35
            bars1 = axes3[2, 1].bar(x - bar_width/2, self_kills, bar_width,
                                     color=self.COLORS['gray'], label='Self Kills',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes3[2, 1].bar(x + bar_width/2, full_selfkills, bar_width,
                                     color=self.COLORS['red'], label='Full Selfkills',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[2, 1], "SELF KILLS vs FULL SELFKILLS")
            axes3[2, 1].set_xticks(x)
            axes3[2, 1].set_xticklabels(display_names, rotation=45, ha="right")
            axes3[2, 1].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes3[2, 1], bars1, bars2,
                                         self_kills, full_selfkills)
            if self.show_timing_dual and dual_shadow_note:
                fig3.text(0.01, 0.01, f"Dual timing note: {dual_shadow_note}",
                          color='#B0B0B0', fontsize=8)

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf3 = io.BytesIO()
            plt.savefig(buf3, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf3.seek(0)
            plt.close(fig3)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 4: PLAYSTYLE ANALYSIS - Full width bars + Legend
            # ═══════════════════════════════════════════════════════════════
            fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(16, 8),
                                               gridspec_kw={'width_ratios': [2, 1]})
            fig4.patch.set_facecolor(self.COLORS['bg_dark'])
            fig4.suptitle(
                f"PLAYSTYLE ANALYSIS  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Player Playstyles (horizontal bars)
            style_colors = [s.color for s in playstyles]
            y_pos = np.arange(n_players)
            bars = ax4a.barh(y_pos, frag_potentials, color=style_colors,
                              edgecolor='white', linewidth=0.5)
            ax4a.set_yticks(y_pos)
            ax4a.set_yticklabels(display_names, color='white', fontsize=10)
            ax4a.invert_yaxis()
            ax4a.set_facecolor(self.COLORS['bg_panel'])
            ax4a.set_title("PLAYER PLAYSTYLES", fontweight="bold",
                           color='white', fontsize=14, pad=10)
            ax4a.set_xlabel("FragPotential", color='white', fontsize=11)
            ax4a.tick_params(colors='white')
            for spine in ['bottom', 'left']:
                ax4a.spines[spine].set_color('#404249')
            for spine in ['top', 'right']:
                ax4a.spines[spine].set_visible(False)
            ax4a.grid(True, alpha=0.15, color='white', axis='x', linestyle='--')

            # Add playstyle labels
            for bar, style, fp in zip(bars, playstyles, frag_potentials):
                width = bar.get_width()
                ax4a.text(width + (max(frag_potentials) * 0.02),
                          bar.get_y() + bar.get_height() / 2,
                          f"{style.name_display} ({int(fp)})",
                          va='center', color='white', fontsize=9, fontweight='bold')

            # Playstyle Legend
            ax4b.set_facecolor(self.COLORS['bg_panel'])
            ax4b.axis('off')
            ax4b.set_title("PLAYSTYLE LEGEND", fontweight="bold",
                           color='white', fontsize=14, pad=10)

            legend_items = [
                ("FRAGGER", "#E74C3C", "High K/D + High FragPotential"),
                ("SLAYER", "#E91E63", "High kills, trades often"),
                ("TANK", "#3498DB", "Survives, low death ratio"),
                ("MEDIC", "#2ECC71", "High revives per round"),
                ("SNIPER", "#9B59B6", "High headshot percentage"),
                ("RUSHER", "#F39C12", "High FP, aggressive play"),
                ("OBJECTIVE", "#1ABC9C", "Objective focused"),
                ("BALANCED", "#95A5A6", "All-around player"),
            ]

            y_pos_legend = 0.92
            for name, color, desc in legend_items:
                ax4b.add_patch(mpatches.FancyBboxPatch(
                    (0.05, y_pos_legend - 0.04), 0.08, 0.06,
                    boxstyle="round,pad=0.01",
                    facecolor=color, edgecolor='white', linewidth=0.5,
                    transform=ax4b.transAxes
                ))
                ax4b.text(0.16, y_pos_legend, f"{name}",
                          transform=ax4b.transAxes,
                          color=color, fontsize=12, fontweight='bold', va='center')
                ax4b.text(0.16, y_pos_legend - 0.04, desc,
                          transform=ax4b.transAxes,
                          color='#B0B0B0', fontsize=9, va='center')
                y_pos_legend -= 0.11

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf4 = io.BytesIO()
            plt.savefig(buf4, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf4.seek(0)
            plt.close(fig4)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 5: DPM TIMELINE
            # ═══════════════════════════════════════════════════════════════
            buf5 = await self._generate_timeline_graph(
                latest_date, session_ids, session_ids_str, names[:16]
            )

            # ═══════════════════════════════════════════════════════════════
            # POST SESSION TIMING DEBUG (optional)
            # ═══════════════════════════════════════════════════════════════
            if self.timing_debug_service and self.timing_debug_service.enabled:
                await self.timing_debug_service.post_session_timing_comparison(
                    session_ids=list(session_ids)
                )

            return buf1, buf2, buf3, buf4, buf5

        except ImportError as e:
            logger.warning(f"matplotlib not available: {e}")
            return None, None, None, None, None
        except Exception as e:
            logger.exception(f"Error generating performance graphs: {e}")
            return None, None, None, None, None

    async def _generate_timeline_graph(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str,
        top_player_names: List[str]
    ) -> Optional[io.BytesIO]:
        """
        Generate Performance Timeline showing DPM evolution
        across all rounds (Map1-R1, Map1-R2, Map2-R1, Map2-R2, etc.)
        """
        try:
            placeholders = ','.join(['?' for _ in session_ids])
            query = f"""
                SELECT
                    p.player_name,
                    r.map_name,
                    r.round_number,
                    r.round_date,
                    p.damage_given,
                    p.time_played_seconds,
                    p.time_dead_ratio,
                    p.kills,
                    p.deaths,
                    r.id as round_id,
                    r.round_time
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.round_id IN ({placeholders})
                ORDER BY r.round_date, r.round_time, r.round_number
            """
            all_rounds = await self.db_adapter.fetch_all(
                query, tuple(session_ids)
            )

            if not all_rounds:
                return None

            # Build round order
            round_order = []
            round_labels = []
            seen_rounds = set()

            for row in all_rounds:
                round_id = row[9]
                if round_id not in seen_rounds:
                    seen_rounds.add(round_id)
                    map_name = row[1][:8] if row[1] else "?"
                    round_num = row[2]
                    round_order.append(round_id)
                    round_labels.append(f"{map_name}\nR{round_num}")

            # Calculate DPM per player per round
            player_timelines = {}
            for name in top_player_names:
                player_timelines[name] = {rid: None for rid in round_order}

            for row in all_rounds:
                name = row[0]
                if name not in top_player_names:
                    continue

                round_id = row[9]
                dmg = row[4] or 0
                time_sec = row[5] or 0

                if time_sec > 0:
                    dpm = (dmg / time_sec) * 60
                else:
                    dpm = 0
                player_timelines[name][round_id] = dpm

            # Create figure
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 12),
                                            gridspec_kw={'height_ratios': [3, 1]})
            fig.patch.set_facecolor(self.COLORS['bg_dark'])
            fig.suptitle(
                f"DPM TIMELINE  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Color palette
            player_colors = [
                '#E74C3C', '#3498DB', '#2ECC71', '#F39C12',
                '#9B59B6', '#1ABC9C', '#E91E63', '#FEE75C',
                '#00BCD4', '#FF5722', '#8BC34A', '#607D8B',
                '#FF6B6B', '#4ECDC4', '#C9B037', '#BA68C8'
            ]

            x_positions = range(len(round_order))
            peak_data = {}
            trend_data = {}

            for idx, name in enumerate(top_player_names):
                timeline = player_timelines.get(name, {})
                y_values = [timeline.get(rid) for rid in round_order]

                valid_points = [(i, v) for i, v in enumerate(y_values) if v is not None]
                if not valid_points:
                    continue

                x_valid = [p[0] for p in valid_points]
                y_valid = [p[1] for p in valid_points]

                color = player_colors[idx % len(player_colors)]

                ax1.plot(x_valid, y_valid, color=color, linewidth=2.5,
                         marker='o', markersize=6, label=name[:12], alpha=0.9)

                if y_valid:
                    peak_idx = y_valid.index(max(y_valid))
                    peak_x = x_valid[peak_idx]
                    peak_y = y_valid[peak_idx]
                    ax1.scatter([peak_x], [peak_y], color=color, s=150,
                                marker='*', zorder=5, edgecolors='white',
                                linewidths=1)
                    peak_data[name] = (peak_x, peak_y, round_labels[peak_x])

                    if len(y_valid) >= 4:
                        mid = len(y_valid) // 2
                        first_half_avg = sum(y_valid[:mid]) / mid
                        second_half_avg = sum(y_valid[mid:]) / (len(y_valid) - mid)

                        avg_all = sum(y_valid) / len(y_valid)
                        variance = sum((v - avg_all)**2 for v in y_valid) / len(y_valid)
                        volatility = (variance ** 0.5) / max(1, avg_all) * 100

                        if volatility > 40:
                            trend_data[name] = ("VOLATILE", "🎢", self.COLORS['orange'])
                        elif second_half_avg > first_half_avg * 1.15:
                            trend_data[name] = ("RISING", "📈", self.COLORS['green'])
                        elif first_half_avg > second_half_avg * 1.15:
                            trend_data[name] = ("FADING", "📉", self.COLORS['red'])
                        else:
                            trend_data[name] = ("STEADY", "➡️", self.COLORS['cyan'])
                    else:
                        trend_data[name] = ("N/A", "❓", self.COLORS['gray'])

            # Style main graph
            ax1.set_facecolor(self.COLORS['bg_panel'])
            ax1.set_ylabel("DPM (Damage Per Minute)", color='white',
                           fontsize=12, fontweight='bold')
            ax1.tick_params(colors='white', labelsize=9)
            ax1.set_xticks(x_positions)
            ax1.set_xticklabels(round_labels, rotation=45, ha='right',
                                fontsize=8, color='white')
            ax1.grid(True, alpha=0.2, color='white', linestyle='--')
            for spine in ['bottom', 'left']:
                ax1.spines[spine].set_color('#404249')
            for spine in ['top', 'right']:
                ax1.spines[spine].set_visible(False)

            ax1.legend(loc='upper left', bbox_to_anchor=(1.01, 1),
                       facecolor=self.COLORS['bg_panel'],
                       edgecolor='white', labelcolor='white',
                       fontsize=9, ncol=1, framealpha=0.9)

            # Bottom panel: Form Summary
            ax2.set_facecolor(self.COLORS['bg_panel'])
            ax2.axis('off')
            ax2.set_title("SESSION FORM ANALYSIS", fontweight="bold",
                          color='white', fontsize=13, pad=10)

            for idx, name in enumerate(top_player_names[:16]):
                col = idx % 4
                row = idx // 4

                x_pos = 0.02 + col * 0.25
                y_pos = 0.7 - row * 0.45

                ax2.text(x_pos, y_pos, name[:12], transform=ax2.transAxes,
                         color='white', fontsize=11, fontweight='bold', va='top')

                if name in trend_data:
                    trend_name, emoji, color = trend_data[name]
                    ax2.text(x_pos, y_pos - 0.12, f"{trend_name}",
                             transform=ax2.transAxes, color=color,
                             fontsize=10, fontweight='bold', va='top')

                if name in peak_data:
                    px, py, plabel = peak_data[name]
                    clean_label = plabel.replace('\n', ' ')
                    ax2.text(x_pos, y_pos - 0.24, f"Peak: {int(py)} DPM",
                             transform=ax2.transAxes, color='#B0B0B0',
                             fontsize=9, va='top')
                    ax2.text(x_pos, y_pos - 0.34, f"@ {clean_label}",
                             transform=ax2.transAxes, color='#808080',
                             fontsize=8, va='top')

            plt.tight_layout(rect=(0, 0, 0.85, 0.96))
            buf = io.BytesIO()
            plt.savefig(buf, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            logger.exception(f"Error generating timeline graph: {e}")
            return None
