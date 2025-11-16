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

    async def show_objectives_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show objectives & support stats only"""
        query = f"""
            SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused, times_revived,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                denied_playtime, most_useful_kills, useless_kills, gibs,
                killing_spree_best, death_spree_worst
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
        """
        awards_rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

        if not awards_rows:
            await ctx.send("❌ No objective/support data available for latest session")
            return

        # Also fetch revives GIVEN per player
        rev_query = f"""
            SELECT clean_name, SUM(revives_given) as revives_given
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
            GROUP BY clean_name
        """
        rev_rows = await self.db_adapter.fetch_all(rev_query, tuple(session_ids))
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
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
        """
        combat_rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

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

            embed.add_field(name="\u200b", value=player_text, inline=False)

        embed.set_footer(text=f"Round: {latest_date} • Use !last_round for full report")
        await ctx.send(embed=embed)

    async def show_weapons_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
        """Show weapon mastery stats only"""
        query = f"""
            SELECT p.player_name, w.weapon_name,
                SUM(w.kills) as weapon_kills,
                SUM(w.hits) as hits,
                SUM(w.shots) as shots,
                SUM(w.headshots) as headshots
            FROM weapon_comprehensive_stats w
            JOIN player_comprehensive_stats p
                ON w.round_id = p.round_id
                AND w.player_guid = p.player_guid
            WHERE w.round_id IN ({session_ids_str})
            GROUP BY p.player_name, w.weapon_name
            HAVING SUM(w.kills) > 0
            ORDER BY p.player_name, SUM(w.kills) DESC
        """
        pw_rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

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
        query = f"""
            SELECT p.player_name,
                SUM(p.revives_given) as revives_given,
                SUM(p.times_revived) as times_revived,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY revives_given DESC
        """
        sup_rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

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

        embed.set_footer(text=f"Round: {latest_date}")
        await ctx.send(embed=embed)

    async def show_sprees_view(self, ctx, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):
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
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY best_spree DESC, megas DESC
        """
        spree_rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

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
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
        """
        top_players = await self.db_adapter.fetch_all(query, tuple(session_ids))

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
        """Show popular stats per map (map summaries only)"""

        # Group sessions into matches (R1 + R2 pairs)
        # Don't group by map_name - this would combine duplicate maps!
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

            # Store this match
            if match_rounds:
                map_matches.append((current_map, match_rounds))

        # Count occurrences of each map for display
        map_counts = {}
        for map_name, _ in map_matches:
            map_counts[map_name] = map_counts.get(map_name, 0) + 1

        # Track which occurrence we're on for each map
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
                    SELECT round_id, player_guid, SUM(hits) as hits, SUM(shots) as shots
                    FROM weapon_comprehensive_stats
                    WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                    GROUP BY round_id, player_guid
                ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
                WHERE p.round_id IN ({map_ids_str})
                GROUP BY p.player_name
                ORDER BY kills DESC
            """
        
            players = await self.db_adapter.fetch_all(query, tuple(map_session_ids))
        
            if not players:
                continue
        
            # Build embed for this map
            embed = discord.Embed(
                title=f"🗺️ Map Stats: {display_map_name}",
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
        
            embed.set_footer(text=f"Round: {latest_date} • Use !last_session maps full for round-by-round")
            await ctx.send(embed=embed)
            await asyncio.sleep(3)  # 3 second delay between maps

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
                SELECT round_id, player_guid, SUM(hits) as hits, SUM(shots) as shots
                FROM weapon_comprehensive_stats
                WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                GROUP BY round_id, player_guid
            ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
            WHERE p.round_id IN ({round_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
        """
    
        players = await self.db_adapter.fetch_all(query, tuple(round_session_ids))
    
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
    
        embed.set_footer(text=f"Round: {latest_date}")
        await ctx.send(embed=embed)
