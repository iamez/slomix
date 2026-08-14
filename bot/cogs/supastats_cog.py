"""Automatic supastats cross-check (DEV TOOL — off unless configured).

Supa reviews the demos every morning and posts a screenshot of his sheet. That
sheet is an independent measurement of the night we parsed ourselves, so it is
the strongest data check available while the project is still a prototype: run
manually on 2026-08-14 it both cleared a suspected scoring regression and
exposed 17 genuinely inverted historical rounds.

This cog watches for that post, reads the screenshot and DMs the owner the
whole run — detected, downloaded, read, matched to a session, compared — so a
disagreement surfaces the morning it happens instead of months later. It never
writes to the database and never posts in the channel.

Retire it once our numbers and supa's agree and the project leaves prototype.
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from bot.services.stopwatch_scoring_service import StopwatchScoringService
from bot.services.supastats_image_reader import (
    UnsupportedScreenshot,
    read_supastats_image,
)
from bot.services.supastats_reconcile_service import (
    format_report,
    load_our_session,
    load_our_teams,
    reconcile,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
_RECENT_LIMIT = 50


class SupastatsCog(commands.Cog):
    """Watches one channel for supa's sheet and reports the comparison in DM."""

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self._handled: list[int] = []   # message ids, newest last

    # -- trigger ------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Cog listeners fire for EVERY message — including the bot's own and
        every channel — so each guard is made here rather than inherited from
        the bot's on_message override.
        """
        try:
            if not self.config.supastats_check_enabled:
                return
            if message.author.bot:
                return
            channel_id = self.config.supastats_channel_id
            if not channel_id or message.channel.id != channel_id:
                return
            authors = self.config.supastats_author_ids
            if authors and message.author.id not in authors:
                return
            attachment = self._first_image(message)
            if attachment is None:
                return
            if message.id in self._handled:
                return
            self._handled.append(message.id)
            del self._handled[:-_RECENT_LIMIT]

            await self._run_check(message, attachment, source="auto")
        except Exception:
            logger.exception("supastats listener failed")

    @commands.command(name="supacheck")
    async def supacheck(self, ctx, date: str | None = None):
        """Re-run the check on an attached sheet (or the one you replied to)."""
        attachment = self._first_image(ctx.message)
        if attachment is None and ctx.message.reference:
            try:
                replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                attachment = self._first_image(replied)
            except discord.HTTPException:
                attachment = None
        if attachment is None:
            await ctx.send("Attach a supastats screenshot, or reply to the message with one.")
            return
        await ctx.send("Checking that sheet — the report goes to the owner's DMs.")
        await self._run_check(ctx.message, attachment, source="manual", date_override=date)

    @staticmethod
    def _first_image(message: discord.Message):
        for attachment in message.attachments or []:
            name = (attachment.filename or "").lower()
            if name.endswith((".png", ".jpg", ".jpeg")) and attachment.size <= MAX_IMAGE_BYTES:
                return attachment
        return None

    # -- run ----------------------------------------------------------------

    async def _run_check(self, message, attachment, *, source: str, date_override=None):
        lines = [
            f"📸 supastats sheet detected ({source}) from **{message.author.display_name}**",
            f"• file: `{attachment.filename}` ({attachment.size / 1024:.0f} KB)",
        ]
        try:
            data = await attachment.read()
        except discord.HTTPException as exc:
            await self._dm(lines + [f"🔴 could not download the attachment: {exc}"])
            return
        if not data.startswith((PNG_MAGIC, JPEG_MAGIC)):
            await self._dm(lines + ["🔴 that attachment is not a PNG/JPEG"])
            return
        lines.append(f"• downloaded {len(data) / 1024:.0f} KB")

        try:
            # Decoding is CPU-bound; keep it off the event loop so the bot
            # stays responsive while it runs.
            sheet = await asyncio.to_thread(read_supastats_image, data)
        except UnsupportedScreenshot as exc:
            await self._dm(lines + [f"⚠️ cannot read this screenshot: {exc}"])
            return
        except Exception as exc:
            logger.exception("supastats reader crashed")
            await self._dm(lines + [f"🔴 reader crashed: {exc}"])
            return

        lines.append(
            f"• read: {sheet.map_count} maps, {len(sheet.kills)} players, "
            f"checksum {'ok' if sheet.kills_checksum_ok else 'FAILED'}"
        )

        try:
            report_text = await self._compare(sheet, date_override)
        except Exception as exc:
            logger.exception("supastats comparison failed")
            await self._dm(lines + [f"🔴 comparison failed: {exc}"])
            alert = getattr(self.bot, "alert_admins", None)
            if alert:
                await alert("supastats check failed", str(exc), "warning")
            return

        await self._dm(lines + ["", report_text])

    async def _compare(self, sheet, date_override) -> str:
        from bot.services.session_data_service import SessionDataService

        adapter = self.bot.db_adapter
        data_service = SessionDataService(adapter, getattr(self.bot, "db_path", None))

        # The sheet's own date rarely decodes (smaller header font), and supa
        # posts the morning after, so the latest session is the right default.
        session_date = date_override or sheet.session_date or await data_service.get_latest_session_date()
        sessions, session_ids, _, _ = await data_service.fetch_session_data_by_date(session_date)
        if not session_ids:
            return f"⚠️ no gaming session found for {session_date}"
        row = await adapter.fetch_one(
            "SELECT gaming_session_id FROM rounds WHERE id = ?", (session_ids[0],)
        )
        gsid = int(row[0]) if row else None

        ours = await load_our_session(adapter, gsid)
        our_winners: list[str] = []
        our_teams: dict[str, list[str]] = {}
        hardcoded = await data_service.get_hardcoded_teams(session_ids)
        rosters = {name: info.get("guids", []) for name, info in (hardcoded or {}).items()}
        if len(rosters) >= 2:
            scoring = await StopwatchScoringService(adapter).calculate_session_scores_with_teams(
                session_date, session_ids, rosters
            )
            if scoring:
                a_name = scoring.get("team_a_name", "Team A")
                b_name = scoring.get("team_b_name", "Team B")
                for entry in scoring.get("maps", []) or []:
                    a_points = entry.get("team_a_points") or 0
                    b_points = entry.get("team_b_points") or 0
                    our_winners.append(
                        a_name if a_points > b_points
                        else (b_name if b_points > a_points else "draw")
                    )
                our_teams = await load_our_teams(adapter, gsid, rosters)

        report = reconcile(
            sheet,
            session_date=session_date,
            gaming_session_id=gsid,
            our_kills=ours["kills"],
            our_dpm=ours["dpm"],
            our_durations=ours["durations"],
            our_map_winners=our_winners,
            our_teams=our_teams,
        )
        return format_report(report, sheet)

    async def _dm(self, lines: list[str]):
        owner_id = getattr(self.config, "owner_user_id", 0)
        if not owner_id:
            logger.warning("supastats check has no OWNER_USER_ID to report to")
            return
        text = "\n".join(lines)
        try:
            user = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
            for chunk in [text[i:i + 1900] for i in range(0, len(text), 1900)]:
                await user.send(chunk)
        except discord.HTTPException:
            logger.exception("could not DM the supastats report")


async def setup(bot):
    await bot.add_cog(SupastatsCog(bot))
