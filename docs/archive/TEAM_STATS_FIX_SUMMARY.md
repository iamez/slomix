# TEAM-BASED STATS - ROOT CAUSE & FIX

## THE PROBLEM

Team-based stats are **fundamentally broken** for stopwatch mode because:

1. **In Stopwatch**: Teams swap sides every round (attackers ↔ defenders)
2. **Database stores**: Which SIDE (1 or 2) a player was on each round
3. **Current aggregation**: Groups stats by `team` column = groups by SIDE not actual team
4. **Result**: "Team 1" stats = all attacker rounds, "Team 2" stats = all defender rounds

### Example from 2025-10-30 session:
```
Every player appears on BOTH teams:
- SuperBoyy: Team 1 (9 rounds), Team 2 (9 rounds)  
- qmr: Team 1 (9 rounds), Team 2 (9 rounds)
- All 10 players switch between Team 1 and Team 2
```

**Current broken output**:
- Team 1: 768 kills, 617 deaths (attacker side stats)
- Team 2: 617 kills, 768 deaths (defender side stats)

This is meaningless! It's just showing attacker performance vs defender performance.

## THE SOLUTION

### What I Fixed:
1. ✅ Rewrote `_aggregate_team_stats()` to use actual team rosters instead of `team` column
2. ✅ Added auto-detection fallback (tries to detect teams from player co-occurrence)
3. ✅ Added warning logs when team rosters aren't available

### What Still Needs to Be Done:

**Option A: Create `session_teams` table** (RECOMMENDED)
- Table already defined in schema.sql but not created in database
- Stores which players (by GUID) are on each named team for each round
- Bot already has code to read from this table

**Option B: Hardcoded config file**
- Create a JSON file like:
```json
{
  "2025-10-30": {
    "slomix": {
      "guids": ["EDBB5DA9", "652EB4A6", "1C747DF1"],
      "names": ["SuperBoyy", "qmr", "SmetarskiProner"]
    },
    "purans": {
      "guids": ["7B84BE88", "D8423F90", "A0B2063D"],
      "names": ["endekk", "vid", "i p k i s s"]
    }
  }
}
```

**Option C: Accept the limitation**
- Just document that team stats show "Attackers vs Defenders" not actual teams
- Only works properly for non-stopwatch game modes

## FILES MODIFIED

- `bot/cogs/last_session_cog.py`:
  - Fixed `_aggregate_team_stats()` to aggregate by actual team roster
  - Fixed `_build_team_mappings()` with better auto-detection
  - Reordered function calls to get team mappings before aggregating stats

## TESTING

Run the bot and use `!last_round` - you'll see:
- ⚠️ Warning in logs: "No team rosters available - stats will group by SIDE not team"
- Team stats will still be wrong until you add team rosters

## NEXT STEPS

**Choose your path:**

1. **Create the session_teams table** - run `tools/create_session_teams_table.py`
2. **Populate it** - either manually or with a script that detects teams
3. **Or create a hardcoded teams config** for known sessions

Without one of these, team stats will continue to show attacker/defender performance,
not actual team performance.
