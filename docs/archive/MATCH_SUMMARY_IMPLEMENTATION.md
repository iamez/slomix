# Match Summary Implementation - Round Number 0

## Overview
Implemented automatic match summary storage and Discord posting by parsing Round 2 files twice to capture both differential (Round 2 only) and cumulative (R1+R2 combined) stats.

## Problem Solved
Previously, there was no pre-calculated match summary - we had to manually SUM round 1 + round 2 stats for every query. This was error-prone and slow.

**Solution:** The Round 2 .txt file ALREADY contains cumulative stats (R1+R2 combined). We now parse it twice:
1. **Differential calculation** → Store as `round_number = 2` (Round 2 performance only)
2. **Raw cumulative parse** → Store as `round_number = 0` (Match summary)

## Implementation Details

### 1. Parser Changes (`bot/community_stats_parser.py`)
Modified `parse_round_2_with_differential()` to attach match summary:

```python
# After calculating differential...
match_summary = round_2_cumulative_result.copy()
match_summary['round_num'] = 0  # Special round number for match summary
match_summary['is_match_summary'] = True

round_2_only_result['match_summary'] = match_summary
```

### 2. Bot Import Logic (`bot/ultimate_bot.py`)
Modified `_import_stats_to_db()` to store match summary:

```python
# After importing Round 2 differential stats...
if stats_data.get('match_summary'):
    match_summary = stats_data['match_summary']
    
    # Insert as round_number = 0
    match_summary_id = await self.db_adapter.fetch_val(
        insert_summary_query,
        (..., round_number=0, ...)
    )
    
    # Insert match summary player stats
    for player in match_summary.get("players", []):
        await self._insert_player_stats(...)
```

### 3. PostgreSQL Manager (`postgresql_database_manager.py`)
Updated `process_file()` and `_create_round_postgresql()`:

```python
async def _create_round_postgresql(..., is_match_summary: bool = False):
    round_number = 0 if is_match_summary else parsed_data.get('round_number', 1)
    # Store with round_number = 0 for match summaries
```

### 4. SSH Monitor (`bot/services/automation/ssh_monitor.py`)
Added automatic match summary posting after Round 2:

```python
# After Round 2 import...
if '-round-2.txt' in filename:
    await self._post_match_summary(filename)

async def _post_match_summary(self, filename):
    # Query round_number=0 for match summary
    match_data = await self._get_match_summary_data(map_name)
    
    # Create beautiful embed with:
    # - Stopwatch times (R1 vs R2)
    # - Match outcome
    # - Top performers (cumulative)
    # - Match totals
```

## Database Schema

### Rounds Table
```sql
round_number INTEGER
  0 = Match Summary (cumulative R1+R2)
  1 = Round 1 (differential)
  2 = Round 2 (differential)
```

### Player Stats
Each `round_id` links to a round entry. For match summaries:
- `round_id` → points to `rounds` entry where `round_number = 0`
- Contains cumulative stats from both rounds
- Same schema as regular rounds

## Discord Posting Sequence

For a typical match on `supply`:

1. **Round 1 file detected** → Import → Post "Round 1 Complete" embed
2. **Round 2 file detected** → Import differential (round 2) + cumulative (round 0) → Post "Round 2 Complete" embed
3. **Immediately after Round 2** → Post "Match Complete" embed (queries round_number=0)

## Benefits

✅ **No manual calculations** - Match summary comes directly from raw file
✅ **Pre-computed totals** - Fast queries, no runtime SUM operations
✅ **Accurate data** - Can't mess up math, it's straight from the game
✅ **Linked properly** - Same `match_id` connects R1, R2, and summary
✅ **Stopwatch times included** - Round 1 time, Round 2 time, winner all stored

## Querying Match Summaries

```sql
-- Get match summary for a specific map
SELECT * FROM rounds 
WHERE map_name = 'supply' 
  AND round_number = 0 
ORDER BY round_date DESC LIMIT 1;

-- Get top players from match summary
SELECT player_name, kills, deaths, damage_given
FROM player_comprehensive_stats
WHERE round_id = (
    SELECT id FROM rounds 
    WHERE map_name = 'supply' AND round_number = 0
    ORDER BY round_date DESC LIMIT 1
)
ORDER BY kills DESC;
```

## Testing Checklist

- [ ] Import Round 1 file - verify `round_number = 1` created
- [ ] Import Round 2 file - verify BOTH `round_number = 2` AND `round_number = 0` created
- [ ] Verify match summary has cumulative stats (R1 + R2 totals)
- [ ] Verify Round 2 has differential stats (R2 only)
- [ ] Check Discord posting sequence: R1 → R2 → Match Summary
- [ ] Verify stopwatch times displayed correctly
- [ ] Verify top players show cumulative performance

## Files Modified

1. `bot/community_stats_parser.py` - Attach match_summary to Round 2 result
2. `bot/ultimate_bot.py` - Import match summary as round_number=0
3. `postgresql_database_manager.py` - Support is_match_summary flag
4. `bot/services/automation/ssh_monitor.py` - Post match summary after R2

## Notes

- Match summary uses `round_number = 0` to avoid confusion with actual rounds
- All three entries (R1, R2, summary) share the same `match_id`
- Match summary inherits stopwatch data from Round 2 header (time_limit, actual_time, winner_team)
- This approach is storage-efficient: ~33% more data but eliminates runtime calculations
