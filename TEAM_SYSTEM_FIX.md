# Team System Fix Guide

## Problem
The bot's auto-detection fails in stopwatch mode because:
- Teams swap sides every round (Attack/Defense)
- Auto-detection looks for players on same SIDE >50% of time
- In stopwatch, both teams play both sides equally (50/50)
- Result: Random team assignments (5 vs 8, etc.)

## Solution: Use !set_teams Command

Before or during your gaming session, set the team rosters:

```
!set_teams
Team 1: slomix
  - SuperBoyy (GUID)
  - carniee (GUID)
  - endekk (GUID)
  - olz (GUID)
  - Imbecil (GUID)

Team 2: ripaZha
  - antii (GUID)
  - eLx (GUID)
  - sNozji (GUID)
  - zubl1k (GUID)
  - dAFF (GUID)
```

## How It Works
1. Bot stores team rosters in `session_teams` table
2. Keyed by `session_start_date` (e.g., "2025-11-01")
3. All rounds on that date use those team rosters
4. `!last_round` will show proper team analytics

## Alternative: Post-Game Team Assignment
If you forget to set teams before playing:
```
!set_teams --date 2025-11-01
```
This retroactively assigns teams to already-completed sessions.

## Current Status
- round_teams table: **0 records** (empty!)
- Nov 1 session: **NO team data**
- Auto-detection result: Team A: 5, Team B: 8 (wrong)

## Recommendation
1. Use `!set_teams` before each round
2. Or create a fixed roster that persists
3. Consider automation: detect teams from Discord voice channels
