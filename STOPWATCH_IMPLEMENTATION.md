# Stopwatch Scoring System - Implementation Complete ✅

## Overview
Implemented Stopwatch team scoring for ET:Legacy matches in the Discord bot. The system tracks team-based scores across multi-round matches using the correct Stopwatch rules.

## Stopwatch Rules
In ET:Legacy Stopwatch mode:
- **2 rounds per map** - teams swap Axis/Allies between rounds
- **Round 1**: First team attacks, sets a time (or gets fullhold)
- **Round 2**: Second team attacks, tries to beat Round 1's time

### Scoring (Per Map)
- **R2 beat R1 time**: 2-0 win for R2 attackers
- **R1 = R2 time**: 1-1 tie (both teams get 1 point)
- **R2 didn't beat R1**: 2-0 win for R1 attackers (defended successfully)

Points are awarded **AFTER Round 2** completes.

## Implementation

### 1. Database Schema
**Migration**: `tools/migrations/002_add_winner_defender_teams.py`
- Added `winner_team INTEGER` to rounds table
- Added `defender_team INTEGER` to rounds table
- Values: 1=Axis, 2=Allies, 0=Unknown/Draw

**Table**: `session_teams`
- Stores team assignments (team_name → player_guids)
- Populated by dynamic team detector
- Used for mapping game teams (Axis/Allies) to actual team names

### 2. Stats Parser
**File**: `bot/community_stats_parser.py`
- Extracts `defender_team` from header field [4]
- Extracts `winner_team` from header field [5]
- Header format: `server\map\config\round\defenderteam\winnerteam\timelimit\actualtime`

**Note**: Current stats files have 0 values (bug in c0rnp0rn3.lua), but parser is ready.

### 3. Stats Importer
**File**: `tools/simple_bulk_import.py`
- Stores `defender_team` and `winner_team` in database
- Updated INSERT statement from 5 to 7 values

### 4. Scoring Calculator
**File**: `tools/stopwatch_scoring.py`

**Key Method**: `calculate_map_score(r1_time_limit, r1_actual, r2_actual)`
```python
# Parse times to seconds
r1_limit_sec = parse_time_to_seconds(r1_time_limit)
r1_actual_sec = parse_time_to_seconds(r1_actual)
r2_actual_sec = parse_time_to_seconds(r2_actual)

# Determine winner
if r1_actual_sec == r2_actual_sec:
    return (1, 1, "Tie")  # 1-1
elif r2_actual_sec < r1_actual_sec:
    return (0, 2, "R2 won")  # 2-0 for R2
else:
    return (2, 0, "R1 held")  # 2-0 for R1
```

**Method**: `calculate_session_scores(round_date)`
- Groups rounds into map pairs
- Calculates score for each map
- Returns total points per team

**Return Structure**:
```python
{
    'team1_name': 15,
    'team2_name': 5,
    'maps': [
        {
            'map': 'supply',
            'team1_points': 0,
            'team2_points': 2,
            'description': 'R2 beat time (8:22 < 9:41)'
        },
        ...
    ],
    'total_maps': 10
}
```

### 5. Bot Integration
**File**: `bot/ultimate_bot.py`

**Command**: `!last_round`
- Calls `scorer.calculate_session_scores(round_date)`
- Displays team scores in embed description
- Shows map-by-map breakdown

**Code**:
```python
from tools.stopwatch_scoring import StopwatchScoring

scorer = StopwatchScoring(self.bot.db_path)
scoring_result = scorer.calculate_session_scores(latest_date)

if scoring_result:
    team_names = [k for k in scoring_result.keys()
                  if k not in ['maps', 'total_maps']]
    team_1_name = team_names[0]
    team_2_name = team_names[1]
    team_1_score = scoring_result[team_1_name]
    team_2_score = scoring_result[team_2_name]
    
    # Display: "🏆 Team Score: insAne 15 - 5 puran"
```

## Test Validation

### October 2nd 2025 Data
**Teams**: slomix vs slo (main DB) / insAne vs puran (github DB)
**Result**: **15 - 5** ✅

**Breakdown**:
- 5 ties (1-1): adlernest, delivery, escape1, brewdog, braundorf
- 5 wins (2-0): supply, escape2(2nd), goldrush, frostbite, erdenberg

**Math**:
- Winner: 5 wins × 2pts + 5 ties × 1pt = **15 points**
- Loser: 0 wins × 2pts + 5 ties × 1pt = **5 points**

### Running Tests
```bash
# Test scorer standalone
python tools/stopwatch_scoring.py 2025-10-02

# Verify deployment
python verify_stopwatch_deployment.py
```

## Files Modified/Created

### Created Files
1. `tools/migrations/002_add_winner_defender_teams.py` - Database migration
2. `tools/stopwatch_scoring.py` - Scoring calculator
3. `verify_stopwatch_deployment.py` - Deployment checklist
4. `real_stopwatch_scoring.py` - Test/validation script

### Modified Files
1. `bot/community_stats_parser.py` - Extract winner/defender
2. `tools/simple_bulk_import.py` - Store winner/defender
3. `bot/ultimate_bot.py` - Display team scores

### Synced to GitHub
All files copied to `github/` folder for deployment.

## Known Issues

### Stats File Bug
Current stats files have `defender_team=0` and `winner_team=0` for all rounds. This is a bug in the c0rnp0rn3.lua mod on the server. The parser and database are ready to handle correct values once the mod is fixed.

**Workaround**: Scoring works by comparing round times, which doesn't require winner/defender fields.

### Team Detection
Teams are detected from `session_teams` table, populated by dynamic team detector. If session_teams is empty, scorer returns None and bot shows "Team 1" and "Team 2" as fallback.

## Future Improvements

1. **Fix c0rnp0rn3.lua**: Update server mod to populate winner_team and defender_team correctly
2. **Team Display**: Add team logos/emblems in Discord embeds
3. **Season Tracking**: Track cumulative team scores across multiple rounds
4. **Map Stats**: Show win/loss/tie records per map
5. **Player Stats**: Individual player contributions to team scores

## Deployment Checklist

✅ Database columns added (winner_team, defender_team)
✅ session_teams table created
✅ Parser extracts winner/defender fields
✅ Importer stores winner/defender in DB
✅ Scoring calculator implements correct rules
✅ Bot displays team scores in !last_round
✅ All files synced to github/ folder
✅ Test validation passed (15-5 result)

## Usage

### Discord Bot Command
```
!last_round
```

**Output**:
```
🏆 Team Score: slomix 15 - 5 slo

Map Results:
  adlernest: 1-1 (tie)
  supply: 2-0 slomix
  delivery: 1-1 (tie)
  ...
```

### Standalone Script
```bash
python tools/stopwatch_scoring.py 2025-10-02
```

**Output**:
```
============================================================
🏆 STOPWATCH SCORING: 2025-10-02
============================================================

📊 Final Score:
   slomix: 15 points
   slo: 5 points

🗺️  Map-by-Map Breakdown (10 maps):
   ...
```

## Credits
- **m1ke**: Explained Stopwatch scoring rules in Discord
- **Article**: [Stopwatch Mode Overview](https://et.trackbase.net/?mod=article&id=5)
- **Implementation**: AI assistant with user guidance

---

**Status**: ✅ **COMPLETE AND READY FOR DEPLOYMENT**
**Last Updated**: 2025-01-XX
**Tested With**: October 2nd 2025 data (15-5 result)
