# Data Accuracy Report - Website vs Database

**Date**: February 9, 2026
**Status**: ⚠️ CRITICAL DATA DISCREPANCIES FOUND

---

## Executive Summary

Comparison of website API responses against direct database queries reveals **significant data accuracy issues**:

- ❌ **Session total kills off by 6x** (139 vs 22)
- ❌ **Missing database migration** (`total_kills` column doesn't exist)
- ❌ **Many API endpoints return 404 Not Found**
- ✅ Website server is running and sessions endpoint responds
- ✅ Database has correct data

---

## Database Ground Truth

### Overall Stats (from PostgreSQL)

| Metric | Value | Source |
|--------|-------|--------|
| Total rounds | 1,657 | `SELECT COUNT(*) FROM rounds` |
| Unique players | 32 | `SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats` |
| Total sessions | 87 | `SELECT COUNT(DISTINCT gaming_session_id) FROM rounds` |
| Latest session ID | 87 | `SELECT MAX(gaming_session_id) FROM rounds` |

### Top 5 Players by DPM (from PostgreSQL)

| Rank | Player GUID | Name | Avg DPM | Total Kills | K/D Ratio | Rounds |
|------|-------------|------|---------|-------------|-----------|--------|
| 1 | 31B54D18 | Peep | 505.97 | 306 | 1.22 | 15 |
| 2 | 3C0354D3 | squAze Bros | 505.06 | 592 | 1.60 | 43 |
| 3 | 1C8F69CA | //^?/M.Demonslayer | 460.13 | 420 | 1.27 | 21 |
| 4 | 2B5938F5 | bronzelow- | 449.59 | 11,477 | 1.37 | 791 |
| 5 | D8423F90 | vid | 443.50 | 19,279 | 1.19 | 1,426 |

### Session 87 Details (from PostgreSQL)

| Metric | Value |
|--------|-------|
| Session ID | 87 |
| Date | 2026-02-06 |
| Rounds | 1 |
| Maps played | 1 (etl_adlernest) |
| Players | 6 |
| **Total kills** | **22** |

#### Session 87 Player Breakdown (from PostgreSQL)

| Player | Kills | Deaths | DPM | K/D |
|--------|-------|--------|-----|-----|
| Cru3lzor. | 7 | 2 | 10.65 | 3.50 |
| Proner2026 | 6 | 1 | 10.06 | 6.00 |
| bronze. | 3 | 3 | 14.87 | 1.00 |
| .olz | 3 | 4 | 10.18 | 0.75 |
| SuperBoyy | 2 | 6 | 10.70 | 0.33 |
| .wajs | 1 | 6 | 4.77 | 0.17 |
| **TOTAL** | **22** | **22** | - | - |

---

## Website API Responses

### Sessions Endpoint: `/api/sessions`

**Status**: ✅ Working (returns data)

Session 87 from API:
```json
{
  "date": "2026-02-06",
  "session_id": 87,
  "rounds": 1,
  "maps": 1,
  "players": 6,
  "total_kills": 139,  // ❌ WRONG! Should be 22
  "maps_played": ["etl_adlernest"],
  "allies_wins": 0,
  "axis_wins": 0,
  "draws": 0,
  "time_ago": "3 days ago",
  "formatted_date": "Friday, February 06, 2026"
}
```

### Leaderboard Endpoint: `/api/leaderboard`

**Status**: ❌ 404 Not Found

### Records Endpoint: `/api/records`

**Status**: ❌ 404 Not Found

### Session Detail: `/api/session/87`

**Status**: ❌ 404 Not Found

### Greatshot Topshots: `/greatshot/topshots/kills`

**Status**: ❌ 404 Not Found

---

## Critical Data Discrepancies

### Issue #1: Session 87 Total Kills Mismatch

| Source | Total Kills | Status |
|--------|-------------|--------|
| **Database (correct)** | 22 | ✅ Verified by summing player kills |
| **Website API** | 139 | ❌ **Off by 117 kills (6.3x error)** |

**Impact**: CRITICAL - Users seeing incorrect statistics

**Possible Causes**:
1. Website might be counting kills from wrong session
2. Query aggregation bug in website service layer
3. Caching issue showing stale/merged data
4. R1/R2 differential calculation error

**Verification Query**:
```sql
-- This confirms database has correct data
SELECT SUM(kills) FROM player_comprehensive_stats p
JOIN rounds r ON p.round_id = r.id
WHERE r.gaming_session_id = 87;
-- Result: 22 ✅
```

### Issue #2: Missing Database Migration

**Finding**: The `total_kills` column I added for Greatshot optimization doesn't exist in the actual database.

**Evidence**:
```sql
SELECT total_kills FROM greatshot_analysis;
-- Error: column ga.total_kills does not exist
```

**Impact**:
- ❌ Topshots optimization won't work
- ❌ Queries will use slow file-reading method
- ❌ May cause 500 errors on topshots endpoints

**Current Schema** (from `mcp__db__search_objects`):
- `greatshot_analysis` has only 5 columns:
  - demo_id
  - metadata_json
  - stats_json
  - events_json
  - created_at
- **Missing**: total_kills column

**Required Action**: Run migration to add column:
```sql
ALTER TABLE greatshot_analysis ADD COLUMN total_kills INTEGER DEFAULT 0;
```

### Issue #3: Multiple API Endpoints Non-Functional

**404 Not Found**:
- `/api/leaderboard` - Leaderboard rankings
- `/api/records` - All-time records
- `/api/session/{id}` - Session details
- `/greatshot/topshots/kills` - Top kills leaderboard

**Impact**: Unknown - these endpoints may not be implemented yet or routing is broken.

---

## Greatshot Data

### Database Status

| Metric | Value |
|--------|-------|
| Total demos | 1 |
| Analyzed demos | 1 |
| Failed demos | 0 |
| Processing demos | 0 |
| Highlights detected | 13 |
| Renders queued | 0 |

**Schema Issues**:
- ❌ `total_kills` column missing
- ✅ Other columns present and functional

---

## Comparison Summary

### What Matches ✅

| Metric | Database | Website | Status |
|--------|----------|---------|--------|
| Session 87 ID | 87 | 87 | ✅ Match |
| Session 87 date | 2026-02-06 | 2026-02-06 | ✅ Match |
| Session 87 rounds | 1 | 1 | ✅ Match |
| Session 87 maps | 1 | 1 | ✅ Match |
| Session 87 players | 6 | 6 | ✅ Match |

### What's Broken ❌

| Metric | Database | Website | Discrepancy |
|--------|----------|---------|-------------|
| **Session 87 total kills** | **22** | **139** | **❌ 117 kills difference** |
| Leaderboard endpoint | N/A | 404 | ❌ Not working |
| Records endpoint | N/A | 404 | ❌ Not working |
| Session detail endpoint | N/A | 404 | ❌ Not working |
| Topshots endpoint | N/A | 404 | ❌ Not working |
| `total_kills` column | Doesn't exist | Expected | ❌ Migration not applied |

---

## Root Cause Analysis

### Session Kills Discrepancy

**Hypothesis 1: Wrong Session Aggregation**
- Website might be querying wrong session ID
- Could be combining multiple sessions
- Test: Check if 139 = sum of kills from multiple sessions

**Hypothesis 2: R1/R2 Double Counting**
- Website might be counting R1 and R2 separately
- Should use differential for R2 only
- Test: Check if session has R1+R2 that sum to 139

**Hypothesis 3: Caching Issue**
- 5-minute TTL cache might have stale data
- Could be showing old session merged with new
- Test: Clear cache and re-query

**Hypothesis 4: Query Bug in Website Service**
- `website/backend/services/website_session_data_service.py` might have aggregation bug
- Could be missing WHERE clause or GROUP BY
- Test: Review service layer code

### Missing Endpoints

**Possible Causes**:
1. Routes not registered in FastAPI app
2. Different URL paths than expected
3. Features not implemented yet
4. Import errors preventing router loading

---

## Testing Recommendations

### Immediate (High Priority)

1. **Investigate session kills discrepancy**
   ```bash
   # Check website service layer code
   grep -r "total_kills" website/backend/services/

   # Check session aggregation query
   grep -r "gaming_session_id = 87" website/backend/
   ```

2. **Run database migration**
   ```sql
   ALTER TABLE greatshot_analysis ADD COLUMN IF NOT EXISTS total_kills INTEGER DEFAULT 0;
   ```

3. **Test website endpoints systematically**
   ```bash
   # List all registered routes
   python3 -c "from website.backend.main import app; print([r.path for r in app.routes])"
   ```

4. **Compare more sessions**
   - Check if discrepancy exists for other sessions
   - Verify if it's session-specific or systemic

### Medium Priority

1. **Clear website cache and retest**
2. **Check website logs for errors**
3. **Review session aggregation service code**
4. **Test bot commands vs database**

### Low Priority

1. **Performance test topshots after migration**
2. **End-to-end Greatshot pipeline test**
3. **Verify all 77 API endpoints claimed**

---

## Required Actions Before Production

### CRITICAL (Must Fix)

- [ ] **Fix session total kills discrepancy** - 6x error is unacceptable
- [ ] **Run database migration** for `total_kills` column
- [ ] **Investigate why 4+ endpoints return 404**
- [ ] **Verify website service layer queries are correct**

### Important (Should Fix)

- [ ] Test bot commands and compare to database
- [ ] Check all sessions for similar discrepancies
- [ ] Review caching strategy for accuracy
- [ ] Audit all aggregation queries in service layer

### Nice to Have

- [ ] Document which API endpoints actually exist
- [ ] Create automated data accuracy tests
- [ ] Set up monitoring for data drift

---

## Root Cause Identified! 🎯

**File**: `website/backend/routers/api.py` lines 2592-2595

The website uses the **OLD BROKEN JOIN pattern** that was already fixed in the bot months ago:

```python
# WEBSITE (WRONG):
INNER JOIN player_comprehensive_stats p
    ON r.round_date = p.round_date
    AND r.map_name = p.map_name
    AND r.round_number = p.round_number

# BOT (CORRECT):
JOIN player_comprehensive_stats p
    ON p.round_id = r.id
```

**Impact**: Website matches ALL rounds from the same day with the same map, causing massive overcounting.

**Fix**: Change ONE JOIN clause to use `round_id` foreign key instead of date+map+round composite key.

**See**: `WEBSITE_STAT_BUGS_FOUND.md` for complete analysis and fix instructions.

---

## Conclusion

**The website is NOT showing accurate data.**

While the website server is running and some endpoints work, there is a critical data accuracy issue:
- Session 87 shows **139 kills** on website vs **22 kills** in database
- This represents a **6.3x error** that would completely mislead users

**This validates your concern** about not trusting the 98% completeness claim without runtime verification.

**Status**: ⚠️ **Website data is unreliable - DO NOT use in production until fixed**

---

## Next Steps

1. **Investigate service layer code** - Find why session aggregation is wrong
2. **Run database migration** - Add missing `total_kills` column
3. **Test more sessions** - Determine if issue is systemic
4. **Review bot output** - Compare bot `!last_session` to database
5. **Fix discrepancies** - Correct queries before any production use

---

**Report Generated**: February 9, 2026
**Database Queries**: 8 successful
**Website Endpoints Tested**: 6 (2 working, 4 failing)
**Critical Issues Found**: 3
**Recommendation**: **DO NOT DEPLOY until data accuracy is verified and fixed**
