"""ProximityCog mixin: Public stats commands (read-only DB queries + embed formatters).

Extracted from bot/cogs/proximity_cog.py in Mega Audit v4 / Sprint 3.

All methods live on ProximityCog via mixin inheritance.
"""
from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from bot.core.utils import normalize_player_name

logger = logging.getLogger("bot.cogs.proximity")


def _is_bot_row(player: dict) -> bool:
    """A prox-scores row for a test bot ([BOT] name / OMNIBOT guid). Normalize the
    name (drop ET colour codes that could split "[B^7OT]") and case-fold both
    fields before matching — a raw check misses coloured names and lowercase
    guids (mirrors the v1 service's ``guid.upper()`` filter)."""
    name = normalize_player_name(player.get("name") or "").upper()
    guid = (player.get("guid") or "").upper()
    return "[BOT]" in name or guid.startswith("OMNIBOT")

# Budget for the bot→web prox-scores fetch (mirrors session_digest_service).
_HTTP_TIMEOUT_S = 10


class _ProximityStatsCommandsMixin:
    """Public stats commands (read-only DB queries + embed formatters) for ProximityCog."""

    @commands.command(name='proximity_spawn_efficiency', aliases=['pse'])
    async def proximity_spawn_efficiency(self, ctx, session_date: str = None):
        """Top 10 players by spawn timing efficiency (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT killer_guid, MAX(killer_name) AS name,
                       ROUND(AVG(spawn_timing_score)::numeric, 3) AS avg_score,
                       COUNT(*) AS kills,
                       ROUND(AVG(time_to_next_spawn)::numeric, 0) AS avg_denial_ms
                FROM proximity_spawn_timing
                {date_filter}
                GROUP BY killer_guid
                HAVING COUNT(*) >= 5
                ORDER BY avg_score DESC
                LIMIT 10
            """, tuple(params))

            if not rows:
                await ctx.send("No spawn timing data found.")
                return

            embed = discord.Embed(
                title="Spawn Timing Efficiency - Top 10",
                description="Higher score = kills timed to maximize enemy respawn wait",
                color=discord.Color.orange()
            )
            for i, row in enumerate(rows, 1):
                name = row[1] or row[0][:8]
                score = float(row[2] or 0)
                kills = int(row[3] or 0)
                denial_ms = int(row[4] or 0)
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"Score: **{score:.1%}** | Kills: {kills} | Avg denial: {denial_ms}ms",
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"spawn_efficiency error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_cohesion', aliases=['pco'])
    async def proximity_cohesion(self, ctx, session_date: str = None):
        """Team cohesion summary - Axis vs Allies formation tightness (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT team,
                       ROUND(AVG(dispersion)::numeric, 1) AS avg_dispersion,
                       ROUND(AVG(max_spread)::numeric, 1) AS avg_max_spread,
                       ROUND(AVG(straggler_count)::numeric, 1) AS avg_stragglers,
                       ROUND(AVG(alive_count)::numeric, 1) AS avg_alive,
                       COUNT(*) AS samples
                FROM proximity_team_cohesion
                {date_filter}
                GROUP BY team
                ORDER BY team
            """, tuple(params))

            if not rows:
                await ctx.send("No team cohesion data found.")
                return

            def classify(disp):
                if disp < 300:
                    return "TIGHT"
                if disp < 800:
                    return "NORMAL"
                if disp < 1500:
                    return "LOOSE"
                return "SCATTERED"

            embed = discord.Embed(
                title="Team Cohesion Summary",
                description="Formation tightness analysis",
                color=discord.Color.blue()
            )

            for row in rows:
                team = row[0]
                disp = float(row[1] or 0)
                spread = float(row[2] or 0)
                stragglers = float(row[3] or 0)
                alive = float(row[4] or 0)
                samples = int(row[5] or 0)
                classification = classify(disp)

                embed.add_field(
                    name=f"{team} - {classification}",
                    value=(
                        f"Avg dispersion: **{disp:.0f}** units\n"
                        f"Max spread: {spread:.0f} | Stragglers: {stragglers:.1f}\n"
                        f"Avg alive: {alive:.1f} | Samples: {samples}"
                    ),
                    inline=True
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"cohesion error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_crossfire_angles', aliases=['pxa'])
    async def proximity_crossfire_angles(self, ctx, session_date: str = None):
        """Crossfire opportunity analysis with utilization rate (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            summary = await self.bot.db_adapter.fetch_one(f"""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) AS executed,
                       ROUND(AVG(angular_separation)::numeric, 1) AS avg_angle
                FROM proximity_crossfire_opportunity
                {date_filter}
            """, tuple(params))

            total = int(summary[0] or 0) if summary else 0
            if total == 0:
                await ctx.send("No crossfire opportunity data found.")
                return

            executed = int(summary[1] or 0)
            avg_angle = float(summary[2] or 0)
            util_rate = (executed / total * 100) if total > 0 else 0

            duos = await self.bot.db_adapter.fetch_all(f"""
                SELECT teammate1_guid, teammate2_guid,
                       COUNT(*) AS executions
                FROM proximity_crossfire_opportunity
                {date_filter} AND was_executed = TRUE
                GROUP BY teammate1_guid, teammate2_guid
                ORDER BY executions DESC
                LIMIT 5
            """, tuple(params))

            embed = discord.Embed(
                title="Crossfire Opportunity Analysis",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Summary",
                value=(
                    f"Total opportunities: **{total}**\n"
                    f"Executed: **{executed}** ({util_rate:.1f}%)\n"
                    f"Avg angle: {avg_angle:.1f} deg"
                ),
                inline=False
            )

            if duos:
                duo_text = ""
                for i, row in enumerate(duos, 1):
                    duo_text += f"{i}. `{row[0][:8]}` + `{row[1][:8]}` = {row[2]} executions\n"
                embed.add_field(name="Top Crossfire Duos", value=duo_text, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"crossfire_angles error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_trades_lua', aliases=['ptl'])
    async def proximity_trades_lua(self, ctx, session_date: str = None):
        """Lua-detected trade kill leaderboard (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            leaders = await self.bot.db_adapter.fetch_all(f"""
                SELECT trader_guid, MAX(trader_name) AS name,
                       COUNT(*) AS trades,
                       ROUND(AVG(delta_ms)::numeric, 0) AS avg_reaction,
                       MIN(delta_ms) AS fastest
                FROM proximity_lua_trade_kill
                {date_filter}
                GROUP BY trader_guid
                ORDER BY trades DESC
                LIMIT 10
            """, tuple(params))

            recent = await self.bot.db_adapter.fetch_all(f"""
                SELECT original_victim_name, original_killer_name, trader_name, delta_ms
                FROM proximity_lua_trade_kill
                {date_filter}
                ORDER BY session_date DESC, traded_kill_time DESC
                LIMIT 5
            """, tuple(params))

            embed = discord.Embed(
                title="Trade Kill Leaderboard (Lua-detected)",
                description="Teammate avenges your death within time window",
                color=discord.Color.gold()
            )

            if leaders:
                for i, row in enumerate(leaders, 1):
                    name = row[1] or row[0][:8]
                    trades = int(row[2] or 0)
                    avg_ms = int(row[3] or 0)
                    fastest = int(row[4] or 0)
                    embed.add_field(
                        name=f"{i}. {name}",
                        value=f"Trades: **{trades}** | Avg: {avg_ms}ms | Fastest: {fastest}ms",
                        inline=False
                    )
            else:
                embed.add_field(name="No data", value="No trade kills recorded", inline=False)

            if recent:
                chain_text = ""
                for row in recent:
                    chain_text += f"{row[0]} killed by {row[1]} -> avenged by **{row[2]}** ({row[3]}ms)\n"
                embed.add_field(name="Recent Trades", value=chain_text, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"trades_lua error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_pushes', aliases=['ppu'])
    async def proximity_pushes(self, ctx, session_date: str = None):
        """Team push quality comparison - Axis vs Allies (v5)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT team,
                       COUNT(*) AS pushes,
                       ROUND(AVG(push_quality)::numeric, 3) AS avg_quality,
                       ROUND(AVG(participant_count)::numeric, 1) AS avg_participants,
                       SUM(CASE WHEN toward_objective NOT IN ('NO', 'N/A') THEN 1 ELSE 0 END) AS obj_pushes
                FROM proximity_team_push
                {date_filter}
                GROUP BY team
                ORDER BY team
            """, tuple(params))

            if not rows:
                await ctx.send("No team push data found.")
                return

            embed = discord.Embed(
                title="Team Push Comparison",
                description="Coordinated team movement analysis",
                color=discord.Color.purple()
            )

            for row in rows:
                team = row[0]
                pushes = int(row[1] or 0)
                quality = float(row[2] or 0)
                participants = float(row[3] or 0)
                obj = int(row[4] or 0)
                obj_pct = (obj / pushes * 100) if pushes > 0 else 0

                embed.add_field(
                    name=f"{team}",
                    value=(
                        f"Pushes: **{pushes}**\n"
                        f"Avg quality: {quality:.3f}\n"
                        f"Avg participants: {participants:.1f}\n"
                        f"Objective-oriented: {obj_pct:.0f}%"
                    ),
                    inline=True
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"pushes error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    async def _fetch_prox_scores(self, session_date, limit: int = 12):
        """Fetch v3.0 proximity composite scores from the website API.

        Single source of truth: the website computes prox_score v3.0 once
        (``compute_prox_scores`` → ``/proximity/prox-scores``); the bot consumes
        the result instead of re-implementing the formula. Mirrors the resilient
        pattern in ``session_digest_service`` — bounded timeout, graceful None on
        any failure. The v3.0 engagement threshold is enforced server-side, so we
        pass only the scope (session_date) + limit, never ``min_engagements``.
        Returns the decoded JSON dict, or None if the web is unreachable / errors.
        """
        url = f"{self.bot.config.website_api_base}/proximity/prox-scores"
        try:
            timeout = aiohttp.ClientTimeout(total=_HTTP_TIMEOUT_S)
            async with aiohttp.ClientSession(timeout=timeout) as http, http.get(
                url, params={"session_date": str(session_date), "limit": limit}
            ) as resp:
                if resp.status != 200:
                    logger.info("psession: prox-scores HTTP %s — skipping", resp.status)
                    return None
                return await resp.json()
        except Exception as e:
            logger.info("psession: prox-scores unreachable (%s)", e)
            return None

    @commands.command(name="proximity_session", aliases=["psession", "pscore"])
    async def proximity_session_scores(self, ctx, session_date: str = None):
        """Per-session proximity composite scores (v3.0).

        Usage: !psession [YYYY-MM-DD]
        Composite score (0-100) from 3 percentile-ranked categories:
        Combat (.40), Team (.35), Gamesense (.25). Same v3.0 formula the website
        shows — fetched from the site so Discord and the web never disagree.
        """
        try:
            if not session_date:
                from bot.services.proximity_session_score_service import (
                    ProximitySessionScoreService,
                )
                session_date = await ProximitySessionScoreService(
                    self.bot.db_adapter
                ).get_latest_session_date()
            if not session_date:
                await ctx.send("No proximity data found.")
                return

            data = await self._fetch_prox_scores(session_date)
            if data is None:
                await ctx.send(
                    "Proximity scores are temporarily unavailable "
                    "(is the website up?). Try again shortly."
                )
                return
            if data.get("status") == "degraded":
                await ctx.send(
                    f"Not enough proximity data to score session {session_date} yet."
                )
                return

            # Drop bot-test rounds so a headless testmode session can't headline
            # (mirrors session_digest_service's [BOT]/OMNIBOT filter).
            players = [p for p in (data.get("players") or []) if not _is_bot_row(p)]
            if not players:
                await ctx.send(f"No proximity data for session {session_date}.")
                return

            embed = discord.Embed(
                title=f"Proximity Session Score — {session_date}",
                description="Composite combat performance (v3.0: Combat · Team · Gamesense)",
                color=discord.Color.teal(),
            )

            # Response is already sorted by prox_overall desc.
            medal = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(players[:12]):
                prefix = medal[i] if i < 3 else f"{i+1}."
                name = normalize_player_name(p.get("name") or "?") or "?"
                embed.add_field(
                    name=f"{prefix} {name} — **{p.get('prox_overall', 0):.1f}** / 100",
                    value=(
                        f"⚔ Combat {p.get('prox_combat', 0):.0f} · "
                        f"🤝 Team {p.get('prox_team', 0):.0f} · "
                        f"🧠 Gamesense {p.get('prox_gamesense', 0):.0f} "
                        f"({p.get('engagements', 0)} eng)"
                    ),
                    inline=False,
                )

            total_eng = sum(int(p.get("engagements", 0)) for p in players)
            embed.set_footer(text=f"{len(players)} players, {total_eng} total engagements · v3.0")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"psession error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_carriers', aliases=['pca'])
    async def proximity_carriers(self, ctx, session_date: str = None):
        """Top carrier leaderboard - distance, secures, efficiency (v6)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT carrier_guid, MAX(carrier_name) AS name,
                       COUNT(*) AS carries,
                       SUM(CASE WHEN outcome = 'secured' THEN 1 ELSE 0 END) AS secures,
                       SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) AS killed,
                       ROUND(SUM(carry_distance)::numeric, 0) AS total_distance,
                       ROUND(AVG(efficiency)::numeric, 3) AS avg_efficiency,
                       ROUND(AVG(duration_ms)::numeric, 0) AS avg_duration
                FROM proximity_carrier_event
                {date_filter}
                GROUP BY carrier_guid
                HAVING COUNT(*) >= 1
                ORDER BY secures DESC, total_distance DESC
                LIMIT 10
            """, tuple(params))

            if not rows:
                await ctx.send("No carrier data found.")
                return

            embed = discord.Embed(
                title="Objective Carriers - Top 10",
                description="Flag/docs/gold carrier stats",
                color=discord.Color.gold()
            )
            for i, row in enumerate(rows, 1):
                name = row[1] or row[0][:8]
                carries = int(row[2] or 0)
                secures = int(row[3] or 0)
                killed = int(row[4] or 0)
                distance = float(row[5] or 0)
                eff = float(row[6] or 0)
                duration = int(row[7] or 0)
                secure_rate = (secures / carries * 100) if carries > 0 else 0
                embed.add_field(
                    name=f"{i}. {name}",
                    value=(
                        f"Carries: {carries} | Secures: **{secures}** ({secure_rate:.0f}%)\n"
                        f"Killed: {killed} | Distance: {distance:.0f}u | Eff: {eff:.1%}\n"
                        f"Avg carry: {duration/1000:.1f}s"
                    ),
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"carriers error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_carrier_kills', aliases=['pck'])
    async def proximity_carrier_kills(self, ctx, session_date: str = None):
        """Top carrier killers - who stops objective runners (v6)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT killer_guid, MAX(killer_name) AS name,
                       COUNT(*) AS carrier_kills,
                       ROUND(AVG(carrier_distance_at_kill)::numeric, 0) AS avg_distance_stopped
                FROM proximity_carrier_kill
                {date_filter}
                GROUP BY killer_guid
                HAVING COUNT(*) >= 1
                ORDER BY carrier_kills DESC
                LIMIT 10
            """, tuple(params))

            if not rows:
                await ctx.send("No carrier kill data found.")
                return

            embed = discord.Embed(
                title="Carrier Killers - Top 10",
                description="Most objective carrier kills",
                color=discord.Color.red()
            )
            for i, row in enumerate(rows, 1):
                name = row[1] or row[0][:8]
                kills = int(row[2] or 0)
                avg_dist = float(row[3] or 0)
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"Carrier kills: **{kills}** | Avg distance stopped: {avg_dist:.0f}u",
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"carrier_kills error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")

    @commands.command(name='proximity_carry_detail', aliases=['pcd'])
    async def proximity_carry_detail(self, ctx, session_date: str = None):
        """Detailed carrier event log for a session (v6)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("Proximity commands are disabled.")
            return

        try:
            date_filter = ""
            params = []
            if session_date:
                date_filter = "WHERE session_date = $1"
                params = [session_date]
            else:
                date_filter = "WHERE session_date = (SELECT MAX(session_date) FROM proximity_carrier_event)"

            rows = await self.bot.db_adapter.fetch_all(f"""
                SELECT carrier_name, carrier_team, flag_team, outcome,
                       carry_distance, beeline_distance, efficiency,
                       duration_ms, map_name, killer_name
                FROM proximity_carrier_event
                {date_filter}
                ORDER BY pickup_time
                LIMIT 20
            """, tuple(params))

            if not rows:
                await ctx.send("No carrier events found.")
                return

            outcome_icons = {
                'secured': '+', 'killed': 'X', 'dropped': 'D',
                'returned': 'R', 'round_end': 'E', 'disconnected': 'DC'
            }

            embed = discord.Embed(
                title="Carrier Event Log",
                description="Recent objective carry events",
                color=discord.Color.dark_gold()
            )
            for row in rows:
                name = row[0]
                team = row[1]
                outcome = row[3]
                distance = float(row[4] or 0)
                eff = float(row[6] or 0)
                duration = int(row[7] or 0)
                map_name = row[8]
                killer = row[9]
                icon = outcome_icons.get(outcome, '?')

                detail = f"[{icon}] {outcome} | {distance:.0f}u ({eff:.0%}) | {duration/1000:.1f}s"
                if outcome == 'killed' and killer:
                    detail += f" by {killer}"
                embed.add_field(
                    name=f"{name} ({team}) on {map_name}",
                    value=detail,
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"carry_detail error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")
