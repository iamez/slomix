# Greatshot Cross-Reference Enhancement Plan

**Date:** 2026-02-08
**Status:** Prototype → Production Enhancement
**Current Issue:** Database cross-reference shows "Not Found" for most demos

---

## Problem Analysis

### Current State

**Cross-reference logic** (`greatshot_crossref.py`) matches demos to stats database by:
1. Map name (LOWER match) - 30% confidence
2. Duration (±5s tolerance) - 30% confidence
3. Winner (axis/allies) - 20% confidence
4. Scores (first/second place) - 20% confidence

**Minimum confidence:** 30% (map name only)

### Why It's Failing

1. **Demo filenames ≠ stats filenames**
   - Demo: `player_recording_2026-02-08.dm_84`
   - Stats: `2026-02-08-143022-te_escape2-round-1.txt`

2. **Duration mismatch**
   - Demos include warmup time
   - Stats files show gameplay time only
   - Example: Demo 25min, Stats 20min → 5min difference = no match

3. **Winner not extracted**
   - UDT `matchStats.winner` may be null/invalid
   - Depends on demo being recorded until endgame

4. **Scores not extracted**
   - UDT `firstPlaceScore`/`secondPlaceScore` may be null
   - Only populated if demo captures full scoreboard

5. **Multiple rounds in one demo**
   - Demos can contain both R1+R2
   - Current logic only checks first round
   - Need to match against BOTH rounds in database

---

## Enhancement Strategy

### Phase 1: Improve Metadata Extraction ✅ (Already Done)

**Current extraction** (`scanner/api.py` lines 357-375):
```python
metadata = {
    "map": "te_escape2",
    "duration_ms": 1200000,  # 20 minutes
    "rounds": [
        {
            "start_ms": 0,
            "end_ms": 600000,
            "duration_ms": 600000,
            "winner": "axis",
            "first_place_score": 3,
            "second_place_score": 1
        }
    ]
}
```

**What we extract:**
✅ Map name
✅ Duration (per round + total)
✅ Winner (per round)
✅ Scores (per round)
✅ Player stats (kills, deaths, damage, accuracy)

### Phase 2: Enhance Matching Logic (TODO)

#### A. Multi-Round Matching

**Current:** Only checks `rounds[0]`
**Enhancement:** Check ALL rounds in demo

```python
# For each round in demo
for demo_round in metadata.get("rounds", []):
    # Find matching round in database
    # Duration tolerance: ±30s (account for warmup)
    # Match by: map + duration + winner + scores
```

#### B. Fuzzy Duration Matching

**Current:** ±5s tolerance
**Enhancement:** ±30s tolerance (account for warmup/pauses)

```python
# Demo might have:
# - Warmup (2-5 min)
# - Pauses (variable)
# - Overtime (variable)

# Relaxed matching:
if diff <= 30:  # Was 5s
    confidence += 30.0
elif diff <= 60:
    confidence += 15.0
```

#### C. Filename-Based Hints

**Current:** Ignores demo filename
**Enhancement:** Extract date from filename

```python
# Demo: "2026-02-08-capture.dm_84"
# Stats: "2026-02-08-143022-te_escape2-round-1.txt"

# Extract date from demo filename
import re
date_pattern = r'(\d{4}-\d{2}-\d{2})'
match = re.search(date_pattern, demo_filename)
if match:
    demo_date = match.group(1)
    # Filter candidates to same date
    candidates = [r for r in candidates if r.round_date == demo_date]
```

#### D. Player-Based Validation

**Current:** Only uses map/duration/winner/scores
**Enhancement:** Validate by player participation

```python
# Get players from demo
demo_players = set([p["name"] for p in player_stats])

# Get players from database round
db_players = set([
    SELECT DISTINCT player_name
    FROM player_comprehensive_stats
    WHERE round_id = ?
])

# Calculate player overlap
overlap = len(demo_players & db_players) / max(len(demo_players), 1)

# Add confidence boost
if overlap >= 0.8:  # 80% of players match
    confidence += 20.0
elif overlap >= 0.5:
    confidence += 10.0
```

#### E. Stats Comparison Validation

**Current:** Matches demo to round, then compares stats
**Enhancement:** Use stats comparison to VALIDATE match

```python
# After finding candidate match, compare stats
demo_kill_total = sum([p.get("kills", 0) for p in demo_stats])
db_kill_total = sum([SELECT SUM(kills) FROM player_comprehensive_stats WHERE round_id = ?])

# If stats are wildly different, reduce confidence
kill_diff_pct = abs(demo_kill_total - db_kill_total) / max(db_kill_total, 1)
if kill_diff_pct > 0.2:  # 20% difference
    confidence -= 20.0  # Probably wrong match
```

---

## Implementation Plan

### Step 1: Enhance Duration Tolerance (Quick Win)

**File:** `website/backend/services/greatshot_crossref.py`
**Change:** Line 98, increase tolerance from 5s to 30s

```python
# Before:
if diff <= 5:
    confidence += 30.0

# After:
if diff <= 30:  # Account for warmup/pauses
    confidence += 30.0
elif diff <= 60:
    confidence += 15.0
```

**Impact:** Will match more demos immediately

### Step 2: Add Multi-Round Support

**File:** `website/backend/services/greatshot_crossref.py`
**Change:** Loop through all demo rounds, return best match

```python
async def find_matching_round(metadata, db):
    rounds_info = metadata.get("rounds") or []
    if not rounds_info:
        # Try matching with total duration
        return await _match_single_round(metadata, db, None)

    best_match = None
    best_confidence = 0.0

    # Try to match each demo round
    for i, demo_round in enumerate(rounds_info):
        match = await _match_single_round(metadata, db, demo_round)
        if match and match["confidence"] > best_confidence:
            best_match = match
            best_confidence = match["confidence"]

    return best_match
```

### Step 3: Add Filename Date Extraction

**File:** `website/backend/services/greatshot_crossref.py`
**Add:** Extract date from demo filename, filter candidates by date

```python
import re

def _extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract YYYY-MM-DD from filename if present."""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    return match.group(1) if match else None

async def find_matching_round(metadata, db):
    demo_map = (metadata.get("map") or "").lower().strip()
    demo_filename = metadata.get("filename", "")
    demo_date = _extract_date_from_filename(demo_filename)

    # Build query with optional date filter
    if demo_date:
        candidates = await db.fetch_all(
            """SELECT ... FROM rounds r
               WHERE LOWER(r.map_name) = $1
               AND r.round_date = $2
               ORDER BY r.round_date DESC, r.round_time DESC
               LIMIT 50""",
            (demo_map, demo_date),
        )
    else:
        # Fallback to just map name
        ...
```

### Step 4: Add Player Overlap Validation

**File:** `website/backend/services/greatshot_crossref.py`
**Add:** Calculate player name overlap, boost confidence

```python
async def _calculate_player_overlap(demo_players, round_id, db):
    """Calculate percentage of player overlap between demo and DB round."""
    db_result = await db.fetch_all(
        "SELECT DISTINCT player_name FROM player_comprehensive_stats WHERE round_id = $1",
        (round_id,)
    )
    db_players = set([row[0].lower().strip() for row in db_result])
    demo_player_names = set([p.lower().strip() for p in demo_players])

    if not demo_player_names:
        return 0.0

    overlap = len(demo_player_names & db_players)
    return overlap / len(demo_player_names)

# In find_matching_round:
# ... after calculating base confidence
if player_stats_available:
    overlap = await _calculate_player_overlap(demo_player_names, round_id, db)
    if overlap >= 0.8:
        confidence += 20.0
        match_details.append(f"players-overlap-{int(overlap*100)}%")
    elif overlap >= 0.5:
        confidence += 10.0
```

### Step 5: Stats Validation (Advanced)

**File:** `website/backend/services/greatshot_crossref.py`
**Add:** Compare aggregate stats (kills, damage) to validate match

```python
async def _validate_stats_match(demo_player_stats, round_id, db):
    """Compare demo stats to DB stats, return confidence adjustment."""
    if not demo_player_stats:
        return 0.0

    demo_kills = sum([p.get("kills", 0) for p in demo_player_stats.values()])

    db_result = await db.fetch_one(
        "SELECT SUM(kills) as total_kills FROM player_comprehensive_stats WHERE round_id = $1",
        (round_id,)
    )
    db_kills = db_result[0] if db_result and db_result[0] else 0

    if db_kills == 0:
        return 0.0

    diff_pct = abs(demo_kills - db_kills) / db_kills

    if diff_pct <= 0.05:  # Within 5%
        return 15.0  # High confidence
    elif diff_pct <= 0.15:  # Within 15%
        return 5.0   # Some confidence
    elif diff_pct >= 0.5:  # 50%+ difference
        return -30.0  # Probably wrong match
    else:
        return 0.0
```

---

## Testing Strategy

### Test Case 1: Single Round Demo
- Upload demo with 1 round (R1 only)
- Should match to corresponding R1 in database
- Confidence > 50% expected

### Test Case 2: Full Match Demo (R1+R2)
- Upload demo with both rounds
- Should match to R1 OR R2 (best match)
- Consider: Should we return BOTH matches?

### Test Case 3: Demo with Warmup
- Upload demo with 5min warmup + 20min gameplay
- Database shows 20min duration
- Demo shows 25min duration
- Should still match with duration tolerance

### Test Case 4: Different Day
- Upload old demo from 2025-12-01
- Should match to correct date in database
- Should NOT match to recent rounds on different maps

### Test Case 5: Partial Player Match
- Demo has 6 players (A, B, C, D, E, F)
- Database round has 8 players (A, B, C, D, G, H, I, J)
- 50% overlap → should boost confidence by 10%

---

## Configuration Options

Add to `greatshot/config.py`:

```python
# Cross-reference matching thresholds
CROSSREF_DURATION_TOLERANCE_SECONDS = 30  # Was 5
CROSSREF_MIN_CONFIDENCE = 40  # Minimum to show match (was 30)
CROSSREF_PLAYER_OVERLAP_WEIGHT = 20  # Confidence boost for player match
CROSSREF_STATS_VALIDATION_WEIGHT = 15  # Confidence boost for stats match
CROSSREF_USE_FILENAME_DATE = True  # Extract date from filename
CROSSREF_MULTI_ROUND_MATCHING = True  # Try to match all demo rounds
```

---

## Expected Outcomes

### Before Enhancement
- Match rate: ~10-20% (only perfect matches with exact duration)
- "Not Found" on most demos

### After Enhancement (Phase 1-3)
- Match rate: ~60-70% (relaxed duration, date filtering, multi-round)
- Confidence scores more meaningful

### After Enhancement (Phase 4-5)
- Match rate: ~80-90% (player validation, stats comparison)
- High confidence on correct matches
- Low confidence warnings on questionable matches

---

## Migration Path

1. ✅ **Current state:** Cross-reference works but rarely finds matches
2. 🔧 **Phase 1 (Quick Win):** Increase duration tolerance to 30s
3. 🔧 **Phase 2 (Medium Effort):** Add multi-round matching
4. 🔧 **Phase 3 (Medium Effort):** Add filename date extraction
5. 🚀 **Phase 4 (Advanced):** Add player overlap validation
6. 🚀 **Phase 5 (Advanced):** Add stats comparison validation

**Recommendation:** Implement Phase 1-3 first (quick wins), test with real data, then consider Phase 4-5 if needed.

---

## User-Facing Features

### Current
```
Database Cross-Reference
Cross-reference failed: Not Found
```

### After Enhancement
```
Database Cross-Reference
✅ Matched to Round #12345 (Confidence: 85%)
Map: te_escape2
Date: 2026-02-08 14:30
Match Quality:
  ✅ Map name exact match
  ✅ Duration within 8s
  ✅ Winner matches (axis)
  ⚠️ Scores not available in demo
  ✅ 83% player overlap (5/6 players)

[View Full Stats Comparison]
```

---

## API Changes Required

### New Query Parameter
```
GET /api/greatshot/{demo_id}/crossref?min_confidence=40
```

### Enhanced Response
```json
{
  "matched": true,
  "confidence": 85,
  "round_id": 12345,
  "match_quality": {
    "map_match": true,
    "duration_diff_seconds": 8,
    "winner_match": true,
    "scores_match": false,
    "player_overlap_pct": 83,
    "stats_validation": "high"
  },
  "round_details": { ... },
  "stats_comparison": [ ... ]
}
```

---

**Status:** Ready for implementation
**Effort:** Phase 1-3 = 2-4 hours, Phase 4-5 = 4-6 hours
**Priority:** HIGH (blocks Greatshot production use)
