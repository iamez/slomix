# Slomix Analytics Enhancement Roadmap

**Date:** 2026-02-01
**Status:** Proposal for Review

---

## Current State Analysis

### What We Have

| Feature | Status | Data Source |
|---------|--------|-------------|
| Per-player stats (55 fields) | ✅ Complete | `player_comprehensive_stats` |
| Session tracking | ✅ Complete | `gaming_session_id`, 60-min gaps |
| Team detection | ✅ Complete | R1-based, real-time tracking |
| Stopwatch scoring | ✅ Complete | Map wins, timing comparison |
| Matchup analytics | ✅ Basic | `matchup_history` table |
| Player badges | ✅ Complete | Achievement thresholds |
| Leaderboards | ✅ Complete | `!top_dpm`, `!top_kd`, etc. |
| Lua real-time data | ✅ Complete | Timing, pauses, warmup |

### Data We Can Leverage (Currently Underused)

| Field | Potential Use |
|-------|---------------|
| `round_time` (HHMMSS) | Time-of-night analysis |
| `actual_time` vs `time_limit` | Clutch/time pressure analysis |
| `times_revived` / `revives_given` | Medic synergy |
| `most_useful_kills` / `useless_kills` | Impact quality |
| `denied_playtime` | Suppression effectiveness |
| `killing_spree_best` / `death_spree_worst` | Momentum tracking |
| `dynamites_planted` / `defused` | Engineer impact |
| `round_start_unix` / `round_end_unix` | Precise timing |
| `end_reason` | Surrender/objective analysis |

---

## Proposed Enhancements

### 1. PLAYER CONSISTENCY SCORE

**What it measures:**
How reliably a player performs across rounds. Low variance = consistent. High variance = streaky.

**Calculation:**
```python
# Coefficient of variation (CV) for DPM across last N rounds
consistency_score = 1 - (std_dev(dpm) / mean(dpm))
# Scale to 0-100 where 100 = perfectly consistent
```

**Data needed:** Already have `dpm` per round
**Effort:** Low
**Impact:** Medium

**Why useful:**
- Helps with team balancing ("this player is reliable")
- Identifies "feast or famine" players
- Discord command: `!consistency <player>`

---

### 2. CLUTCH RATING

**What it measures:**
Performance in close matches (games decided in final minutes).

**Definition of "clutch situation":**
- Round ends within 90 seconds of time limit (close attack)
- Both teams complete but within 60 seconds of each other

**Calculation:**
```python
# Compare player's DPM/impact in clutch rounds vs normal rounds
clutch_rating = (clutch_dpm - baseline_dpm) / baseline_dpm * 100
```

**Data needed:**
- `actual_time` vs `time_limit` (have it)
- Need to flag rounds as `is_clutch` during import

**Effort:** Medium
**Impact:** High

**Why useful:**
- Identifies "big game players"
- Community loves clutch narratives

---

### 3. MAP AFFINITY

**What it measures:**
How a player's performance varies by map.

**Calculation:**
```python
# For each map, compare player's average DPM to their overall average
map_affinity[map] = (map_dpm - overall_dpm) / overall_dpm * 100

# Example output:
# puran: +18% on mp_beach, -12% on supply
```

**Data needed:** Already have `map_name` per round
**Effort:** Low
**Impact:** Medium

**Why useful:**
- Map veto strategy
- "This is puran's map"
- Discord command: `!map_stats <player>`

---

### 4. SESSION FATIGUE DETECTION

**What it measures:**
Performance decline over a gaming session (late-night fade).

**Calculation:**
```python
# Split session into thirds (early, mid, late)
# Compare DPM in each third
fatigue_index = (late_third_dpm - early_third_dpm) / early_third_dpm * 100

# Negative = fatiguing, Positive = warming up
```

**Data needed:**
- `round_time` within session (have it)
- Need to calculate round order within session

**Effort:** Low
**Impact:** Medium

**Why useful:**
- Know when to stop playing
- "I'm better after warmup" vs "I fade after 2 hours"
- Session summary could include: "Performance dropped 15% in final hour"

---

### 5. ATTACK vs DEFENSE PREFERENCE

**What it measures:**
Player's relative strength on attack vs defense in stopwatch mode.

**Calculation:**
```python
# Track performance when player was on attacking side vs defending
# Use team assignment + defender_team to determine role

attack_dpm = avg DPM when on attacking side
defense_dpm = avg DPM when on defending side
preference = "attacker" if attack_dpm > defense_dpm else "defender"
```

**Data needed:**
- `team` (player's side)
- `defender_team` (which side defends)
- Already have both!

**Effort:** Medium
**Impact:** High

**Why useful:**
- Team building (balance attack/defense players)
- Personal insight ("I should volunteer to attack")
- Discord command: `!playstyle <player>`

---

### 6. TEAMMATE SYNERGY MATRIX

**What it measures:**
How every player pair performs together (extension of existing synergy).

**Calculation:**
```python
# For each player pair who've played together 3+ times:
synergy[A][B] = (A's_dpm_with_B - A's_baseline_dpm) / A's_baseline_dpm * 100

# Bidirectional: A helps B, and B helps A (can differ!)
```

**Data needed:** Already have in `matchup_history` player_stats
**Effort:** Low (extend existing)
**Impact:** High

**Why useful:**
- Optimal team composition
- "These two players elevate each other"
- Discord command: `!team_builder` (suggest optimal lineup)

---

### 7. SUPPRESSION INDEX (Who Shuts Down Whom)

**What it measures:**
When player A faces player B, how much does A underperform?

**Calculation:**
```python
# Already implemented as anti-synergy in matchup_analytics_service
# Enhance to show bidirectional:
# "A suppresses B by -20%, but B suppresses A by -35%"
```

**Data needed:** Already in matchup_history
**Effort:** Low
**Impact:** High

**Why useful:**
- Counter-picking in draft scenarios
- "I need to avoid facing this player"
- Discord command: `!counter <player>` (already have `!nemesis`)

---

### 8. MEDIC PARTNERSHIP SCORE

**What it measures:**
How well medic pairs keep each other alive.

**Calculation:**
```python
# For players who frequently revive each other:
medic_partnership = mutual_revives / (A_deaths + B_deaths)

# Higher = better at keeping each other alive
```

**Data needed:**
- `revives_given`, `times_revived` (have it)
- Need to track WHO revived whom (not in current schema)

**Effort:** High (requires data model change)
**Impact:** Medium

**Schema change needed:**
```sql
-- New table to track revive relationships
CREATE TABLE revive_events (
    round_id INT,
    reviver_guid TEXT,
    revived_guid TEXT,
    timestamp INT
);
```

**Defer for now** - requires Lua script changes.

---

### 9. FUN STATS (Community-Friendly)

Non-toxic celebratory stats for session summaries.

| Stat | Calculation | Why Fun |
|------|-------------|---------|
| **Zombie Mode** | Most `times_revived` | "Kept getting up" |
| **The Wall** | Best defense win rate | Defensive anchor |
| **Glass Cannon** | High DPM + high deaths | High risk, high reward |
| **Silent Assassin** | Best headshot % | Precision player |
| **Team Dad** | Most `revives_given` | Takes care of team |
| **Cleanup Crew** | Most `gibs` | Makes sure they stay down |
| **Demolition Expert** | Most dynamites planted | Engineer special |
| **Bomb Squad** | Most dynamites defused | Counter-engineer |
| **Hot Streak** | Best `killing_spree_best` | Momentum king |
| **Useful Fragger** | Best `most_useful_kills` ratio | Impact kills |

**Data needed:** All available in current schema
**Effort:** Low
**Impact:** High (community loves these)

**Implementation:**
Add to `!last_session` output or new `!awards` command.

---

### 10. MAP FATIGUE (Same Map Repeated)

**What it measures:**
Performance decline when the same map is played multiple times in a session.

**Calculation:**
```python
# When map X is played 2nd or 3rd time in session:
map_fatigue = (nth_play_dpm - 1st_play_dpm) / 1st_play_dpm * 100
```

**Data needed:** Already have - just need to count map occurrences per session
**Effort:** Low
**Impact:** Low-Medium

**Why useful:**
- "We've played this map 3 times, we're getting worse"
- Map rotation suggestions

---

## Implementation Priority

### Phase 1: Quick Wins (Low Effort, High Value)

1. **Fun Stats / Awards** - Immediate community engagement
2. **Map Affinity** - Already have data
3. **Session Fatigue** - Already have data
4. **Consistency Score** - Simple calculation

### Phase 2: Core Analytics (Medium Effort, High Value)

5. **Attack vs Defense Preference** - Uses existing data
6. **Teammate Synergy Matrix** - Extends matchup service
7. **Clutch Rating** - Needs round flagging

### Phase 3: Advanced Features (Higher Effort)

8. **Enhanced Suppression Index** - Bidirectional display
9. **Map Fatigue** - Nice to have
10. **Medic Partnership** - Requires schema change (defer)

---

## Schema Changes Needed

### Minimal Changes (Phase 1-2)

```sql
-- Add clutch flag to rounds
ALTER TABLE rounds ADD COLUMN is_clutch BOOLEAN DEFAULT FALSE;

-- Add fatigue tracking to player stats (optional, can calculate on-the-fly)
ALTER TABLE player_comprehensive_stats ADD COLUMN round_order_in_session INT;

-- Add map play count within session
ALTER TABLE player_comprehensive_stats ADD COLUMN map_play_number INT DEFAULT 1;
```

### Future Changes (Phase 3)

```sql
-- Revive relationship tracking (requires Lua changes)
CREATE TABLE revive_events (
    id SERIAL PRIMARY KEY,
    round_id INT REFERENCES rounds(id),
    reviver_guid TEXT NOT NULL,
    revived_guid TEXT NOT NULL,
    game_time_seconds INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Discord Commands Summary

### Existing (Keep)
- `!stats <player>` - Lifetime stats
- `!last_session` - Session summary
- `!matchup A vs B` - Lineup comparison
- `!synergy A B` - Teammate synergy
- `!nemesis <player>` - Who counters you

### New (Proposed)

| Command | Description | Phase |
|---------|-------------|-------|
| `!consistency <player>` | Variance/reliability score | 1 |
| `!map_stats <player>` | Per-map performance | 1 |
| `!playstyle <player>` | Attack/defense preference | 2 |
| `!clutch <player>` | Performance in close games | 2 |
| `!team_builder` | Suggest optimal lineup | 2 |
| `!awards` | Fun stats for session | 1 |
| `!fatigue` | Session performance trend | 1 |

---

## Summary

**Total proposed features:** 10
**Features using existing data:** 8
**Features needing schema changes:** 2

**Recommended first implementation:**
1. Fun Stats (community engagement)
2. Map Affinity (simple, useful)
3. Consistency Score (complements existing stats)

These three can be shipped in one update with minimal risk.
