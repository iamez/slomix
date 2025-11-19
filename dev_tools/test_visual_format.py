"""
Test the new visual format for round stats posting.
Simulates what the bot will post for the last round in the database.
"""
import asyncio
import aiosqlite
import discord
from discord.ext import commands
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Create a minimal bot instance
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

db_path = 'bot/etlegacy_production.db'

async def create_test_embed():
    """Create the embed exactly as the bot will post it"""
    
    # Get last round from database
    async with aiosqlite.connect(db_path) as db:
        # Get last round info
        cursor = await db.execute("""
            SELECT id, round_date, round_time, map_name, round_number, 
                   time_limit, actual_time, winner_team, round_outcome
            FROM rounds
            ORDER BY id DESC
            LIMIT 1
        """)
        round_info = await cursor.fetchone()
        
        if not round_info:
            print("❌ No rounds found in database")
            return
        
        round_id, round_date, round_time, map_name, round_num, time_limit, actual_time, winner_team, round_outcome = round_info
        
        print(f"📊 Creating embed for Round {round_id} - {map_name} (R{round_num})")
        print(f"   Date: {round_date} {round_time}")
        print(f"   Outcome: {round_outcome}")
        print()
        
        # Get player stats
        cursor = await db.execute("""
            SELECT 
                player_name, team, kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received, gibs, headshot_kills,
                accuracy, revives_given, times_revived, time_dead_minutes,
                efficiency, kd_ratio, time_played_minutes, dpm
            FROM player_comprehensive_stats
            WHERE round_id = ? AND round_number = ?
            ORDER BY kills DESC
        """, (round_id, round_num))
        
        rows = await cursor.fetchall()
        
        # Convert to dict format
        players = []
        for row in rows:
            players.append({
                'name': row[0],
                'team': row[1],
                'kills': row[2],
                'deaths': row[3],
                'damage_given': row[4],
                'damage_received': row[5],
                'team_damage_given': row[6],
                'team_damage_received': row[7],
                'gibs': row[8],
                'headshots': row[9],
                'accuracy': row[10],
                'revives': row[11],
                'times_revived': row[12],
                'time_dead': row[13],
                'efficiency': row[14],
                'kd_ratio': row[15],
                'time_played': row[16],
                'dpm': row[17]
            })
    
    print(f"✅ Found {len(players)} players\n")
    
    # Rank emoji/number helper
    def get_rank_display(rank):
        """Get rank emoji for top 3, numbers with emojis for 4+"""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        else:
            # Convert number to digit emojis
            num_str = str(rank)
            emoji_map = {
                '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
            }
            return ''.join(emoji_map.get(digit, digit) for digit in num_str)
    
    # Determine round type
    round_type = "Round 1" if round_num == 1 else "Round 2"
    
    # Build title - simple and clean
    title = f"🎮 {round_type} Complete - {map_name}"
    
    description_parts = []
    
    # Add time information
    if time_limit and actual_time and time_limit != 'Unknown' and actual_time != 'Unknown':
        description_parts.append(f"⏱️ **Time:** {actual_time} / {time_limit}")
    elif actual_time and actual_time != 'Unknown':
        description_parts.append(f"⏱️ **Duration:** {actual_time}")
    
    # Add round outcome
    outcome_line = ""
    if winner_team and str(winner_team) != 'Unknown':
        outcome_line = f"🏆 **Winner:** {winner_team}"
    if round_outcome:
        if outcome_line:
            outcome_line += f" ({round_outcome})"
        else:
            outcome_line = f"🏆 **Outcome:** {round_outcome}"
    
    if outcome_line:
        description_parts.append(outcome_line)
    
    # Determine embed color based on round type
    embed_color = discord.Color.blue() if round_num == 1 else discord.Color.red()
    
    # Create embed
    embed = discord.Embed(
        title=title,
        description="\n".join(description_parts),
        color=embed_color,
        timestamp=datetime.now()
    )
    
    # Add player stats in chunks
    players_sorted = sorted(players, key=lambda p: p.get('kills', 0), reverse=True)
    
    chunk_size = 5
    for i in range(0, len(players_sorted), chunk_size):
        chunk = players_sorted[i:i + chunk_size]
        field_name = f'📊 Players {i+1}-{min(i+chunk_size, len(players_sorted))}'
        
        player_lines = []
        for idx, player in enumerate(chunk):
            rank = i + idx + 1
            rank_display = get_rank_display(rank)
            
            name = player.get('name', 'Unknown')[:16]
            kills = player.get('kills', 0)
            deaths = player.get('deaths', 0)
            dmg = player.get('damage_given', 0)
            dpm = player.get('dpm', 0)
            acc = player.get('accuracy', 0)
            hs = player.get('headshots', 0)
            revives = player.get('revives', 0)
            got_revived = player.get('times_revived', 0)
            gibs = player.get('gibs', 0)
            team_dmg_given = player.get('team_damage_given', 0)
            time_dead = player.get('time_dead', 0)
            
            kd_str = f'{kills}/{deaths}'
            
            # Line 1: Rank + Name + Core stats (simplified)
            line1 = (
                f"{rank_display} **{name}** • K/D:`{kd_str}` "
                f"DMG:`{int(dmg):,}` DPM:`{int(dpm)}` "
                f"ACC:`{acc:.1f}%` HS:`{hs}`"
            )
            
            # Line 2: Support stats (simplified)
            line2 = (
                f"     ↳ Rev:`{revives}/{got_revived}` Gibs:`{gibs}` "
                f"TmDmg:`{int(team_dmg_given)}` Dead:`{time_dead:.1f}m`"
            )
            
            player_lines.append(f"{line1}\n{line2}")
        
        embed.add_field(
            name=field_name,
            value='\n'.join(player_lines) if player_lines else 'No stats',
            inline=False
        )
    
    # Calculate totals
    total_kills = sum(p.get('kills', 0) for p in players)
    total_deaths = sum(p.get('deaths', 0) for p in players)
    total_dmg = sum(p.get('damage_given', 0) for p in players)
    total_hs = sum(p.get('headshots', 0) for p in players)
    total_revives = sum(p.get('revives', 0) for p in players)
    total_gibs = sum(p.get('gibs', 0) for p in players)
    total_team_dmg = sum(p.get('team_damage_given', 0) for p in players)
    avg_acc = sum(p.get('accuracy', 0) for p in players) / len(players) if players else 0
    avg_dpm = sum(p.get('dpm', 0) for p in players) / len(players) if players else 0
    avg_time_dead = sum(p.get('time_dead', 0) for p in players) / len(players) if players else 0
    
    embed.add_field(
        name="📊 Round Summary",
        value=(
            f"**Totals:** Kills:`{total_kills}` Deaths:`{total_deaths}` HS:`{total_hs}` "
            f"Damage:`{int(total_dmg):,}` TeamDmg:`{int(total_team_dmg):,}`\n"
            f"**Averages:** Accuracy:`{avg_acc:.1f}%` DPM:`{int(avg_dpm)}` DeadTime:`{avg_time_dead:.1f}m`"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"Round ID: {round_id} | {round_date}-{round_time}-{map_name}-round-{round_num}.txt")
    
    return embed

async def main():
    print("=" * 80)
    print("🎨 TESTING NEW VISUAL FORMAT FOR ROUND STATS")
    print("=" * 80)
    print()
    
    embed = await create_test_embed()
    
    if embed:
        print("\n" + "=" * 80)
        print("📋 EMBED PREVIEW (as Discord will show it)")
        print("=" * 80)
        print()
        print(f"TITLE: {embed.title}")
        print(f"COLOR: {embed.color}")
        print()
        print("DESCRIPTION:")
        print(embed.description)
        print()
        
        for field in embed.fields:
            print(f"\n{'=' * 60}")
            print(f"FIELD: {field.name}")
            print(f"{'=' * 60}")
            print(field.value)
        
        print("\n" + "=" * 80)
        print(f"FOOTER: {embed.footer.text}")
        print("=" * 80)
        print()
        print("✅ This is how the bot will post round stats!")
        print()

if __name__ == '__main__':
    asyncio.run(main())
