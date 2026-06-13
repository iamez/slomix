"""Morning session digest (VISION_2026 S1.1).

Auto-posted Discord recap after a gaming session ends — the "push memory,
don't park it" pattern (R4): winner + per-map score, MVPs, form note and
deep links back to the website. The digest is best-effort enrichment on top
of data the bot already owns; the website API calls (KIS MVP) are optional
and the embed NEVER fails because of them.
"""
from __future__ import annotations

from datetime import datetime

import aiohttp
import discord

from bot.logging_config import get_logger
from bot.services.session_data_service import SessionDataService
from bot.services.stopwatch_scoring_service import StopwatchScoringService

logger = get_logger("bot.services.session_digest")

_HTTP_TIMEOUT_S = 10


class SessionDigestService:
    """Builds and posts the morning recap embed for the latest session."""

    def __init__(self, bot, db_adapter, config):
        self.bot = bot
        self.db_adapter = db_adapter
        self.config = config

    async def generate_and_post(self) -> bool:
        """Build the digest for the latest session and post it. Returns True on post."""
        try:
            embed = await self._build_embed()
        except Exception:
            logger.exception("digest build failed — skipping post")
            return False
        if embed is None:
            return False

        channel_id = self.config.stats_channel_id or self.config.production_channel_id
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if not channel:
            logger.warning("digest: no usable channel (stats/production) — not posting")
            return False
        await channel.send(embed=embed)
        logger.info("📰 Morning digest posted to #%s", getattr(channel, "name", channel_id))
        return True

    async def _build_embed(self) -> discord.Embed | None:
        data_service = SessionDataService(
            self.db_adapter,
            self.bot.db_path if hasattr(self.bot, "db_path") else None,
        )
        scoring_service = StopwatchScoringService(self.db_adapter)

        latest_date = await data_service.get_latest_session_date()
        if not latest_date:
            logger.debug("digest: no session date found")
            return None
        sessions, session_ids, session_ids_str, player_count = (
            await data_service.fetch_session_data(latest_date)
        )
        if not sessions or len(sessions) < self.config.session_digest_min_rounds:
            # Guard against false session-end triggers / stub sessions.
            logger.info(
                "digest: only %d rounds for %s (< %d) — skipping",
                len(sessions or []), latest_date, self.config.session_digest_min_rounds,
            )
            return None

        # Scoring (team-aware first, same as session finalization).
        scoring = None
        hardcoded_teams = await data_service.get_hardcoded_teams(session_ids)
        if hardcoded_teams and len(hardcoded_teams) >= 2:
            rosters = {n: d.get("guids", []) for n, d in hardcoded_teams.items()}
            scoring = await scoring_service.calculate_session_scores_with_teams(
                latest_date, session_ids, rosters
            )
        if not scoring:
            scoring = await scoring_service.calculate_session_scores(latest_date, session_ids)

        # Resolve display team names (same mapping !last_session uses) —
        # falls back to the generic Team A/B labels.
        name_a = name_b = None
        try:
            name_a, name_b, _p1, _p2, _n2t = await data_service.build_team_mappings(
                session_ids, session_ids_str, hardcoded_teams
            )
        except Exception:
            logger.debug("digest: team name mapping unavailable", exc_info=True)

        web = self.config.website_public_base
        session_url = f"{web}/#/session-detail/date/{latest_date}"

        embed = discord.Embed(
            title=f"📰 Morning Report — {latest_date}",
            url=session_url,
            color=0x22D3EE,
            timestamp=datetime.now(),  # noqa: DTZ005 naive datetime intentional — project convention (see voice_session_service)
        )

        # Headline: score + maps. Scoring payloads carry team_a_maps/_team1_score
        # (NOT team_a_score) and maps[].map — verified against live shape.
        if scoring:
            generic_a = scoring.get("team_a_name") or scoring.get("_team1_name") or "Team A"
            generic_b = scoring.get("team_b_name") or scoring.get("_team2_name") or "Team B"
            a_name = name_a or generic_a
            b_name = name_b or generic_b
            a_score = scoring.get("team_a_maps", scoring.get("_team1_score", 0)) or 0
            b_score = scoring.get("team_b_maps", scoring.get("_team2_score", 0)) or 0
            lead = "🤝 Dead even" if a_score == b_score else (
                f"🏆 **{a_name}** took the night" if a_score > b_score
                else f"🏆 **{b_name}** took the night"
            )
            embed.description = f"{lead} — **{a_name} {a_score} : {b_score} {b_name}**"
            maps = scoring.get("maps") or []
            if maps:
                display = {generic_a: a_name, generic_b: b_name}
                lines = []
                for m in maps[:8]:
                    winner = m.get("winner") or "draw"
                    lines.append(
                        f"• {m.get('map') or m.get('map_name') or '?'} — {display.get(winner, winner)}"
                    )
                embed.add_field(name="🗺️ Maps", value="\n".join(lines), inline=False)
        else:
            embed.description = f"{len(sessions)} rounds played by {player_count} players."

        # MVPs (bot-owned data). Lookup with the generic roster keys,
        # display with the resolved names.
        try:
            g1 = (scoring or {}).get("team_a_name") or "Team A"
            g2 = (scoring or {}).get("team_b_name") or "Team B"
            mvp1, mvp2 = await data_service.get_team_mvps(
                session_ids, session_ids_str, hardcoded_teams, g1, g2
            )
            mvp_lines = []
            for team, mvp in ((name_a or g1, mvp1), (name_b or g2, mvp2)):
                if mvp:
                    name, kills, dpm = mvp[0], mvp[1], mvp[2]
                    mvp_lines.append(f"**{team}**: {name} — {kills} kills, {dpm:.0f} DPM")
            if mvp_lines:
                embed.add_field(name="⭐ MVPs", value="\n".join(mvp_lines), inline=False)
        except Exception:
            logger.exception("digest: MVP block failed — continuing without")

        # Optional web enrichment: KIS top impact (also warms the lazy KIS
        # cache for the morning visitors).
        kis_line = await self._fetch_kis_top(latest_date)
        if kis_line:
            embed.add_field(name="💥 Highest impact (KIS)", value=kis_line, inline=False)

        # MVP vote (S3): always open after a session — peer recognition.
        gsid = await self._gaming_session_id(latest_date)
        if gsid is not None:
            embed.add_field(
                name="🗳️ MVP vote open",
                value=f"Who carried tonight? [Cast your vote]({web}/#/session-detail/{gsid})",
                inline=False,
            )

        # Challenge of the week (S3): admin-defined, read straight from DB.
        challenge = await self._fetch_weekly_challenge()
        if challenge:
            embed.add_field(name="🏆 Challenge of the week", value=challenge, inline=False)

        embed.add_field(
            name="🔗 Deep dive",
            value=(
                f"[Full session breakdown]({session_url}) · "
                f"[Smart stats]({web}/#/story) · "
                f"[Leaderboards]({web}/#/leaderboards)"
            ),
            inline=False,
        )
        embed.set_footer(text="Slomix morning report — see you on the server 🎮")
        return embed

    async def _gaming_session_id(self, session_date) -> int | None:
        """Resolve the gaming_session_id for the session date (for vote link)."""
        try:
            row = await self.db_adapter.fetch_one(
                "SELECT gaming_session_id FROM rounds WHERE round_date = ? "
                "AND gaming_session_id IS NOT NULL ORDER BY gaming_session_id DESC LIMIT 1",
                (str(session_date),),
            )
            return int(row[0]) if row and row[0] is not None else None
        except Exception:
            logger.debug("digest: gaming_session_id lookup failed", exc_info=True)
            return None

    async def _fetch_weekly_challenge(self) -> str | None:
        """Current ISO-week challenge straight from the DB (best-effort)."""
        from datetime import datetime, timedelta
        try:
            today = datetime.now().date()  # noqa: DTZ005 local week boundary
            monday = today - timedelta(days=today.weekday())
            row = await self.db_adapter.fetch_one(
                "SELECT title, description FROM weekly_challenges WHERE week_start_date = ?",
                (monday,),
            )
            if not row:
                return None
            title, desc = row[0], row[1]
            return f"**{title}**" + (f" — {desc}" if desc else "")
        except Exception:
            logger.debug("digest: weekly challenge lookup failed", exc_info=True)
            return None

    async def _fetch_kis_top(self, session_date) -> str | None:
        """Top kill-impact player via the website API (optional, 10s budget)."""
        url = f"{self.config.website_api_base}/storytelling/kill-impact"
        try:
            timeout = aiohttp.ClientTimeout(total=_HTTP_TIMEOUT_S)
            async with aiohttp.ClientSession(timeout=timeout) as http, http.get(
                url, params={"session_date": str(session_date), "limit": 3}
            ) as resp:
                if resp.status != 200:
                    logger.info("digest: kill-impact HTTP %s — skipping KIS block", resp.status)
                    return None
                data = await resp.json()
        except Exception as e:
            logger.info("digest: kill-impact unreachable (%s) — skipping KIS block", e)
            return None
        players = (data or {}).get("players") or []
        # KIS scope is the DATE, which can include bot testmode rounds —
        # never headline a bot.
        players = [
            p for p in players
            if "[BOT]" not in (p.get("name") or "")
            and not (p.get("guid") or "").startswith("OMNIBOT")
        ]
        if not players:
            return None
        top = players[0]
        name = top.get("name") or "?"
        guid = top.get("guid") or ""
        kis = top.get("total_kis")
        profile = f"{self.config.website_public_base}/#/profile/{guid[:8]}" if guid else None
        text = f"{name} — {kis} impact" if kis is not None else name
        return f"[{text}]({profile})" if profile else text
