"""UltimateETLegacyBot mixin: Webhook round-metadata queue + rate-limit helpers.

Extracted from ultimate_bot.py in P3e Sprint 7 / C.5.

All methods live on UltimateETLegacyBot via mixin inheritance.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

from bot.logging_config import get_logger

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _WebhookMetadataMixin:
    """Webhook round-metadata queue + rate-limit helpers for UltimateETLegacyBot."""

    def _normalize_lua_round_for_metadata_paths(self, raw_round) -> int:
        """
        Normalize Lua round numbering for webhook/gametime metadata paths.
        ET:Legacy may report g_currentRound=0 for stopwatch R2.
        """
        if raw_round is None:
            return 0
        raw_text = str(raw_round).strip()
        if not raw_text:
            return 0
        try:
            parsed = int(raw_text)
        except (TypeError, ValueError):
            return 0
        if parsed == 0 and raw_text.lstrip("+-") == "0":
            return 2
        if parsed < 0:
            return 0
        return parsed

    def _normalize_metadata_map_name(self, map_name: str | None) -> str:
        return str(map_name or "").strip().lower()

    def _pending_metadata_key(self, map_name: str | None, round_number) -> str | None:
        normalized_map = self._normalize_metadata_map_name(map_name)
        normalized_round = self._normalize_lua_round_for_metadata_paths(round_number)
        if not normalized_map or normalized_round <= 0:
            return None
        return f"{normalized_map}_R{normalized_round}"

    def _metadata_event_unix(self, metadata: dict) -> int:
        for field in ("round_end_unix", "round_start_unix"):
            try:
                value = int(metadata.get(field, 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
        return 0

    def _parse_stats_filename_context(self, filename: str) -> dict | None:
        match = re.match(
            r'^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)\.txt$',
            filename,
        )
        if not match:
            return None
        date_part, time_part, map_name, round_text = match.groups()
        try:
            filename_ts = int(
                datetime.strptime(
                    f"{date_part} {time_part}", "%Y-%m-%d %H%M%S"
                ).timestamp()
            )
        except ValueError:
            filename_ts = 0
        return {
            "map_name": map_name,
            "round_number": int(round_text),
            "filename_ts": filename_ts,
        }

    def _prune_pending_round_metadata(self) -> None:
        if not self._pending_round_metadata:
            return
        cutoff_unix = int(time.time()) - self._pending_metadata_ttl_seconds
        stale_keys = []
        for key, entries in list(self._pending_round_metadata.items()):
            pruned_entries = [
                entry for entry in entries
                if int(entry.get("received_unix", 0)) >= cutoff_unix
            ]
            if len(pruned_entries) > self._pending_metadata_max_per_key:
                pruned_entries = pruned_entries[-self._pending_metadata_max_per_key:]
            if pruned_entries:
                self._pending_round_metadata[key] = pruned_entries
            else:
                stale_keys.append(key)
        for key in stale_keys:
            self._pending_round_metadata.pop(key, None)

    def _queue_pending_metadata(self, round_metadata: dict, source: str) -> None:
        metadata_key = self._pending_metadata_key(
            round_metadata.get("map_name"),
            round_metadata.get("round_number"),
        )
        if not metadata_key:
            return

        self._prune_pending_round_metadata()
        bucket = self._pending_round_metadata[metadata_key]
        bucket.append(
            {
                "metadata": dict(round_metadata),
                "received_unix": int(time.time()),
                "source": source,
            }
        )
        if len(bucket) > self._pending_metadata_max_per_key:
            del bucket[:-self._pending_metadata_max_per_key]

    def _pop_pending_metadata(self, filename: str):
        """
        Pop best matching Lua metadata from pending queue for this stats filename.
        Chooses by timestamp proximity when both sides have timestamps.
        """
        self._prune_pending_round_metadata()
        if not self._pending_round_metadata:
            return None

        context = self._parse_stats_filename_context(filename)
        if not context:
            return None

        metadata_key = self._pending_metadata_key(
            context.get("map_name"),
            context.get("round_number"),
        )
        if not metadata_key:
            return None

        candidates = self._pending_round_metadata.get(metadata_key) or []
        if not candidates:
            return None

        filename_ts = int(context.get("filename_ts", 0) or 0)
        best_idx = len(candidates) - 1  # Fallback to newest metadata
        best_diff = None
        if filename_ts:
            for idx, entry in enumerate(candidates):
                meta_ts = self._metadata_event_unix(entry.get("metadata") or {})
                if not meta_ts:
                    continue
                diff = abs(meta_ts - filename_ts)
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_idx = idx

        selected = candidates.pop(best_idx)
        if not candidates:
            self._pending_round_metadata.pop(metadata_key, None)

        metadata = selected.get("metadata")
        if metadata:
            if best_diff is not None:
                webhook_logger.info(
                    f"📎 Attached pending Lua metadata for {metadata_key} (Δ {best_diff}s)"
                )
            else:
                webhook_logger.info(f"📎 Attached pending Lua metadata for {metadata_key}")
        return metadata

    def _prune_processed_webhook_message_ids(self) -> None:
        if not self._processed_webhook_message_ids:
            return
        cutoff = datetime.now() - timedelta(seconds=self._webhook_message_dedupe_ttl)
        while self._processed_webhook_message_ids and self._processed_webhook_message_ids[0][0] < cutoff:
            _, stale_id = self._processed_webhook_message_ids.popleft()
            self._processed_webhook_message_id_set.discard(stale_id)

    def _register_processed_webhook_message_id(self, message_id: int | None) -> bool:
        """
        Return False when this webhook message id was already seen recently.
        """
        if not message_id:
            return True
        self._prune_processed_webhook_message_ids()
        if message_id in self._processed_webhook_message_id_set:
            return False
        now = datetime.now()
        self._processed_webhook_message_ids.append((now, message_id))
        self._processed_webhook_message_id_set.add(message_id)
        return True

    def _check_rate_limit(
        self,
        bucket,
        bucket_key: int,
        *,
        max_events: int,
        window_seconds: int,
        label: str,
    ) -> bool:
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        timestamps = bucket[bucket_key]

        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= max_events:
            wait_time = (timestamps[0] + timedelta(seconds=window_seconds) - now).total_seconds()
            webhook_logger.warning(
                f"🚨 {label} {bucket_key} rate limited "
                f"({len(timestamps)} triggers in {window_seconds}s). "
                f"Retry in {wait_time:.1f}s"
            )
            return False

        timestamps.append(now)
        return True

    def _check_webhook_rate_limit(self, webhook_id: int) -> bool:
        """Rate limit filename/endstats triggers per webhook."""
        return self._check_rate_limit(
            self._webhook_rate_limit,
            webhook_id,
            max_events=self._webhook_rate_limit_max,
            window_seconds=self._webhook_rate_limit_window,
            label="Webhook",
        )

    def _check_stats_ready_rate_limit(self, webhook_id: int) -> bool:
        """Lightweight STATS_READY rate limit per webhook."""
        return self._check_rate_limit(
            self._stats_ready_rate_limit,
            webhook_id,
            max_events=self._stats_ready_rate_limit_max,
            window_seconds=self._stats_ready_rate_limit_window,
            label="STATS_READY webhook",
        )
