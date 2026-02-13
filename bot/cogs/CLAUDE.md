# Bot Cogs Package - CLAUDE.md

## Overview

Discord.py Cogs for the ET:Legacy Statistics Bot.
Each cog handles a specific domain of commands.

## Available Cogs (20 total)

### Core User Cogs

| File | Purpose |
|------|---------|
| `achievements_cog.py` | Achievement help and badge legend |
| `analytics_cog.py` | Consistency, map stats, playstyle, awards |
| `last_session_cog.py` | Latest session embeds and endstats audits |
| `leaderboard_cog.py` | Leaderboards and player stats entrypoint |
| `link_cog.py` | Discord-to-player linking and alias tools |
| `matchup_cog.py` | Duo performance, matchup and nemesis commands |
| `predictions_cog.py` | Public prediction and trend commands |
| `proximity_cog.py` | Proximity import/status/objective commands |
| `session_cog.py` | Session and rounds queries |
| `stats_cog.py` | General help, compare, achievements progress |
| `team_cog.py` | Team pool, team record, head-to-head |

### Admin and Operations Cogs

| File | Purpose |
|------|---------|
| `admin_cog.py` | Cache/reload/diagnostic admin commands |
| `admin_predictions_cog.py` | Admin prediction management |
| `automation_commands.py` | Automation status, health, metrics, DB maintenance |
| `permission_management_cog.py` | Permission whitelist management |
| `server_control.py` | ET server control and RCON actions |
| `session_management_cog.py` | Manual session start/end |
| `sync_cog.py` | Manual sync/backfill commands |
| `team_management_cog.py` | Team assignment helpers |

### Optional/Extended

| File | Purpose |
|------|---------|
| `synergy_analytics.py` | Experimental synergy and team-balancing analytics |

## Cog Template

```python
import discord
from discord.ext import commands
import logging

from bot.core.checks import is_public_channel, is_admin_channel
from bot.core.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class MyCog(commands.Cog):
    """Description of what this cog does."""

    def __init__(self, bot):
        self.bot = bot
        # Access database via: self.bot.db_adapter

    @commands.command(name="mycommand")
    @is_public_channel()
    async def my_command(self, ctx, arg: str):
        """Command description shown in !help."""
        try:
            # Use parameterized queries
            query = "SELECT * FROM table WHERE col = ?"
            results = await self.bot.db_adapter.fetch_all(query, (arg,))

            embed = discord.Embed(title="Result", color=discord.Color.green())
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Command error: {e}", exc_info=True)
            await ctx.send(f"Error: {e}")


async def setup(bot):
    await bot.add_cog(MyCog(bot))
```text

## Key Patterns

### Channel Checks

```python
from bot.core.checks import is_public_channel, is_admin_channel

@is_public_channel()  # For user commands
@is_admin_channel()   # For admin commands
```text

### Database Access

```python
# Always use bot.db_adapter
results = await self.bot.db_adapter.fetch_all(query, params)
result = await self.bot.db_adapter.fetch_one(query, params)
await self.bot.db_adapter.execute(query, params)
```text

### Player Lookup

```python
# When aggregating player stats, group by GUID not name
query = """
    SELECT player_guid, MAX(player_name) as name, SUM(kills)
    FROM player_comprehensive_stats
    WHERE gaming_session_id = ?
    GROUP BY player_guid
"""
```text

### Session Queries

```python
# Use gaming_session_id for session queries
# 60-minute gap between rounds = new session
WHERE gaming_session_id = ?
```text

## Common Mistakes to Avoid

1. **Don't use `GROUP BY player_name`** - Players change names
2. **Don't hardcode channel IDs** - Use config
3. **Don't skip error handling** - Log all exceptions
4. **Don't use sync database calls** - Always async
5. **Don't forget channel checks** - Commands should respect channel restrictions

## Testing a Cog

```bash
# Syntax check
python3 -m py_compile bot/cogs/my_cog.py

# Import check
python3 -c "from bot.cogs.my_cog import MyCog; print('OK')"
```
