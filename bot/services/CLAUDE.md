# Bot Services Package - CLAUDE.md

## Overview

Service layer for the ET:Legacy Statistics Bot.
Services encapsulate complex business logic, data aggregation, and external integrations.

## Service Architecture

```
Cogs (commands) → Services (business logic) → DatabaseAdapter (data access)
                                            → External APIs
```

Services are stateless and receive the bot instance for database/config access.

## Service Reference

### Session Services

| Service | File | Purpose |
|---------|------|---------|
| `SessionDataService` | `session_data_service.py` | Fetches session data from DB |
| `SessionStatsAggregator` | `session_stats_aggregator.py` | Aggregates player stats |
| `SessionEmbedBuilder` | `session_embed_builder.py` | Builds Discord embeds |
| `SessionGraphGenerator` | `session_graph_generator.py` | Creates performance graphs |
| `SessionViewHandlers` | `session_view_handlers.py` | Interactive Discord views |

### Player Services

| Service | File | Purpose |
|---------|------|---------|
| `PlayerBadgeService` | `player_badge_service.py` | Achievement badge display |
| `PlayerDisplayNameService` | `player_display_name_service.py` | GUID → name resolution |
| `PlayerFormatter` | `player_formatter.py` | Consistent player display |

### Game Services

| Service | File | Purpose |
|---------|------|---------|
| `PredictionEngine` | `prediction_engine.py` | AI match predictions |
| `StopwatchScoringService` | `stopwatch_scoring_service.py` | Stopwatch mode scoring |
| `VoiceSessionService` | `voice_session_service.py` | Voice channel tracking |

### Publishing

| Service | File | Purpose |
|---------|------|---------|
| `RoundPublisherService` | `round_publisher_service.py` | Auto-post round stats |

## Key Patterns

### Service Initialization
```python
class SessionDataService:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_adapter

    async def get_latest_session(self) -> dict:
        query = "SELECT MAX(gaming_session_id) FROM rounds"
        result = await self.db.fetch_one(query)
        return result
```

### Player GUID Aggregation (CRITICAL)
```python
# ALWAYS group by player_guid, use MAX(player_name) for display
query = """
    SELECT player_guid, MAX(player_name) as display_name,
           SUM(kills) as total_kills,
           SUM(deaths) as total_deaths
    FROM player_comprehensive_stats
    WHERE round_id IN ({placeholders})
    GROUP BY player_guid
"""
```

### Session ID Queries
```python
# Use gaming_session_id for session boundaries
# 60-minute gap = new session
query = """
    SELECT * FROM rounds
    WHERE gaming_session_id = ?
    ORDER BY round_date, round_time
"""
```

### Time Dead Capping (Bug Workaround)
```python
# ET:Legacy Lua bug causes time_dead > time_played
# Cap per-round using LEAST()
SELECT
    player_guid,
    LEAST(
        time_played_minutes * time_dead_ratio / 100.0 * 60,
        time_played_seconds
    ) as capped_time_dead
FROM player_comprehensive_stats
```

## Critical Implementation Notes

### SessionStatsAggregator (lines 88-96)
```python
"""
IMPORTANT: In stopwatch mode, players swap sides between rounds,
so the 'team' column (1 or 2) represents the SIDE they played,
not their actual team.
We must use hardcoded teams or session_teams table to determine
actual teams.
"""
```

### SessionGraphGenerator
- Generates matplotlib graphs as Discord file attachments
- Uses `io.BytesIO` for in-memory image creation
- Graphs: DPM over rounds, K/D trends, team performance

### VoiceSessionService
- Tracks Discord voice channel membership
- Uses for team detection (players in same voice = same team)
- Error tracking integrated with bot.track_error()

## DPM Calculation (Damage Per Minute)

DPM is calculated in multiple places - ensure consistency:

```python
# Correct calculation
dpm = damage_given / (time_played_seconds / 60)

# NOT
dpm = damage_given / time_played_minutes  # May have rounding errors
```

## Testing Services

```bash
# Syntax check
python3 -m py_compile bot/services/session_data_service.py

# Import check
python3 -c "from bot.services import SessionDataService; print('OK')"
```
