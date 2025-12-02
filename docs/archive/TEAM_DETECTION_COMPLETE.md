# Team Detection System - Implementation Complete ✅

## What We Built

### 1. **Correct Team Detector** (`correct_team_detector.py`)
The final working solution that properly detects teams in stopwatch mode.

**Key Discovery:** 
- Must analyze **each map separately** (not all maps at once!)
- Each map has its own Round 1 baseline teams
- Tracks teams through stopwatch swaps (Axis ↔ Allies)

**Features:**
- Per-map team detection
- Stopwatch swap verification
- Cross-map consistency checking
- Handles roster changes between maps

**Verified Working On:**
- Oct 28, 2024 (3v3 match - 5 maps)
- Nov 1-2, 2025 (5v5 match - 4 maps + 1 warmup)

### 2. **Round Analysis Tool** (`analyze_last_session.py`)
Deep round-by-round, map-by-map analysis showing:
- Player rosters per round
- Team swaps between rounds
- Player joins/leaves
- Kill/death/time stats
- Round-wide participation summary

### 3. **Supporting Scripts**

**Diagnostic Tools:**
- `comprehensive_round_analyzer.py` - Full verbose round analysis
- `inspect_oct28_round1.py` - Raw data inspection
- `check_round2_swap.py` - Stopwatch swap verification
- `verify_oct28.py` - Team structure verification
- `find_good_sessions.py` - Find sessions with proper data
- `check_duplicate_root_cause.py` - Debug duplicate records
- `find_correct_table.py` - Database schema investigation

**Detection Attempts (Learning Process):**
- `stopwatch_team_tracker.py` - Early GUID tracking attempt
- `fixed_team_detector.py` - Deduplication approach
- `real_team_detector.py` - Co-occurrence analysis

## Critical Discoveries

### The Data Structure Problem

**Initial Problem:**
When querying ALL maps at once, every player appeared on BOTH Axis AND Allies, creating massive confusion.

**Root Cause:**
The `player_comprehensive_stats` table contains:
1. **Multiple snapshots per round** (periodic stat updates during gameplay)
2. **All maps lumped together** (no separation by map in queries)

**Solution:**
1. **Deduplicate** using `ROW_NUMBER() OVER (PARTITION BY player_guid, round, team ORDER BY time_played DESC)`
2. **Query per-map** separately, not all maps at once
3. **Use Round 1 of each map** as baseline for team assignment

### Stopwatch Mode Explained

In stopwatch (standard competitive ET mode):
- **Round 1:** Team A plays Axis, Team B plays Allies
- **Round 2:** Teams SWAP - Team A plays Allies, Team B plays Axis
- **Goal:** Each team tries to beat the other's time when attacking

**Detection Strategy:**
1. Get Round 1 rosters: Axis players = Team A, Allies players = Team B
2. Track those GUIDs through Round 2
3. Verify they swapped sides (Team A now on Allies, Team B now on Axis)

## Example Round Analysis

### Oct 28, 2024 - Perfect 3v3 Match

**Team A:** .olz, noProne.lgz, v_kt_r  
**Team B:** carniee, endekk, wajs

**5 Maps Played:**
1. etl_adlernest ✅ Perfect stopwatch
2. supply ✅ Perfect stopwatch  
3. sw_goldrush_te ✅ Perfect stopwatch
4. etl_sp_delivery ✅ Perfect stopwatch
5. te_escape2 ⚠️ Fun/warmup map (all players mixed)

### Nov 1-2, 2025 - 5v5 with Substitutes

**Team Slomix (5):** Imbecil, SuperBoyy, carniee, endekk, olz  
**Team RipaZha (5):** sNozji, tokYo, zubl1k, antii', dAFF  
**Substitutes:** //^?/M team (3 players) joined ripazha on some maps

**4 Competitive Maps:**
1. etl_sp_delivery ✅ 5v5 pure
2. supply ✅ 5v8 (ripazha + substitutes)
3. sw_goldrush_te ⚠️ Mixed
4. etl_adlernest (Nov 2) ✅ 5v5 pure

## Database Schema

### Key Table: `player_comprehensive_stats`
```sql
- round_date TEXT
- map_name TEXT  
- round_number INTEGER
- player_guid TEXT
- player_name TEXT
- team INTEGER (1=Axis, 2=Allies)
- kills, deaths, damage_given, etc.
- time_played_minutes REAL
```

### Key Table: `session_teams`
```sql
- round_start_date TEXT
- map_name TEXT
- team_name TEXT
- player_guids JSON
- player_names JSON
```

## Usage Examples

### Detect Teams for a Session
```bash
python correct_team_detector.py 2024-10-28
```

### Analyze Session in Detail
```bash
python analyze_last_session.py
```

### Find Sessions with Good Data
```bash
python find_good_sessions.py
```

## Integration Points

### For Bot Integration (`bot/cogs/last_session_cog.py`):

```python
from bot.core.correct_team_detector import detect_session_teams

# Detect teams for a round
result = detect_session_teams("2024-10-28")

# Get team rosters
team_a_guids = result['team_a']  
team_b_guids = result['team_b']
player_names = result['names']

# Store in session_teams table
cursor.execute("""
    INSERT INTO session_teams (session_start_date, team_name, player_guids, player_names)
    VALUES (?, ?, ?, ?)
""", (round_date, "Team A", json.dumps(list(team_a_guids)), 
      json.dumps([player_names[g] for g in team_a_guids])))
```

## Next Steps

### Immediate:
1. ✅ Team detection working for per-map analysis
2. ⬜ Move `correct_team_detector.py` to `bot/core/`
3. ⬜ Integrate with `team_manager.py`
4. ⬜ Update `last_session_cog.py` to use new detection

### Future Enhancements:
1. **Historical Re-detection:** Run on all past sessions to populate `session_teams`
2. **Substitution Tracking:** Expand to track player substitutions formally
3. **Team Naming:** Auto-detect clan tags (slomix, ripazha, //^?/M)
4. **Confidence Scoring:** Rate detection quality per round
5. **Cross-Session Teams:** Track same teams across multiple rounds

## Files Created

### Production Ready:
- `correct_team_detector.py` ⭐ **Main detector**
- `analyze_last_session.py` ⭐ **Session analysis**

### Documentation:
- `TEAM_DETECTION_COMPLETE.md` (this file)
- `ADVANCED_TEAM_DETECTION.md` (earlier comprehensive docs)
- `SUBSTITUTION_DETECTION.md` (substitution system docs)

### Diagnostic/Development:
- Multiple helper scripts for debugging and verification

## Lessons Learned

1. **Always query per-map** - Critical for accurate team detection
2. **Deduplicate snapshot data** - Take last record per player/round/team
3. **Stopwatch = side swapping** - Track GUIDs, not Axis/Allies labels
4. **Round 1 is baseline** - Establishes which players are on which team
5. **Some maps are warmup/mixed** - Not all maps have organized teams

## Success Metrics

✅ **Accurate detection** on verified sessions (Oct 28, Nov 1-2)  
✅ **Stopwatch swap verification** working perfectly  
✅ **Handles different roster sizes** (3v3, 5v5, 5v8)  
✅ **Detects substitutions** (//^?/M joining ripazha)  
✅ **Cross-map tracking** shows team consistency  

---

**Status:** Production Ready 🚀  
**Last Updated:** November 2, 2025  
**Tested On:** Oct 28, 2024 & Nov 1-2, 2025 sessions
