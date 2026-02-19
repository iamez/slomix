"""
Session timing shadow comparison service.

This service compares legacy timing fields from player_comprehensive_stats against
Lua spawn telemetry (lua_spawn_stats) for a given list of round/session IDs.
"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("bot.services.session_timing_shadow")


@dataclass(frozen=True)
class ComputedShadowTiming:
    """Deterministic shadow timing values for one player/round sample."""

    new_dead_seconds: int
    new_denied_playtime: int
    cap_limit_seconds: int
    lua_dead_seconds_raw: Optional[int]
    fallback_reason: str


@dataclass(frozen=True)
class PlayerRoundTimingShadow:
    """Round-scoped old/new timing comparison for one player GUID."""

    round_id: int
    map_name: str
    round_number: int
    player_guid: str
    player_name: str
    guid_prefix: str
    old_time_played_seconds: int
    old_dead_seconds: int
    old_denied_playtime: int
    new_dead_seconds: int
    new_denied_playtime: int
    dead_diff_seconds: int
    denied_diff_seconds: int
    lua_spawn_row_count: int
    lua_dead_seconds_raw: Optional[int]
    lua_dead_cap_seconds: int
    lua_round_duration_seconds: Optional[int]
    fallback_reason: str


@dataclass(frozen=True)
class PlayerSessionTimingShadow:
    """Session-scoped old/new timing aggregation for one player GUID."""

    player_guid: str
    player_name: str
    rounds: int
    old_time_played_seconds: int
    old_dead_seconds: int
    old_denied_playtime: int
    new_dead_seconds: int
    new_denied_playtime: int
    dead_diff_seconds: int
    denied_diff_seconds: int
    lua_spawn_rows: int
    rounds_with_lua: int
    coverage_percent: float
    fallback_reason_counts: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RoundTimingShadowDiagnostics:
    """Round-level diagnostics for shadow timing coverage and fallback reasons."""

    round_id: int
    map_name: str
    round_number: int
    player_count: int
    players_with_lua: int
    lua_spawn_rows_total: int
    lua_spawn_rows_matched: int
    coverage_percent: float
    fallback_reason_counts: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionTimingShadowResult:
    """Complete shadow timing result for a list of session_ids (round IDs)."""

    session_ids: Tuple[int, ...]
    generated_at: datetime
    player_rounds: Tuple[PlayerRoundTimingShadow, ...]
    player_summaries: Tuple[PlayerSessionTimingShadow, ...]
    round_diagnostics: Tuple[RoundTimingShadowDiagnostics, ...]
    overall_coverage_percent: float
    artifact_path: Optional[str]


@dataclass
class _LuaPrefixAggregate:
    """Mutable accumulator for Lua dead-seconds by (round_id, guid_prefix)."""

    dead_seconds: int = 0
    row_count: int = 0


class SessionTimingShadowService:
    """Service for session timing shadow comparisons and diagnostics."""

    def __init__(self, db_adapter, artifact_dir: str | Path = "logs/timing_shadow"):
        self.db_adapter = db_adapter
        self.artifact_dir = Path(artifact_dir)
        self._cache: Dict[Tuple[int, ...], SessionTimingShadowResult] = {}

    @staticmethod
    def _coerce_int(value: object) -> int:
        if value is None:
            return 0
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return max(low, min(value, high))

    @staticmethod
    def _guid_prefix(guid: object) -> str:
        return str(guid or "").strip().lower()[:8]

    @staticmethod
    def _format_reason(parts: List[str]) -> str:
        clean = [p for p in parts if p and p != "none"]
        return "|".join(clean) if clean else "none"

    @staticmethod
    def compute_shadow_values(
        *,
        time_played_seconds: int,
        old_dead_seconds: int,
        old_denied_playtime: int,
        lua_dead_seconds: Optional[int],
        lua_round_duration_seconds: Optional[int],
        lua_missing_reason: str = "lua_missing_for_guid_prefix",
    ) -> ComputedShadowTiming:
        """
        Compute deterministic NEW dead/denied values with strict invariants.

        Invariants:
        - dead >= 0
        - denied >= 0
        - dead <= min(time_played_seconds, lua_round_duration_seconds if present)
        """
        played = max(SessionTimingShadowService._coerce_int(time_played_seconds), 0)
        old_dead = SessionTimingShadowService._clamp(
            SessionTimingShadowService._coerce_int(old_dead_seconds),
            0,
            played,
        )
        old_denied = SessionTimingShadowService._clamp(
            SessionTimingShadowService._coerce_int(old_denied_playtime),
            0,
            played,
        )

        cap_limit = played
        if lua_round_duration_seconds is not None:
            lua_round_cap = max(SessionTimingShadowService._coerce_int(lua_round_duration_seconds), 0)
            cap_limit = min(cap_limit, lua_round_cap)

        reasons: List[str] = []
        raw_lua_dead: Optional[int] = None

        if lua_dead_seconds is None:
            reasons.append(lua_missing_reason or "lua_missing_for_guid_prefix")
            return ComputedShadowTiming(
                new_dead_seconds=old_dead,
                new_denied_playtime=old_denied,
                cap_limit_seconds=cap_limit,
                lua_dead_seconds_raw=None,
                fallback_reason=SessionTimingShadowService._format_reason(reasons),
            )

        raw_lua_dead = SessionTimingShadowService._coerce_int(lua_dead_seconds)
        bounded_dead = max(raw_lua_dead, 0)
        if raw_lua_dead < 0:
            reasons.append("lua_dead_negative_clamped")
        if bounded_dead > cap_limit:
            bounded_dead = cap_limit
            reasons.append("lua_dead_capped_to_plausible_limit")

        old_active = max(played - old_dead, 0)
        new_active = max(played - bounded_dead, 0)

        if old_active == 0:
            new_denied = SessionTimingShadowService._clamp(old_denied, 0, new_active)
            if old_denied > 0:
                reasons.append("old_active_zero")
        else:
            denied_rate = old_denied / old_active
            projected_denied = int(round(denied_rate * new_active))
            new_denied = SessionTimingShadowService._clamp(projected_denied, 0, new_active)

        return ComputedShadowTiming(
            new_dead_seconds=bounded_dead,
            new_denied_playtime=new_denied,
            cap_limit_seconds=cap_limit,
            lua_dead_seconds_raw=raw_lua_dead,
            fallback_reason=SessionTimingShadowService._format_reason(reasons),
        )

    async def compare_session(
        self,
        session_ids: Sequence[int],
        *,
        force_refresh: bool = False,
    ) -> SessionTimingShadowResult:
        """
        Compare old/new timing fields for a session scope (list of round IDs).
        """
        normalized_ids = tuple(sorted({self._coerce_int(sid) for sid in session_ids if sid is not None}))
        if not normalized_ids:
            return SessionTimingShadowResult(
                session_ids=tuple(),
                generated_at=datetime.utcnow(),
                player_rounds=tuple(),
                player_summaries=tuple(),
                round_diagnostics=tuple(),
                overall_coverage_percent=0.0,
                artifact_path=None,
            )

        if not force_refresh and normalized_ids in self._cache:
            return self._cache[normalized_ids]

        generated_at = datetime.utcnow()
        round_rows = await self._fetch_round_rows(normalized_ids)
        old_rows = await self._fetch_old_rows(normalized_ids)

        lua_query_error = False
        try:
            lua_rows = await self._fetch_lua_rows(normalized_ids)
        except Exception as exc:
            logger.warning("timing_shadow lua query failed: %s", exc)
            lua_rows = []
            lua_query_error = True

        round_meta: Dict[int, Tuple[str, int, Optional[int]]] = {}
        for row in round_rows:
            rid, map_name, round_number, lua_duration = tuple(row)
            round_meta[self._coerce_int(rid)] = (
                str(map_name or "unknown"),
                self._coerce_int(round_number),
                None if lua_duration is None else self._coerce_int(lua_duration),
            )

        lua_by_prefix: Dict[Tuple[int, str], _LuaPrefixAggregate] = defaultdict(_LuaPrefixAggregate)
        round_lua_rows_total: Counter[int] = Counter()

        for row in lua_rows:
            rid, lua_guid, lua_dead = tuple(row)
            round_id = self._coerce_int(rid)
            guid_prefix = self._guid_prefix(lua_guid)
            if not guid_prefix:
                continue

            key = (round_id, guid_prefix)
            bucket = lua_by_prefix[key]
            bucket.dead_seconds += max(self._coerce_int(lua_dead), 0)
            bucket.row_count += 1
            round_lua_rows_total[round_id] += 1

        player_rounds: List[PlayerRoundTimingShadow] = []
        round_player_counts: Counter[int] = Counter()
        round_players_with_lua: Counter[int] = Counter()
        round_lua_rows_matched: Counter[int] = Counter()
        round_fallbacks: Dict[int, Counter[str]] = defaultdict(Counter)

        for row in old_rows:
            (
                rid,
                player_guid,
                player_name,
                old_played_seconds,
                old_dead_seconds,
                old_denied_playtime,
            ) = tuple(row)

            round_id = self._coerce_int(rid)
            guid = str(player_guid or "")
            guid_prefix = self._guid_prefix(guid)
            map_name, round_number, lua_round_duration = round_meta.get(round_id, ("unknown", 0, None))

            old_played = max(self._coerce_int(old_played_seconds), 0)
            old_dead = self._clamp(self._coerce_int(old_dead_seconds), 0, old_played)
            old_denied = self._clamp(self._coerce_int(old_denied_playtime), 0, old_played)

            lua_bucket = lua_by_prefix.get((round_id, guid_prefix))
            lua_dead = lua_bucket.dead_seconds if lua_bucket else None
            lua_row_count = lua_bucket.row_count if lua_bucket else 0

            if lua_query_error:
                missing_reason = "lua_query_failed"
            elif round_lua_rows_total.get(round_id, 0) == 0:
                missing_reason = "lua_missing_for_round"
            else:
                missing_reason = "lua_missing_for_guid_prefix"

            computed = self.compute_shadow_values(
                time_played_seconds=old_played,
                old_dead_seconds=old_dead,
                old_denied_playtime=old_denied,
                lua_dead_seconds=lua_dead,
                lua_round_duration_seconds=lua_round_duration,
                lua_missing_reason=missing_reason,
            )

            comparison = PlayerRoundTimingShadow(
                round_id=round_id,
                map_name=map_name,
                round_number=round_number,
                player_guid=guid,
                player_name=str(player_name or guid),
                guid_prefix=guid_prefix,
                old_time_played_seconds=old_played,
                old_dead_seconds=old_dead,
                old_denied_playtime=old_denied,
                new_dead_seconds=computed.new_dead_seconds,
                new_denied_playtime=computed.new_denied_playtime,
                dead_diff_seconds=computed.new_dead_seconds - old_dead,
                denied_diff_seconds=computed.new_denied_playtime - old_denied,
                lua_spawn_row_count=lua_row_count,
                lua_dead_seconds_raw=computed.lua_dead_seconds_raw,
                lua_dead_cap_seconds=computed.cap_limit_seconds,
                lua_round_duration_seconds=lua_round_duration,
                fallback_reason=computed.fallback_reason,
            )
            player_rounds.append(comparison)

            round_player_counts[round_id] += 1
            if lua_row_count > 0:
                round_players_with_lua[round_id] += 1
            round_lua_rows_matched[round_id] += lua_row_count
            round_fallbacks[round_id][comparison.fallback_reason] += 1

        round_diagnostics = self._build_round_diagnostics(
            session_ids=normalized_ids,
            round_meta=round_meta,
            round_player_counts=round_player_counts,
            round_players_with_lua=round_players_with_lua,
            round_lua_rows_total=round_lua_rows_total,
            round_lua_rows_matched=round_lua_rows_matched,
            round_fallbacks=round_fallbacks,
        )

        player_summaries = self._build_player_summaries(player_rounds)

        total_player_rows = sum(round_player_counts.values())
        total_players_with_lua = sum(round_players_with_lua.values())
        overall_coverage_percent = round(
            ((total_players_with_lua / total_player_rows) * 100.0) if total_player_rows else 0.0,
            2,
        )

        artifact_path = self._write_debug_artifact(
            session_ids=normalized_ids,
            player_rows=player_rounds,
            round_diagnostics=round_diagnostics,
            generated_at=generated_at,
        )

        coverage_by_round = {diag.round_id: diag.coverage_percent for diag in round_diagnostics}
        total_lua_rows_by_round = {diag.round_id: diag.lua_spawn_rows_total for diag in round_diagnostics}
        session_scope = ",".join(str(sid) for sid in normalized_ids)
        for row in player_rounds:
            logger.info(
                "timing_shadow_player session_scope=%s round_id=%s player_guid=%s old_dead=%s new_dead=%s "
                "old_denied=%s new_denied=%s lua_rows=%s lua_rows_total=%s coverage_pct=%.2f "
                "fallback_reason=%s",
                session_scope,
                row.round_id,
                row.player_guid,
                row.old_dead_seconds,
                row.new_dead_seconds,
                row.old_denied_playtime,
                row.new_denied_playtime,
                row.lua_spawn_row_count,
                total_lua_rows_by_round.get(row.round_id, 0),
                coverage_by_round.get(row.round_id, 0.0),
                row.fallback_reason,
            )

        result = SessionTimingShadowResult(
            session_ids=normalized_ids,
            generated_at=generated_at,
            player_rounds=tuple(sorted(player_rounds, key=lambda r: (r.round_id, r.player_guid))),
            player_summaries=tuple(player_summaries),
            round_diagnostics=tuple(round_diagnostics),
            overall_coverage_percent=overall_coverage_percent,
            artifact_path=artifact_path,
        )
        self._cache[normalized_ids] = result

        logger.info(
            "timing_shadow_session_complete session_ids=%s rows=%d players=%d coverage_pct=%.2f artifact=%s",
            ",".join(str(sid) for sid in normalized_ids),
            len(result.player_rounds),
            len(result.player_summaries),
            result.overall_coverage_percent,
            result.artifact_path or "none",
        )
        return result

    def get_player_summary(
        self,
        result: SessionTimingShadowResult,
        player_guid: str,
    ) -> Optional[PlayerSessionTimingShadow]:
        """Lookup aggregated session timing for one player GUID (supports prefix match)."""
        needle = self._guid_prefix(player_guid)
        if not needle:
            return None

        for summary in result.player_summaries:
            if summary.player_guid == player_guid:
                return summary
        for summary in result.player_summaries:
            if self._guid_prefix(summary.player_guid) == needle:
                return summary
        return None

    def get_player_rounds(
        self,
        result: SessionTimingShadowResult,
        player_guid: str,
    ) -> Tuple[PlayerRoundTimingShadow, ...]:
        """Lookup all round rows for one player GUID (supports prefix match)."""
        needle = self._guid_prefix(player_guid)
        if not needle:
            return tuple()
        rows = [
            row
            for row in result.player_rounds
            if row.player_guid == player_guid or self._guid_prefix(row.player_guid) == needle
        ]
        return tuple(rows)

    def top_n_diff_summary(
        self,
        result: SessionTimingShadowResult,
        *,
        n: int = 5,
        metric: str = "dead_diff_seconds",
        absolute: bool = True,
    ) -> List[PlayerSessionTimingShadow]:
        """Return top-N player summaries by requested diff metric."""
        if n <= 0:
            return []

        allowed = {"dead_diff_seconds", "denied_diff_seconds"}
        if metric not in allowed:
            raise ValueError(f"Unsupported metric '{metric}'. Allowed: {sorted(allowed)}")

        def sort_key(row: PlayerSessionTimingShadow) -> Tuple[float, str]:
            value = getattr(row, metric)
            score = abs(value) if absolute else value
            return score, row.player_guid

        return sorted(result.player_summaries, key=sort_key, reverse=True)[:n]

    async def _fetch_round_rows(self, session_ids: Sequence[int]):
        placeholders = ",".join("?" for _ in session_ids)
        query = f"""
            SELECT
                r.id,
                r.map_name,
                r.round_number,
                l.actual_duration_seconds
            FROM rounds r
            LEFT JOIN LATERAL (
                SELECT actual_duration_seconds
                FROM lua_round_teams
                WHERE round_id = r.id
                ORDER BY captured_at DESC
                LIMIT 1
            ) l ON TRUE
            WHERE r.id IN ({placeholders})
            ORDER BY r.id
        """  # nosec B608 - parameterized
        return await self.db_adapter.fetch_all(query, tuple(session_ids))

    async def _fetch_old_rows(self, session_ids: Sequence[int]):
        placeholders = ",".join("?" for _ in session_ids)
        query = f"""
            SELECT
                p.round_id,
                p.player_guid,
                MAX(p.player_name) AS player_name,
                COALESCE(SUM(GREATEST(COALESCE(p.time_played_seconds, 0), 0)), 0) AS time_played_seconds,
                COALESCE(
                    SUM(
                        LEAST(
                            GREATEST(COALESCE(p.time_dead_minutes, 0) * 60, 0),
                            GREATEST(COALESCE(p.time_played_seconds, 0), 0)
                        )
                    ),
                    0
                ) AS old_dead_seconds,
                COALESCE(SUM(GREATEST(COALESCE(p.denied_playtime, 0), 0)), 0) AS old_denied_playtime
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({placeholders})
            GROUP BY p.round_id, p.player_guid
            ORDER BY p.round_id, p.player_guid
        """  # nosec B608 - parameterized
        return await self.db_adapter.fetch_all(query, tuple(session_ids))

    async def _fetch_lua_rows(self, session_ids: Sequence[int]):
        placeholders = ",".join("?" for _ in session_ids)
        query = f"""
            SELECT
                round_id,
                player_guid,
                COALESCE(dead_seconds, 0) AS dead_seconds
            FROM lua_spawn_stats
            WHERE round_id IN ({placeholders})
              AND player_guid IS NOT NULL
            ORDER BY round_id, player_guid
        """  # nosec B608 - parameterized
        return await self.db_adapter.fetch_all(query, tuple(session_ids))

    def _build_round_diagnostics(
        self,
        *,
        session_ids: Tuple[int, ...],
        round_meta: Dict[int, Tuple[str, int, Optional[int]]],
        round_player_counts: Counter[int],
        round_players_with_lua: Counter[int],
        round_lua_rows_total: Counter[int],
        round_lua_rows_matched: Counter[int],
        round_fallbacks: Dict[int, Counter[str]],
    ) -> List[RoundTimingShadowDiagnostics]:
        diagnostics: List[RoundTimingShadowDiagnostics] = []
        for round_id in session_ids:
            map_name, round_number, _ = round_meta.get(round_id, ("unknown", 0, None))
            player_count = round_player_counts.get(round_id, 0)
            players_with_lua = round_players_with_lua.get(round_id, 0)
            coverage = round((players_with_lua / player_count) * 100.0, 2) if player_count else 0.0

            diagnostics.append(
                RoundTimingShadowDiagnostics(
                    round_id=round_id,
                    map_name=map_name,
                    round_number=round_number,
                    player_count=player_count,
                    players_with_lua=players_with_lua,
                    lua_spawn_rows_total=round_lua_rows_total.get(round_id, 0),
                    lua_spawn_rows_matched=round_lua_rows_matched.get(round_id, 0),
                    coverage_percent=coverage,
                    fallback_reason_counts=dict(sorted(round_fallbacks.get(round_id, Counter()).items())),
                )
            )
        return diagnostics

    def _build_player_summaries(
        self,
        player_rows: Sequence[PlayerRoundTimingShadow],
    ) -> List[PlayerSessionTimingShadow]:
        accumulator: Dict[str, Dict[str, object]] = {}

        for row in player_rows:
            bucket = accumulator.get(row.player_guid)
            if not bucket:
                bucket = {
                    "player_name": row.player_name,
                    "rounds": 0,
                    "old_time_played_seconds": 0,
                    "old_dead_seconds": 0,
                    "old_denied_playtime": 0,
                    "new_dead_seconds": 0,
                    "new_denied_playtime": 0,
                    "dead_diff_seconds": 0,
                    "denied_diff_seconds": 0,
                    "lua_spawn_rows": 0,
                    "rounds_with_lua": 0,
                    "fallback_reason_counts": Counter(),
                }
                accumulator[row.player_guid] = bucket

            bucket["rounds"] = int(bucket["rounds"]) + 1
            bucket["old_time_played_seconds"] = int(bucket["old_time_played_seconds"]) + row.old_time_played_seconds
            bucket["old_dead_seconds"] = int(bucket["old_dead_seconds"]) + row.old_dead_seconds
            bucket["old_denied_playtime"] = int(bucket["old_denied_playtime"]) + row.old_denied_playtime
            bucket["new_dead_seconds"] = int(bucket["new_dead_seconds"]) + row.new_dead_seconds
            bucket["new_denied_playtime"] = int(bucket["new_denied_playtime"]) + row.new_denied_playtime
            bucket["dead_diff_seconds"] = int(bucket["dead_diff_seconds"]) + row.dead_diff_seconds
            bucket["denied_diff_seconds"] = int(bucket["denied_diff_seconds"]) + row.denied_diff_seconds
            bucket["lua_spawn_rows"] = int(bucket["lua_spawn_rows"]) + row.lua_spawn_row_count
            if row.lua_spawn_row_count > 0:
                bucket["rounds_with_lua"] = int(bucket["rounds_with_lua"]) + 1
            fallback_counts = bucket["fallback_reason_counts"]
            if isinstance(fallback_counts, Counter):
                fallback_counts[row.fallback_reason] += 1

        summaries: List[PlayerSessionTimingShadow] = []
        for player_guid, bucket in accumulator.items():
            rounds = int(bucket["rounds"])
            coverage = round((int(bucket["rounds_with_lua"]) / rounds) * 100.0, 2) if rounds else 0.0
            fallback_counts = bucket["fallback_reason_counts"]
            summaries.append(
                PlayerSessionTimingShadow(
                    player_guid=player_guid,
                    player_name=str(bucket["player_name"]),
                    rounds=rounds,
                    old_time_played_seconds=int(bucket["old_time_played_seconds"]),
                    old_dead_seconds=int(bucket["old_dead_seconds"]),
                    old_denied_playtime=int(bucket["old_denied_playtime"]),
                    new_dead_seconds=int(bucket["new_dead_seconds"]),
                    new_denied_playtime=int(bucket["new_denied_playtime"]),
                    dead_diff_seconds=int(bucket["dead_diff_seconds"]),
                    denied_diff_seconds=int(bucket["denied_diff_seconds"]),
                    lua_spawn_rows=int(bucket["lua_spawn_rows"]),
                    rounds_with_lua=int(bucket["rounds_with_lua"]),
                    coverage_percent=coverage,
                    fallback_reason_counts=dict(
                        sorted((fallback_counts or Counter()).items())  # type: ignore[arg-type]
                    ),
                )
            )

        return sorted(summaries, key=lambda row: (abs(row.dead_diff_seconds), row.player_guid), reverse=True)

    def _write_debug_artifact(
        self,
        *,
        session_ids: Tuple[int, ...],
        player_rows: Sequence[PlayerRoundTimingShadow],
        round_diagnostics: Sequence[RoundTimingShadowDiagnostics],
        generated_at: datetime,
    ) -> Optional[str]:
        if not player_rows:
            return None

        try:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
            if len(session_ids) == 1:
                session_token = str(session_ids[0])
            else:
                session_token = f"{session_ids[0]}_{session_ids[-1]}_{len(session_ids)}r"

            filename = (
                f"timing_shadow_{session_token}_{generated_at.strftime('%Y%m%d_%H%M%S')}.csv"
            )
            artifact_path = self.artifact_dir / filename

            coverage_by_round = {diag.round_id: diag.coverage_percent for diag in round_diagnostics}
            with artifact_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(
                    [
                        "round_id",
                        "map_name",
                        "round_number",
                        "player_guid",
                        "player_name",
                        "guid_prefix",
                        "old_time_played_seconds",
                        "old_dead_seconds",
                        "new_dead_seconds",
                        "old_denied_playtime",
                        "new_denied_playtime",
                        "dead_diff_seconds",
                        "denied_diff_seconds",
                        "lua_spawn_row_count",
                        "lua_dead_seconds_raw",
                        "lua_dead_cap_seconds",
                        "lua_round_duration_seconds",
                        "coverage_percent",
                        "fallback_reason",
                    ]
                )
                for row in player_rows:
                    writer.writerow(
                        [
                            row.round_id,
                            row.map_name,
                            row.round_number,
                            row.player_guid,
                            row.player_name,
                            row.guid_prefix,
                            row.old_time_played_seconds,
                            row.old_dead_seconds,
                            row.new_dead_seconds,
                            row.old_denied_playtime,
                            row.new_denied_playtime,
                            row.dead_diff_seconds,
                            row.denied_diff_seconds,
                            row.lua_spawn_row_count,
                            row.lua_dead_seconds_raw,
                            row.lua_dead_cap_seconds,
                            row.lua_round_duration_seconds,
                            coverage_by_round.get(row.round_id, 0.0),
                            row.fallback_reason,
                        ]
                    )
            return str(artifact_path)
        except Exception as exc:
            logger.warning("timing_shadow failed to write CSV artifact: %s", exc)
            return None
