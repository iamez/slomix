# TODO: Stopwatch Scoring Investigation

## Status: BLOCKED - Need Domain Knowledge

We discovered critical issues with how match winners are calculated, but we don't understand ET:Legacy stopwatch scoring well enough to fix it properly.

---

## What We Know (Facts)

### Stats File Structure
From `c0rnp0rn7.lua` line 291 and 348:
```lua
local winnerteam = tonumber(isEmpty(et.Info_ValueForKey(
    et.trap_GetConfigstring(et.CS_MULTI_MAPWINNER), "w"))) + 1
local header = string.format("%s\\%s\\%s\\%d\\%d\\%d\\%s\\%s\n",
    servername, mapname, config, round, defenderteam, winnerteam, timelimit, nextTimeLimit)
```

**Header format:** `servername\mapname\config\round\defender_team\winner_team\timelimit\actual_time`

### Current Database Behavior
The parser creates 3 database entries per map:
1. **R1 entry** (round_number = 1): Player stats for R1 only
2. **R2 entry** (round_number = 2): Player stats for R2 only (differential)
3. **Match summary** (round_number = 0): Cumulative R1+R2 stats + match winner

### The Parser Bug We Fixed
**File:** `bot/community_stats_parser.py` line 662-674

The R2 differential calculation was NOT including `winner_team`, so R2 database entries had missing/wrong winner data.

**Our "fix":** Intentionally omit `winner_team` from R2 differential since we don't know what it should be.

---

## What We DON'T Know (Mysteries)

### Mystery 1: What does CS_MULTI_MAPWINNER contain?

**Theory A:** Round-specific winner
- R1 file: CS_MULTI_MAPWINNER = who won R1
- R2 file: CS_MULTI_MAPWINNER = who won R2

**Theory B:** Match winner in R2
- R1 file: CS_MULTI_MAPWINNER = who won R1
- R2 file: CS_MULTI_MAPWINNER = who won the MATCH (stopwatch calculation)

**Evidence for Theory A:**
- Makes logical sense that each file contains that round's result
- Simpler implementation
- User suggested this

**Evidence for Theory B:**
- ET:Legacy engine would need to calculate match winner after R2
- More complex but more complete data
- My initial assumption

**How to verify:**
1. Check ET:Legacy source code for CS_MULTI_MAPWINNER behavior
2. Find ET:Legacy documentation on stopwatch mode
3. Test on live server and observe actual behavior

### Mystery 2: Why is defender_team always 1?

**Example from adlernest and supply:**
- R1: defender_team = 1 (Allies)
- R2: defender_team = 1 (Allies again?!)

In traditional stopwatch, teams should SWAP between rounds. So why is the same team defending in both rounds?

**Possible explanations:**
1. `defender_team` doesn't mean what we think (maybe it's starting team or map-specific)
2. This isn't traditional stopwatch mode
3. Teams genuinely didn't swap (custom game mode?)
4. The field is bugged/unreliable

**How to verify:**
- Check ET:Legacy documentation for what defender_team actually represents
- Look at player team assignments across R1 and R2 to see if they swapped

### Mystery 3: Contradictory Data

**Supply map (2026-01-27):**

| Source | R1 Winner | R2 Winner | R2 Outcome |
|--------|-----------|-----------|------------|
| Stats file | Axis (2) | Allies (1) | N/A |
| Database | Axis (2) | Axis (2) ❌ | Fullhold |
| Should be | Axis | ??? | Completed (8:43 < 12:00) |

**Issues:**
1. Database R2 winner doesn't match stats file
2. Database R2 outcome is "Fullhold" but math says it should be "Completed" (8:43 is 197s under 12:00 limit)
3. Match summary shows Allies won, but under competitive stopwatch Axis should win (they completed, Allies didn't?)

---

## Existing Code We Found

### StopwatchScoringService
**File:** `bot/services/stopwatch_scoring_service.py`

This service EXISTS and has stopwatch logic implemented! Lines 60-133 show competitive stopwatch:

```python
def calculate_map_score(self, round1_time_limit, round1_actual_time, round2_actual_time):
    """
    Stopwatch scoring rules:
    - Each map awards 1 point to the winner (not per-round)
    - R1 attackers set the benchmark time
    - R2 attackers must beat the benchmark to win
    - Full hold = attackers fail to complete before time limit
    - Double full hold = 0-0, no one wins the map
    """
```

**Logic:**
- Both complete → faster time wins
- One completes → that team wins
- Both fullhold → 1-1 (tie)

**BUT:** This service is NOT used by the parser! The parser creates match summaries independently.

---

## Questions to Research

### High Priority
1. **What does CS_MULTI_MAPWINNER actually contain in R1 vs R2?**
   - Check ET:Legacy source code
   - Test on live server
   - Find documentation

2. **What stopwatch mode is actually being used?**
   - Independent round scoring (each round = 1 point)
   - Competitive stopwatch (match winner = 1 point)
   - Some other variant

3. **Why is defender_team always 1?**
   - What does this field actually represent?
   - Do teams swap or not?

### Medium Priority
4. **Should we use StopwatchScoringService instead of parser match summaries?**
   - Is the existing service correct?
   - How to integrate it?

5. **Why is the database data contradictory?**
   - Is this all due to the parser bug we found?
   - Or is there deeper data corruption?

---

## Proposed Solutions (BLOCKED until research complete)

### Option A: Remove Match Summaries
- Don't create round_number = 0 entries in parser
- Use StopwatchScoringService to calculate match winners on-demand
- Clean separation of concerns

### Option B: Fix Match Summary Calculation
- Keep match summaries but calculate winner correctly
- Use stopwatch logic in parser (duplicate logic from service)
- More data redundancy

### Option C: Hybrid
- Match summary has cumulative stats but NO winner_team
- Use StopwatchScoringService for actual scoring
- Best of both worlds?

---

## Action Items

### Before Next Coding Session

- [ ] **User:** Research ET:Legacy stopwatch scoring
  - Official documentation
  - Community guides
  - Forum posts
  - Source code if needed

- [ ] **User:** Test on live server
  - Play a stopwatch match
  - Check stats files after R1 and R2
  - Note what CS_MULTI_MAPWINNER shows
  - Note if teams actually swap

- [ ] **User:** Find ET:Legacy developer docs
  - What is CS_MULTI_MAPWINNER?
  - What is defender_team?
  - How does stopwatch scoring work?

### For Next Claude Session

- [ ] Review research findings
- [ ] Decide on correct stopwatch interpretation
- [ ] Implement proper match winner calculation
- [ ] Test against historical data
- [ ] Database rebuild to fix corrupted data

---

## Files Involved

### Parser
- `bot/community_stats_parser.py` - Creates match summaries (line 482-489)

### Scoring Service (UNUSED)
- `bot/services/stopwatch_scoring_service.py` - Has correct logic but not integrated

### Lua Stats Script
- `c0rnp0rn7.lua` - Writes stats files (line 279-358)

### Database
- `rounds` table - Contains R1, R2, and match summary entries
- Round 0 entries have winner_team that might be wrong

---

## Current State (End of Session)

### What We Fixed Today
1. ✅ Match details JavaScript bug
2. ✅ Match details API SQL bug
3. ✅ Team rebalancing
4. ✅ Session scores display added
5. ✅ Removed winner_team from R2 differential (temporary fix)

### What's Broken
1. ❌ Match summaries (round_number = 0) have unreliable winner_team
2. ❌ Session scores might be wrong (counting match summaries that have bad data)
3. ❌ Don't know which stopwatch scoring system to use
4. ❌ Database has contradictory/corrupted historical data

### Safe to Use
- Website match details ✅
- Website session scores ✅ (shows what's in DB, even if DB is wrong)
- Player stats ✅
- Round stats ✅

### NOT Safe to Use
- Match winner determination ❌
- Session W-L records ❌
- Stopwatch scoring calculations ❌

---

## Date Created
January 31, 2026

## Priority
**Medium** - System works, but match scoring is unreliable. Can be fixed later once we understand ET:Legacy stopwatch properly.

## Estimated Complexity
**High** - Requires domain knowledge of ET:Legacy game mechanics that we don't currently have.
