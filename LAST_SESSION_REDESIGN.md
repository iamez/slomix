# 📊 Last Round Command Redesign

**Date:** November 1, 2025  
**Purpose:** Split and enhance the `!last_round` command

---

## 🎯 Current vs New Design

### Current (Monolithic)
```
!last_round → Shows everything in one massive output (7+ embeds)
```

### New (Modular)
```
!last_round             → Quick overview + subcommand menu
!last_round overview    → Same as default
!last_round maps        → Map summaries with visual graphs
!last_round rounds      → Detailed round-by-round breakdown
!last_round graphs      → Comprehensive statistical graphs
```

---

## 📁 File Structure

```
bot/cogs/session_cog.py  (NEW - extracted from ultimate_bot.py)
├── SessionCog class
│   ├── last_round()           # Main command with subcommand routing
│   ├── _last_session_overview() # Quick summary
│   ├── _last_session_maps()     # Map-level aggregation + graphs
│   ├── _last_session_rounds()   # Round-by-round details
│   └── _last_session_graphs()   # Statistical analysis + charts
│
└── Helper methods:
    ├── _get_session_data()      # Fetch session from DB
    ├── _aggregate_by_map()      # Group rounds by map
    ├── _create_map_graph()      # Generate map performance chart
    ├── _create_player_graph()   # Generate player performance chart
    └── _format_round_embed()    # Format individual round display
```

---

## 🎨 Command Examples

### 1. `!last_round` (Overview - Default)
**Output:**
```
📊 Daily Session Summary - October 31, 2025
────────────────────────────────────────
🗓️ Duration: 6:30 PM - 11:45 PM (5h 15m)
🎮 Maps Played: 4 unique maps
🔄 Total Games: 8 games (16 rounds)
👥 Players: 12 participants

📍 Maps:
  • te_escape2    - 4 games (8 rounds)
  • etl_adlernest - 2 games (4 rounds)
  • et_brewdog    - 1 game (2 rounds)
  • supply        - 1 game (2 rounds)

🏆 Session MVP: vid (K/D: 3.2, 142 DPM)
⚔️ Total Kills: 1,247
💀 Total Deaths: 1,158

📖 View Details:
  • !last_round maps     - Map summaries + graphs
  • !last_round rounds   - Round-by-round breakdown
  • !last_round graphs   - Statistical analysis
```

---

### 2. `!last_round maps` (Map-Level View)
**Output:**
```
🗺️ Map Performance Summary - October 31, 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 te_escape2 (4 games, 8 rounds)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏱️ Average Round Time: 8:45
🏆 Defenders Won: 5 rounds (62.5%)
⚔️ Attackers Won: 3 rounds (37.5%)

Top Performers:
  1. 🥇 vid       - 45K/14D (K/D: 3.21) | 156 DPM
  2. 🥈 slomix    - 38K/19D (K/D: 2.00) | 142 DPM
  3. 🥉 player3   - 32K/22D (K/D: 1.45) | 128 DPM

[Graph showing K/D trends across 8 rounds]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 etl_adlernest (2 games, 4 rounds)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏱️ Average Round Time: 12:30
🏆 Defenders Won: 3 rounds (75%)
⚔️ Attackers Won: 1 round (25%)

Top Performers:
  1. 🥇 slomix    - 28K/8D (K/D: 3.50) | 168 DPM
  2. 🥈 vid       - 24K/11D (K/D: 2.18) | 145 DPM
  3. 🥉 player5   - 19K/15D (K/D: 1.27) | 118 DPM

[Graph showing kills per round]

... (continues for each map)
```

---

### 3. `!last_round rounds` (Round-by-Round Details)
**Output:**
```
🔄 Round-by-Round Breakdown - October 31, 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Game 1: te_escape2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔵 Round 1 - 6:45 PM
├─ Map: te_escape2
├─ Duration: 8:32
├─ Result: 🛡️ Defenders Win (Fullhold)
├─ Defending Team: Axis
└─ Top Players:
   • vid (Axis)      - 12K/3D (K/D: 4.00) | 178 DPM
   • slomix (Allies) - 8K/5D (K/D: 1.60) | 142 DPM

🔴 Round 2 - 6:55 PM
├─ Map: te_escape2
├─ Duration: 7:48
├─ Result: ⚔️ Attackers Win
├─ Defending Team: Allies
└─ Top Players:
   • slomix (Axis)   - 11K/2D (K/D: 5.50) | 195 DPM
   • vid (Allies)    - 9K/4D (K/D: 2.25) | 156 DPM

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Game 2: te_escape2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔵 Round 3 - 7:10 PM
├─ Map: te_escape2
├─ Duration: 9:15
├─ Result: 🛡️ Defenders Win
...

[Continues for all 16 rounds]

📖 Use !session rounds <map_name> to filter by map
```

---

### 4. `!last_round graphs` (Statistical Analysis)
**Output:**
```
📈 Statistical Analysis - October 31, 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Player Performance Graphs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Graph 1: K/D Ratio Trends Over Time]
Shows how each player's K/D changed throughout the round

[Graph 2: Damage Per Minute by Map]
Bar chart comparing DPM across different maps

[Graph 3: Kill Distribution]
Pie chart showing % of total kills per player

[Graph 4: Performance Timeline]
Line graph showing kills/deaths over the round timeline

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Round Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Most Played Map:     te_escape2 (50% of rounds)
Longest Round:       etl_adlernest R1 (14:32)
Shortest Round:      supply R2 (5:47)
Most Kills/Round:    vid @ te_escape2 R3 (18 kills)
Highest DPM:         slomix @ adlernest R1 (195 DPM)

Defender Win Rate:   68.75% (11/16 rounds)
Average Round Time:  9:23
Total Playtime:      2h 30m (active gameplay)
```

---

## 💻 Implementation Code Structure

### File: `bot/cogs/session_cog.py`

```python
#!/usr/bin/env python3
"""
Game session management and analysis commands.
Handles daily session tracking, round breakdowns, and statistical analysis.
"""
import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import io

logger = logging.getLogger("SessionCog")


class SessionCog(commands.Cog):
    """Commands for managing and viewing game sessions"""
    
    def __init__(self, bot):
        self.bot = bot
        
    # ========================================================================
    # MAIN COMMAND: !last_round
    # ========================================================================
    
    @commands.command(name="last_round")
    async def last_round(self, ctx, subcommand: str = None):
        """
        Display the most recent gaming session with various views.
        
        Usage:
            !last_round              - Quick overview (default)
            !last_round overview     - Same as default
            !last_round maps         - Map-level summary with graphs
            !last_round rounds       - Round-by-round breakdown
            !last_round graphs       - Statistical analysis with charts
        
        A round is all games played in one day (with 1-hour grace period
        after midnight for late-night gaming).
        """
        # Route to appropriate subcommand
        if subcommand is None or subcommand.lower() == "overview":
            await self._last_session_overview(ctx)
        elif subcommand.lower() == "maps":
            await self._last_session_maps(ctx)
        elif subcommand.lower() == "rounds":
            await self._last_session_rounds(ctx)
        elif subcommand.lower() == "graphs":
            await self._last_session_graphs(ctx)
        else:
            await ctx.send(
                f"❌ Unknown subcommand: `{subcommand}`\n\n"
                "Valid options:\n"
                "• `!last_round` or `!last_round overview`\n"
                "• `!last_round maps`\n"
                "• `!last_round rounds`\n"
                "• `!last_round graphs`"
            )
    
    # ========================================================================
    # SUBCOMMAND 1: OVERVIEW (Default)
    # ========================================================================
    
    async def _last_session_overview(self, ctx):
        """Quick summary of the most recent session"""
        try:
            # Get round data
            session_data = await self._get_latest_session_data()
            
            if not session_data:
                await ctx.send("❌ No rounds found in database.")
                return
            
            # Create overview embed
            embed = discord.Embed(
                title=f"📊 Daily Session Summary - {session_data['date']}",
                description="Quick overview of your gaming session",
                color=0x00D2FF,
                timestamp=discord.utils.utcnow()
            )
            
            # Round info
            embed.add_field(
                name="🗓️ Round Info",
                value=(
                    f"**Duration:** {session_data['start_time']} - {session_data['end_time']} "
                    f"({session_data['duration']})\n"
                    f"**Maps Played:** {session_data['unique_maps']} unique maps\n"
                    f"**Total Games:** {session_data['total_games']} games "
                    f"({session_data['total_rounds']} rounds)\n"
                    f"**Players:** {session_data['total_players']} participants"
                ),
                inline=False
            )
            
            # Map list
            map_list = "\n".join([
                f"• {map_info['name']} - {map_info['games']} games ({map_info['rounds']} rounds)"
                for map_info in session_data['maps'][:5]  # Top 5 maps
            ])
            embed.add_field(
                name="📍 Maps",
                value=map_list,
                inline=False
            )
            
            # Round stats
            embed.add_field(
                name="📊 Round Stats",
                value=(
                    f"**MVP:** {session_data['mvp_name']} "
                    f"(K/D: {session_data['mvp_kd']:.2f}, {session_data['mvp_dpm']:.0f} DPM)\n"
                    f"**Total Kills:** {session_data['total_kills']:,}\n"
                    f"**Total Deaths:** {session_data['total_deaths']:,}"
                ),
                inline=False
            )
            
            # Navigation
            embed.add_field(
                name="📖 View Details",
                value=(
                    "• `!last_round maps` - Map summaries + graphs\n"
                    "• `!last_round rounds` - Round-by-round breakdown\n"
                    "• `!last_round graphs` - Statistical analysis"
                ),
                inline=False
            )
            
            embed.set_footer(text="ET:Legacy Session Tracker")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.exception("Error in last_round overview")
            await ctx.send(f"❌ Error fetching round data: {e}")
    
    # ========================================================================
    # SUBCOMMAND 2: MAPS (Map-Level Aggregation)
    # ========================================================================
    
    async def _last_session_maps(self, ctx):
        """Show map-level statistics with performance graphs"""
        try:
            session_data = await self._get_latest_session_data()
            
            if not session_data:
                await ctx.send("❌ No rounds found.")
                return
            
            # Send main header
            await ctx.send(
                f"🗺️ **Map Performance Summary - {session_data['date']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            # Process each map
            for map_info in session_data['maps']:
                # Create embed for this map
                embed = await self._create_map_embed(map_info)
                await ctx.send(embed=embed)
                
                # Generate and send graph
                graph_file = await self._create_map_performance_graph(map_info)
                if graph_file:
                    await ctx.send(file=graph_file)
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.exception("Error in last_round maps")
            await ctx.send(f"❌ Error: {e}")
    
    # ========================================================================
    # SUBCOMMAND 3: ROUNDS (Round-by-Round Breakdown)
    # ========================================================================
    
    async def _last_session_rounds(self, ctx):
        """Show detailed round-by-round breakdown"""
        try:
            session_data = await self._get_latest_session_data()
            
            if not session_data:
                await ctx.send("❌ No rounds found.")
                return
            
            await ctx.send(
                f"🔄 **Round-by-Round Breakdown - {session_data['date']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            current_game = 0
            current_map = None
            
            for round_info in session_data['rounds']:
                # New game header
                if round_info['map'] != current_map:
                    current_game += 1
                    current_map = round_info['map']
                    await ctx.send(
                        f"\n**Game {current_game}: {current_map}**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    )
                
                # Create round embed
                embed = await self._create_round_embed(round_info)
                await ctx.send(embed=embed)
                
                await asyncio.sleep(0.3)
                
        except Exception as e:
            logger.exception("Error in last_round rounds")
            await ctx.send(f"❌ Error: {e}")
    
    # ========================================================================
    # SUBCOMMAND 4: GRAPHS (Statistical Analysis)
    # ========================================================================
    
    async def _last_session_graphs(self, ctx):
        """Generate comprehensive statistical graphs"""
        try:
            session_data = await self._get_latest_session_data()
            
            if not session_data:
                await ctx.send("❌ No rounds found.")
                return
            
            await ctx.send(
                f"📈 **Statistical Analysis - {session_data['date']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Generating graphs... This may take a moment."
            )
            
            # Generate multiple graphs
            graphs = [
                ("K/D Ratio Trends", self._create_kd_trend_graph(session_data)),
                ("DPM by Map", self._create_dpm_map_graph(session_data)),
                ("Kill Distribution", self._create_kill_distribution_graph(session_data)),
                ("Performance Timeline", self._create_timeline_graph(session_data)),
            ]
            
            for title, graph_coro in graphs:
                graph_file = await graph_coro
                if graph_file:
                    await ctx.send(f"**{title}**", file=graph_file)
                    await asyncio.sleep(0.5)
            
            # Send statistics summary
            stats_embed = await self._create_stats_summary_embed(session_data)
            await ctx.send(embed=stats_embed)
            
        except Exception as e:
            logger.exception("Error in last_round graphs")
            await ctx.send(f"❌ Error generating graphs: {e}")
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_latest_session_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent round data from database.
        
        A round includes all games from a single day, with a 1-hour
        grace period after midnight for late-night gaming.
        """
        # Implementation will query database and aggregate data
        # This is a placeholder for the structure
        pass
    
    async def _aggregate_by_map(self, rounds: List[Dict]) -> List[Dict]:
        """Group rounds by map and calculate aggregated stats"""
        pass
    
    async def _create_map_embed(self, map_info: Dict) -> discord.Embed:
        """Create embed for a single map's performance"""
        pass
    
    async def _create_round_embed(self, round_info: Dict) -> discord.Embed:
        """Create embed for a single round"""
        pass
    
    async def _create_map_performance_graph(self, map_info: Dict) -> Optional[discord.File]:
        """Generate performance graph for a map"""
        pass
    
    async def _create_kd_trend_graph(self, session_data: Dict) -> Optional[discord.File]:
        """Generate K/D trend graph"""
        pass
    
    # ... more helper methods ...


# Required for Cog loading
async def setup(bot):
    await bot.add_cog(SessionCog(bot))
```

---

## 🔍 Session Definition Logic

### Database Query for "Daily Session"

```python
async def _get_latest_session_data(self):
    """
    Get all rounds from the most recent day of gaming.
    
    Rules:
    1. Find the most recent round in database
    2. Get its date (not timestamp)
    3. Include all rounds from that date
    4. PLUS rounds from next day if within 1 hour of midnight
    
    Example:
    - Most recent round: 2025-10-31 23:45:00
    - Include: All rounds from 2025-10-31 00:00 to 23:59
    - Include: Rounds from 2025-11-01 00:00 to 01:00 (grace period)
    """
    async with aiosqlite.connect(self.bot.db_path) as db:
        # Get the most recent session date
        cursor = await db.execute("""
            SELECT round_date 
            FROM rounds 
            ORDER BY round_date DESC 
            LIMIT 1
        """)
        latest = await cursor.fetchone()
        
        if not latest:
            return None
        
        latest_date = latest[0]  # Format: "YYYY-MM-DD-HHMMSS"
        session_day = latest_date[:10]  # Extract "YYYY-MM-DD"
        
        # Calculate next day for grace period
        from datetime import datetime, timedelta
        day_obj = datetime.strptime(session_day, "%Y-%m-%d")
        next_day = (day_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Query for all rounds in this round
        cursor = await db.execute("""
            SELECT 
                s.round_date,
                s.map_name,
                s.round_number,
                s.time_limit,
                s.actual_time,
                -- Add more fields as needed
            FROM rounds s
            WHERE (
                -- Same day
                s.round_date LIKE ? || '%'
                OR
                -- Next day within 1 hour (grace period)
                (s.round_date LIKE ? || '-00%' OR s.round_date LIKE ? || '-01%')
            )
            ORDER BY s.round_date ASC
        """, (session_day, next_day, next_day))
        
        rounds = await cursor.fetchall()
        
        # Process and aggregate data
        return await self._process_session_rounds(rounds)
```

---

## 📝 TODO Checklist

- [ ] Extract `last_round` from `ultimate_bot.py` to `session_cog.py`
- [ ] Implement `_last_session_overview()` (simple version of current command)
- [ ] Implement `_last_session_maps()` (aggregate by map + graphs)
- [ ] Implement `_last_session_rounds()` (round-by-round details)
- [ ] Implement `_last_session_graphs()` (statistical analysis)
- [ ] Implement session date logic with 1-hour grace period
- [ ] Create map performance graphs (matplotlib)
- [ ] Create K/D trend graphs
- [ ] Create kill distribution pie charts
- [ ] Test with real round data
- [ ] Update documentation

---

## 🎯 Benefits of This Approach

1. **Separation of Concerns** - Each subcommand is isolated
2. **User Choice** - Users pick level of detail they want
3. **Performance** - Don't generate all data/graphs unless requested
4. **Maintainable** - Easy to add new visualizations
5. **Testable** - Each method can be unit tested independently

---

## 💡 Additional Ideas

### Future Enhancements:
```python
# Filter by map
!last_round rounds te_escape2

# Filter by player
!last_round rounds @vid

# Compare sessions
!last_round compare 2025-10-31 2025-10-30

# Export round data
!last_round export json
!last_round export csv
```

---

Ready to implement this? I can help you:
1. Extract the current `last_round` code
2. Refactor it into the new structure
3. Add the new subcommand logic
4. Create the graph generation methods

Let me know which part you want to tackle first! 🚀
