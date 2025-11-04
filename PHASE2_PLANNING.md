# Phase 2: Session → Round Terminology Rename

**Status:** 📋 PLANNED (Not Yet Implemented)  
**Type:** BREAKING CHANGE  
**Prerequisite:** Phase 1 Complete ✅

---

## Overview

Phase 2 will fix the Day 0 terminology mistake by renaming:
- `rounds` table → `rounds` table
- `round_id` → `round_id` (in all tables and foreign keys)
- All code references updated throughout entire codebase

This is a **BREAKING CHANGE** that requires database migration and extensive testing.

---

## Why Phase 2 is Needed

### Current Problem (Day 0 Mistake)
```
Database says "session" but means "round"
- rounds table stores ROUNDS (12 minutes each)
- round_id refers to individual ROUNDS
- Gaming sessions (2-3 hours) are tracked separately via gaming_session_id
```

### After Phase 2
```
Terminology will be correct:
- rounds table stores ROUNDS (12 minutes each)
- round_id refers to individual ROUNDS
- gaming_session_id tracks entire gaming sessions (2-3 hours)
- match_id links R1+R2 pairs (24 minutes)
```

---

## Scope (From Comprehensive Audit)

### Files to Update: 100+

**Critical Files:**
- `database_manager.py` - 50+ instances
- `bot/cogs/last_session_cog.py` - 60+ instances
- `bot/ultimate_bot.py` - 100+ instances
- All other cogs and bot files
- 60+ utility scripts
- All documentation

**Total Changes:** ~800+ occurrences across codebase

---

## Migration Strategy

### Step 1: Database Schema Migration
```sql
-- Create new rounds table with correct naming
CREATE TABLE rounds (
    id INTEGER PRIMARY KEY,
    gaming_session_id INTEGER,
    match_id INTEGER,
    round_number INTEGER,
    -- ... all other columns same as sessions
);

-- Copy all data
INSERT INTO rounds SELECT * FROM rounds;

-- Update foreign keys in dependent tables
UPDATE player_comprehensive_stats 
SET round_id = round_id;

UPDATE weapon_comprehensive_stats 
SET round_id = round_id;

-- Drop old table
DROP TABLE sessions;

-- Recreate indexes
CREATE INDEX idx_gaming_session_id ON rounds(gaming_session_id);
CREATE INDEX idx_round_date_time ON rounds(round_date, round_time);
```

### Step 2: Code Updates

**Priority Order:**
1. Core data layer (`database_manager.py`)
2. Bot cogs (all Discord commands)
3. Utility scripts
4. Documentation

**Find & Replace:**
- `rounds` → `rounds` (table name)
- `round_id` → `round_id` (column/variable)
- `round_date` → `round_date`
- `round_time` → `round_time`
- Functions: `create_session()` → `create_round()`
- Functions: `get_session()` → `get_round()`

**Careful Exceptions (DO NOT RENAME):**
- `gaming_session_id` (keep as-is)
- `_session` (Discord session objects)
- `session_start_time` (gaming session tracking)

### Step 3: Testing

**Test Coverage Required:**
1. Database migration validates correctly
2. All foreign keys intact
3. All bot commands work
4. All queries return correct data
5. Performance unchanged
6. No data loss

**Test Commands:**
- `!stats` - Player statistics
- `!last_round` - Gaming session display
- `!leaderboard` - Rankings
- `!session` - Individual round details
- Manual imports work
- Auto-imports work

---

## Implementation Checklist

### Pre-Implementation
- [ ] Create `phase2-rename` branch
- [ ] Backup production database
- [ ] Review COMPLETE_SESSION_TERMINOLOGY_AUDIT.md
- [ ] Create comprehensive test suite
- [ ] Plan rollback strategy

### Database Migration
- [ ] Write migration script
- [ ] Test on backup database
- [ ] Validate all data copied correctly
- [ ] Verify foreign key integrity
- [ ] Check index performance

### Code Updates
- [ ] Update database_manager.py
- [ ] Update all bot cogs
- [ ] Update utility scripts
- [ ] Update documentation
- [ ] Fix all imports/references

### Testing
- [ ] Run full test suite
- [ ] Test all Discord commands
- [ ] Test manual imports
- [ ] Test auto-imports
- [ ] Load testing (performance)
- [ ] Edge case testing

### Deployment
- [ ] Merge to team-system branch
- [ ] Create backup point
- [ ] Deploy to production
- [ ] Monitor for 24 hours
- [ ] Document any issues

---

## Risks & Mitigation

### Risk 1: Data Loss
**Mitigation:** 
- Full database backup before migration
- Test migration on copy first
- Validate row counts match

### Risk 2: Breaking Bot Commands
**Mitigation:**
- Comprehensive testing before deployment
- Keep Phase 1 branch as rollback point
- Deploy during low-usage time

### Risk 3: Performance Degradation
**Mitigation:**
- Recreate all indexes after migration
- Test query performance
- Monitor for 24 hours post-deployment

### Risk 4: Foreign Key Breakage
**Mitigation:**
- Map all foreign key relationships first
- Update in correct order
- Validate with queries after migration

---

## Timeline Estimate

**Preparation:** 2-4 hours
- Review audit document
- Create migration script
- Set up test environment

**Implementation:** 4-6 hours
- Run database migration
- Update all code files
- Fix compilation errors

**Testing:** 2-4 hours
- Full test suite
- Manual testing
- Edge cases

**Total:** 8-14 hours of focused work

---

## Success Criteria

✅ All database tables renamed correctly  
✅ All foreign keys updated  
✅ All code compiles without errors  
✅ All bot commands work correctly  
✅ No data loss (row counts match)  
✅ Performance unchanged (<2ms queries)  
✅ All tests pass  
✅ Documentation updated  

---

## Rollback Plan

If Phase 2 deployment fails:

1. **Stop the bot immediately**
2. **Restore database from backup**
3. **Checkout Phase 1 code** (`git checkout team-system`)
4. **Restart bot**
5. **Investigate issues**
6. **Fix and retry**

---

## Phase 1 vs Phase 2 Comparison

### Phase 1 (DONE ✅)
- **Type:** Non-breaking addition
- **Change:** Added `gaming_session_id` column
- **Risk:** Low
- **Time:** Completed
- **Rollback:** Easy (just ignore new column)

### Phase 2 (PLANNED 📋)
- **Type:** Breaking change
- **Change:** Rename sessions → rounds throughout
- **Risk:** Medium
- **Time:** 8-14 hours
- **Rollback:** Database restore required

---

## Recommendation

**When to do Phase 2:**

✅ **Good time:**
- During major refactor
- When doing database cleanup
- When adding new features that benefit from correct naming
- During scheduled maintenance window

❌ **Bad time:**
- Right before important event/tournament
- When system is unstable
- When team is unavailable for support
- During high-usage periods

**Current Status:** Phase 1 is production-ready. Phase 2 can wait until a convenient maintenance window.

---

## References

- **Audit Document:** COMPLETE_SESSION_TERMINOLOGY_AUDIT.md
- **Phase 1 Implementation:** PHASE1_IMPLEMENTATION_COMPLETE.md
- **Edge Cases:** EDGE_CASES.md
- **Test Results:** PHASE1_VALIDATION_REPORT.md

---

**Last Updated:** November 4, 2025  
**Status:** Planning Complete - Ready for implementation when needed
