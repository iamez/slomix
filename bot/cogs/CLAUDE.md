# Bot Cogs Package - CLAUDE.md

## Overview

Discord.py Cogs for the ET:Legacy Statistics Bot.
Each cog handles a specific domain of commands.

## Available Cogs (14 total)

### User-Facing Commands

| Cog | File | Purpose | Key Commands |
|-----|------|---------|--------------|
| LastSessionCog | `last_session_cog.py` | Gaming session stats | `!last_session`, `!last_session graphs` |
| LeaderboardCog | `leaderboard_cog.py` | Rankings & leaderboards | `!top_dpm`, `!top_kd`, `!stats` |
| StatsCog | `stats_cog.py` | Individual player stats | `!stats <player>` |
| TeamCog | `team_cog.py` | Team-based statistics | `!team_stats` |
| SessionCog | `session_cog.py` | Session exploration | `!sessions`, `!session <id>` |
| PredictionsCog | `predictions_cog.py` | Match predictions | `!predictions`, `!predict` |
| LinkCog | `link_cog.py` | Account linking | `!link`, `!unlink`, `!whoami` |

### Admin Commands

| Cog | File | Purpose | Key Commands |
|-----|------|---------|--------------|
| AdminCog | `admin_cog.py` | Database & sync operations | `!sync_all`, `!rebuild_sessions` |
| AdminPredictionsCog | `admin_predictions_cog.py` | Prediction management | `!resolve_prediction` |
| SyncCog | `sync_cog.py` | File synchronization | `!sync_historical` |
| ServerControlCog | `server_control.py` | Game server control | `!rcon`, `!restart` |
| AutomationCommandsCog | `automation_commands.py` | Automation control | `!automation_status` |

### Specialized

| Cog | File | Purpose |
|-----|------|---------|
| SynergyAnalyticsCog | `synergy_analytics.py` | Player synergy analysis |
| SessionManagementCog | `session_management_cog.py` | Session operations |
| TeamManagementCog | `team_management_cog.py` | Team assignment |
| PermissionManagementCog | `permission_management_cog.py` | Permission control |

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
```

## Key Patterns

### Channel Checks
```python
from bot.core.checks import is_public_channel, is_admin_channel

@is_public_channel()  # For user commands
@is_admin_channel()   # For admin commands
```

### Database Access
```python
# Always use bot.db_adapter
results = await self.bot.db_adapter.fetch_all(query, params)
result = await self.bot.db_adapter.fetch_one(query, params)
await self.bot.db_adapter.execute(query, params)
```

### Player Lookup
```python
# When aggregating player stats, group by GUID not name
query = """
    SELECT player_guid, MAX(player_name) as name, SUM(kills)
    FROM player_comprehensive_stats
    WHERE gaming_session_id = ?
    GROUP BY player_guid
"""
```

### Session Queries
```python
# Use gaming_session_id for session queries
# 60-minute gap between rounds = new session
WHERE gaming_session_id = ?
```

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
