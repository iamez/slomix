# Team System Implementation Plan

## Branch: `team-system`

## Overview
Building a comprehensive team tracking and scoring system for ET:Legacy competitive play. The game is team-based with pickup/gather style matches where rosters change between sessions.

## Core Requirements

### 1. Team Detection & Tracking
- ✅ Automatic team detection from round data
- ✅ Handle Axis/Allies role switching (stopwatch mode)
- ✅ Identify persistent teams across all maps in a round
- ✅ Handle late joiners using co-membership voting
- ✅ Store teams in `session_teams` table

### 2. Team Names
- ✅ Default: "Team A" vs "Team B"
- 🔄 Custom names: Allow setting custom team names per round
- 🔄 Historical names: Track team name changes over time
- 🔄 Display: Use custom names in all bot outputs

### 3. Lineup Tracking
- ✅ Detect roster changes between sessions
- 🔄 Track which players joined/left
- 🔄 Identify core vs rotating players
- 🔄 Calculate lineup stability metrics

### 4. Scoring & Records
- ✅ Stopwatch scoring already implemented (`tools/stopwatch_scoring.py`)
- 🔄 Link scores to team rosters
- 🔄 Track win/loss/tie records per lineup
- 🔄 Calculate win rates for specific rosters
- 🔄 Store session results in database

### 5. Map Performance
- 🔄 Track team performance per map
- 🔄 Win rates on specific maps
- 🔄 Best/worst maps for each team
- 🔄 Attack vs defense performance

### 6. Statistics & Analytics
- 🔄 Team composition analysis (player synergy)
- 🔄 Optimal lineup suggestions based on history
- 🔄 Head-to-head matchup statistics
- 🔄 Team momentum tracking (winning/losing streaks)

## Implementation Files

### Core Components
1. ✅ `bot/core/team_manager.py` - Main team detection and tracking logic
2. 🔄 `bot/cogs/team_cog.py` - Discord commands for team management
3. 🔄 `tools/team_analytics.py` - Advanced analytics and statistics
4. 🔄 Database schema updates for session results

### Database Schema Updates Needed

```sql
-- New table: session_results
CREATE TABLE session_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_date TEXT NOT NULL,
    team_a_name TEXT NOT NULL,
    team_b_name TEXT NOT NULL,
    team_a_score INTEGER NOT NULL,
    team_b_score INTEGER NOT NULL,
    winner TEXT,  -- 'Team A', 'Team B', or 'TIE'
    total_maps INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(round_date)
);

-- New table: map_results
CREATE TABLE map_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    team_a_points INTEGER NOT NULL,
    team_b_points INTEGER NOT NULL,
    time_limit TEXT,
    round1_time TEXT,
    round2_time TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(round_date, map_name)
);

-- Add indexes
CREATE INDEX idx_session_results_date ON session_results(round_date);
CREATE INDEX idx_map_results_date ON map_results(round_date);
CREATE INDEX idx_map_results_map ON map_results(map_name);
```

## Discord Commands to Implement

### Basic Team Commands
- `/teams` - Show current session teams (auto-detect if needed)
- `/teams <date>` - Show teams for specific date
- `/set_team_names <date> <team_a> <team_b>` - Set custom names
- `/lineup_changes` - Compare current vs previous session roster
- `/lineup_changes <date1> <date2>` - Compare two specific sessions

### Statistics Commands
- `/team_record <team_roster>` - Win/loss record for specific lineup
- `/team_stats <team_name> [date_range]` - Overall team statistics
- `/map_performance <date>` - Team performance per map for session
- `/head_to_head <team1> <team2>` - Historical matchup stats
- `/best_lineup [min_games]` - Best performing lineups

### Round Commands
- `/session_score <date>` - Show final score for session
- `/session_recap <date>` - Detailed session breakdown with teams and scores

## Integration Points

### With Existing Systems
1. **StopwatchScoring** (`tools/stopwatch_scoring.py`)
   - Already calculates map scores correctly
   - Need to link scores to team names from `session_teams`
   - Store results in new `session_results` and `map_results` tables

2. **Last Round Command** (`bot/cogs/last_session_cog.py`)
   - Already uses `get_hardcoded_teams()` method
   - Enhance to show team names prominently
   - Add win/loss record display
   - Show lineup changes from previous session

3. **Session Command** (`bot/cogs/session_cog.py`)
   - Add team information to session displays
   - Show team scores and records

4. **Leaderboard** (`bot/cogs/leaderboard_cog.py`)
   - Add team-based leaderboards
   - Best win rates, most games played, etc.

## Work Phases

### Phase 1: Core Team System (Today)
- ✅ Create `TeamManager` class
- 🔄 Create database schema updates
- 🔄 Create `team_cog.py` with basic commands
- 🔄 Test team detection on recent sessions
- 🔄 Implement custom team names

### Phase 2: Scoring Integration
- 🔄 Link `StopwatchScoring` to team names
- 🔄 Store session results in database
- 🔄 Store map results in database
- 🔄 Create session recap command

### Phase 3: Statistics & Analytics
- 🔄 Implement win/loss tracking
- 🔄 Create lineup comparison tools
- 🔄 Build team performance analytics
- 🔄 Add map-specific statistics

### Phase 4: Advanced Features
- 🔄 Player synergy analysis
- 🔄 Lineup optimization suggestions
- 🔄 Momentum tracking
- 🔄 Historical trend analysis

## Testing Plan
1. Test on October 2nd session (known good data)
2. Test on October 28th session (most recent)
3. Verify lineup change detection across multiple rounds
4. Test custom team names
5. Verify stopwatch scoring integration

## Success Criteria
- ✅ Teams automatically detected for any session
- ✅ Custom team names can be set and persist
- ✅ Lineup changes accurately detected
- ✅ Session scores correctly calculated and stored
- ✅ Team records accurately tracked
- ✅ All statistics commands work reliably

## Notes
- Keep "Team A" and "Team B" as fallback defaults
- Game uses Axis/Allies but these are just roles
- Focus on persistent team identity across session
- Handle edge cases: uneven teams, mid-session joins/leaves
- Performance: optimize queries for large date ranges
