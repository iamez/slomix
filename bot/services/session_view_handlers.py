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
import io
import discord
import logging
from datetime import datetime
from typing import List

from bot.stats import StatsCalculator

logger = logging.getLogger("bot.services.session_view_handlers")


class SessionViewHandlers:
    """Service for handling different view modes"""

    def __init__(self, db_adapter, stats_calculator):
        """
        Initialize the view handlers

        Args:
            db_adapter: Database adapter for queries
            stats_calculator: StatsCalculator instance for calculations
        """
        self.db_adapter = db_adapter
        self.stats_calculator = stats_calculator

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
            SELECT clean_name, SUM(revives_given) as revives_given
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
            GROUP BY clean_name
        """
        rev_rows = await self.db_adapter.fetch_all(rev_query.format(session_ids_str=session_ids_str), tuple(session_ids))
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
        embed = discord.Embed(
            title=f"⏱️ Time Audit - {latest_date}",
            description=(
                "Units: time played/dead/denied are seconds (displayed MM:SS). "
                "Time dead comes from `time_dead_minutes` (Lua), time denied from `denied_playtime`."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )

        total_played = 0
        total_dead = 0
        total_denied = 0
        cap_hits = 0
        cap_seconds = 0

        # Limit rows to keep embed size manageable
        rows = rows[:15]

        lines = []
        for row in rows:
            name, _guid, tp, td_raw, td_cap, denied, avg_ratio, rounds = row
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

            diff = td_raw - td_cap
            if diff >= 5:
                cap_hits += 1
                cap_seconds += diff

            dead_pct = (td_cap / tp * 100) if tp > 0 else 0
            denied_pct = (denied / tp * 100) if tp > 0 else 0

            cap_note = f" ⚠️cap-{diff}s" if diff >= 5 else ""
            ratio_note = f" r{avg_ratio:.1f}%" if avg_ratio > 0 else ""

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
