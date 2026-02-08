# Bot Core Package - CLAUDE.md

## Overview

Core business logic for the ET:Legacy Statistics Bot.
This package contains the foundational components used by cogs and services.

## Module Reference

### Database Layer

| Module | Purpose |
|--------|---------|
| `database_adapter.py` | Async PostgreSQL/SQLite abstraction |
| `stats_cache.py` | 5-minute TTL query caching |

### Team Detection (5 modules work together)

| Module | Purpose |
|--------|---------|
| `team_manager.py` | Orchestrates team detection + real-time tracking |
| `advanced_team_detector.py` | Multi-strategy detection with confidence |
| `team_detector_integration.py` | Integration layer for team detection |
| `substitution_detector.py` | Detects mid-session player swaps |
| `team_history.py` | Historical team pairing data |

**Real-Time Team Tracking (Feb 2026):**

Teams are now tracked in real-time as rounds are imported:

```text
R1 of new session → create_initial_teams_from_round()
                    Side 1 = Team A, Side 2 = Team B

Subsequent rounds → update_teams_from_round()
                    New players added to appropriate team
```

This allows tracking games that grow from 3v3 → 4v4 → 6v6.

### Player & Session

| Module | Purpose |
|--------|---------|
| `match_tracker.py` | Tracks R1+R2 match pairing |
| `season_manager.py` | Season/period management |
| `achievement_system.py` | Player badge awards |
| `frag_potential.py` | Expected frag calculations |

### Utilities

| Module | Purpose |
|--------|---------|
| `utils.py` | Shared utility functions |
| `checks.py` | Discord command permission checks |
| `pagination_view.py` | Paginated Discord embeds |
| `lazy_pagination_view.py` | Lazy-loading pagination |

## Key Components

### DatabaseAdapter (database_adapter.py)

Async abstraction over PostgreSQL (primary) and SQLite (fallback).

```python
# Usage in cogs/services
async def my_function(self):
    query = "SELECT * FROM rounds WHERE gaming_session_id = ?"
    results = await self.bot.db_adapter.fetch_all(query, (session_id,))
```python

**Methods:**

- `fetch_all(query, params)` - Returns list of rows
- `fetch_one(query, params)` - Returns single row or None
- `execute(query, params)` - For INSERT/UPDATE/DELETE
- `executemany(query, params_list)` - Batch operations

### StatsCache (stats_cache.py)

5-minute TTL caching for expensive queries.

```python
# Automatic caching via decorator or manual
cache_key = f"player_stats_{player_guid}"
cached = await self.bot.stats_cache.get(cache_key)
if not cached:
    data = await expensive_query()
    await self.bot.stats_cache.set(cache_key, data, ttl=300)
```python

### TeamManager (team_manager.py)

Orchestrates team detection using multiple strategies:

1. **Voice Channel Detection** - Players in same voice channel
2. **Historical Patterns** - Previous session team pairings
3. **Multi-Round Consensus** - Who plays together across rounds
4. **Co-occurrence Matrix** - Statistical team pairing

```python
team_manager = TeamManager(bot)
teams = await team_manager.detect_teams(session_id)
# Returns: {"team1": [guid1, guid2], "team2": [guid3, guid4]}
```python

### Checks (checks.py)

Discord command permission decorators.

```python
from bot.core.checks import is_public_channel, is_admin_channel

@commands.command()
@is_public_channel()  # Only works in public_channels from config
async def my_command(self, ctx):
    pass

@commands.command()
@is_admin_channel()  # Only works in admin_channel from config
async def admin_command(self, ctx):
    pass
```text

**Behavior**: Returns `False` silently if wrong channel (no error message).

## Stopwatch Mode (CRITICAL)

ET:Legacy stopwatch mode means teams swap sides between R1 and R2.

```text

Round 1: Team A = Axis,  Team B = Allies
Round 2: Team A = Allies, Team B = Axis  (SWAPPED!)

```python

The `team` column in database indicates SIDE (axis/allies), NOT actual team!
Use `team_manager.py` to determine persistent team assignments.

## Data Integrity Rules

1. **Group by `player_guid`** - Never `player_name`
2. **60-minute session gaps** - Not 30 minutes
3. **R2 files are cumulative** - Parser calculates differential
4. **Parameterized queries only** - No string interpolation

## Common Patterns

### Safe Database Query

```python
async def get_player_stats(self, guid: str) -> dict:
    query = """
        SELECT player_guid, MAX(player_name) as name,
               SUM(kills) as total_kills
        FROM player_comprehensive_stats
        WHERE player_guid = ?
        GROUP BY player_guid
    """
    return await self.bot.db_adapter.fetch_one(query, (guid,))
```text

### Session-Scoped Query

```python
async def get_session_players(self, session_id: int) -> list:
    query = """
        SELECT DISTINCT player_guid
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = ?
    """
    return await self.bot.db_adapter.fetch_all(query, (session_id,))
```
