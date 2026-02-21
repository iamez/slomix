# Bot Services Package - CLAUDE.md

## Overview

Service layer for the ET:Legacy Statistics Bot.
Services encapsulate complex business logic, data aggregation, and external integrations.

## Service Architecture

```text
Cogs (commands) → Services (business logic) → DatabaseAdapter (data access)
                                            → External APIs
```python

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
```text

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
```text

### Session ID Queries

```python
# Use gaming_session_id for session boundaries
# 60-minute gap = new session
query = """
    SELECT * FROM rounds
    WHERE gaming_session_id = ?
    ORDER BY round_date, round_time
"""
```text

### Time Dead Capping (Bug Workaround)

```python
# FIX (2026-02-01): Use time_dead_minutes directly, NOT ratio calculation!
# The time_dead_ratio in R2 files is calculated against cumulative time_played,
# but we store differential time_played. Using the ratio causes ~15 min/session errors.
# Cap per-round using LEAST() to handle edge cases
SELECT
    player_guid,
    LEAST(
        COALESCE(time_dead_minutes, 0) * 60,
        time_played_seconds
    ) as capped_time_dead
FROM player_comprehensive_stats
```text

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

### StopwatchScoringService

**Key Methods:**

1. `calculate_map_score()` - Determines map winner based on R1/R2 times
2. `calculate_session_scores()` - Legacy method, counts rounds by side
3. `calculate_session_scores_with_teams()` - **NEW (2026-02-01)**: Team-aware MAP scoring

**Stopwatch Mode Logic:**
```text
Round 1: Team A attacks (as Axis), Team B defends (as Allies)
Round 2: Teams SWAP sides - Team B attacks, Team A defends

Map Winner = faster attack time wins
- Both complete: faster team wins the map
- One fullholds: completing team wins
- Double fullhold: 1-1 tie (both defended successfully)
```

**Usage in !last_session:**
```python
# Build team rosters from session_teams table
team_rosters = {"puran": [guid1, guid2], "sWat": [guid3, guid4]}
scoring = await scoring_service.calculate_session_scores_with_teams(
    session_date, session_ids, team_rosters
)
# Returns: {'team_a_name': 'puran', 'team_a_maps': 3, 'team_b_maps': 2, 'maps': [...]}
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
```text

## Testing Services

```bash
# Syntax check
python3 -m py_compile bot/services/session_data_service.py

# Import check
python3 -c "from bot.services import SessionDataService; print('OK')"
```
