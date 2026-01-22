# Bot Package - CLAUDE.md

## Overview

This is the main Discord bot package for the ET:Legacy Statistics Bot (Slomix).
The bot tracks player statistics from ET:Legacy game servers and provides
Discord commands for viewing stats, leaderboards, and gaming session summaries.

## Directory Structure

```python
bot/
├── ultimate_bot.py          # Main entry point (4,990 lines)
├── community_stats_parser.py # Stats file parser (1,036 lines)
├── config.py                # Configuration management
├── logging_config.py        # Logging setup
├── cogs/                    # Discord command modules (14 cogs)
├── core/                    # Business logic layer
├── services/                # Service layer
├── automation/              # SSH monitoring & file tracking
├── diagnostics/             # Debug utilities (standalone)
├── repositories/            # Data access layer
├── stats/                   # Statistics calculation
├── session_views/           # Discord UI components
├── local_stats/             # Downloaded stats files
├── logs/                    # Bot logs
└── tools/                   # Utility scripts
```python

## Critical Files

### ultimate_bot.py

- Main bot class extending `commands.Bot`
- Loads all 14 cogs on startup
- Contains `endstats_monitor` task loop (SSH polling)
- Schema validation at startup
- Admin notification system (`alert_admins()`, `track_error()`)

### community_stats_parser.py

- Parses ET:Legacy stats text files
- **CRITICAL**: Handles Round 2 differential calculation
  - R2 files contain CUMULATIVE stats
  - Parser finds matching R1 and calculates: `R2_only = R2_cumulative - R1`
- 30-minute window for R1-R2 matching (line 384)
- Handles midnight crossovers

### config.py

- Loads from `.env` or `bot_config.json`
- Environment variables take precedence
- Contains session gap threshold (60 minutes)

## Key Patterns

### Database Access

```python
# Always use database_adapter for async operations
results = await self.bot.db_adapter.fetch_all(query, params)

# Use parameterized queries with ?
query = "SELECT * FROM players WHERE guid = ?"
params = (player_guid,)
```text

### Player Aggregation

```python
# ALWAYS group by player_guid, NEVER player_name
GROUP BY player_guid
# Use MAX(player_name) to get a display name
SELECT player_guid, MAX(player_name) as name, SUM(kills) as total_kills
```text

### Session Queries

```python
# Use gaming_session_id, not date ranges
WHERE gaming_session_id = ?
# 60-minute gaps define session boundaries
```sql

## Common Pitfalls

1. **Don't use SQLite syntax** - This is PostgreSQL
   - Wrong: `INSERT OR REPLACE`
   - Right: `INSERT ... ON CONFLICT DO UPDATE`

2. **Don't recalculate R2 differential** - Parser handles it correctly

3. **Don't group by player_name** - Players change names, use GUID

4. **Don't use 30-minute session gaps** - Correct value is 60 minutes

5. **Don't modify processed_files manually** - SHA256 validation in place

## Running the Bot

```bash
# Development
python -m bot.ultimate_bot

# Production (systemd)
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
```

## Adding New Commands

1. Create or modify a cog in `bot/cogs/`
2. Never add commands directly to `ultimate_bot.py`
3. Use `@commands.command()` decorator
4. Add proper channel checks (`is_public_channel()`, `is_admin_channel()`)
5. Use the database adapter, not direct connections

## Testing Changes

1. Check syntax: `python3 -m py_compile bot/ultimate_bot.py`
2. Test specific cog: `python3 -c "from bot.cogs.stats_cog import StatsCog"`
3. Run the bot in a test Discord server first
