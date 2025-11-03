"""
Last Session Cog - Comprehensive session analytics with multiple view modes

This cog handles the massive !last_session command with proper refactoring:
- Multiple view modes: default, graphs, full, top, combat, obj, weapons, support, sprees
- Team analytics with hardcoded team detection
- Performance graphs using matplotlib
- Weapon mastery breakdowns
- Objective and support stats
- Special awards and chaos stats

Refactored into ~20 helper methods for maintainability
"""

import asyncio
import io
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiosqlite
import discord
from discord.ext import commands

from tools.stopwatch_scoring import StopwatchScoring

logger = logging.getLogger("bot.cogs.last_session")


class LastSessionCog(commands.Cog):
    """🎮 Comprehensive last session analytics with multiple view modes"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🎮 LastSessionCog initializing...")

    # ═══════════════════════════════════════════════════════
    # PHASE 1: CORE INFRASTRUCTURE - Database & Session Fetching
    # ═══════════════════════════════════════════════════════

    async def _get_latest_session_date(self, db) -> Optional[str]:
        """
        Get the most recent gaming session date from database.
        
        Returns the most recent date that has session data.
        Now properly sorts by BOTH date AND time to get the actual last session.
        """
        async with db.execute(
            """
            SELECT SUBSTR(s.session_date, 1, 10) as date
            FROM sessions s
            WHERE EXISTS (
                SELECT 1 FROM player_comprehensive_stats p
                WHERE p.session_id = s.id
            )
            AND SUBSTR(s.session_date, 1, 4) = '2025'
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 1
            """
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

    async def _fetch_session_data(self, db, latest_date: str) -> Tuple[List, List, str, int]:
        """
        Fetch all session data for the LAST gaming session.
        
        Works BACKWARDS from the absolute last session in the database,
        grouping sessions that are within 30 minutes of each other.
        This properly handles multiple gaming sessions on the same day.
        
        Returns:
            (sessions, session_ids, session_ids_str, player_count)
        """
        from datetime import datetime, timedelta
        
        # Get the absolute last session (by date AND time)
        async with db.execute(
            """
            SELECT id, map_name, round_number, actual_time, session_date, session_time
            FROM sessions
            ORDER BY session_date DESC, session_time DESC
            LIMIT 1
            """,
        ) as cursor:
            last_session = await cursor.fetchone()
        
        if not last_session:
            return None, None, None, 0
        
        last_session_id = last_session[0]
        last_session_date = last_session[4]
        last_session_time = last_session[5]
        last_dt = datetime.strptime(f"{last_session_date}-{last_session_time}", '%Y-%m-%d-%H%M%S')
        
        # Now work BACKWARDS, collecting sessions within 30min gaps
        gaming_session_ids = [last_session_id]
        current_dt = last_dt
        
        # Get recent sessions before the last one (limit search to same day + previous day)
        search_start_date = (last_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        
        async with db.execute(
            """
            SELECT id, map_name, round_number, actual_time, session_date, session_time
            FROM sessions
            WHERE session_date >= ?
              AND id < ?
            ORDER BY session_date DESC, session_time DESC
            """,
            (search_start_date, last_session_id),
        ) as cursor:
            previous_sessions = await cursor.fetchall()
        
        # Work backwards through sessions, stop at first gap > 30 minutes
        for sess in previous_sessions:
            sess_date = sess[4]
            sess_time = sess[5]
            sess_dt = datetime.strptime(f"{sess_date}-{sess_time}", '%Y-%m-%d-%H%M%S')
            
            gap_minutes = (current_dt - sess_dt).total_seconds() / 60
            
            if gap_minutes <= 30:
                gaming_session_ids.insert(0, sess[0])  # Insert at beginning (chronological order)
                current_dt = sess_dt  # Update for next comparison
            else:
                break  # Gap too large - different gaming session
        
        # Now fetch full session data for the gaming session
        session_ids_str = ','.join(str(sid) for sid in gaming_session_ids)
        
        async with db.execute(
            f"""
            SELECT id, map_name, round_number, actual_time, session_date, session_time
            FROM sessions
            WHERE id IN ({session_ids_str})
            ORDER BY id ASC
            """
        ) as cursor:
            primary_sessions = await cursor.fetchall()

        if not primary_sessions:
            return None, None, None, 0

        # Check for sessions after midnight (next day)
        last_session_id = primary_sessions[-1][0]
        last_session_date = primary_sessions[-1][4]  # YYYY-MM-DD
        last_session_time = primary_sessions[-1][5]  # HHMMSS
        
        # Calculate next day date string
        last_session_date_full = f"{last_session_date}-{last_session_time}"
        last_dt = datetime.strptime(last_session_date_full, '%Y-%m-%d-%H%M%S')
        next_day = (last_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Get sessions from next day that might be part of same gaming session
        async with db.execute(
            """
            SELECT id, map_name, round_number, actual_time, session_date, session_time
            FROM sessions
            WHERE SUBSTR(session_date, 1, 10) = ?
                AND id > ?
            ORDER BY id ASC
            LIMIT 10
            """,
            (next_day, last_session_id),
        ) as cursor:
            next_day_sessions = await cursor.fetchall()
        
        # Include next-day sessions if they're within 30min of last session
        continuation_sessions = []
        if next_day_sessions:
            for sess in next_day_sessions:
                sess_dt = datetime.strptime(sess[4], '%Y-%m-%d-%H%M%S')
                gap_minutes = (sess_dt - last_dt).total_seconds() / 60
                
                if gap_minutes <= 30:
                    continuation_sessions.append(sess)
                    last_dt = sess_dt  # Update for next comparison
                else:
                    break  # Gap too large, stop checking
        
        # Combine all sessions
        all_sessions = primary_sessions + continuation_sessions
        sessions = [(s[0], s[1], s[2], s[3]) for s in all_sessions]
        
        session_ids = [s[0] for s in sessions]
        session_ids_str = ",".join("?" * len(session_ids))

        # Get unique player count
        query = f"""
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
        """
        async with db.execute(query, session_ids) as cursor:
            player_count = (await cursor.fetchone())[0]

        return sessions, session_ids, session_ids_str, player_count

    async def _get_hardcoded_teams(self, db, session_ids: List[int]) -> Optional[Dict]:
        """
        Get hardcoded team assignments from session_teams table
        
        NOTE: Queries by date range of the gaming session rounds.
        
        Args:
            session_ids: List of session IDs (rounds) for this gaming session
        
        Returns:
            Dict with team names as keys, containing 'guids' list
        """
        try:
            import json
            
            # Get the date range for these session_ids
            placeholders = ','.join('?' * len(session_ids))
            async with db.execute(
                f"""
                SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
                FROM sessions
                WHERE id IN ({placeholders})
                """,
                session_ids
            ) as cursor:
                dates = [row[0] for row in await cursor.fetchall()]
            
            if not dates:
                return None
            
            # Query session_teams for these dates
            date_placeholders = ','.join('?' * len(dates))
            async with db.execute(
                f"""
                SELECT team_name, player_guids, player_names
                FROM session_teams
                WHERE session_start_date IN ({date_placeholders}) AND map_name = 'ALL'
                ORDER BY team_name
                """,
                dates,
            ) as cursor:
                rows = await cursor.fetchall()

            if not rows:
                return None

            teams = {}
            for team_name, player_guids_json, player_names_json in rows:
                if team_name not in teams:
                    teams[team_name] = {
                        "guids": json.loads(player_guids_json) if player_guids_json else [],
                        "names": json.loads(player_names_json) if player_names_json else []
                    }

            return teams if teams else None

        except Exception as e:
            logger.debug(f"No hardcoded teams found: {e}")
            return None

    async def _ensure_player_name_alias(self, db):
        """Create TEMP VIEW alias for player_name if needed"""
        try:
            # Check if clean_name exists but player_name doesn't
            async with db.execute("PRAGMA table_info(player_comprehensive_stats)") as cursor:
                columns = await cursor.fetchall()
                col_names = [col[1] for col in columns]
                
                if "clean_name" in col_names and "player_name" not in col_names:
                    await db.execute("""
                        CREATE TEMP VIEW IF NOT EXISTS player_name_alias AS
                        SELECT *, clean_name as player_name
                        FROM player_comprehensive_stats
                    """)
                    logger.debug("✅ Created player_name alias for clean_name")
        except Exception as e:
            logger.debug(f"player_name alias setup: {e}")

    async def _enable_sql_diag(self, db):
        """Enable lightweight SQL diagnostics for debugging"""
        # This is a placeholder for future diagnostic features
        pass

    async def _send_last_session_help(self, ctx):
        """Send persistent help hint about available subcommands"""
        # This could show available view modes in a small embed
        pass

    # ═══════════════════════════════════════════════════════
    # PHASE 2: VIEW MODE HANDLERS - Specialized views
    # ═══════════════════════════════════════════════════════

    async def _show_objectives_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show objectives & support stats only"""
        query = f"""
            SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused, times_revived,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                denied_playtime, most_useful_kills, useless_kills, gibs,
                killing_spree_best, death_spree_worst
            FROM player_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
        """
        async with db.execute(query, session_ids) as cursor:
            awards_rows = await cursor.fetchall()

        if not awards_rows:
            await ctx.send("❌ No objective/support data available for latest session")
            return

        # Also fetch revives GIVEN per player
        rev_query = f"""
            SELECT clean_name, SUM(revives_given) as revives_given
            FROM player_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
            GROUP BY clean_name
        """
        async with db.execute(rev_query, session_ids) as cursor:
            rev_rows = await cursor.fetchall()
        revives_map = {r[0]: (r[1] or 0) for r in rev_rows}

        # Aggregate per-player across rounds
        player_objectives = {}
        for row in awards_rows:
            name = row[0]
            if name not in player_objectives:
                player_objectives[name] = {
                    "xp": 0, "assists": 0, "obj_stolen": 0, "obj_returned": 0,
                    "dyn_planted": 0, "dyn_defused": 0, "times_revived": 0,
                    "revives_given": 0, "multi_2x": 0, "multi_3x": 0,
                    "multi_4x": 0, "multi_5x": 0, "multi_6x": 0,
                    "denied_time": 0, "useful_kills": 0, "useless_kills": 0,
                    "gibs": 0, "best_spree": 0, "worst_spree": 0
                }

            player_objectives[name]["xp"] += row[1] or 0
            player_objectives[name]["assists"] += row[2] or 0
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

        embed.set_footer(text=f"Session: {latest_date} • Use !last_session for full report")
        await ctx.send(embed=embed)

    async def _show_combat_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show combat-focused stats only"""
        query = f"""
            SELECT p.player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                SUM(p.damage_given) as damage_given,
                SUM(p.damage_received) as damage_received,
                SUM(p.gibs) as gibs,
                SUM(p.headshot_kills) as headshot_kills,
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as weighted_dpm
            FROM player_comprehensive_stats p
            WHERE p.session_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
        """
        async with db.execute(query, session_ids) as cursor:
            combat_rows = await cursor.fetchall()

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
            name, kills, deaths, dmg_g, dmg_r, gibs, hsk, dpm = row
            kd = kills / deaths if deaths and deaths > 0 else (kills or 0)
            
            player_text = (
                f"{medals[i-1] if i <= 3 else f'{i}.'} **{name}**\n"
                f"💀 `{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM`\n"
                f"💥 Damage: `{(dmg_g or 0):,}` given • `{(dmg_r or 0):,}` received\n"
            )
            if gibs and gibs > 0:
                player_text += f"🦴 `{gibs} Gibs`"
            if hsk and hsk > 0:
                player_text += f" • 🎯 `{hsk} Headshot Kills`"

            embed.add_field(name="\u200b", value=player_text, inline=False)

        embed.set_footer(text=f"Session: {latest_date} • Use !last_session for full report")
        await ctx.send(embed=embed)

    async def _show_weapons_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show weapon mastery stats only"""
        query = f"""
            SELECT p.player_name, w.weapon_name,
                SUM(w.kills) as weapon_kills,
                SUM(w.hits) as hits,
                SUM(w.shots) as shots,
                SUM(w.headshots) as headshots
            FROM weapon_comprehensive_stats w
            JOIN player_comprehensive_stats p
                ON w.session_id = p.session_id
                AND w.player_guid = p.player_guid
            WHERE w.session_id IN ({session_ids_str})
            GROUP BY p.player_name, w.weapon_name
            HAVING weapon_kills > 0
            ORDER BY p.player_name, weapon_kills DESC
        """
        async with db.execute(query, session_ids) as cursor:
            pw_rows = await cursor.fetchall()

        if not pw_rows:
            await ctx.send("❌ No weapon data available for latest session")
            return

        # Group by player
        player_weapon_map = {}
        for player, weapon, kills, hits, shots, hs in pw_rows:
            if player not in player_weapon_map:
                player_weapon_map[player] = []
            acc = (hits / shots * 100) if shots and shots > 0 else 0
            hs_pct = (hs / hits * 100) if hits and hits > 0 else 0
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

        embed.set_footer(text=f"Session: {latest_date} • Use !last_session for full report")
        await ctx.send(embed=embed)

    async def _show_support_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show support activity stats only"""
        query = f"""
            SELECT p.player_name,
                SUM(p.revives_given) as revives_given,
                SUM(p.times_revived) as times_revived,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths
            FROM player_comprehensive_stats p
            WHERE p.session_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY revives_given DESC
        """
        async with db.execute(query, session_ids) as cursor:
            sup_rows = await cursor.fetchall()

        if not sup_rows:
            await ctx.send("❌ No support data available for latest session")
            return

        embed = discord.Embed(
            title=f"💉 Support Stats - {latest_date}",
            description=f"Support activity • {player_count} players",
            color=0x57F287,
            timestamp=datetime.now(),
        )

        for name, revives_given, times_revived, kills, deaths in sup_rows:
            txt = f"Revives Given: `{revives_given or 0}` • Times Revived: `{times_revived or 0}`\n"
            txt += f"Kills: `{kills or 0}` • Deaths: `{deaths or 0}`"
            embed.add_field(name=f"{name}", value=txt, inline=False)

        embed.set_footer(text=f"Session: {latest_date}")
        await ctx.send(embed=embed)

    async def _show_sprees_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show killing sprees & multikills only"""
        query = f"""
            SELECT p.player_name,
                SUM(p.killing_spree_best) as best_spree,
                SUM(p.double_kills) as doubles,
                SUM(p.triple_kills) as triples,
                SUM(p.quad_kills) as quads,
                SUM(p.multi_kills) as multis,
                SUM(p.mega_kills) as megas,
                SUM(p.kills) as total_kills
            FROM player_comprehensive_stats p
            WHERE p.session_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY best_spree DESC, megas DESC
        """
        async with db.execute(query, session_ids) as cursor:
            spree_rows = await cursor.fetchall()

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

        embed.set_footer(text=f"Session: {latest_date}")
        await ctx.send(embed=embed)

    async def _show_top_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int, total_maps: int):
        """Show all players ranked by kills"""
        query = f"""
            SELECT p.player_name,
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
            WHERE p.session_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
        """
        async with db.execute(query, session_ids) as cursor:
            top_players = await cursor.fetchall()

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
            kd = kills / deaths if deaths > 0 else kills
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

        embed.set_footer(text="💡 Use !last_session for full details")
        await ctx.send(embed=embed)

    async def _show_maps_view(self, ctx, db, latest_date: str, sessions: List, session_ids: List, session_ids_str: str, player_count: int):
        """Show popular stats per map (map summaries only)"""
        
        # Group sessions by map
        map_sessions = {}
        for session_id, map_name, round_num, actual_time in sessions:
            if map_name not in map_sessions:
                map_sessions[map_name] = []
            map_sessions[map_name].append(session_id)
        
        # For each map, get aggregated stats (both rounds combined)
        for map_name, map_session_ids in map_sessions.items():
            map_ids_str = ','.join('?' * len(map_session_ids))
            
            # Get all players for this map (aggregated across both rounds)
            query = f"""
                SELECT p.player_name,
                    SUM(p.kills) as kills,
                    SUM(p.deaths) as deaths,
                    CASE
                        WHEN SUM(p.time_played_seconds) > 0
                        THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                        ELSE 0
                    END as dpm,
                    SUM(p.damage_given) as dmg_given,
                    SUM(p.damage_received) as dmg_received,
                    SUM(p.gibs) as gibs,
                    SUM(p.headshot_kills) as headshots,
                    SUM(p.time_played_seconds) as time_played,
                    SUM(p.time_dead_minutes) as time_dead_minutes,
                    SUM(p.denied_playtime) as time_denied,
                    COALESCE(SUM(w.hits), 0) as total_hits,
                    COALESCE(SUM(w.shots), 0) as total_shots
                FROM player_comprehensive_stats p
                LEFT JOIN (
                    SELECT session_id, player_guid, SUM(hits) as hits, SUM(shots) as shots
                    FROM weapon_comprehensive_stats
                    WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                    GROUP BY session_id, player_guid
                ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                WHERE p.session_id IN ({map_ids_str})
                GROUP BY p.player_name
                ORDER BY kills DESC
            """
            
            async with db.execute(query, map_session_ids) as cursor:
                players = await cursor.fetchall()
            
            if not players:
                continue
            
            # Build embed for this map
            embed = discord.Embed(
                title=f"🗺️ Map Stats: {map_name}",
                description=f"{len(players)} players • Map Summary (both rounds)",
                color=0x5865F2,
                timestamp=datetime.now()
            )
            
            # Split players into multiple fields (3 per field to avoid 1024 char limit)
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "1️⃣1️⃣", "1️⃣2️⃣"]
            players_per_field = 3
            
            for field_idx in range(0, len(players), players_per_field):
                field_players = players[field_idx:field_idx + players_per_field]
                field_text = ""
                
                for i, player in enumerate(field_players):
                    global_idx = field_idx + i
                    name, kills, deaths, dpm, dmg_given, dmg_received, gibs, hs, time_played, time_dead, time_denied, hits, shots = player
                    
                    # Handle nulls
                    kills = kills or 0
                    deaths = deaths or 0
                    dpm = dpm or 0
                    dmg_given = dmg_given or 0
                    dmg_received = dmg_received or 0
                    gibs = gibs or 0
                    hs = hs or 0
                    time_played = time_played or 0
                    time_dead = time_dead or 0
                    time_denied = time_denied or 0
                    hits = hits or 0
                    shots = shots or 0
                    
                    # Calculate metrics
                    kd = kills / deaths if deaths > 0 else kills
                    acc = (hits / shots * 100) if shots > 0 else 0
                    
                    # Format times
                    play_min = int(time_played // 60)
                    play_sec = int(time_played % 60)
                    dead_min = int(time_dead)
                    denied_min = int(time_denied // 60)
                    denied_sec = int(time_denied % 60)
                    
                    medal = medals[global_idx] if global_idx < len(medals) else "🔹"
                    
                    field_text += f"{medal} **{name}**\n"
                    field_text += f"`{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM` • `{acc:.1f}% ACC`\n"
                    field_text += f"💥 `{dmg_given:,}↑ / {dmg_received:,}↓` • 🦴 `{gibs}` • 🎯 `{hs} HS`\n"
                    field_text += f"⏱️ `{play_min}:{play_sec:02d}` • 💀 `{dead_min}m` • ⏳ `{denied_min}:{denied_sec:02d}`\n"
                
                # Add field
                if field_idx == 0:
                    field_name = "📊 All Players"
                else:
                    field_name = "\u200b"
                
                embed.add_field(name=field_name, value=field_text.rstrip(), inline=False)
            
            embed.set_footer(text=f"Session: {latest_date} • Use !last_session maps full for round-by-round")
            await ctx.send(embed=embed)
            await asyncio.sleep(3)  # 3 second delay between maps

    async def _show_maps_full_view(self, ctx, db, latest_date: str, sessions: List, session_ids: List, session_ids_str: str, player_count: int):
        """Show round-by-round breakdown for each map"""
        
        # Group sessions by map and round
        map_rounds = {}
        for session_id, map_name, round_num, actual_time in sessions:
            if map_name not in map_rounds:
                map_rounds[map_name] = {'round1': [], 'round2': [], 'all': []}
            
            map_rounds[map_name]['all'].append(session_id)
            if round_num == 1:
                map_rounds[map_name]['round1'].append(session_id)
            elif round_num == 2:
                map_rounds[map_name]['round2'].append(session_id)
        
        # For each map, show Round 1, Round 2, and Map Summary
        for map_name, rounds in map_rounds.items():
            
            # ===== ROUND 1 =====
            if rounds['round1']:
                await self._send_round_stats(ctx, db, map_name, "Round 1", rounds['round1'], latest_date)
                await asyncio.sleep(3)
            
            # ===== ROUND 2 =====
            if rounds['round2']:
                await self._send_round_stats(ctx, db, map_name, "Round 2", rounds['round2'], latest_date)
                await asyncio.sleep(3)
            
            # ===== MAP SUMMARY (both rounds combined) =====
            if rounds['all']:
                await self._send_round_stats(ctx, db, map_name, "Map Summary", rounds['all'], latest_date)
                await asyncio.sleep(3)

    async def _send_round_stats(self, ctx, db, map_name: str, round_label: str, round_session_ids: List, latest_date: str):
        """Helper to send stats for a single round or map summary"""
        
        round_ids_str = ','.join('?' * len(round_session_ids))
        
        # Get all players for this round
        query = f"""
            SELECT p.player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as dpm,
                SUM(p.damage_given) as dmg_given,
                SUM(p.damage_received) as dmg_received,
                SUM(p.gibs) as gibs,
                SUM(p.headshot_kills) as headshots,
                SUM(p.time_played_seconds) as time_played,
                SUM(p.time_dead_minutes) as time_dead_minutes,
                SUM(p.denied_playtime) as time_denied,
                COALESCE(SUM(w.hits), 0) as total_hits,
                COALESCE(SUM(w.shots), 0) as total_shots
            FROM player_comprehensive_stats p
            LEFT JOIN (
                SELECT session_id, player_guid, SUM(hits) as hits, SUM(shots) as shots
                FROM weapon_comprehensive_stats
                WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                GROUP BY session_id, player_guid
            ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
            WHERE p.session_id IN ({round_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
        """
        
        async with db.execute(query, round_session_ids) as cursor:
            players = await cursor.fetchall()
        
        if not players:
            return
        
        # Determine color based on round
        if "Round 1" in round_label:
            color = 0xED4245  # Red
        elif "Round 2" in round_label:
            color = 0x5865F2  # Blue
        else:
            color = 0x57F287  # Green (summary)
        
        # Build embed
        embed = discord.Embed(
            title=f"🗺️ {map_name} - {round_label}",
            description=f"{len(players)} players",
            color=color,
            timestamp=datetime.now()
        )
        
        # Split players into fields (3 per field)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "1️⃣1️⃣", "1️⃣2️⃣"]
        players_per_field = 3
        
        for field_idx in range(0, len(players), players_per_field):
            field_players = players[field_idx:field_idx + players_per_field]
            field_text = ""
            
            for i, player in enumerate(field_players):
                global_idx = field_idx + i
                name, kills, deaths, dpm, dmg_given, dmg_received, gibs, hs, time_played, time_dead, time_denied, hits, shots = player
                
                # Handle nulls
                kills = kills or 0
                deaths = deaths or 0
                dpm = dpm or 0
                dmg_given = dmg_given or 0
                dmg_received = dmg_received or 0
                gibs = gibs or 0
                hs = hs or 0
                time_played = time_played or 0
                time_dead = time_dead or 0
                time_denied = time_denied or 0
                hits = hits or 0
                shots = shots or 0
                
                # Calculate
                kd = kills / deaths if deaths > 0 else kills
                acc = (hits / shots * 100) if shots > 0 else 0
                
                # Format times
                play_min = int(time_played // 60)
                play_sec = int(time_played % 60)
                dead_min = int(time_dead)
                denied_min = int(time_denied // 60)
                denied_sec = int(time_denied % 60)
                
                medal = medals[global_idx] if global_idx < len(medals) else "🔹"
                
                field_text += f"{medal} **{name}**\n"
                field_text += f"`{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM` • `{acc:.1f}% ACC`\n"
                field_text += f"💥 `{dmg_given:,}↑ / {dmg_received:,}↓` • 🦴 `{gibs}` • 🎯 `{hs} HS`\n"
                field_text += f"⏱️ `{play_min}:{play_sec:02d}` • 💀 `{dead_min}m` • ⏳ `{denied_min}:{denied_sec:02d}`\n"
            
            # Add field
            if field_idx == 0:
                field_name = "📊 All Players"
            else:
                field_name = "\u200b"
            
            embed.add_field(name=field_name, value=field_text.rstrip(), inline=False)
        
        embed.set_footer(text=f"Session: {latest_date}")
        await ctx.send(embed=embed)

    # ═══════════════════════════════════════════════════════
    # PHASE 3: DATA AGGREGATION - Heavy data processing
    # ═══════════════════════════════════════════════════════

    async def _aggregate_all_player_stats(self, db, session_ids: List, session_ids_str: str):
        """
        Aggregate ALL player stats across all rounds with weighted DPM
        
        Returns: List of player stat tuples
        """
        query = f"""
            SELECT p.player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as weighted_dpm,
                COALESCE(SUM(w.hits), 0) as total_hits,
                COALESCE(SUM(w.shots), 0) as total_shots,
                COALESCE(SUM(w.headshots), 0) as total_headshots,
                SUM(p.headshot_kills) as headshot_kills,
                SUM(p.time_played_seconds) as total_seconds,
                CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead,
                SUM(p.denied_playtime) as total_denied
            FROM player_comprehensive_stats p
            LEFT JOIN (
                SELECT session_id, player_guid,
                    SUM(hits) as hits,
                    SUM(shots) as shots,
                    SUM(headshots) as headshots
                FROM weapon_comprehensive_stats
                WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                GROUP BY session_id, player_guid
            ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
            WHERE p.session_id IN ({session_ids_str})
            GROUP BY p.player_guid
            ORDER BY kills DESC
        """
        async with db.execute(query, session_ids) as cursor:
            return await cursor.fetchall()

    async def _aggregate_team_stats(self, db, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict] = None, name_to_team: Optional[Dict] = None):
        """
        Get aggregated team statistics
        
        IMPORTANT: In stopwatch mode, players swap sides between rounds, so the 'team' 
        column (1 or 2) represents the SIDE they played, not their actual team.
        We must use hardcoded teams or session_teams table to determine actual teams.
        
        Without hardcoded teams, stats will show ATTACKERS vs DEFENDERS, not actual teams!
        """
        if not hardcoded_teams or not name_to_team or len(name_to_team) == 0:
            # WARNING: In stopwatch mode this groups by SIDE (attacker/defender) not actual team!
            logger.warning("⚠️ No team rosters available - stats will group by SIDE not team")
            query = f"""
                SELECT team,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage
                FROM player_comprehensive_stats
                WHERE session_id IN ({session_ids_str})
                GROUP BY team
            """
            async with db.execute(query, session_ids) as cursor:
                return await cursor.fetchall()
        
        # Get all player stats
        query = f"""
            SELECT player_name, player_guid,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(damage_given) as total_damage
            FROM player_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
            GROUP BY player_guid
        """
        async with db.execute(query, session_ids) as cursor:
            player_stats = await cursor.fetchall()
        
        # Aggregate by actual team
        team_aggregates = {}
        for player_name, player_guid, kills, deaths, damage in player_stats:
            team_name = name_to_team.get(player_name)
            if team_name:
                if team_name not in team_aggregates:
                    team_aggregates[team_name] = {"kills": 0, "deaths": 0, "damage": 0}
                team_aggregates[team_name]["kills"] += kills
                team_aggregates[team_name]["deaths"] += deaths
                team_aggregates[team_name]["damage"] += damage
        
        # Convert to expected format (team_number, kills, deaths, damage)
        # We'll use 1 and 2 as team numbers, but they now represent actual teams
        result = []
        team_names = list(team_aggregates.keys())
        for i, team_name in enumerate(team_names[:2], start=1):
            stats = team_aggregates[team_name]
            result.append((i, stats["kills"], stats["deaths"], stats["damage"]))
        
        return result

    async def _aggregate_weapon_stats(self, db, session_ids: List, session_ids_str: str):
        """Get per-player weapon mastery data"""
        query = f"""
            SELECT p.player_name,
                w.weapon_name,
                SUM(w.kills) as weapon_kills,
                SUM(w.hits) as weapon_hits,
                SUM(w.shots) as weapon_shots,
                SUM(w.headshots) as weapon_headshots
            FROM weapon_comprehensive_stats w
            JOIN player_comprehensive_stats p
                ON w.session_id = p.session_id
                AND w.player_guid = p.player_guid
            WHERE w.session_id IN ({session_ids_str})
            GROUP BY p.player_guid, w.weapon_name
            HAVING weapon_kills > 0
            ORDER BY p.player_name, weapon_kills DESC
        """
        async with db.execute(query, session_ids) as cursor:
            return await cursor.fetchall()

    async def _get_dpm_leaderboard(self, db, session_ids: List, session_ids_str: str, limit: int = 10):
        """Get DPM leaderboard with weighted calculation"""
        query = f"""
            SELECT player_name,
                CASE
                    WHEN SUM(time_played_seconds) > 0
                    THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                    ELSE 0
                END as weighted_dpm,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths
            FROM player_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
            GROUP BY player_guid
            ORDER BY weighted_dpm DESC
            LIMIT ?
        """
        async with db.execute(query, session_ids + [limit]) as cursor:
            return await cursor.fetchall()

    async def _calculate_team_scores(self, session_ids: List[int]) -> Tuple[str, str, int, int, Optional[Dict]]:
        """
        Calculate Stopwatch team scores using StopwatchScoring
        
        NOTE: Calculates scores for a GAMING SESSION (multiple matches/rounds).
        
        Args:
            session_ids: List of session IDs (rounds) for this gaming session
        
        Returns: (team_1_name, team_2_name, team_1_score, team_2_score, scoring_result)
        """
        scorer = StopwatchScoring(self.bot.db_path)
        scoring_result = scorer.calculate_session_scores(session_ids=session_ids)

        if scoring_result:
            # Get team names (exclude 'maps' and 'total_maps' keys)
            team_names = [
                k for k in scoring_result.keys()
                if k not in ["maps", "total_maps"]
            ]
            if len(team_names) >= 2:
                team_1_name = team_names[0]
                team_2_name = team_names[1]
                team_1_score = scoring_result[team_1_name]
                team_2_score = scoring_result[team_2_name]
                return team_1_name, team_2_name, team_1_score, team_2_score, scoring_result

        return "Team 1", "Team 2", 0, 0, None

    async def _build_team_mappings(self, db, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict]):
        """
        Build team mappings from hardcoded teams or auto-detect
        
        NOTE: Works with gaming session rounds (session_ids list).
        
        Args:
            db: Database connection
            session_ids: List of session IDs (rounds) for this gaming session
            session_ids_str: Comma-separated session IDs for SQL queries
            hardcoded_teams: Optional pre-defined team assignments
        
        Returns: (team_1_name, team_2_name, team_1_players, team_2_players, name_to_team)
        """
        if hardcoded_teams:
            logger.info("✅ Using hardcoded teams from session_teams table")
            
            # Extract team names
            team_names_list = list(hardcoded_teams.keys())
            team_1_name = team_names_list[0] if len(team_names_list) > 0 else "Team A"
            team_2_name = team_names_list[1] if len(team_names_list) > 1 else "Team B"
            
            # Create GUID -> team_name mapping
            guid_to_team = {}
            for team_name, team_data in hardcoded_teams.items():
                for guid in team_data["guids"]:
                    guid_to_team[guid] = team_name
            
            # Get player GUIDs to map names to teams
            query = f"""
                SELECT DISTINCT player_name, player_guid
                FROM player_comprehensive_stats
                WHERE session_id IN ({session_ids_str})
            """
            async with db.execute(query, session_ids) as cursor:
                player_guid_map = await cursor.fetchall()
            
            # Build name -> team mapping
            name_to_team = {}
            for player_name, player_guid in player_guid_map:
                if player_guid in guid_to_team:
                    name_to_team[player_name] = guid_to_team[player_guid]
            
            # Organize players by team
            team_1_players = [name for name, team in name_to_team.items() if team == team_1_name]
            team_2_players = [name for name, team in name_to_team.items() if team == team_2_name]
            
            return team_1_name, team_2_name, team_1_players, team_2_players, name_to_team
        else:
            # Auto-detect teams using co-occurrence analysis
            logger.info("⚠️ No hardcoded teams - attempting smart auto-detection")
            
            # Get all player-side pairings
            # IMPORTANT: Include session_id in the key to handle multiple plays of same map
            query = f"""
                SELECT player_guid, player_name, team, session_id, map_name, round_number
                FROM player_comprehensive_stats
                WHERE session_id IN ({session_ids_str})
                ORDER BY session_id, map_name, round_number
            """
            async with db.execute(query, session_ids) as cursor:
                all_records = await cursor.fetchall()
            
            if not all_records:
                return "Team 1", "Team 2", [], [], {}
            
            # Build round-by-round side assignments: (session_id, map, round) -> {guid: side}
            # Using session_id ensures each play of a map is tracked separately
            from collections import defaultdict
            round_sides = defaultdict(dict)
            guid_to_name = {}
            all_guids = set()
            
            for guid, name, side, sess_id, map_name, round_num in all_records:
                round_sides[(sess_id, map_name, round_num)][guid] = side
                guid_to_name[guid] = name
                all_guids.add(guid)
            
            # Count how often each pair of players is on the SAME side
            # This works because actual teammates play together regardless of which side they're assigned
            from itertools import combinations
            cooccurrence = defaultdict(int)
            
            for (sess_id, map_name, round_num), sides in round_sides.items():
                guids_in_round = list(sides.keys())
                for guid1, guid2 in combinations(guids_in_round, 2):
                    if sides[guid1] == sides[guid2]:
                        # They were on same side this round -> likely same team
                        cooccurrence[(guid1, guid2)] += 1
            
            # Build team clusters using graph clustering
            # Strategy: Players with >50% co-occurrence are on same team
            if not all_guids:
                return "Team 1", "Team 2", [], [], {}
            
            # Build adjacency: guid -> set of guids they play with frequently
            teammates = defaultdict(set)
            
            for (guid1, guid2), cooccur_count in cooccurrence.items():
                # Calculate total rounds these two played together
                total_rounds_together = sum(
                    1 for sides in round_sides.values()
                    if guid1 in sides and guid2 in sides
                )
                
                if total_rounds_together > 0:
                    same_side_ratio = cooccur_count / total_rounds_together
                    if same_side_ratio > 0.5:  # More than 50% = same team
                        teammates[guid1].add(guid2)
                        teammates[guid2].add(guid1)
            
            # Use connected components to find teams
            team_a_guids = set()
            team_b_guids = set()
            visited = set()
            
            def get_cluster(start_guid):
                """Get all connected players (teammates)"""
                cluster = set()
                to_visit = [start_guid]
                
                while to_visit:
                    guid = to_visit.pop()
                    if guid in visited:
                        continue
                    visited.add(guid)
                    cluster.add(guid)
                    to_visit.extend(teammates.get(guid, []))
                
                return cluster
            
            # Find first cluster (Team A)
            if all_guids:
                first_guid = next(iter(all_guids))
                team_a_guids = get_cluster(first_guid)
                
                # Remaining players are Team B
                team_b_guids = all_guids - team_a_guids
            
            # Build name_to_team mapping
            name_to_team = {}
            team_a_players = []
            team_b_players = []
            
            for guid in team_a_guids:
                name = guid_to_name.get(guid)
                if name:
                    name_to_team[name] = "Team A"
                    team_a_players.append(name)
            
            for guid in team_b_guids:
                name = guid_to_name.get(guid)
                if name:
                    name_to_team[name] = "Team B"
                    team_b_players.append(name)
            
            logger.info(f"✅ Auto-detected Team A: {len(team_a_players)} players, Team B: {len(team_b_players)} players")
            
            return "Team A", "Team B", team_a_players, team_b_players, name_to_team

    async def _get_team_mvps(self, db, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict], team_1_name: str, team_2_name: str):
        """
        Get MVP for each team with detailed stats
        
        Returns: (team_1_mvp_stats, team_2_mvp_stats)
        Each MVP stats tuple: (player_name, kills, dpm, deaths, revives, gibs)
        """
        team_1_mvp_stats = None
        team_2_mvp_stats = None

        if hardcoded_teams:
            # Calculate MVP per hardcoded team (by GUID)
            for team_name in [team_1_name, team_2_name]:
                if team_name not in hardcoded_teams:
                    continue
                    
                team_guids = hardcoded_teams[team_name]["guids"]
                team_guids_placeholders = ",".join("?" * len(team_guids))

                # Get MVP by kills
                query = f"""
                    SELECT player_name, SUM(kills) as total_kills, player_guid
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                        AND player_guid IN ({team_guids_placeholders})
                    GROUP BY player_name, player_guid
                    ORDER BY total_kills DESC
                    LIMIT 1
                """
                params = session_ids + team_guids
                async with db.execute(query, params) as cursor:
                    result = await cursor.fetchone()
                    
                if result:
                    player_name, kills, guid = result
                    
                    # Get detailed stats for MVP
                    detail_query = f"""
                        SELECT
                            CASE
                                WHEN SUM(time_played_seconds) > 0
                                THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            SUM(deaths),
                            SUM(revives_given),
                            SUM(gibs)
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                            AND player_name = ?
                            AND player_guid IN ({team_guids_placeholders})
                    """
                    detail_params = session_ids + [player_name] + team_guids
                    async with db.execute(detail_query, detail_params) as cursor:
                        detail_result = await cursor.fetchone()
                        
                    if detail_result:
                        mvp_stats = (player_name, kills, detail_result[0], detail_result[1], detail_result[2], detail_result[3])
                        if team_name == team_1_name:
                            team_1_mvp_stats = mvp_stats
                        else:
                            team_2_mvp_stats = mvp_stats

        return team_1_mvp_stats, team_2_mvp_stats

    # ═══════════════════════════════════════════════════════
    # PHASE 4: EMBED BUILDERS
    # ═══════════════════════════════════════════════════════

    async def _build_session_overview_embed(
        self,
        latest_date: str,
        all_players: List,
        maps_played: str,
        rounds_played: int,
        player_count: int,
        team_1_name: str,
        team_2_name: str,
        team_1_score: int,
        team_2_score: int,
        hardcoded_teams: bool,
        scoring_result: Optional[Dict] = None
    ) -> discord.Embed:
        """Build main session overview embed with all players and match score."""
        # Build description with match score
        desc = f"**{player_count} players** • **{rounds_played} rounds** • **Maps**: {maps_played}"
        if hardcoded_teams and team_1_score + team_2_score > 0:
            if team_1_score == team_2_score:
                desc += f"\n\n🤝 **Match Result: {team_1_score} - {team_2_score} (PERFECT TIE)**"
            else:
                desc += f"\n\n🏆 **Match Result: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}**"
            
            # Add map-by-map breakdown if available
            if scoring_result and 'maps' in scoring_result:
                desc += "\n\n**📊 Map Breakdown:**"
                for map_result in scoring_result['maps']:
                    map_name = map_result['map']
                    t1_pts = map_result['team1_points']
                    t2_pts = map_result['team2_points']
                    
                    # Show winner emoji
                    if t1_pts > t2_pts:
                        winner_emoji = "🟢"
                    elif t2_pts > t1_pts:
                        winner_emoji = "🔴"
                    else:
                        winner_emoji = "🟡"
                    
                    desc += f"\n{winner_emoji} `{map_name}`: {t1_pts}-{t2_pts}"

        embed = discord.Embed(
            title=f"📊 Session Summary: {latest_date}",
            description=desc,
            color=0x5865F2,
            timestamp=datetime.now()
        )

        # Build player summary - split into multiple fields to avoid 1024 char limit
        medals = ["🥇", "🥈", "🥉", "❌"]
        players_per_field = 3  # 3 players per field to stay under 1024 chars
        
        for field_idx in range(0, len(all_players), players_per_field):
            field_text = ""
            field_players = all_players[field_idx:field_idx + players_per_field]
            
            for i, player in enumerate(field_players):
                global_idx = field_idx + i
                name, kills, deaths, dpm, hits, shots = player[0:6]
                total_hs, hsk, total_seconds, total_time_dead, total_denied = player[6:11]

                # Handle NULL values
                kills = kills or 0
                deaths = deaths or 0
                dpm = dpm or 0
                hits = hits or 0
                shots = shots or 0
                total_hs = total_hs or 0
                total_seconds = total_seconds or 0
                total_time_dead = total_time_dead or 0
                total_denied = total_denied or 0

                # Calculate metrics
                kd_ratio = kills / deaths if deaths > 0 else kills
                acc = (hits / shots * 100) if shots and shots > 0 else 0
                hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0

                # Format times
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                time_display = f"{minutes}:{seconds:02d}"

                dead_minutes = int(total_time_dead // 60)
                dead_seconds = int(total_time_dead % 60)
                time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

                denied_minutes = int(total_denied // 60)
                denied_seconds = int(total_denied % 60)
                time_denied_display = f"{denied_minutes}:{denied_seconds:02d}"

                # 3-line format matching original screenshot
                medal = medals[global_idx] if global_idx < len(medals) else "🔹"
                field_text += f"{medal} **{name}**\n"
                field_text += f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • `{dpm:.0f} DPM` • `{acc:.1f}% ACC ({hits}/{shots})`\n"
                field_text += f"`{total_hs} HS ({hs_rate:.1f}%)` • ⏱️ `{time_display}` • 💀 `{time_dead_display}` • ⏳ `{time_denied_display}`\n"
            
            # Add field with appropriate name
            if field_idx == 0:
                field_name = "🏆 All Players"
            else:
                field_name = "\u200b"  # Invisible character for continuation fields
            
            embed.add_field(name=field_name, value=field_text.rstrip(), inline=False)
        embed.set_footer(text=f"Session: {latest_date}")
        return embed

    async def _build_team_analytics_embed(
        self,
        latest_date: str,
        team_1_name: str,
        team_2_name: str,
        team_stats: List,
        team_1_mvp_stats: Optional[tuple],
        team_2_mvp_stats: Optional[tuple],
        team_1_score: int,
        team_2_score: int,
        hardcoded_teams: bool
    ) -> discord.Embed:
        """Build team analytics embed with stats and MVPs."""
        analytics_desc = "Comprehensive team performance comparison"
        if hardcoded_teams and team_1_score + team_2_score > 0:
            if team_1_score == team_2_score:
                analytics_desc += f"\n\n🤝 **Maps Won: {team_1_score} - {team_2_score} (PERFECT TIE)**"
            else:
                analytics_desc += f"\n\n🏆 **Maps Won: {team_1_score} - {team_2_score}**"

        embed = discord.Embed(
            title=f"⚔️ Team Analytics - {team_1_name} vs {team_2_name}",
            description=analytics_desc,
            color=0xED4245,
            timestamp=datetime.now()
        )

        # Team stats - separate fields for each team
        if len(team_stats) > 1:
            for team, kills, deaths, damage in team_stats:
                if team == 1:
                    current_team_name = team_1_name
                    emoji = "🔴"
                elif team == 2:
                    current_team_name = team_2_name
                    emoji = "🔵"
                else:
                    continue

                kd_ratio = kills / deaths if deaths > 0 else kills
                team_text = (
                    f"**Total Kills:** `{kills:,}`\n"
                    f"**Total Deaths:** `{deaths:,}`\n"
                    f"**K/D Ratio:** `{kd_ratio:.2f}`\n"
                    f"**Total Damage:** `{damage:,}`\n"
                )
                embed.add_field(name=f"{emoji} {current_team_name} Team Stats", value=team_text, inline=True)

        # Team MVPs
        if team_1_mvp_stats:
            player, kills, dpm, deaths, revives, gibs = team_1_mvp_stats
            kd = kills / deaths if deaths else kills
            team_1_mvp_text = (
                f"**{player}**\n"
                f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                f"💥 `{dpm:.0f} DPM`\n"
                f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
            )
            embed.add_field(name=f"🔴 {team_1_name} MVP", value=team_1_mvp_text, inline=True)

        if team_2_mvp_stats:
            player, kills, dpm, deaths, revives, gibs = team_2_mvp_stats
            kd = kills / deaths if deaths else kills
            team_2_mvp_text = (
                f"**{player}**\n"
                f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                f"💥 `{dpm:.0f} DPM`\n"
                f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
            )
            embed.add_field(name=f"🔵 {team_2_name} MVP", value=team_2_mvp_text, inline=True)

        embed.set_footer(text=f"Session: {latest_date}")
        return embed

    async def _build_team_composition_embed(
        self,
        latest_date: str,
        team_1_name: str,
        team_2_name: str,
        team_1_players_list: List,
        team_2_players_list: List,
        total_rounds: int,
        total_maps: int,
        unique_maps: int,
        team_1_score: int,
        team_2_score: int,
        hardcoded_teams: bool
    ) -> discord.Embed:
        """Build team composition embed with rosters and session info."""
        embed = discord.Embed(
            title="👥 Team Composition",
            description=(
                f"Player roster for {team_1_name} vs {team_2_name}\n"
                f"🔄 indicates players who swapped teams during session"
            ),
            color=0x57F287,
            timestamp=datetime.now()
        )

        # Team 1 roster
        if team_1_players_list:
            team_1_text = f"**{len(team_1_players_list)} players**\n\n"
            for i, player in enumerate(team_1_players_list[:15], 1):
                team_1_text += f"{i}. {player}\n"
            if len(team_1_players_list) > 15:
                more_count = len(team_1_players_list) - 15
                team_1_text += f"\n*...and {more_count} more*"
            embed.add_field(name=f"🔴 {team_1_name} Roster", value=team_1_text.rstrip(), inline=True)

        # Team 2 roster
        if team_2_players_list:
            team_2_text = f"**{len(team_2_players_list)} players**\n\n"
            for i, player in enumerate(team_2_players_list[:15], 1):
                team_2_text += f"{i}. {player}\n"
            if len(team_2_players_list) > 15:
                more_count = len(team_2_players_list) - 15
                team_2_text += f"\n*...and {more_count} more*"
            embed.add_field(name=f"🔵 {team_2_name} Roster", value=team_2_text.rstrip(), inline=True)

        # Session info with match score
        session_info = f"📍 **{total_rounds} rounds** played ({total_maps} maps)\n"
        session_info += "🎮 **Format**: Stopwatch (2 rounds per map)\n"
        session_info += f"🗺️ **Unique map names**: {unique_maps}\n"

        if hardcoded_teams and team_1_score + team_2_score > 0:
            if team_1_score == team_2_score:
                session_info += f"\n🤝 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name} (TIE)"
            else:
                session_info += f"\n🏆 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}"

        embed.add_field(name="📊 Session Info", value=session_info, inline=False)
        embed.set_footer(text=f"Session: {latest_date}")
        return embed

    async def _build_dpm_analytics_embed(
        self,
        latest_date: str,
        dpm_leaders: List
    ) -> discord.Embed:
        """Build DPM analytics embed with leaderboard and insights."""
        embed = discord.Embed(
            title="💥 DPM Analytics - Damage Per Minute",
            description="Enhanced DPM with Kill/Death Details",
            color=0xFEE75C,
            timestamp=datetime.now()
        )

        # DPM Leaderboard
        if dpm_leaders:
            dpm_text = ""
            for i, (player, dpm, kills, deaths) in enumerate(dpm_leaders[:10], 1):
                kd = kills / deaths if deaths else kills
                dpm_text += f"{i}. **{player}**\n"
                dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
            embed.add_field(name="🏆 Enhanced DPM Leaderboard", value=dpm_text.rstrip(), inline=False)

            # DPM Insights
            avg_dpm = sum(p[1] for p in dpm_leaders) / len(dpm_leaders)
            highest_dpm = dpm_leaders[0][1] if dpm_leaders else 0
            leader_name = dpm_leaders[0][0] if dpm_leaders else "N/A"

            insights = (
                f"📊 **Enhanced Session DPM Stats:**\n"
                f"• Average DPM: `{avg_dpm:.1f}`\n"
                f"• Highest DPM: `{highest_dpm:.0f}`\n"
                f"• DPM Leader: **{leader_name}**\n"
                f"• Formula: `(Total Damage × 60) / Time Played (seconds)`"
            )
            embed.add_field(name="💥 DPM Insights", value=insights, inline=False)

        embed.set_footer(text="💥 Enhanced with Kill/Death Details")
        return embed

    async def _build_weapon_mastery_embed(
        self,
        latest_date: str,
        player_weapons: List,
        player_revives_raw: List
    ) -> discord.Embed:
        """Build weapon mastery embed with per-player breakdown."""
        embed = discord.Embed(
            title="🔫 Weapon Mastery Breakdown",
            description="Top weapons and combat statistics",
            color=0x5865F2,
            timestamp=datetime.now()
        )

        # Group weapons by player
        player_weapon_map = {}
        for player, weapon, kills, hits, shots, hs in player_weapons:
            if player not in player_weapon_map:
                player_weapon_map[player] = []
            acc = (hits / shots * 100) if shots > 0 else 0
            hs_pct = (hs / hits * 100) if hits > 0 else 0
            weapon_clean = weapon.replace("WS_", "").replace("_", " ").title()
            player_weapon_map[player].append((weapon_clean, kills, acc, hs_pct, hs, hits, shots))

        # Convert revives data
        player_revives = {player: revives for player, revives in player_revives_raw}

        # Sort players by total kills
        player_totals = []
        for player, weapons in player_weapon_map.items():
            total_kills = sum(w[1] for w in weapons)
            player_totals.append((player, total_kills))
        player_totals.sort(key=lambda x: x[1], reverse=True)

        # Show all players and their weapons
        for player, total_kills in player_totals:
            weapons = player_weapon_map[player]
            revives = player_revives.get(player, 0)

            weapon_text = ""
            for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
                weapon_text += f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • `{hs} HS ({hs_pct:.1f}%)`\n"

            if revives > 0:
                weapon_text += f"\n💉 **Teammates Revived**: `{revives}`"

            embed.add_field(name=f"{player} ({total_kills} total kills)", value=weapon_text, inline=False)

        embed.set_footer(text=f"Session: {latest_date}")
        return embed

    async def _build_special_awards_embed(
        self,
        chaos_awards_data: List
    ) -> discord.Embed:
        """Build special awards embed with chaos stats."""
        embed = discord.Embed(
            title="🏆 SESSION SPECIAL AWARDS 🏆",
            description="*Celebrating excellence... and chaos!*",
            color=0xFFD700,  # Gold
            timestamp=datetime.now()
        )

        # Calculate awards
        awards = {
            "teamkill_king": {"player": None, "value": 0},
            "selfkill_master": {"player": None, "value": 0},
            "kill_thief": {"player": None, "value": 0},
            "spray_pray": {"player": None, "value": 0},
            "trigger_shy": {"player": None, "value": 999999},
            "damage_king": {"player": None, "value": 0},
            "glass_cannon": {"player": None, "value": 0},
            "engineer": {"player": None, "value": 0},
            "tank_shield": {"player": None, "value": 0},
            "respawn_king": {"player": None, "value": 0},
            "useless_king": {"player": None, "value": 0},
            "death_magnet": {"player": None, "value": 0},
            "worst_spree": {"player": None, "value": 0},
        }

        for row in chaos_awards_data:
            name = row[0]
            teamkills, selfkills, steals, bullets = row[1:5]
            kills, deaths, dmg_given, dmg_received = row[5:9]
            constructions, tank, useless = row[9:12]
            worst_spree, play_time = row[12:14]

            # Teamkill King
            if teamkills > awards["teamkill_king"]["value"]:
                awards["teamkill_king"] = {"player": name, "value": teamkills}

            # Self-Kill Master
            if selfkills > awards["selfkill_master"]["value"]:
                awards["selfkill_master"] = {"player": name, "value": selfkills}

            # Kill Thief
            if steals > awards["kill_thief"]["value"]:
                awards["kill_thief"] = {"player": name, "value": steals}

            # Spray & Pray
            if kills > 0 and bullets:
                bpk = bullets / kills
                if bpk > awards["spray_pray"]["value"]:
                    awards["spray_pray"] = {"player": name, "value": bpk}

            # Too Scared to Shoot
            if (kills >= 5 and bullets and
                    bullets < awards["trigger_shy"]["value"]):
                awards["trigger_shy"] = {"player": name, "value": bullets}

            # Damage Efficiency King
            if dmg_received > 0:
                eff = dmg_given / dmg_received
                if eff > awards["damage_king"]["value"]:
                    awards["damage_king"] = {"player": name, "value": eff}

            # Glass Cannon
            if dmg_received > awards["glass_cannon"]["value"]:
                awards["glass_cannon"] = {"player": name, "value": dmg_received}

            # Chief Engineer
            if constructions > awards["engineer"]["value"]:
                awards["engineer"] = {"player": name, "value": constructions}

            # Tank Shield
            if tank > awards["tank_shield"]["value"]:
                awards["tank_shield"] = {"player": name, "value": tank}

            # Respawn King
            if deaths > awards["respawn_king"]["value"]:
                awards["respawn_king"] = {"player": name, "value": deaths}

            # Most Useless Kills
            if useless > awards["useless_king"]["value"]:
                awards["useless_king"] = {"player": name, "value": useless}

            # Death Magnet
            if deaths > awards["death_magnet"]["value"]:
                awards["death_magnet"] = {"player": name, "value": deaths}

            # Worst Death Spree
            if worst_spree > awards["worst_spree"]["value"]:
                awards["worst_spree"] = {"player": name, "value": worst_spree}

        # Build awards text
        awards_text = []

        # Positive awards
        if awards["damage_king"]["value"] > 1.5:
            player = awards["damage_king"]["player"]
            ratio = awards["damage_king"]["value"]
            awards_text.append(f"💥 **Damage Efficiency King:** `{player}` ({ratio:.2f}x ratio)")

        if awards["engineer"]["value"] >= 1:
            player = awards["engineer"]["player"]
            count = int(awards["engineer"]["value"])
            awards_text.append(f"🔧 **Chief Engineer:** `{player}` ({count} repairs)")

        if awards["tank_shield"]["value"] >= 50:
            player = awards["tank_shield"]["player"]
            count = int(awards["tank_shield"]["value"])
            awards_text.append(f"🛡️ **Tank Shield:** `{player}` ({count} damage absorbed)")

        # Chaos awards
        if awards["teamkill_king"]["value"] >= 3:
            player = awards["teamkill_king"]["player"]
            count = int(awards["teamkill_king"]["value"])
            awards_text.append(f"🔴 **Teamkill King:** `{player}` ({count} teamkills)")

        if awards["selfkill_master"]["value"] >= 2:
            player = awards["selfkill_master"]["player"]
            count = int(awards["selfkill_master"]["value"])
            awards_text.append(f"💣 **Self-Destruct Master:** `{player}` ({count} self-kills)")

        if awards["kill_thief"]["value"] >= 5:
            player = awards["kill_thief"]["player"]
            count = int(awards["kill_thief"]["value"])
            awards_text.append(f"🦹 **Kill Thief:** `{player}` ({count} stolen kills)")

        if awards["spray_pray"]["value"] >= 50:
            player = awards["spray_pray"]["player"]
            bpk = awards["spray_pray"]["value"]
            awards_text.append(f"🔫 **Spray & Pray Champion:** `{player}` ({bpk:.0f} bullets/kill)")

        if awards["trigger_shy"]["value"] < 999999:
            player = awards["trigger_shy"]["player"]
            bullets = int(awards["trigger_shy"]["value"])
            awards_text.append(f"🎯 **Too Scared to Shoot:** `{player}` ({bullets} bullets total)")

        if awards["glass_cannon"]["value"] >= 1000:
            player = awards["glass_cannon"]["player"]
            dmg = int(awards["glass_cannon"]["value"])
            awards_text.append(f"🥊 **Glass Cannon:** `{player}` ({dmg:,} damage taken)")

        if awards["useless_king"]["value"] >= 3:
            player = awards["useless_king"]["player"]
            count = int(awards["useless_king"]["value"])
            awards_text.append(f"🤡 **Most Useless Kills:** `{player}` ({count} useless)")

        if awards["worst_spree"]["value"] >= 5:
            player = awards["worst_spree"]["player"]
            count = int(awards["worst_spree"]["value"])
            awards_text.append(f"💀 **Worst Death Spree:** `{player}` ({count} consecutive deaths)")

        if awards_text:
            embed.add_field(name="🎖️ Special Awards", value="\n".join(awards_text), inline=False)
        else:
            embed.add_field(name="🎖️ Special Awards", value="*No notable achievements this session*", inline=False)

        embed.set_footer(text="🏆 Excellence, Efficiency, and Chaos!")
        return embed

    # ═══════════════════════════════════════════════════════
    # PHASE 5: GRAPH GENERATION
    # ═══════════════════════════════════════════════════════

    async def _generate_performance_graphs(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str,
        db
    ) -> Optional[io.BytesIO]:
        """Generate 6-panel performance graph (kills, deaths, DPM, time played, time dead, time denied)."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io

            # Get all players data (limit to top 10 for readability)
            query = f"""
                SELECT p.player_name,
                    SUM(p.kills) as kills,
                    SUM(p.deaths) as deaths,
                    CASE
                        WHEN SUM(p.time_played_seconds) > 0
                        THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                        ELSE 0
                    END as dpm,
                    SUM(p.time_played_seconds) as time_played,
                    CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as time_dead,
                    SUM(p.denied_playtime) as denied
                FROM player_comprehensive_stats p
                WHERE p.session_id IN ({session_ids_str})
                GROUP BY p.player_name
                ORDER BY kills DESC
                LIMIT 10
            """
            async with db.execute(query, session_ids) as cursor:
                top_players = await cursor.fetchall()

            if not top_players:
                return None

            player_names = [p[0] for p in top_players]
            kills = [p[1] or 0 for p in top_players]
            deaths = [p[2] or 0 for p in top_players]
            dpm = [p[3] or 0 for p in top_players]
            time_played = [p[4] / 60 if p[4] else 0 for p in top_players]
            time_dead = [p[5] / 60 if p[5] else 0 for p in top_players]
            denied = [p[6] or 0 for p in top_players]

            # Create 2x3 grid
            fig, axes = plt.subplots(2, 3, figsize=(18, 10))
            fig.patch.set_facecolor('#2b2d31')
            fig.suptitle(f"Visual Performance Analytics - {latest_date}", fontsize=16, fontweight="bold", color='white')

            # Graph 1: Kills
            axes[0, 0].bar(range(len(player_names)), kills, color="#57F287")
            axes[0, 0].set_title("Kills", fontweight="bold", color='white')
            axes[0, 0].set_xticks(range(len(player_names)))
            axes[0, 0].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[0, 0].set_facecolor('#1e1f22')
            axes[0, 0].tick_params(colors='white')
            axes[0, 0].spines['bottom'].set_color('white')
            axes[0, 0].spines['left'].set_color('white')
            axes[0, 0].spines['top'].set_visible(False)
            axes[0, 0].spines['right'].set_visible(False)
            axes[0, 0].grid(True, alpha=0.2, color='white', axis='y')

            # Graph 2: Deaths
            axes[0, 1].bar(range(len(player_names)), deaths, color="#ED4245")
            axes[0, 1].set_title("Deaths", fontweight="bold", color='white')
            axes[0, 1].set_xticks(range(len(player_names)))
            axes[0, 1].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[0, 1].set_facecolor('#1e1f22')
            axes[0, 1].tick_params(colors='white')
            axes[0, 1].spines['bottom'].set_color('white')
            axes[0, 1].spines['left'].set_color('white')
            axes[0, 1].spines['top'].set_visible(False)
            axes[0, 1].spines['right'].set_visible(False)
            axes[0, 1].grid(True, alpha=0.2, color='white', axis='y')

            # Graph 3: DPM
            axes[0, 2].bar(range(len(player_names)), dpm, color="#FEE75C")
            axes[0, 2].set_title("DPM (Damage Per Minute)", fontweight="bold", color='white')
            axes[0, 2].set_xticks(range(len(player_names)))
            axes[0, 2].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[0, 2].set_facecolor('#1e1f22')
            axes[0, 2].tick_params(colors='white')
            axes[0, 2].spines['bottom'].set_color('white')
            axes[0, 2].spines['left'].set_color('white')
            axes[0, 2].spines['top'].set_visible(False)
            axes[0, 2].spines['right'].set_visible(False)
            axes[0, 2].grid(True, alpha=0.2, color='white', axis='y')

            # Graph 4: Time Played
            axes[1, 0].bar(range(len(player_names)), time_played, color="#5865F2")
            axes[1, 0].set_title("Time Played (minutes)", fontweight="bold", color='white')
            axes[1, 0].set_xticks(range(len(player_names)))
            axes[1, 0].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[1, 0].set_facecolor('#1e1f22')
            axes[1, 0].tick_params(colors='white')
            axes[1, 0].spines['bottom'].set_color('white')
            axes[1, 0].spines['left'].set_color('white')
            axes[1, 0].spines['top'].set_visible(False)
            axes[1, 0].spines['right'].set_visible(False)
            axes[1, 0].grid(True, alpha=0.2, color='white', axis='y')

            # Graph 5: Time Dead
            axes[1, 1].bar(range(len(player_names)), time_dead, color="#EB459E")
            axes[1, 1].set_title("Time Dead (minutes)", fontweight="bold", color='white')
            axes[1, 1].set_xticks(range(len(player_names)))
            axes[1, 1].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[1, 1].set_facecolor('#1e1f22')
            axes[1, 1].tick_params(colors='white')
            axes[1, 1].spines['bottom'].set_color('white')
            axes[1, 1].spines['left'].set_color('white')
            axes[1, 1].spines['top'].set_visible(False)
            axes[1, 1].spines['right'].set_visible(False)
            axes[1, 1].grid(True, alpha=0.2, color='white', axis='y')

            # Graph 6: Time Denied
            axes[1, 2].bar(range(len(player_names)), denied, color="#9B59B6")
            axes[1, 2].set_title("Time Denied (seconds)", fontweight="bold", color='white')
            axes[1, 2].set_xticks(range(len(player_names)))
            axes[1, 2].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[1, 2].set_facecolor('#1e1f22')
            axes[1, 2].tick_params(colors='white')
            axes[1, 2].spines['bottom'].set_color('white')
            axes[1, 2].spines['left'].set_color('white')
            axes[1, 2].spines['top'].set_visible(False)
            axes[1, 2].spines['right'].set_visible(False)
            axes[1, 2].grid(True, alpha=0.2, color='white', axis='y')

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", facecolor='#2b2d31', dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close()

            return buf

        except ImportError:
            logger.warning("matplotlib not installed - graphs unavailable")
            return None
        except Exception as e:
            logger.exception(f"Error generating performance graphs: {e}")
            return None

    async def _generate_combat_efficiency_graphs(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str,
        db
    ) -> Optional[io.BytesIO]:
        """Generate 4-panel combat efficiency graph (damage given/received, ratio, bullets, bullets per kill)."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io

            # Get efficiency data for all players (limit to top 10 for readability)
            query = f"""
                SELECT p.player_name,
                    SUM(p.damage_given) as dmg_given,
                    SUM(p.damage_received) as dmg_received,
                    SUM(w.shots) as bullets,
                    SUM(p.kills) as kills
                FROM player_comprehensive_stats p
                LEFT JOIN (
                    SELECT session_id, player_guid, SUM(shots) as shots
                    FROM weapon_comprehensive_stats
                    WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                    GROUP BY session_id, player_guid
                ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                WHERE p.session_id IN ({session_ids_str})
                GROUP BY p.player_name
                ORDER BY dmg_given DESC
                LIMIT 10
            """
            async with db.execute(query, session_ids) as cursor:
                efficiency_players = await cursor.fetchall()

            if not efficiency_players:
                return None

            eff_names = [row[0] for row in efficiency_players]
            eff_dmg_given = [row[1] or 0 for row in efficiency_players]
            eff_dmg_received = [row[2] or 0 for row in efficiency_players]
            eff_bullets = [row[3] or 0 for row in efficiency_players]
            eff_kills = [row[4] or 0 for row in efficiency_players]

            # Calculate ratios
            eff_damage_ratio = [(g / r) if r > 0 else g for g, r in zip(eff_dmg_given, eff_dmg_received)]
            eff_bullets_per_kill = [(b / k) if k > 0 else 0 for b, k in zip(eff_bullets, eff_kills)]

            # Create 2x2 grid
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 10))
            fig.patch.set_facecolor('#2b2d31')
            fig.suptitle(f"Combat Efficiency Analysis - {latest_date}", fontsize=16, fontweight="bold", color='white')

            x_eff = range(len(eff_names))
            width_eff = 0.35

            # Subplot 1: Damage Given vs Received
            ax1.bar([i - width_eff / 2 for i in x_eff], eff_dmg_given, width_eff, label="Damage Given", color="#5865f2", alpha=0.8)
            ax1.bar([i + width_eff / 2 for i in x_eff], eff_dmg_received, width_eff, label="Damage Received", color="#ed4245", alpha=0.8)
            ax1.set_xticks(x_eff)
            ax1.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax1.set_ylabel("Damage", color="white", fontsize=11)
            ax1.set_title("Damage Given vs Received", color="white", fontsize=12, fontweight="bold")
            ax1.set_facecolor("#1e1f22")
            ax1.tick_params(colors="white")
            ax1.spines["bottom"].set_color("white")
            ax1.spines["left"].set_color("white")
            ax1.spines["top"].set_visible(False)
            ax1.spines["right"].set_visible(False)
            ax1.grid(True, alpha=0.2, color="white", axis="y")
            ax1.legend(facecolor="#1e1f22", edgecolor="white", labelcolor="white", fontsize=9)

            # Subplot 2: Damage Efficiency Ratio
            colors_ratio = ["#57f287" if r > 1.5 else "#fee75c" if r > 1.0 else "#ed4245" for r in eff_damage_ratio]
            ax2.bar(x_eff, eff_damage_ratio, color=colors_ratio, alpha=0.8)
            ax2.axhline(y=1.0, color="white", linestyle="--", alpha=0.5, linewidth=1)
            ax2.set_xticks(x_eff)
            ax2.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax2.set_ylabel("Ratio (Given/Received)", color="white", fontsize=11)
            ax2.set_title("Damage Efficiency Ratio", color="white", fontsize=12, fontweight="bold")
            ax2.set_facecolor("#1e1f22")
            ax2.tick_params(colors="white")
            ax2.spines["bottom"].set_color("white")
            ax2.spines["left"].set_color("white")
            ax2.spines["top"].set_visible(False)
            ax2.spines["right"].set_visible(False)
            ax2.grid(True, alpha=0.2, color="white", axis="y")
            for i, v in enumerate(eff_damage_ratio):
                ax2.text(i, v, f"{v:.2f}x", ha="center", va="bottom", color="white", fontsize=8)

            # Subplot 3: Total Bullets Fired
            ax3.bar(x_eff, eff_bullets, color="#fee75c", alpha=0.8)
            ax3.set_xticks(x_eff)
            ax3.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax3.set_ylabel("Bullets Fired", color="white", fontsize=11)
            ax3.set_title("Total Ammunition Fired", color="white", fontsize=12, fontweight="bold")
            ax3.set_facecolor("#1e1f22")
            ax3.tick_params(colors="white")
            ax3.spines["bottom"].set_color("white")
            ax3.spines["left"].set_color("white")
            ax3.spines["top"].set_visible(False)
            ax3.spines["right"].set_visible(False)
            ax3.grid(True, alpha=0.2, color="white", axis="y")
            for i, v in enumerate(eff_bullets):
                ax3.text(i, v, f"{int(v):,}", ha="center", va="bottom", color="white", fontsize=8)

            # Subplot 4: Bullets per Kill
            colors_bpk = ["#57f287" if b < 100 else "#fee75c" if b < 200 else "#ed4245" for b in eff_bullets_per_kill]
            ax4.bar(x_eff, eff_bullets_per_kill, color=colors_bpk, alpha=0.8)
            ax4.set_xticks(x_eff)
            ax4.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax4.set_ylabel("Bullets per Kill", color="white", fontsize=11)
            ax4.set_title("Accuracy Metric (Lower = Better)", color="white", fontsize=12, fontweight="bold")
            ax4.set_facecolor("#1e1f22")
            ax4.tick_params(colors="white")
            ax4.spines["bottom"].set_color("white")
            ax4.spines["left"].set_color("white")
            ax4.spines["top"].set_visible(False)
            ax4.spines["right"].set_visible(False)
            ax4.grid(True, alpha=0.2, color="white", axis="y")
            for i, v in enumerate(eff_bullets_per_kill):
                ax4.text(i, v, f"{v:.0f}", ha="center", va="bottom", color="white", fontsize=8)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", facecolor='#2b2d31', dpi=100, bbox_inches="tight")
            buf.seek(0)
            plt.close()

            return buf

        except ImportError:
            logger.warning("matplotlib not installed - graphs unavailable")
            return None
        except Exception as e:
            logger.exception(f"Error generating combat efficiency graphs: {e}")
            return None

    # ═══════════════════════════════════════════════════════
    # MAIN COMMAND - Orchestrates everything
    # ═══════════════════════════════════════════════════════

    @commands.command(name="last_session", aliases=["last", "latest", "recent"])
    async def last_session(self, ctx, subcommand: str = None):
        """🎮 Show the most recent session/match

        Displays detailed stats for the latest played session (full day).
        A session = one day of gaming with all maps/rounds.

        Subcommands:
        - !last_session          → Clean view with essential stats
        - !last_session top      → Top 10 players
        - !last_session combat   → Combat stats
        - !last_session obj      → Objectives & support
        - !last_session weapons  → Weapon mastery
        - !last_session support  → Support activity
        - !last_session sprees   → Killing sprees
        - !last_session maps     → Per-map summaries (popular stats)
        - !last_session maps full → Round-by-round breakdown
        - !last_session graphs   → Performance graphs
        """
        try:
            # Send help hint
            try:
                await self._send_last_session_help(ctx)
            except Exception:
                pass

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Setup database aliases and diagnostics
                try:
                    await self._ensure_player_name_alias(db)
                    await self._enable_sql_diag(db)
                except Exception:
                    pass

                # Phase 1: Get session data
                latest_date = await self._get_latest_session_date(db)
                if not latest_date:
                    await ctx.send("❌ No sessions found in database")
                    return

                sessions, session_ids, session_ids_str, player_count = await self._fetch_session_data(
                    db, latest_date
                )
                if not sessions:
                    await ctx.send("❌ No sessions found for latest date")
                    return

                # Calculate total maps for top view
                total_maps = len(sessions) // 2

                # Route to appropriate view based on subcommand
                if subcommand and subcommand.lower() in ("obj", "objectives"):
                    await self._show_objectives_view(ctx, db, latest_date, session_ids, session_ids_str, player_count)
                    return

                if subcommand and subcommand.lower() in ("combat",):
                    await self._show_combat_view(ctx, db, latest_date, session_ids, session_ids_str, player_count)
                    return

                if subcommand and subcommand.lower() in ("weapons", "weapon", "weap"):
                    await self._show_weapons_view(ctx, db, latest_date, session_ids, session_ids_str, player_count)
                    return

                if subcommand and subcommand.lower() in ("support",):
                    await self._show_support_view(ctx, db, latest_date, session_ids, session_ids_str, player_count)
                    return

                if subcommand and subcommand.lower() in ("sprees", "spree"):
                    await self._show_sprees_view(ctx, db, latest_date, session_ids, session_ids_str, player_count)
                    return

                if subcommand and subcommand.lower() in ("top", "top10"):
                    await self._show_top_view(ctx, db, latest_date, session_ids, session_ids_str, player_count, total_maps)
                    return

                # NEW: Maps view routing
                if subcommand and subcommand.lower() == "maps":
                    # Check for "full" subcommand
                    parts = ctx.message.content.split()
                    if len(parts) > 2 and parts[2].lower() == "full":
                        await self._show_maps_full_view(ctx, db, latest_date, sessions, session_ids, session_ids_str, player_count)
                    else:
                        await self._show_maps_view(ctx, db, latest_date, sessions, session_ids, session_ids_str, player_count)
                    return

                # ═══════════════════════════════════════════════════════════════════════
                # DEFAULT COMPREHENSIVE VIEW - Full session analytics
                # ═══════════════════════════════════════════════════════════════════════

                # Phase 3: Get hardcoded teams and team scores
                hardcoded_teams = await self._get_hardcoded_teams(db, session_ids)
                team_1_name, team_2_name, team_1_score, team_2_score, scoring_result = await self._calculate_team_scores(session_ids)

                # Get team mappings FIRST (needed for proper team stats aggregation)
                team_1_name_mapped, team_2_name_mapped, team_1_players_list, team_2_players_list, name_to_team = await self._build_team_mappings(
                    db, session_ids, session_ids_str, hardcoded_teams
                )
                
                # Use mapped team names if available
                if team_1_name_mapped and team_2_name_mapped:
                    team_1_name = team_1_name_mapped
                    team_2_name = team_2_name_mapped

                # Phase 3: Aggregate all data (now with correct team mappings)
                all_players = await self._aggregate_all_player_stats(db, session_ids, session_ids_str)
                team_stats = await self._aggregate_team_stats(db, session_ids, session_ids_str, hardcoded_teams, name_to_team)
                player_weapons = await self._aggregate_weapon_stats(db, session_ids, session_ids_str)
                dpm_leaders = await self._get_dpm_leaderboard(db, session_ids, session_ids_str, limit=10)
                
                team_1_mvp_stats, team_2_mvp_stats = await self._get_team_mvps(
                    db, session_ids, session_ids_str, hardcoded_teams, team_1_name, team_2_name
                )

                # Get player revives for weapon mastery embed
                query = f"""
                    SELECT player_name, SUM(revives_given) as total_revives
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_guid
                """
                async with db.execute(query, session_ids) as cursor:
                    player_revives_raw = await cursor.fetchall()

                # Get chaos awards data
                query = f"""
                    SELECT player_name,
                        SUM(team_kills) as teamkills,
                        SUM(self_kills) as selfkills,
                        SUM(kill_assists) as steals,
                        SUM(w.shots) as bullets,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        SUM(p.damage_given) as dmg_given,
                        SUM(p.damage_received) as dmg_received,
                        SUM(p.constructions) as constructions,
                        SUM(p.tank_meatshield) as tank,
                        SUM(p.useless_kills) as useless,
                        MAX(p.death_spree_worst) as worst_spree,
                        SUM(p.time_played_seconds) as play_time
                    FROM player_comprehensive_stats p
                    LEFT JOIN (
                        SELECT session_id, player_guid, SUM(shots) as shots
                        FROM weapon_comprehensive_stats
                        WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                        GROUP BY session_id, player_guid
                    ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                    WHERE p.session_id IN ({session_ids_str})
                    GROUP BY p.player_guid
                """
                async with db.execute(query, session_ids) as cursor:
                    chaos_awards_data = await cursor.fetchall()

                # Calculate maps info
                rounds_played = len(sessions)
                total_rounds = rounds_played
                unique_maps = len(set(s[1] for s in sessions))
                
                # Build maps played string
                map_play_counts = {}
                for session_id, map_name, round_num, actual_time in sessions:
                    if round_num == 2:
                        map_play_counts[map_name] = map_play_counts.get(map_name, 0) + 1
                
                maps_played = ", ".join(f"{name} (x{count})" for name, count in map_play_counts.items())

                # ═══════════════════════════════════════════════════════════════════════
                # BUILD AND SEND EMBEDS
                # ═══════════════════════════════════════════════════════════════════════

                # Embed 1: Session Overview
                embed1 = await self._build_session_overview_embed(
                    latest_date, all_players, maps_played, rounds_played, player_count,
                    team_1_name, team_2_name, team_1_score, team_2_score, hardcoded_teams is not None,
                    scoring_result
                )
                await ctx.send(embed=embed1)
                await asyncio.sleep(2)

                # Embed 2: Team Analytics
                embed2 = await self._build_team_analytics_embed(
                    latest_date, team_1_name, team_2_name, team_stats,
                    team_1_mvp_stats, team_2_mvp_stats, team_1_score, team_2_score,
                    hardcoded_teams is not None
                )
                await ctx.send(embed=embed2)
                await asyncio.sleep(4)

                # Embed 3: Team Composition
                embed3 = await self._build_team_composition_embed(
                    latest_date, team_1_name, team_2_name, team_1_players_list, team_2_players_list,
                    total_rounds, total_maps, unique_maps, team_1_score, team_2_score,
                    hardcoded_teams is not None
                )
                await ctx.send(embed=embed3)
                await asyncio.sleep(8)

                # Embed 4: DPM Analytics
                embed4 = await self._build_dpm_analytics_embed(latest_date, dpm_leaders)
                await ctx.send(embed=embed4)
                await asyncio.sleep(16)

                # Embed 5: Weapon Mastery
                if player_weapons:
                    embed5 = await self._build_weapon_mastery_embed(
                        latest_date, player_weapons, player_revives_raw
                    )
                    await ctx.send(embed=embed5)
                    await asyncio.sleep(2)

                # Embed 6: Special Awards
                if chaos_awards_data:
                    embed6 = await self._build_special_awards_embed(chaos_awards_data)
                    await ctx.send(embed=embed6)
                    await asyncio.sleep(2)

                # ═══════════════════════════════════════════════════════════════════════
                # GENERATE AND SEND GRAPHS (if not subcommand-specific)
                # ═══════════════════════════════════════════════════════════════════════

                if not subcommand or subcommand.lower() in ("full", "graphs"):
                    # Graph 1: Performance Analytics (6-panel)
                    buf1 = await self._generate_performance_graphs(
                        latest_date, session_ids, session_ids_str, db
                    )
                    if buf1:
                        file1 = discord.File(buf1, filename="performance_analytics.png")
                        await ctx.send("📊 **Visual Performance Analytics**", file=file1)
                        await asyncio.sleep(2)

                    # Graph 2: Combat Efficiency (4-panel)
                    buf2 = await self._generate_combat_efficiency_graphs(
                        latest_date, session_ids, session_ids_str, db
                    )
                    if buf2:
                        file2 = discord.File(buf2, filename="combat_efficiency.png")
                        await ctx.send("📊 **Combat Efficiency & Bullets Analysis**", file=file2)
                        await asyncio.sleep(2)

                # Show helpful message about additional options
                if not subcommand:
                    help_embed = discord.Embed(
                        title="💡 Want More Details?",
                        description=(
                            "**Available Options:**\n"
                            "`!last_session graphs` - Visual analytics with performance graphs\n"
                            "`!last_session full` - Everything including advanced combat stats\n"
                            "`!last_session top` - Quick top 10 players view\n"
                            "`!last_session combat` - Combat stats only\n"
                            "`!last_session weapons` - Weapon mastery breakdown\n"
                            "`!last_session obj` - Objectives & support\n"
                            "`!last_session support` - Support activity\n"
                            "`!last_session sprees` - Killing sprees & multikills"
                        ),
                        color=0x5865F2,
                    )
                    await ctx.send(embed=help_embed)

        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving last session: {e}")

    @commands.command(name="team_history")
    async def team_history_command(self, ctx, days: int = 30):
        """
        Show team history and performance statistics.
        
        Usage: !team_history [days]
        Example: !team_history 60  (shows last 60 days)
        """
        try:
            from bot.core.team_history import TeamHistoryManager
            
            manager = TeamHistoryManager(self.bot.db_path)
            
            # Get recent lineups
            recent = manager.get_recent_lineups(days=days, min_sessions=1)
            
            if not recent:
                await ctx.send(f"❌ No team history found in the last {days} days.")
                return
            
            # Build embed
            embed = discord.Embed(
                title=f"📊 Team History - Last {days} Days",
                description=f"Found {len(recent)} unique lineup(s)",
                color=0x5865F2,
                timestamp=datetime.now()
            )
            
            # Show top lineups
            for i, lineup in enumerate(recent[:5], 1):
                total_games = lineup['total_wins'] + lineup['total_losses'] + lineup['total_ties']
                win_rate = (lineup['total_wins'] / total_games * 100) if total_games > 0 else 0
                
                field_text = (
                    f"**Sessions:** {lineup['total_sessions']}\n"
                    f"**Record:** {lineup['total_wins']}W - {lineup['total_losses']}L - {lineup['total_ties']}T\n"
                    f"**Win Rate:** {win_rate:.1f}%\n"
                    f"**Players:** {lineup['player_count']}\n"
                    f"**Active:** {lineup['first_seen']} to {lineup['last_seen']}"
                )
                
                embed.add_field(
                    name=f"#{i} - Lineup {lineup['id']}",
                    value=field_text,
                    inline=False
                )
            
            # Add best performers section
            best = manager.get_best_lineups(min_sessions=1, limit=3)
            if best:
                best_text = ""
                for lineup in best:
                    total = lineup['total_wins'] + lineup['total_losses'] + lineup['total_ties']
                    wr = (lineup['total_wins'] / total * 100) if total > 0 else 0
                    best_text += f"**Lineup {lineup['id']}:** {wr:.1f}% WR ({lineup['total_wins']}W-{lineup['total_losses']}L-{lineup['total_ties']}T)\n"
                
                embed.add_field(
                    name="🏆 Best Win Rates",
                    value=best_text.rstrip(),
                    inline=False
                )
            
            embed.set_footer(text="Use !team_history <days> to adjust time range")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in team_history command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving team history: {e}")


async def setup(bot):
    """Load the Last Session Cog"""
    await bot.add_cog(LastSessionCog(bot))
    logger.info("🎮 LastSessionCog loaded - !last_session with comprehensive analytics (26 helper methods)")
