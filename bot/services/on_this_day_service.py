"""On This Day — daily throwback Discord post (VISION_2026 S6 SPOMIN).

Surfaces sessions/results from the SAME calendar day (month-day) in previous
years — "an archive nobody is reminded of is a dead archive" (R4). Scheduled
(not event-driven). Best-effort: posts nothing if there's no history for the day.
"""
from __future__ import annotations

import datetime as _dt

import discord

from bot.logging_config import get_logger

logger = get_logger("bot.services.on_this_day")

_MAX_YEARS = 4  # cap the embed to the most recent N matching years


class OnThisDayService:
    """Builds and posts the 'on this day' throwback embed."""

    def __init__(self, bot, db_adapter, config):
        self.bot = bot
        self.db_adapter = db_adapter
        self.config = config

    async def generate_and_post(self, today: _dt.date | None = None) -> bool:
        try:
            embed = await self.build_embed(today)
        except Exception:
            logger.exception("on-this-day build failed — skipping post")
            return False
        if embed is None:
            logger.debug("on-this-day: no history for today — nothing to post")
            return False
        channel_id = self.config.on_this_day_channel_id or self.config.stats_channel_id
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if not channel:
            logger.warning("on-this-day: no usable channel — not posting")
            return False
        await channel.send(embed=embed)
        logger.info("📅 On-this-day posted to #%s", getattr(channel, "name", channel_id))
        return True

    async def _fetch_day_history(self, month: int, day: int, this_year: int) -> list[dict]:
        """Sessions that happened on this month-day in PRIOR years, newest first.

        Grouped per gaming_session_id (audit W1: grouping by DATE alone summed
        winners across distinct gaming sessions on the same date, fabricating a
        combined score no evening actually produced). The extra DATE key keeps
        pre-gsid legacy rows (gaming_session_id IS NULL) merged per-date as
        before instead of collapsing them into one NULL bucket across years.
        """
        rows = await self.db_adapter.fetch_all(
            """
            SELECT MIN(CAST(session_date AS DATE)) AS sd,
                   COUNT(*)                                  AS maps,
                   MAX(team_1_name)                          AS t1,
                   MAX(team_2_name)                          AS t2,
                   SUM(CASE WHEN winning_team = 1 THEN 1 ELSE 0 END) AS t1_wins,
                   SUM(CASE WHEN winning_team = 2 THEN 1 ELSE 0 END) AS t2_wins
            FROM session_results
            WHERE EXTRACT(MONTH FROM CAST(session_date AS DATE)) = ?
              AND EXTRACT(DAY   FROM CAST(session_date AS DATE)) = ?
              AND EXTRACT(YEAR  FROM CAST(session_date AS DATE)) < ?
            GROUP BY gaming_session_id, CAST(session_date AS DATE)
            ORDER BY sd DESC
            """,
            (month, day, this_year),
        )
        return [{
            "date": r[0], "maps": int(r[1] or 0),
            "t1": r[2], "t2": r[3],
            "t1_wins": int(r[4] or 0), "t2_wins": int(r[5] or 0),
        } for r in (rows or [])]

    async def _top_fragger(self, month: int, day: int, this_year: int) -> dict | None:
        """Best single-SESSION kill total on this month-day in prior years (flavor).

        Same W1 grain fix as _fetch_day_history: per gaming_session_id, so two
        sessions on one date don't merge into a kill total nobody actually shot.
        """
        try:
            row = await self.db_adapter.fetch_one(
                """
                SELECT MAX(pcs.player_name) AS name, SUM(pcs.kills) AS kills,
                       MIN(CAST(r.round_date AS DATE)) AS sd
                FROM player_comprehensive_stats pcs
                JOIN rounds r ON r.id = pcs.round_id
                WHERE r.is_valid IS DISTINCT FROM FALSE
                  -- played rounds only: round_number=0 match-summary rows carry
                  -- cumulative map totals and would ~double the kill sum
                  AND r.round_number IN (1, 2)
                  AND pcs.player_guid NOT LIKE 'OMNIBOT%'
                  AND pcs.player_name NOT LIKE '[BOT]%'
                  AND EXTRACT(MONTH FROM CAST(r.round_date AS DATE)) = ?
                  AND EXTRACT(DAY   FROM CAST(r.round_date AS DATE)) = ?
                  AND EXTRACT(YEAR  FROM CAST(r.round_date AS DATE)) < ?
                GROUP BY pcs.player_guid, r.gaming_session_id, CAST(r.round_date AS DATE)
                ORDER BY kills DESC
                LIMIT 1
                """,
                (month, day, this_year),
            )
            if row and row[1]:
                return {"name": row[0], "kills": int(row[1]), "date": row[2]}
        except Exception:
            logger.debug("on-this-day: top fragger lookup failed", exc_info=True)
        return None

    async def build_embed(self, today: _dt.date | None = None) -> discord.Embed | None:
        today = today or _dt.datetime.now().date()  # noqa: DTZ005 local wall-clock day
        history = await self._fetch_day_history(today.month, today.day, today.year)
        if not history:
            return None

        embed = discord.Embed(
            title=f"📅 On this day — {today.strftime('%B')} {today.day}",
            description="A throwback to what happened on this date in years past.",
            color=0x8B5CF6,
        )
        for h in history[:_MAX_YEARS]:
            d = h["date"]
            years = today.year - d.year
            ago = f"{years} year{'s' if years != 1 else ''} ago"
            score = ""
            if h["t1"] and h["t2"]:
                score = f"{h['t1']} {h['t1_wins']}–{h['t2_wins']} {h['t2']}"
            elif h["maps"]:
                score = f"{h['maps']} map{'s' if h['maps'] != 1 else ''} played"
            embed.add_field(
                name=f"{ago} · {d.isoformat()}",
                value=score or "—",
                inline=False,
            )

        frag = await self._top_fragger(today.month, today.day, today.year)
        if frag:
            embed.add_field(
                name="🔥 Best single day",
                value=f"**{frag['name']}** — {frag['kills']} kills ({frag['date'].isoformat()})",
                inline=False,
            )
        web = getattr(self.config, "website_public_base", "https://www.slomix.fyi")
        embed.set_footer(text="Slomix — the community's memory 🏟️")
        embed.add_field(name="​", value=f"[Record Book]({web}/#/record-book)", inline=False)
        return embed
