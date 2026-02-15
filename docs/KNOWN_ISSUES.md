# Known Issues

## Time Dead Anomalies (Dec 16, 2025) - Low Priority

**Issue**: 13 player records show `time_dead_minutes > time_played_minutes` by small margins (0.06 to 2.06 minutes).

**Investigation**: Comprehensive investigation revealed:

- Parser correctly uses round duration for stopwatch mode (design intent)
- DPM calculations are correct (confirmed by user)
- Database rebuild reduced corruption from 43 records (100+ min errors) to 13 records (0.06-2.06 min errors)
- Field mappings verified correct: tab_fields[22] = time_played, [25] = time_dead_ratio, [26] = time_dead_minutes

**Possible Causes**:

1. Rounding differences between Lua (`roundNum(value, 1)`) and Python (`int(minutes * 60)`)
2. Edge cases: players joining mid-round or disconnecting
3. Potential Lua bug in `death_time_total` accumulation
4. Acceptable tolerance given system complexity

**Status**: Marked as **unsolved** - low priority. System works well enough for production use.

**Reference**: Investigation documented in `/home/samba/.claude/plans/sorted-wandering-horizon.md`

**Recommendation**: Accept current state or investigate Lua script if time permits in future.
