"""
Session View Handlers - Handles different view modes for !last_session

This service manages:
- Objectives view
- Combat view
- Weapons view
- Support view
- Sprees view
- Top view
- Maps view
- Maps full view
- Round stats
"""

import asyncio
import csv
import inspect
import io
import discord
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bot.stats import StatsCalculator

logger = logging.getLogger("bot.services.session_view_handlers")


class SessionViewHandlers:
    """Service for handling different view modes"""

    def __init__(
        self,
        db_adapter,
        stats_calculator,
        timing_shadow_service=None,
        show_timing_dual: bool = False
    ):
        """
        Initialize the view handlers

        Args:
            db_adapter: Database adapter for queries
            stats_calculator: StatsCalculator instance for calculations
            timing_shadow_service: Optional shadow/comparison service for timing dual-mode
            show_timing_dual: Feature flag for old vs new timing display
        """
        self.db_adapter = db_adapter
        self.stats_calculator = stats_calculator
        self.timing_shadow_service = timing_shadow_service
        self.show_timing_dual = bool(show_timing_dual)

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Format seconds as MM:SS (safe for None/float)."""
        try:
            total = int(round(seconds or 0))
        except Exception:
            total = 0
        minutes = total // 60
        secs = total % 60
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def _format_delta_seconds(delta_seconds: int) -> str:
        """Format a signed delta in MM:SS format."""
        sign = "+" if delta_seconds > 0 else "-"
        total = abs(int(delta_seconds or 0))
        minutes = total // 60
        secs = total % 60
        if total == 0:
            return "0:00"
        return f"{sign}{minutes}:{secs:02d}"

    @staticmethod
    def _parse_time_to_seconds(time_value: Any) -> int:
        """Parse a time value (MM:SS, HH:MM:SS, or numeric) into seconds."""
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
        """
        Build round-level timing correction factors from shadow/comparison service.

        Returns:
            {
              factors: {round_id: factor},
              round_rows: {round_id: {map_name, round_number, stats_seconds, lua_seconds, diff_seconds}},
              rounds_total: int,
              rounds_with_telemetry: int,
              reason: str
            }
        """
        result: Dict[str, Any] = {
            "factors": {},
            "round_rows": {},
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

        # Preferred API path if the shadow service exposes round factors directly
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
                if isinstance(payload, dict):
                    payload_rows = payload.get("round_rows") or payload.get("rows") or {}
                    if isinstance(payload_rows, dict):
                        result["round_rows"] = payload_rows
                    elif isinstance(payload_rows, list):
                        for item in payload_rows:
                            if not isinstance(item, dict):
                                continue
                            rid = item.get("round_id") or item.get("id")
                            try:
                                rid_int = int(rid)
                            except (TypeError, ValueError):
                                continue
                            result["round_rows"][rid_int] = item
                result["reason"] = (
                    f"Lua timing unavailable for {len(session_ids) - len(factors)}/{len(session_ids)} rounds"
                    if len(factors) < len(session_ids) else "OK"
                )
                result["source"] = method_name
                return result

        # Compatibility path: derive factors from timing comparison service internals
        has_fetch_lua = hasattr(self.timing_shadow_service, "_fetch_lua_data")
        if not has_fetch_lua:
            result["reason"] = "Timing service does not expose round comparison data"
            return result

        placeholders = ",".join("?" for _ in session_ids)
        rounds_query = f"""
            SELECT r.id, r.map_name, r.round_number, r.round_date, r.round_time, r.actual_time
            FROM rounds r
            WHERE r.id IN ({placeholders})
            ORDER BY r.round_date, r.round_time, r.round_number
        """
        round_rows = await self.db_adapter.fetch_all(rounds_query, tuple(session_ids))
        if not round_rows:
            result["reason"] = "No rounds found"
            return result

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
                except Exception as e:  # nosec B110
                    stats_data = None
                    logger.debug("shadow _fetch_stats_file_data failed for round %s: %s", round_id, e)
                if isinstance(stats_data, dict):
                    map_name = stats_data.get("map_name") or map_name
                    round_number = int(stats_data.get("round_number") or round_number or 0)
                    round_date = stats_data.get("round_date") or round_date
                    round_time = stats_data.get("round_time") or round_time
                    stats_seconds = int(stats_data.get("stats_duration_seconds") or stats_seconds or 0)

            lua_seconds: Optional[int] = None
            try:
                lua_data = await self.timing_shadow_service._fetch_lua_data(
                    round_id,
                    map_name,
                    round_number,
                    round_date,
                    round_time,
                )
            except Exception as e:  # nosec B110
                lua_data = None
                logger.debug("shadow _fetch_lua_data failed for round %s: %s", round_id, e)

            if isinstance(lua_data, dict):
                lua_seconds_raw = lua_data.get("lua_duration_seconds")
                try:
                    lua_seconds = int(lua_seconds_raw) if lua_seconds_raw is not None else None
                except (TypeError, ValueError):
                    lua_seconds = None

            diff_seconds: Optional[int] = None
            if stats_seconds > 0 and lua_seconds and lua_seconds > 0:
                factor = max(0.0, min(2.0, float(lua_seconds) / float(stats_seconds)))
                result["factors"][round_id] = factor
                result["rounds_with_telemetry"] += 1
                diff_seconds = int(stats_seconds - lua_seconds)

            result["round_rows"][round_id] = {
                "round_id": round_id,
                "map_name": map_name,
                "round_number": round_number,
                "stats_seconds": int(stats_seconds or 0),
                "lua_seconds": int(lua_seconds or 0) if lua_seconds else None,
                "diff_seconds": diff_seconds,
            }

        missing_rounds = len(session_ids) - result["rounds_with_telemetry"]
        if result["rounds_with_telemetry"] == 0:
            result["reason"] = "No Lua timing telemetry linked to this session"
        elif missing_rounds > 0:
            result["reason"] = f"Lua timing missing for {missing_rounds}/{len(session_ids)} rounds"
        else:
            result["reason"] = "OK"
        result["source"] = "compat_fetch"
        return result

    async def get_session_timing_dual_by_guid(self, session_ids: List[int]) -> Dict[str, Any]:
        """Build per-player old/new timing aggregates for dual-mode displays."""
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

        # Preferred path: dedicated session shadow service
        called, shadow_result = await self._call_service_method("compare_session", session_ids)
        if called and shadow_result is not None:
            players: Dict[str, Dict[str, Any]] = {}
            round_diagnostics = tuple(getattr(shadow_result, "round_diagnostics", ()) or ())
            rounds_total = len(round_diagnostics)
            rounds_with_telemetry = sum(
                1 for diag in round_diagnostics if int(getattr(diag, "players_with_lua", 0) or 0) > 0
            )

            for summary in tuple(getattr(shadow_result, "player_summaries", ()) or ()):
                rounds_played = int(getattr(summary, "rounds", 0) or 0)
                telemetry_rounds = int(getattr(summary, "rounds_with_lua", 0) or 0)
                if rounds_played == 0:
                    missing_reason = "No timing rows"
                elif telemetry_rounds == 0:
                    missing_reason = "No Lua telemetry"
                elif telemetry_rounds < rounds_played:
                    missing_reason = f"Lua partial {telemetry_rounds}/{rounds_played}"
                else:
                    missing_reason = ""

                entry = {
                    "player_guid": getattr(summary, "player_guid", ""),
                    "player_name": getattr(summary, "player_name", "Unknown"),
                    "time_played_seconds": int(getattr(summary, "old_time_played_seconds", 0) or 0),
                    "old_time_dead_seconds": int(getattr(summary, "old_dead_seconds", 0) or 0),
                    "new_time_dead_seconds": int(getattr(summary, "new_dead_seconds", 0) or 0),
                    "old_denied_seconds": int(getattr(summary, "old_denied_playtime", 0) or 0),
                    "new_denied_seconds": int(getattr(summary, "new_denied_playtime", 0) or 0),
                    "rounds_played": rounds_played,
                    "telemetry_rounds": telemetry_rounds,
                    "missing_reason": missing_reason,
                }

                guid_key = str(entry["player_guid"])
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
                "overall_coverage_percent": float(
                    getattr(shadow_result, "overall_coverage_percent", 0.0) or 0.0
                ),
                "reason": reason,
                "source": "compare_session",
                "artifact_path": getattr(shadow_result, "artifact_path", None),
            }
            return payload

        shadow = await self._get_round_timing_shadow(session_ids)
        round_factors: Dict[int, float] = shadow.get("factors", {}) or {}
        payload["meta"]["rounds_with_telemetry"] = int(shadow.get("rounds_with_telemetry") or 0)
        payload["meta"]["reason"] = shadow.get("reason", "")
        payload["meta"]["source"] = shadow.get("source", "none")

        placeholders = ",".join("?" for _ in session_ids)
        query = f"""
            SELECT p.player_guid,
                MAX(COALESCE(p.clean_name, p.player_name)) as player_name,
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
            name = self._row_get(row, 1, "player_name", "Unknown") or "Unknown"
            round_id = int(self._row_get(row, 2, "round_id", 0) or 0)
            played = int(self._row_get(row, 3, "time_played_seconds", 0) or 0)
            dead_old = int(round(float(self._row_get(row, 4, "time_dead_old_seconds", 0) or 0)))
            denied_old = int(round(float(self._row_get(row, 5, "denied_old_seconds", 0) or 0)))
            dead_old = max(0, min(dead_old, played if played > 0 else dead_old))
            denied_old = max(0, min(denied_old, played if played > 0 else denied_old))

            factor = round_factors.get(round_id)
            telemetry_hit = factor is not None
            if telemetry_hit:
                dead_new = int(round(dead_old * factor))
                denied_new = int(round(denied_old * factor))
                dead_new = max(0, min(dead_new, played if played > 0 else dead_new))
                denied_new = max(0, min(denied_new, played if played > 0 else denied_new))
            else:
                dead_new = dead_old
                denied_new = denied_old

            player_entry = payload["players"].setdefault(
                guid,
                {
                    "player_guid": guid,
                    "player_name": name,
                    "time_played_seconds": 0,
                    "old_time_dead_seconds": 0,
                    "new_time_dead_seconds": 0,
                    "old_denied_seconds": 0,
                    "new_denied_seconds": 0,
                    "rounds_played": 0,
                    "telemetry_rounds": 0,
                },
            )

            player_entry["player_name"] = name
            player_entry["time_played_seconds"] += played
            player_entry["old_time_dead_seconds"] += dead_old
            player_entry["new_time_dead_seconds"] += dead_new
            player_entry["old_denied_seconds"] += denied_old
            player_entry["new_denied_seconds"] += denied_new
            player_entry["rounds_played"] += 1
            if telemetry_hit:
                player_entry["telemetry_rounds"] += 1

        for player_entry in payload["players"].values():
            rounds_played = int(player_entry.get("rounds_played", 0) or 0)
            telemetry_rounds = int(player_entry.get("telemetry_rounds", 0) or 0)
            if rounds_played == 0:
                player_entry["missing_reason"] = "No timing rows"
            elif telemetry_rounds == 0:
                player_entry["missing_reason"] = "No Lua telemetry"
            elif telemetry_rounds < rounds_played:
                player_entry["missing_reason"] = f"Lua partial {telemetry_rounds}/{rounds_played}"
            else:
                player_entry["missing_reason"] = ""

        return payload

    async def get_timing_diff_summary(self, session_ids: List[int], top_n: int = 8) -> Dict[str, Any]:
        """Return compact top-N round timing diffs for admin debug output."""
        top_n = max(1, min(int(top_n or 8), 20))

        called, shadow_result = await self._call_service_method("compare_session", session_ids)
        if called and shadow_result is not None:
            round_rows = tuple(getattr(shadow_result, "player_rounds", ()) or ())
            rows_sorted = sorted(
                round_rows,
                key=lambda row: abs(int(getattr(row, "dead_diff_seconds", 0) or 0))
                + abs(int(getattr(row, "denied_diff_seconds", 0) or 0)),
                reverse=True,
            )
            rows = []
            for row in rows_sorted[:top_n]:
                rows.append(
                    {
                        "round_id": int(getattr(row, "round_id", 0) or 0),
                        "map_name": getattr(row, "map_name", "unknown"),
                        "round_number": int(getattr(row, "round_number", 0) or 0),
                        "player_name": getattr(row, "player_name", "Unknown"),
                        "old_dead_seconds": int(getattr(row, "old_dead_seconds", 0) or 0),
                        "new_dead_seconds": int(getattr(row, "new_dead_seconds", 0) or 0),
                        "dead_diff_seconds": int(getattr(row, "dead_diff_seconds", 0) or 0),
                        "old_denied_seconds": int(getattr(row, "old_denied_playtime", 0) or 0),
                        "new_denied_seconds": int(getattr(row, "new_denied_playtime", 0) or 0),
                        "denied_diff_seconds": int(getattr(row, "denied_diff_seconds", 0) or 0),
                        "fallback_reason": getattr(row, "fallback_reason", ""),
                    }
                )

            round_diagnostics = tuple(getattr(shadow_result, "round_diagnostics", ()) or ())
            rounds_total = len(round_diagnostics)
            rounds_with_telemetry = sum(
                1 for diag in round_diagnostics if int(getattr(diag, "players_with_lua", 0) or 0) > 0
            )
            if rounds_total == 0:
                reason = "No round diagnostics"
            elif rounds_with_telemetry == 0:
                reason = "No Lua telemetry linked to this session"
            elif rounds_with_telemetry < rounds_total:
                reason = f"Lua timing partial {rounds_with_telemetry}/{rounds_total} rounds"
            else:
                reason = "OK"

            return {
                "rows": rows,
                "meta": {
                    "rounds_total": rounds_total,
                    "rounds_with_telemetry": rounds_with_telemetry,
                    "overall_coverage_percent": float(
                        getattr(shadow_result, "overall_coverage_percent", 0.0) or 0.0
                    ),
                    "reason": reason,
                    "source": "compare_session",
                    "artifact_path": getattr(shadow_result, "artifact_path", None),
                },
            }

        shadow = await self._get_round_timing_shadow(session_ids)
        rows = []
        for round_row in (shadow.get("round_rows") or {}).values():
            diff_seconds = round_row.get("diff_seconds")
            if diff_seconds is None:
                continue
            rows.append(round_row)

        rows.sort(key=lambda r: abs(int(r.get("diff_seconds") or 0)), reverse=True)
        return {
            "rows": rows[:top_n],
            "meta": {
                "rounds_total": int(shadow.get("rounds_total") or len(session_ids or [])),
                "rounds_with_telemetry": int(shadow.get("rounds_with_telemetry") or 0),
                "reason": shadow.get("reason", ""),
                "source": shadow.get("source", "none"),
            },
        }

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

    async def show_objectives_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show objectives & support stats only"""
        query = """
            SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused, times_revived,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                denied_playtime, most_useful_kills, useless_kills, gibs,
                killing_spree_best, death_spree_worst
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
        """
        awards_rows = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        if not awards_rows:
            await ctx.send("❌ No objective/support data available for latest session")
            return

        # Also fetch revives GIVEN per player
        rev_query = """
            SELECT player_guid, MAX(clean_name) as clean_name, SUM(revives_given) as revives_given
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
            GROUP BY player_guid
        """
        rev_rows = await self.db_adapter.fetch_all(rev_query.format(session_ids_str=session_ids_str), tuple(session_ids))
        revives_map = {r[1]: (r[2] or 0) for r in rev_rows}  # r[1] is clean_name, r[2] is revives_given

        # Aggregate per-player across rounds
        player_objectives = {}
        for row in awards_rows:
            name = row[0]
            if name not in player_objectives:
                player_objectives[name] = {
                    "xp": 0, "kill_assists": 0, "obj_stolen": 0, "obj_returned": 0,
                    "dyn_planted": 0, "dyn_defused": 0, "times_revived": 0,
                    "revives_given": 0, "multi_2x": 0, "multi_3x": 0,
                    "multi_4x": 0, "multi_5x": 0, "multi_6x": 0,
                    "denied_time": 0, "useful_kills": 0, "useless_kills": 0,
                    "gibs": 0, "best_spree": 0, "worst_spree": 0
                }

            player_objectives[name]["xp"] += row[1] or 0
            player_objectives[name]["kill_assists"] += row[2] or 0
            player_objectives[name]["obj_stolen"] += row[3] or 0
            player_objectives[name]["obj_returned"] += row[4] or 0
            player_objectives[name]["dyn_planted"] += row[5] or 0
            player_objectives[name]["dyn_defused"] += row[6] or 0
            player_objectives[name]["times_revived"] += row[7] or 0
            player_objectives[name]["multi_2x"] += row[8] or 0
            player_objectives[name]["multi_3x"] += row[9] or 0
            player_objectives[name]["multi_4x"] += row[10] or 0
            player_objectives[name]["multi_5x"] += row[11] or 0
            player_objectives[name]["multi_6x"] += row[12] or 0
            player_objectives[name]["denied_time"] += row[13] or 0
            player_objectives[name]["useful_kills"] += row[14] or 0
            player_objectives[name]["useless_kills"] += row[15] or 0
            player_objectives[name]["gibs"] += row[16] or 0
            player_objectives[name]["best_spree"] = max(player_objectives[name]["best_spree"], row[17] or 0)
            player_objectives[name]["worst_spree"] = max(player_objectives[name]["worst_spree"], row[18] or 0)

        # Merge revives_given
        for pname, gv in revives_map.items():
            if pname in player_objectives:
                player_objectives[pname]["revives_given"] = gv or 0

        # Build embed
        top_n = min(8, len(player_objectives))
        sorted_players = sorted(player_objectives.items(), key=lambda x: x[1]["xp"], reverse=True)[:top_n]

        embed = discord.Embed(
            title=f"🎯 Objective & Support - {latest_date}",
            description=f"Top objective contributors • {player_count} players",
            color=0x00D166,
            timestamp=datetime.now(),
        )

        for i, (player, stats) in enumerate(sorted_players, 1):
            txt_lines = []
            txt_lines.append(f"XP: `{stats.get('xp',0)}`")
            txt_lines.append(f"Kill Assists: `{stats.get('kill_assists',0)}`")
            txt_lines.append(f"Revives Given: `{stats.get('revives_given',0)}` • Times Revived: `{stats.get('times_revived',0)}`")
            txt_lines.append(f"Dyns P/D: `{stats.get('dyn_planted',0)}/{stats.get('dyn_defused',0)}` • S/R: `{stats.get('obj_stolen',0)}/{stats.get('obj_returned',0)}`")
        
            if stats.get("gibs", 0) > 0:
                txt_lines.append(f"Gibs: `{stats.get('gibs',0)}`")
            txt_lines.append(f"Best Spree: `{stats.get('best_spree',0)}` • Worst Spree: `{stats.get('worst_spree',0)}`")
        
            if stats.get("denied_time", 0) > 0:
                dt = int(stats.get("denied_time", 0))
                dm = dt // 60
                ds = dt % 60
                txt_lines.append(f"Enemy Denied: `{dm}:{ds:02d}`")

            embed.add_field(name=f"{i}. {player}", value="\n".join(txt_lines), inline=False)

        embed.set_footer(text=f"Round: {latest_date} • Use !last_round for full report")
        await ctx.send(embed=embed)

    async def show_combat_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show combat-focused stats only"""
        columns = await self._get_player_stats_columns()
        has_full_selfkills = "full_selfkills" in columns
        full_selfkills_select = (
            "SUM(p.full_selfkills) as full_selfkills"
            if has_full_selfkills
            else "0 as full_selfkills"
        )

        query = f"""
            SELECT MAX(p.player_name) as player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                SUM(p.damage_given) as damage_given,
                SUM(p.damage_received) as damage_received,
                SUM(p.gibs) as gibs,
                SUM(p.headshot_kills) as headshot_kills,
                SUM(p.self_kills) as self_kills,
                {full_selfkills_select},
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as weighted_dpm
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_guid
            ORDER BY kills DESC
        """
        combat_rows = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        if not combat_rows:
            await ctx.send("❌ No combat data available for latest session")
            return

        embed = discord.Embed(
            title=f"⚔️ Combat Stats - {latest_date}",
            description=f"Combat leaders • {player_count} players",
            color=0xED4245,
            timestamp=datetime.now(),
        )

        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(combat_rows, 1):
            name, kills, deaths, dmg_g, dmg_r, gibs, hsk, self_kills, full_selfkills, dpm = row
            kd = StatsCalculator.calculate_kd(kills, deaths)
        
            player_text = (
                f"{medals[i-1] if i <= 3 else f'{i}.'} **{name}**\n"
                f"💀 `{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM`\n"
                f"💥 Damage: `{(dmg_g or 0):,}` given • `{(dmg_r or 0):,}` received\n"
            )
            if gibs and gibs > 0:
                player_text += f"🦴 `{gibs} Gibs`"
            if hsk and hsk > 0:
                player_text += f" • 🎯 `{hsk} Headshot Kills`"
            if self_kills and self_kills > 0:
                player_text += f" • ☠️ `{self_kills} SK`"
            if has_full_selfkills and full_selfkills and full_selfkills > 0:
                player_text += f" • 💀 `{full_selfkills} FSK`"

            embed.add_field(name="\u200b", value=player_text, inline=False)

        embed.set_footer(text=f"Round: {latest_date} • Use !last_round for full report")
        await ctx.send(embed=embed)

    async def show_weapons_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show weapon mastery stats only"""
        query = """
            SELECT MAX(p.player_name) as player_name, w.weapon_name,
                SUM(w.kills) as weapon_kills,
                SUM(w.hits) as hits,
                SUM(w.shots) as shots,
                SUM(w.headshots) as headshots
            FROM weapon_comprehensive_stats w
            JOIN player_comprehensive_stats p
                ON w.round_id = p.round_id
                AND w.player_guid = p.player_guid
            WHERE w.round_id IN ({session_ids_str})
            GROUP BY p.player_guid, w.weapon_name
            HAVING SUM(w.kills) > 0
            ORDER BY player_name, SUM(w.kills) DESC
        """
        pw_rows = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        if not pw_rows:
            await ctx.send("❌ No weapon data available for latest session")
            return

        # Group by player
        player_weapon_map = {}
        for player, weapon, kills, hits, shots, hs in pw_rows:
            if player not in player_weapon_map:
                player_weapon_map[player] = []
            acc = StatsCalculator.calculate_accuracy(hits, shots)
            hs_pct = StatsCalculator.calculate_headshot_percentage(hs, hits)
            weapon_clean = weapon.replace("WS_", "").replace("_", " ").title()
            player_weapon_map[player].append((weapon_clean, kills, acc, hs_pct, hs, hits, shots))

        embed = discord.Embed(
            title=f"🔫 Weapon Mastery - {latest_date}",
            description=f"Top weapons per player • {len(player_weapon_map)} players",
            color=0x5865F2,
            timestamp=datetime.now(),
        )

        for player, weapons in player_weapon_map.items():
            text = ""
            for weapon, kills, acc, hs_pct, hs, hits, shots in weapons[:6]:
                text += f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • `{hs} HS ({hs_pct:.1f}%)`\n"
            embed.add_field(name=f"⚔️ {player}", value=text.rstrip(), inline=False)

        embed.set_footer(text=f"Round: {latest_date} • Use !last_round for full report")
        await ctx.send(embed=embed)

    async def show_support_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show support activity stats only"""
        columns = await self._get_player_stats_columns()
        has_full_selfkills = "full_selfkills" in columns
        full_selfkills_select = (
            "SUM(p.full_selfkills) as full_selfkills"
            if has_full_selfkills
            else "0 as full_selfkills"
        )

        query = f"""
            SELECT MAX(p.player_name) as player_name,
                SUM(p.revives_given) as revives_given,
                SUM(p.times_revived) as times_revived,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                SUM(p.self_kills) as self_kills,
                {full_selfkills_select}
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_guid
            ORDER BY revives_given DESC
        """
        sup_rows = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        if not sup_rows:
            await ctx.send("❌ No support data available for latest session")
            return

        embed = discord.Embed(
            title=f"💉 Support Stats - {latest_date}",
            description=f"Support activity • {player_count} players",
            color=0x57F287,
            timestamp=datetime.now(),
        )

        for name, revives_given, times_revived, kills, deaths, self_kills, full_selfkills in sup_rows:
            txt = f"Revives Given: `{revives_given or 0}` • Times Revived: `{times_revived or 0}`\n"
            txt += f"Kills: `{kills or 0}` • Deaths: `{deaths or 0}`"
            if self_kills and self_kills > 0:
                txt += f"\nSelf Kills: `{self_kills}`"
            if has_full_selfkills and full_selfkills and full_selfkills > 0:
                txt += f" • Full Selfkills: `{full_selfkills}`"
            embed.add_field(name=f"{name}", value=txt, inline=False)

        embed.set_footer(text=f"Round: {latest_date}")
        await ctx.send(embed=embed)

    async def show_sprees_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show killing sprees & multikills only"""
        query = """
            SELECT MAX(p.player_name) as player_name,
                SUM(p.killing_spree_best) as best_spree,
                SUM(p.double_kills) as doubles,
                SUM(p.triple_kills) as triples,
                SUM(p.quad_kills) as quads,
                SUM(p.multi_kills) as multis,
                SUM(p.mega_kills) as megas,
                SUM(p.kills) as total_kills
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_guid
            ORDER BY best_spree DESC, megas DESC
        """
        spree_rows = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        if not spree_rows:
            await ctx.send("❌ No spree data available for latest session")
            return

        embed = discord.Embed(
            title=f"🔥 Killing Sprees & Multi-Kills - {latest_date}",
            description=f"Sprees and monster kills • {player_count} players",
            color=0xFEE75C,
            timestamp=datetime.now(),
        )

        for i, (name, best_spree, doubles, triples, quads, multis, megas, total_kills) in enumerate(spree_rows, 1):
            if best_spree == 0 and doubles == 0 and triples == 0 and quads == 0 and multis == 0 and megas == 0:
                continue
            txt = f"Best Spree: `{best_spree}` • MEGA: `{megas}` • Multis: `{multis}`\n"
            txt += f"Doubles/Triples/Quads: `{doubles}/{triples}/{quads}` • Kills: `{total_kills}`"
            embed.add_field(name=f"{i}. {name}", value=txt, inline=False)

        embed.set_footer(text=f"Round: {latest_date}")
        await ctx.send(embed=embed)

    async def show_top_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int, total_maps: int):
        """Show all players ranked by kills"""
        query = """
            SELECT MAX(p.player_name) as player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as weighted_dpm,
                SUM(p.damage_given) as total_damage,
                SUM(p.headshot_kills) as headshot_kills,
                SUM(p.gibs) as gibs,
                SUM(p.time_played_seconds) as total_seconds
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_guid
            ORDER BY kills DESC
        """
        top_players = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        embed = discord.Embed(
            title=f"🏆 All Players - {latest_date}",
            description=f"All {player_count} players from {total_maps} maps",
            color=0xFEE75C,
            timestamp=datetime.now(),
        )

        medals = ["🥇", "🥈", "🥉"]
    
        # Build player list in batches to avoid Discord field limits
        field_text = ""
        for i, player in enumerate(top_players, 1):
            name, kills, deaths, dpm, damage, hsk, gibs, seconds = player
            kd = StatsCalculator.calculate_kd(kills, deaths)
            hours = int((seconds or 0) // 3600)
            minutes = int(((seconds or 0) % 3600) // 60)
            time_display = f"{hours}h{minutes}m" if hours > 0 else f"{minutes}m"

            # Medal for top 3, number for rest
            prefix = medals[i-1] if i <= 3 else f"{i}."
        
            player_line = (
                f"{prefix} **{name}**\n"
                f"`{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM` • `{damage:,} DMG`\n"
                f"`{hsk} HSK` • `{gibs} Gibs` • ⏱️ `{time_display}`\n"
            )
        
            # Check if adding this player would exceed field limit (1024)
            if len(field_text) + len(player_line) > 1000:
                embed.add_field(name="\u200b", value=field_text, inline=False)
                field_text = player_line
            else:
                field_text += player_line
    
        # Add remaining players
        if field_text:
            embed.add_field(name="\u200b", value=field_text, inline=False)

        embed.set_footer(text="💡 Use !last_round for full details")
        await ctx.send(embed=embed)

    async def show_maps_view(self, ctx, latest_date: str, sessions: List, session_ids: List, session_ids_str: str, player_count: int):
        """Show map summaries only - matches live round_publisher_service format"""

        # Group sessions into matches (R1 + R2 pairs)
        map_matches = []
        i = 0
        while i < len(sessions):
            match_rounds = []
            current_map = sessions[i][1]  # map_name

            # Collect R1 and R2 for this match
            while i < len(sessions) and sessions[i][1] == current_map and len(match_rounds) < 2:
                round_id, map_name, round_num, actual_time = sessions[i]
                match_rounds.append(round_id)
                i += 1

            if match_rounds:
                map_matches.append((current_map, match_rounds))

        # Count occurrences of each map for display
        map_counts = {}
        for map_name, _ in map_matches:
            map_counts[map_name] = map_counts.get(map_name, 0) + 1

        map_occurrence = {}

        # For each match, get aggregated stats (both rounds combined)
        for map_name, map_session_ids in map_matches:
            map_ids_str = ','.join('?' * len(map_session_ids))

            # Determine display name (add counter for duplicates)
            if map_counts[map_name] > 1:
                occurrence_num = map_occurrence.get(map_name, 0) + 1
                map_occurrence[map_name] = occurrence_num
                display_map_name = f"{map_name} (#{occurrence_num})"
            else:
                display_map_name = map_name
        
            # Query with time_played and denied_playtime
            query = """
                WITH target_rounds AS (
                    SELECT id FROM rounds WHERE id IN ({map_ids_str})
                )
                SELECT MAX(p.player_name) as player_name,
                    SUM(p.kills) as kills,
                    SUM(p.deaths) as deaths,
                    SUM(p.damage_given) as dmg_given,
                    SUM(p.gibs) as gibs,
                    SUM(p.headshot_kills) as headshots,
                    AVG(p.accuracy) as accuracy,
                    SUM(p.revives_given) as revives,
                    SUM(p.times_revived) as times_revived,
                    SUM(p.time_dead_minutes) as time_dead,
                    SUM(p.team_damage_given) as team_dmg,
                    SUM(p.time_played_minutes) as time_played,
                    SUM(p.denied_playtime) as time_denied,
                    CASE
                        WHEN SUM(p.time_played_seconds) > 0
                        THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                        ELSE 0
                    END as dpm
                FROM player_comprehensive_stats p
                WHERE p.round_id IN (SELECT id FROM target_rounds)
                GROUP BY p.player_guid
                ORDER BY kills DESC
            """
        
            players = await self.db_adapter.fetch_all(query, tuple(map_session_ids))
        
            if not players:
                continue
        
            # Build embed matching live format
            embed = discord.Embed(
                title=f"🗺️ {display_map_name.upper()} - Map Complete!",
                description=f"Aggregate stats from **{len(map_session_ids)} rounds** • {len(players)} players",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )

            # Rank emoji helper
            def get_rank_display(rank):
                if rank == 1:
                    return "🥇"
                elif rank == 2:
                    return "🥈"
                elif rank == 3:
                    return "🥉"
                else:
                    rank_str = str(rank)
                    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                                   '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
                    return ''.join(emoji_digits[d] for d in rank_str)

            # Smart chunking - split evenly based on player count
            # For 6 players: 3+3, for 8: 4+4, for 10: 5+5, for 12: 6+6
            # For odd numbers: larger chunk first (7: 4+3)
            total_players = len(players)
            if total_players <= 6:
                # Small games: split in half
                chunk_size = (total_players + 1) // 2  # Rounds up for first half
            elif total_players <= 10:
                # Medium games: max 5 per chunk
                chunk_size = 5
            else:
                # Large games: max 6 per chunk  
                chunk_size = 6

            for i in range(0, len(players), chunk_size):
                chunk = players[i:i + chunk_size]
                
                # Use "All Players" for single chunk, otherwise show range
                if total_players <= chunk_size:
                    field_name = '📊 All Players'
                else:
                    field_name = f'📊 Players {i+1}-{i+len(chunk)}'
                
                player_lines = []
                for idx, player in enumerate(chunk):
                    rank = i + idx + 1
                    rank_display = get_rank_display(rank)
                    
                    (name, kills, deaths, dmg, gibs, hs, acc, revives, 
                     got_revived, time_dead, team_dmg, time_played, time_denied, dpm) = player
                    
                    # Handle nulls
                    kills = kills or 0
                    deaths = deaths or 0
                    dmg = dmg or 0
                    gibs = gibs or 0
                    hs = hs or 0
                    acc = acc or 0
                    revives = revives or 0
                    got_revived = got_revived or 0
                    time_dead = time_dead or 0
                    team_dmg = team_dmg or 0
                    time_played = time_played or 0
                    time_denied = time_denied or 0
                    dpm = dpm or 0
                    
                    name = (name or 'Unknown')[:16]
                    kd_str = f'{kills}/{deaths}'
                    
                    # Format time_played as MM:SS
                    tp_min = int(time_played)
                    tp_sec = int((time_played - tp_min) * 60)
                    
                    # Format time_denied as MM:SS (it's in seconds)
                    td_min = int(time_denied // 60)
                    td_sec = int(time_denied % 60)

                    # Calculate time percentages
                    if time_played > 0:
                        dead_pct = (time_dead / time_played) * 100
                        denied_pct = ((time_denied / 60) / time_played) * 100
                    else:
                        dead_pct = denied_pct = 0

                    # Line 1: Rank + Name + Core stats
                    line1 = (
                        f"{rank_display} **{name}** • K/D:`{kd_str}` "
                        f"DMG:`{int(dmg):,}` DPM:`{int(dpm)}` "
                        f"ACC:`{acc:.1f}%` HS:`{hs}`"
                    )

                    # Line 2: Support + Time stats
                    line2 = (
                        f"     ↳ Rev:`{int(revives)}/{int(got_revived)}` Gibs:`{gibs}` "
                        f"TmDmg:`{int(team_dmg)}` "
                        f"⏱️`{tp_min}:{tp_sec:02d}` 💀`{time_dead:.1f}m`({dead_pct:.0f}%) ⏳`{td_min}:{td_sec:02d}`({denied_pct:.0f}%)"
                    )

                    player_lines.append(f"{line1}\n{line2}")

                embed.add_field(
                    name=field_name,
                    value='\n'.join(player_lines) if player_lines else 'No stats',
                    inline=False
                )

            # Add round summary
            total_kills = sum((p[1] or 0) for p in players)
            total_deaths = sum((p[2] or 0) for p in players)
            total_dmg = sum((p[3] or 0) for p in players)
            total_hs = sum((p[5] or 0) for p in players)
            total_team_dmg = sum((p[10] or 0) for p in players)
            avg_acc = sum((p[6] or 0) for p in players) / len(players) if players else 0
            avg_dpm = sum((p[13] or 0) for p in players) / len(players) if players else 0
            avg_time_dead = sum((p[9] or 0) for p in players) / len(players) if players else 0

            embed.add_field(
                name="📊 Round Summary",
                value=(
                    f"**Totals:** Kills:`{total_kills}` Deaths:`{total_deaths}` HS:`{total_hs}` "
                    f"Damage:`{int(total_dmg):,}` TeamDmg:`{int(total_team_dmg):,}`\n"
                    f"**Averages:** Accuracy:`{avg_acc:.1f}%` DPM:`{int(avg_dpm)}` DeadTime:`{avg_time_dead:.1f}m`"
                ),
                inline=False
            )
        
            embed.set_footer(text=f"Session: {latest_date} • Use !last_session maps full for round-by-round")
            await ctx.send(embed=embed)
            await asyncio.sleep(3)

    async def show_maps_full_view(self, ctx, latest_date: str, sessions: List, session_ids: List, session_ids_str: str, player_count: int):
        """Show round-by-round breakdown for each map"""

        # Group into matches (R1 + R2 pairs) to handle duplicate maps
        map_matches = []
        i = 0
        while i < len(sessions):
            match_data = {'map_name': None, 'round1': [], 'round2': [], 'all': []}
            current_map = sessions[i][1]
            match_data['map_name'] = current_map

            # Collect R1 and R2 for this match
            while i < len(sessions) and sessions[i][1] == current_map and len(match_data['all']) < 2:
                round_id, map_name, round_num, actual_time = sessions[i]
                match_data['all'].append(round_id)
                if round_num == 1:
                    match_data['round1'].append(round_id)
                elif round_num == 2:
                    match_data['round2'].append(round_id)
                i += 1

            map_matches.append(match_data)

        # Count occurrences for display names
        map_counts = {}
        for match in map_matches:
            map_name = match['map_name']
            map_counts[map_name] = map_counts.get(map_name, 0) + 1

        map_occurrence = {}

        # For each match, show round 1, round 2, and combined stats
        for match in map_matches:
            map_name = match['map_name']
            rounds = {'round1': match['round1'], 'round2': match['round2'], 'all': match['all']}

            # Determine display name (add counter for duplicates)
            if map_counts[map_name] > 1:
                occurrence_num = map_occurrence.get(map_name, 0) + 1
                map_occurrence[map_name] = occurrence_num
                display_map_name = f"{map_name} (#{occurrence_num})"
            else:
                display_map_name = map_name
        
            # ===== ROUND 1 =====
            if rounds['round1']:
                await self._send_round_stats(ctx, display_map_name, "Round 1", rounds['round1'], latest_date)
                await asyncio.sleep(3)

            # ===== ROUND 2 =====
            if rounds['round2']:
                await self._send_round_stats(ctx, display_map_name, "Round 2", rounds['round2'], latest_date)
                await asyncio.sleep(3)

            # ===== MAP SUMMARY (both rounds combined) =====
            if rounds['all']:
                await self._send_round_stats(ctx, display_map_name, "Map Summary", rounds['all'], latest_date)
                await asyncio.sleep(3)

    async def _send_round_stats(self, ctx, map_name: str, round_label: str, round_session_ids: List, latest_date: str):
        """
        Send round stats embed - matches live round_publisher_service format exactly
        """
        round_ids_str = ','.join('?' * len(round_session_ids))
    
        # Using CTE to avoid duplicate placeholder references
        query = """
            WITH target_rounds AS (
                SELECT id FROM rounds WHERE id IN ({round_ids_str})
            )
            SELECT MAX(p.player_name) as player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                SUM(p.damage_given) as dmg_given,
                SUM(p.gibs) as gibs,
                SUM(p.headshot_kills) as headshots,
                AVG(p.accuracy) as accuracy,
                SUM(p.revives_given) as revives,
                SUM(p.times_revived) as times_revived,
                SUM(p.time_dead_minutes) as time_dead,
                SUM(p.team_damage_given) as team_dmg,
                SUM(p.time_played_minutes) as time_played,
                SUM(p.denied_playtime) as time_denied,
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as dpm
            FROM player_comprehensive_stats p
            WHERE p.round_id IN (SELECT id FROM target_rounds)
            GROUP BY p.player_guid
            ORDER BY kills DESC
        """
    
        players = await self.db_adapter.fetch_all(query, tuple(round_session_ids))
    
        if not players:
            return
    
        # Determine color based on round
        if "Round 1" in round_label:
            color = discord.Color.blue()
        elif "Round 2" in round_label:
            color = discord.Color.red()
        else:
            color = discord.Color.gold()  # Map summary
    
        # Build title matching live format
        if "Summary" in round_label:
            title = f"🗺️ {map_name.upper()} - Map Complete!"
            description = f"Aggregate stats from **{len(round_session_ids)} rounds** • {len(players)} players"
        else:
            title = f"🎮 {round_label} Complete - {map_name}"
            description = f"**Players:** {len(players)}"
    
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )

        # Rank emoji helper
        def get_rank_display(rank):
            if rank == 1:
                return "🥇"
            elif rank == 2:
                return "🥈"
            elif rank == 3:
                return "🥉"
            else:
                rank_str = str(rank)
                emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                               '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
                return ''.join(emoji_digits[d] for d in rank_str)

        # Smart chunking based on player count
        total_players = len(players)
        if total_players <= 6:
            chunk_size = (total_players + 1) // 2
        elif total_players <= 10:
            chunk_size = 5
        else:
            chunk_size = 6

        for i in range(0, len(players), chunk_size):
            chunk = players[i:i + chunk_size]
            
            if total_players <= chunk_size:
                field_name = '📊 All Players'
            else:
                field_name = f'📊 Players {i+1}-{i+len(chunk)}'
            
            player_lines = []
            for idx, player in enumerate(chunk):
                rank = i + idx + 1
                rank_display = get_rank_display(rank)
                
                (name, kills, deaths, dmg, gibs, hs, acc, revives,
                 got_revived, time_dead, team_dmg, time_played, time_denied, dpm) = player
                
                # Handle nulls
                kills = kills or 0
                deaths = deaths or 0
                dmg = dmg or 0
                gibs = gibs or 0
                hs = hs or 0
                acc = acc or 0
                revives = revives or 0
                got_revived = got_revived or 0
                time_dead = time_dead or 0
                team_dmg = team_dmg or 0
                time_played = time_played or 0
                time_denied = time_denied or 0
                dpm = dpm or 0
                
                name = (name or 'Unknown')[:16]
                kd_str = f'{kills}/{deaths}'
                
                # Format time_played as MM:SS
                tp_min = int(time_played)
                tp_sec = int((time_played - tp_min) * 60)
                
                # Format time_denied as MM:SS (it's in seconds)
                td_min = int(time_denied // 60)
                td_sec = int(time_denied % 60)

                # Calculate percentages (time_dead and time_played in minutes, time_denied in seconds)
                if time_played > 0:
                    dead_pct = (time_dead / time_played) * 100
                    denied_pct = ((time_denied / 60) / time_played) * 100
                else:
                    dead_pct = denied_pct = 0

                # Line 1: Rank + Name + Core stats
                line1 = (
                    f"{rank_display} **{name}** • K/D:`{kd_str}` "
                    f"DMG:`{int(dmg):,}` DPM:`{int(dpm)}` "
                    f"ACC:`{acc:.1f}%` HS:`{hs}`"
                )
                
                # Line 2: Support + Time stats
                line2 = (
                    f"     ↳ Rev:`{int(revives)}/{int(got_revived)}` Gibs:`{gibs}` "
                    f"TmDmg:`{int(team_dmg)}` "
                    f"⏱️`{tp_min}:{tp_sec:02d}` 💀`{time_dead:.1f}m`({dead_pct:.0f}%) ⏳`{td_min}:{td_sec:02d}`({denied_pct:.0f}%)"
                )
                
                player_lines.append(f"{line1}\n{line2}")
            
            embed.add_field(
                name=field_name,
                value='\n'.join(player_lines) if player_lines else 'No stats',
                inline=False
            )

        # Add round summary
        total_kills = sum((p[1] or 0) for p in players)
        total_deaths = sum((p[2] or 0) for p in players)
        total_dmg = sum((p[3] or 0) for p in players)
        total_hs = sum((p[5] or 0) for p in players)
        total_team_dmg = sum((p[10] or 0) for p in players)
        avg_acc = sum((p[6] or 0) for p in players) / len(players) if players else 0
        avg_dpm = sum((p[13] or 0) for p in players) / len(players) if players else 0
        avg_time_dead = sum((p[9] or 0) for p in players) / len(players) if players else 0

        embed.add_field(
            name="📊 Round Summary",
            value=(
                f"**Totals:** Kills:`{total_kills}` Deaths:`{total_deaths}` HS:`{total_hs}` "
                f"Damage:`{int(total_dmg):,}` TeamDmg:`{int(total_team_dmg):,}`\n"
                f"**Averages:** Accuracy:`{avg_acc:.1f}%` DPM:`{int(avg_dpm)}` DeadTime:`{avg_time_dead:.1f}m`"
            ),
            inline=False
        )
    
        embed.set_footer(text=f"Session: {latest_date}")
        await ctx.send(embed=embed)

    async def show_time_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Audit time metrics (time played, time dead, denied playtime)."""
        query = """
            SELECT MAX(p.clean_name) as player_name,
                p.player_guid,
                SUM(COALESCE(p.time_played_seconds, 0)) as time_played_seconds,
                SUM(COALESCE(p.time_dead_minutes, 0)) * 60 as time_dead_raw_seconds,
                SUM(
                    LEAST(
                        COALESCE(p.time_dead_minutes, 0) * 60,
                        COALESCE(p.time_played_seconds, 0)
                    )
                ) as time_dead_capped_seconds,
                SUM(COALESCE(p.denied_playtime, 0)) as denied_seconds,
                AVG(COALESCE(p.time_dead_ratio, 0)) as avg_dead_ratio,
                COUNT(DISTINCT p.round_id) as rounds_played
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_guid
            ORDER BY time_played_seconds DESC
        """

        rows = await self.db_adapter.fetch_all(
            query.format(session_ids_str=session_ids_str),
            tuple(session_ids)
        )

        if not rows:
            await ctx.send("❌ No time data available for latest session")
            return

        # Build embed
        dual_payload = None
        dual_players = {}
        dual_meta = {}
        if self.show_timing_dual:
            try:
                dual_payload = await self.get_session_timing_dual_by_guid(session_ids)
            except Exception as e:  # nosec B110
                logger.warning("Dual timing payload failed: %s", e)
                dual_payload = {"players": {}, "meta": {"reason": "Shadow timing lookup failed"}}
            dual_players = dual_payload.get("players", {}) if dual_payload else {}
            dual_meta = dual_payload.get("meta", {}) if dual_payload else {}

        description = (
            "Units: time played/dead/denied are seconds (displayed MM:SS). "
            "Time dead comes from `time_dead_minutes` (Lua), time denied from `denied_playtime`."
        )
        if self.show_timing_dual:
            description = (
                "Dual mode: `O` = legacy stored values, `N` = shadow-corrected values "
                "(Δ = N-O, MM:SS)."
            )

        embed = discord.Embed(
            title=f"⏱️ Time Audit - {latest_date}",
            description=description,
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )

        total_played = 0
        total_dead = 0
        total_denied = 0
        total_dead_new = 0
        total_denied_new = 0
        cap_hits = 0
        cap_seconds = 0

        # Limit rows to keep embed size manageable
        rows = rows[:15]

        lines = []
        for row in rows:
            name, guid, tp, td_raw, td_cap, denied, avg_ratio, rounds = row
            name = (name or "Unknown")[:16]
            tp = int(tp or 0)
            td_raw = int(round(td_raw or 0))
            td_cap = int(round(td_cap or 0))
            denied = int(denied or 0)
            avg_ratio = float(avg_ratio or 0)
            rounds = int(rounds or 0)

            total_played += tp
            total_dead += td_cap
            total_denied += denied

            dead_new = td_cap
            denied_new = denied
            telemetry_note = ""
            if self.show_timing_dual:
                player_shadow = dual_players.get(guid, {})
                if player_shadow:
                    dead_new = int(player_shadow.get("new_time_dead_seconds", td_cap) or 0)
                    denied_new = int(player_shadow.get("new_denied_seconds", denied) or 0)
                    missing_reason = (player_shadow.get("missing_reason") or "").lower()
                    if missing_reason.startswith("no lua"):
                        telemetry_note = " ⚠️no-lua"
                    elif "partial" in missing_reason:
                        telemetry_note = " ⚠️partial"
                else:
                    telemetry_note = " ⚠️shadow"

            total_dead_new += dead_new
            total_denied_new += denied_new

            diff = td_raw - td_cap
            if diff >= 5:
                cap_hits += 1
                cap_seconds += diff

            dead_pct = (td_cap / tp * 100) if tp > 0 else 0
            denied_pct = (denied / tp * 100) if tp > 0 else 0

            cap_note = f" ⚠️cap-{diff}s" if diff >= 5 else ""
            ratio_note = f" r{avg_ratio:.1f}%" if avg_ratio > 0 else ""

            if self.show_timing_dual:
                delta_dead = dead_new - td_cap
                delta_denied = denied_new - denied
                lines.append(
                    f"**{name}** ⏱`{self._format_seconds(tp)}` "
                    f"💀O`{self._format_seconds(td_cap)}` N`{self._format_seconds(dead_new)}`"
                    f"(Δ{self._format_delta_seconds(delta_dead)}) "
                    f"⏳O`{self._format_seconds(denied)}` N`{self._format_seconds(denied_new)}`"
                    f"(Δ{self._format_delta_seconds(delta_denied)})"
                    f"{telemetry_note}{cap_note}{ratio_note} ({rounds}r)"
                )
            else:
                lines.append(
                    f"**{name}** ⏱`{self._format_seconds(tp)}` "
                    f"💀`{self._format_seconds(td_cap)}`({dead_pct:.0f}%) "
                    f"⏳`{self._format_seconds(denied)}`({denied_pct:.0f}%)"
                    f"{cap_note}{ratio_note} ({rounds}r)"
                )

        # Chunk into fields (6 per field)
        chunk_size = 6
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            embed.add_field(
                name="Players" if i == 0 else "Players (cont.)",
                value="\n".join(chunk),
                inline=False
            )

        # Totals summary
        total_dead_pct = (total_dead / total_played * 100) if total_played > 0 else 0
        total_denied_pct = (total_denied / total_played * 100) if total_played > 0 else 0
        if self.show_timing_dual:
            total_dead_new_pct = (total_dead_new / total_played * 100) if total_played > 0 else 0
            total_denied_new_pct = (total_denied_new / total_played * 100) if total_played > 0 else 0
            embed.add_field(
                name="Totals",
                value=(
                    f"OLD: ⏱`{self._format_seconds(total_played)}` "
                    f"💀`{self._format_seconds(total_dead)}`({total_dead_pct:.0f}%) "
                    f"⏳`{self._format_seconds(total_denied)}`({total_denied_pct:.0f}%)\n"
                    f"NEW: ⏱`{self._format_seconds(total_played)}` "
                    f"💀`{self._format_seconds(total_dead_new)}`({total_dead_new_pct:.0f}%) "
                    f"⏳`{self._format_seconds(total_denied_new)}`({total_denied_new_pct:.0f}%)\n"
                    f"Δ: 💀`{self._format_delta_seconds(total_dead_new - total_dead)}` "
                    f"⏳`{self._format_delta_seconds(total_denied_new - total_denied)}`"
                ),
                inline=False
            )

            rounds_total = int(dual_meta.get("rounds_total") or len(session_ids or []))
            rounds_with_telemetry = int(dual_meta.get("rounds_with_telemetry") or 0)
            reason = dual_meta.get("reason") or ""
            if rounds_with_telemetry <= 0:
                footer = "Dual mode fallback: no Lua telemetry (N=O)"
            elif rounds_with_telemetry < rounds_total:
                footer = f"Dual mode partial: Lua {rounds_with_telemetry}/{rounds_total} rounds"
            else:
                footer = "Dual mode active: all rounds have Lua timing telemetry"
            if reason and reason != "OK":
                footer += f" • {reason}"
            if cap_hits > 0:
                footer += f" • cap-{cap_seconds}s"
            embed.set_footer(text=footer)
        else:
            embed.add_field(
                name="Totals",
                value=(
                    f"⏱`{self._format_seconds(total_played)}` "
                    f"💀`{self._format_seconds(total_dead)}`({total_dead_pct:.0f}%) "
                    f"⏳`{self._format_seconds(total_denied)}`({total_denied_pct:.0f}%)"
                ),
                inline=False
            )
            if cap_hits > 0:
                embed.set_footer(
                    text=f"Cap applied for {cap_hits} player(s), {cap_seconds}s trimmed"
                )
            else:
                embed.set_footer(text="No time_dead caps applied")

        await ctx.send(embed=embed)

    async def show_time_raw_export(self, ctx, latest_date: str, session_ids: List, session_ids_str: str):
        """Export raw Lua timing fields without aggregation/capping."""
        query = """
            SELECT r.round_date,
                r.map_name,
                r.round_number,
                p.player_name,
                p.player_guid,
                p.time_played_minutes,
                p.time_dead_minutes,
                p.time_dead_ratio,
                p.denied_playtime
            FROM player_comprehensive_stats p
            JOIN rounds r ON r.id = p.round_id
            WHERE p.round_id IN ({session_ids_str})
            ORDER BY r.round_date, r.map_name, r.round_number, p.player_name
        """

        rows = await self.db_adapter.fetch_all(
            query.format(session_ids_str=session_ids_str),
            tuple(session_ids)
        )

        if not rows:
            await ctx.send("❌ No raw time data available for latest session")
            return

        # Build CSV export (raw Lua values as stored)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "round_date",
            "map_name",
            "round_number",
            "player_name",
            "player_guid",
            "time_played_minutes",
            "time_dead_minutes",
            "time_dead_ratio",
            "denied_playtime_seconds"
        ])

        for row in rows:
            (round_date, map_name, round_number, player_name, player_guid,
             time_played_minutes, time_dead_minutes, time_dead_ratio, denied_playtime) = row
            writer.writerow([
                round_date,
                map_name,
                round_number,
                player_name,
                player_guid,
                float(time_played_minutes or 0),
                float(time_dead_minutes or 0),
                float(time_dead_ratio or 0),
                int(denied_playtime or 0)
            ])

        buffer.seek(0)
        filename = f"time_raw_{latest_date}.csv"
        file = discord.File(fp=io.BytesIO(buffer.getvalue().encode("utf-8")), filename=filename)

        embed = discord.Embed(
            title=f"⏱️ Raw Time Export - {latest_date}",
            description=(
                "Attached CSV contains **raw Lua values** as stored in DB (no aggregation, no caps).\n"
                "`denied_playtime` is in **seconds**; `time_dead_minutes` is in **minutes**."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Rows: {len(rows)}")
        await ctx.send(embed=embed, file=file)
