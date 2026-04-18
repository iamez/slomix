"""AvailabilityPollCog mixin: Daily reminder scheduler + promotion job dispatch + voice-check followup.

Extracted from bot/cogs/availability_poll_cog.py in Mega Audit v4 / Sprint 1.

All methods live on AvailabilityPollCog via mixin inheritance.
Discord.py's CogMeta scans base classes via MRO for @commands.command,
@commands.Cog.listener, and @tasks.loop decorators, so these work unchanged.
"""
from __future__ import annotations

import json
import re
from datetime import date as dt_date
from datetime import datetime, timezone
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from discord.ext import tasks

from bot.logging_config import get_logger
from bot.services.availability_notifier_service import (
    EVENT_DAILY_REMINDER,
    EVENT_SESSION_READY,
)

logger = get_logger("bot.core")


class _AvailabilitySchedulerMixin:
    """Daily reminder scheduler + promotion job dispatch + voice-check followup for AvailabilityPollCog."""

    async def _run_scheduler_with_lock(self, now: datetime) -> None:
        lock_acquired = False
        try:
            lock_row = await self.bot.db_adapter.fetch_one(
                "SELECT pg_try_advisory_lock($1)",
                (self.scheduler_lock_key,),
            )
            lock_acquired = bool(lock_row and lock_row[0])
        except Exception:
            # SQLite/local adapters do not support advisory locks.
            lock_acquired = True

        if not lock_acquired:
            return

        try:
            today = now.date()
            if self._is_reminder_due(now):
                if self.last_daily_reminder_date != today:
                    await self._send_daily_reminder(today)
                    self.last_daily_reminder_date = today
            await self._check_session_ready(today)
            if self.promotion_enabled:
                await self._process_promotion_jobs(now)
        finally:
            try:
                await self.bot.db_adapter.fetch_one(
                    "SELECT pg_advisory_unlock($1)",
                    (self.scheduler_lock_key,),
                )
            except Exception:
                logger.debug("Advisory unlock failed (best-effort; lock expires on disconnect)", exc_info=True)

    def _is_reminder_due(self, now: datetime) -> bool:
        try:
            hour, minute = map(int, self.daily_reminder_time.split(":"))
        except (TypeError, ValueError):
            return False
        return now.hour == hour and now.minute == minute

    async def _send_daily_reminder(self, today: dt_date) -> None:
        rows = await self.bot.db_adapter.fetch_all(
            "SELECT discord_id FROM player_links WHERE discord_id IS NOT NULL",
        )
        user_ids = [int(row[0]) for row in (rows or []) if row[0]]
        if not user_ids:
            return

        event_key = self.notifier.build_event_key(EVENT_DAILY_REMINDER, today)
        message = (
            "🎮 Availability check-in: set your status for today and tomorrow "
            "on the website or with !avail."
        )
        announce = (
            "📣 Daily availability reminder is out. "
            "Set status on the website or run `!avail today LOOKING`."
        )
        result = await self.notifier.notify_users(
            event_type=EVENT_DAILY_REMINDER,
            event_key=event_key,
            message=message,
            user_ids=user_ids,
            payload={"date": today.isoformat()},
            announce_message=announce,
        )
        logger.info(
            "Daily reminder dispatched: sent=%s failed=%s skipped=%s",
            result.sent,
            result.failed,
            result.skipped,
        )

    async def _check_session_ready(self, today: dt_date) -> None:
        count_row = await self.bot.db_adapter.fetch_one(
            "SELECT COUNT(*) FROM availability_entries WHERE entry_date = $1 AND status = 'LOOKING'",
            (today,),
        )
        looking_count = int(count_row[0]) if count_row else 0
        if looking_count < self.session_ready_threshold:
            return

        event_key = self.notifier.build_event_key(
            EVENT_SESSION_READY,
            today,
            qualifier=f"threshold={self.session_ready_threshold}",
        )

        users = await self.bot.db_adapter.fetch_all(
            """
            SELECT DISTINCT user_id
            FROM availability_entries
            WHERE entry_date = $1
              AND status IN ('LOOKING', 'AVAILABLE', 'MAYBE')
            """,
            (today,),
        )
        user_ids = [int(row[0]) for row in (users or []) if row[0]]
        if not user_ids:
            return

        message = (
            f"🔥 Session ready for {today.isoformat()}: "
            f"{looking_count} players marked Looking."
        )
        announce = (
            f"🔥 Session ready: {looking_count} players are looking to play "
            f"(threshold {self.session_ready_threshold})."
        )
        result = await self.notifier.notify_users(
            event_type=EVENT_SESSION_READY,
            event_key=event_key,
            message=message,
            user_ids=user_ids,
            payload={
                "date": today.isoformat(),
                "looking_count": looking_count,
                "threshold": self.session_ready_threshold,
            },
            announce_message=announce,
        )
        logger.info(
            "Session-ready notifications dispatched: sent=%s failed=%s skipped=%s",
            result.sent,
            result.failed,
            result.skipped,
        )

    @staticmethod
    def _decode_json_dict(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
                if isinstance(loaded, dict):
                    return loaded
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _decode_json_list(value) -> list[dict]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
                if isinstance(loaded, list):
                    return [item for item in loaded if isinstance(item, dict)]
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    def _normalize_name_for_match(name: str | None) -> str:
        text = str(name or "").strip().lower()
        text = re.sub(r"\^[0-9]", "", text)
        text = re.sub(r"[^a-z0-9]+", "", text)
        return text

    @staticmethod
    def _is_time_in_quiet_window(local_time: dt_time, quiet_start: dt_time, quiet_end: dt_time) -> bool:
        """Evaluate quiet-hours windows, including overnight ranges (e.g. 23:00-08:00)."""
        current_minutes = (local_time.hour * 60) + local_time.minute
        start_minutes = (quiet_start.hour * 60) + quiet_start.minute
        end_minutes = (quiet_end.hour * 60) + quiet_end.minute

        if start_minutes == end_minutes:
            return True
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def _recipient_in_quiet_hours_now(self, recipient: dict, *, now_utc: datetime | None = None) -> bool:
        quiet_hours = recipient.get("quiet_hours")
        if not isinstance(quiet_hours, dict):
            quiet_hours = self._decode_json_dict(quiet_hours)

        start_raw = str(quiet_hours.get("start") or "").strip()
        end_raw = str(quiet_hours.get("end") or "").strip()
        if not start_raw or not end_raw:
            return False
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", start_raw):
            return False
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", end_raw):
            return False

        start_hour, start_minute = map(int, start_raw.split(":"))
        end_hour, end_minute = map(int, end_raw.split(":"))
        quiet_start = dt_time(hour=start_hour, minute=start_minute)
        quiet_end = dt_time(hour=end_hour, minute=end_minute)

        timezone_name = str(recipient.get("timezone") or self.promotion_timezone or "Europe/Ljubljana").strip()
        try:
            recipient_tz = ZoneInfo(timezone_name)
        except Exception:
            recipient_tz = self.timezone

        reference_utc = now_utc or datetime.now(timezone.utc)
        if reference_utc.tzinfo is None:
            reference_utc = reference_utc.replace(tzinfo=timezone.utc)
        local_now = reference_utc.astimezone(recipient_tz).time().replace(tzinfo=None)

        return self._is_time_in_quiet_window(local_now, quiet_start, quiet_end)

    @staticmethod
    def _coerce_campaign_date(value) -> dt_date:
        if isinstance(value, dt_date):
            return value
        return dt_date.fromisoformat(str(value)[:10])

    @staticmethod
    def _promotion_event_key(*, campaign_date: dt_date, phase: str) -> str:
        return f"PROMOTE:{phase}:{campaign_date.isoformat()}"

    async def _process_promotion_jobs(self, now: datetime) -> None:
        now_utc = now.astimezone(timezone.utc)
        rows = await self.bot.db_adapter.fetch_all(
            """
            SELECT id, campaign_id, job_type
            FROM availability_promotion_jobs
            WHERE status = 'pending'
              AND run_at <= $1
            ORDER BY run_at ASC, id ASC
            LIMIT 20
            """,
            (now_utc,),
        )
        if not rows:
            return

        for row in rows:
            job_id = int(row[0])
            campaign_id = int(row[1])
            job_type = str(row[2])

            claim = await self.bot.db_adapter.fetch_one(
                """
                UPDATE availability_promotion_jobs
                SET status = 'running',
                    attempts = COALESCE(attempts, 0) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                  AND status = 'pending'
                RETURNING attempts, max_attempts
                """,
                (job_id,),
            )
            if not claim:
                continue

            attempts = int(claim[0] or 0)
            max_attempts = int(claim[1] or self.promotion_job_max_attempts)

            try:
                campaign = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT id,
                           campaign_date,
                           initiated_by_user_id,
                           initiated_by_discord_id,
                           dry_run,
                           status,
                           recipients_snapshot
                    FROM availability_promotion_campaigns
                    WHERE id = $1
                    LIMIT 1
                    """,
                    (campaign_id,),
                )
                if not campaign:
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = 'skipped',
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = 'campaign not found',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (job_id,),
                    )
                    continue

                campaign_date = self._coerce_campaign_date(campaign[1])
                recipients = self._decode_json_list(campaign[6])
                if job_type in {"send_reminder_2045", "send_start_2100"}:
                    sent, failed = await self._dispatch_promotion_notification(
                        campaign_id=campaign_id,
                        job_id=job_id,
                        job_type=job_type,
                        campaign_date=campaign_date,
                        recipients=recipients,
                    )
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = $1,
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                        """,
                        ("failed" if sent == 0 and failed > 0 else "sent", job_id),
                    )
                    if job_type == "send_start_2100":
                        campaign_status = "sent" if failed == 0 else ("partial" if sent > 0 else "failed")
                        await self.bot.db_adapter.execute(
                            """
                            UPDATE availability_promotion_campaigns
                            SET status = $1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = $2
                            """,
                            (campaign_status, campaign_id),
                        )
                elif job_type == "voice_check_2100":
                    await self._dispatch_voice_check_followup(
                        campaign_id=campaign_id,
                        job_id=job_id,
                        campaign_date=campaign_date,
                        recipients=recipients,
                        initiated_by_discord_id=int(campaign[3]),
                    )
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = 'sent',
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (job_id,),
                    )
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_campaigns
                        SET status = 'followup_sent',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (campaign_id,),
                    )
                else:
                    await self.bot.db_adapter.execute(
                        """
                        UPDATE availability_promotion_jobs
                        SET status = 'skipped',
                            sent_at = CURRENT_TIMESTAMP,
                            last_error = 'unsupported job type',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (job_id,),
                    )
            except Exception as exc:
                error_text = str(exc).strip()[:1200]
                retry_status = "pending" if attempts < max_attempts else "failed"
                await self.bot.db_adapter.execute(
                    """
                    UPDATE availability_promotion_jobs
                    SET status = $1,
                        last_error = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $3
                    """,
                    (retry_status, error_text, job_id),
                )
                logger.warning(
                    "Promotion job failed id=%s campaign=%s type=%s attempts=%s/%s error=%s",
                    job_id,
                    campaign_id,
                    job_type,
                    attempts,
                    max_attempts,
                    error_text,
                )

    async def _dispatch_promotion_notification(
        self,
        *,
        campaign_id: int,
        job_id: int,
        job_type: str,
        campaign_date: dt_date,
        recipients: list[dict],
    ) -> tuple[int, int]:
        sent = 0
        failed = 0
        phase = "T-15" if job_type == "send_reminder_2045" else "T0"
        event_key = self._promotion_event_key(campaign_date=campaign_date, phase=phase)
        message = (
            "Session reminder: kickoff is at 21:00 CET (in 15 minutes). "
            "Join voice if you're available."
            if job_type == "send_reminder_2045"
            else "Session starts now (21:00 CET). Join voice and game server when ready."
        )

        for recipient in recipients:
            user_id = int(recipient.get("user_id") or 0)
            channel_type = str(recipient.get("selected_channel") or "discord").lower()
            if self._recipient_in_quiet_hours_now(recipient):
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="recipient in quiet hours",
                    payload={"job_type": job_type},
                )
                continue
            target = self._promotion_target_for_recipient(recipient, channel_type)
            if not target:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="missing delivery target",
                    payload={"job_type": job_type},
                )
                continue

            try:
                status, message_id = await self.notifier.send_via_channel_idempotent(
                    user_id=user_id,
                    event_key=event_key,
                    channel_type=channel_type,
                    target=target,
                    message=message,
                    payload={
                        "campaign_id": int(campaign_id),
                        "job_type": job_type,
                    },
                )
                if status == "sent":
                    sent += 1
                elif status == "failed":
                    failed += 1
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status=status,
                    message_id=str(message_id or ""),
                    error=None if status != "skipped" else "idempotent skip",
                    payload={"job_type": job_type, "event_key": event_key},
                )
            except Exception as exc:
                failed += 1
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="failed",
                    message_id=None,
                    error=str(exc)[:1200],
                    payload={"job_type": job_type, "event_key": event_key},
                )
        return sent, failed

    def _promotion_target_for_recipient(self, recipient: dict, channel_type: str) -> str | None:
        if channel_type == "discord":
            user_id = int(recipient.get("user_id") or 0)
            return str(user_id) if user_id > 0 else None

        if channel_type == "telegram":
            encrypted = recipient.get("telegram_handle_encrypted")
            return self.contact_crypto.decrypt(encrypted)
        if channel_type == "signal":
            encrypted = recipient.get("signal_handle_encrypted")
            return self.contact_crypto.decrypt(encrypted)
        return None

    async def _dispatch_voice_check_followup(
        self,
        *,
        campaign_id: int,
        job_id: int,
        campaign_date: dt_date,
        recipients: list[dict],
        initiated_by_discord_id: int,
    ) -> None:
        if not self.promotion_voice_check_enabled:
            return

        expected_by_id: dict[int, dict] = {}
        for recipient in recipients:
            user_id = int(recipient.get("user_id") or 0)
            if user_id > 0:
                expected_by_id[user_id] = recipient
        if not expected_by_id:
            return

        voice_row = await self.bot.db_adapter.fetch_one(
            """
            SELECT status_data
            FROM live_status
            WHERE status_type = 'voice_channel'
            LIMIT 1
            """
        )
        voice_members = []
        if voice_row and voice_row[0]:
            voice_payload = self._decode_json_dict(voice_row[0])
            voice_members = voice_payload.get("members") if isinstance(voice_payload.get("members"), list) else []

        voice_member_ids: set[int] = set()
        voice_member_names: list[str] = []
        for member in voice_members:
            if not isinstance(member, dict):
                continue
            raw_id = member.get("id") or member.get("discord_id")
            try:
                member_id = int(raw_id)
            except (TypeError, ValueError):
                member_id = None
            if member_id is not None:
                voice_member_ids.add(member_id)
            name = str(member.get("name") or "").strip()
            if name:
                voice_member_names.append(name)

        missing_ids = sorted(user_id for user_id in expected_by_id if user_id not in voice_member_ids)
        if not missing_ids:
            return

        missing_names = [
            str(expected_by_id[user_id].get("display_name") or f"User {user_id}")
            for user_id in missing_ids
        ]

        in_server_not_voice: list[str] = []
        if self.promotion_server_check_enabled:
            server_row = await self.bot.db_adapter.fetch_one(
                """
                SELECT status_data
                FROM live_status
                WHERE status_type = 'game_server'
                LIMIT 1
                """
            )
            server_names: set[str] = set()
            if server_row and server_row[0]:
                server_payload = self._decode_json_dict(server_row[0])
                players = server_payload.get("players") if isinstance(server_payload.get("players"), list) else []
                for player in players:
                    if isinstance(player, dict):
                        server_names.add(self._normalize_name_for_match(player.get("name")))
            for name in missing_names:
                if self._normalize_name_for_match(name) in server_names:
                    in_server_not_voice.append(name)

        targeted_message_base = "We're starting now (21:00 CET). Join voice if you can."
        targeted_sent = 0
        followup_event_key = self._promotion_event_key(campaign_date=campaign_date, phase="FOLLOWUP")
        for user_id in missing_ids:
            recipient = expected_by_id[user_id]
            channel_type = str(recipient.get("selected_channel") or "discord").lower()

            if self._recipient_in_quiet_hours_now(recipient):
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="recipient in quiet hours",
                    payload={"job_type": "voice_check_2100"},
                )
                continue

            target = self._promotion_target_for_recipient(recipient, channel_type)
            if not target:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="skipped",
                    message_id=None,
                    error="missing delivery target",
                    payload={"job_type": "voice_check_2100"},
                )
                continue

            display_name = str(recipient.get("display_name") or f"User {user_id}")
            direct_message = targeted_message_base
            if display_name in in_server_not_voice:
                direct_message += " You're in server but not in voice."

            try:
                status, message_id = await self.notifier.send_via_channel_idempotent(
                    user_id=user_id,
                    event_key=followup_event_key,
                    channel_type=channel_type,
                    target=target,
                    message=direct_message,
                    payload={
                        "campaign_id": int(campaign_id),
                        "job_type": "voice_check_2100",
                    },
                )
                if status == "sent":
                    targeted_sent += 1
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status=status,
                    message_id=str(message_id or ""),
                    error=None if status != "skipped" else "idempotent skip",
                    payload={"job_type": "voice_check_2100", "event_key": followup_event_key},
                )
            except Exception as exc:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=user_id,
                    channel_type=channel_type,
                    status="failed",
                    message_id=None,
                    error=str(exc)[:1200],
                    payload={"job_type": "voice_check_2100", "event_key": followup_event_key},
                )

        followup_parts = [f"We're waiting on: {', '.join(missing_names)}."]
        if voice_member_names:
            followup_parts.append(f"In voice now: {', '.join(voice_member_names[:12])}.")
        if in_server_not_voice:
            followup_parts.append(f"In server but not in voice: {', '.join(in_server_not_voice)}.")
        followup_parts.append(f"Direct follow-up sent: {targeted_sent}/{len(missing_ids)}.")
        message = " ".join(followup_parts)

        channel_id = int(
            self.promotion_followup_channel_id
            or self.notifier.discord_announce_channel_id
            or self.channel_id
            or 0
        )
        if channel_id > 0:
            try:
                summary_status, summary_message_id = await self.notifier.send_discord_channel_idempotent(
                    channel_id=channel_id,
                    event_key=followup_event_key,
                    message=message,
                    payload={
                        "campaign_id": int(campaign_id),
                        "job_type": "voice_check_2100",
                        "missing_count": len(missing_names),
                        "targeted_sent": targeted_sent,
                    },
                )
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=int(initiated_by_discord_id),
                    channel_type="discord",
                    status=summary_status,
                    message_id=str(summary_message_id or ""),
                    error=None if summary_status != "skipped" else "idempotent skip",
                    payload={
                        "job_type": "voice_check_2100",
                        "event_key": followup_event_key,
                        "missing_count": len(missing_names),
                        "targeted_sent": targeted_sent,
                    },
                )
            except Exception as exc:
                await self._log_promotion_send(
                    campaign_id=campaign_id,
                    job_id=job_id,
                    user_id=int(initiated_by_discord_id),
                    channel_type="discord",
                    status="failed",
                    message_id=None,
                    error=str(exc)[:1200],
                    payload={
                        "job_type": "voice_check_2100",
                        "missing_count": len(missing_names),
                        "targeted_sent": targeted_sent,
                    },
                )

    async def _log_promotion_send(
        self,
        *,
        campaign_id: int,
        job_id: int,
        user_id: int,
        channel_type: str,
        status: str,
        message_id: str | None,
        error: str | None,
        payload: dict,
    ) -> None:
        payload_json = json.dumps(payload or {}, ensure_ascii=True)
        await self.bot.db_adapter.execute(
            """
            INSERT INTO availability_promotion_send_logs
                (campaign_id, job_id, user_id, channel_type, status, message_id, error, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, CAST($8 AS JSONB), CURRENT_TIMESTAMP)
            """,
            (
                int(campaign_id),
                int(job_id),
                int(user_id or 0),
                str(channel_type),
                str(status),
                message_id,
                error,
                payload_json,
            ),
        )

    @tasks.loop(minutes=1)
    async def availability_scheduler_loop(self):
        if not self.multichannel_enabled:
            return

        try:
            await self._ensure_multichannel_tables()
            now = datetime.now(self.timezone)
            await self._run_scheduler_with_lock(now)
        except Exception as exc:
            logger.error("Error in availability scheduler loop: %s", exc, exc_info=True)

    @availability_scheduler_loop.before_loop
    async def before_availability_scheduler_loop(self):
        await self.bot.wait_until_ready()
