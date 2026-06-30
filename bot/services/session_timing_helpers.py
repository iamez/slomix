"""Shared session timing / stat helpers.

`SessionTimingHelpersMixin` was extracted from ~150 lines that were duplicated
near-byte-for-byte across `SessionViewHandlers` and `SessionGraphGenerator`
(Wave 2 audit Val B de-dup). Both host classes set ``self.db_adapter`` and
``self.timing_shadow_service`` in their ``__init__``; the instance methods here
rely on those attributes, the rest are static.
"""
from __future__ import annotations

import inspect
from typing import Any


class SessionTimingHelpersMixin:
    """Timing/row/service helpers shared by the session render + graph services."""

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

    async def _call_service_method(self, method_name: str, *args, **kwargs) -> tuple[bool, Any]:
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

    def _normalize_round_factor_payload(self, payload: Any) -> dict[int, float]:
        """Normalize service payload into round_id->factor mapping."""
        factors: dict[int, float] = {}
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

    async def _get_player_stats_columns(self):
        """Get columns for player_comprehensive_stats (cached)."""
        if hasattr(self, "_player_stats_columns"):
            return self._player_stats_columns

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
