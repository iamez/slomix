-- Migration 051: Add hot-path indexes flagged by 2026-05-07 audit
--
-- See docs/audit_2026-05-07.md L1+L2/P1, L7/P0+P2 for context.
--
-- All indexes use IF NOT EXISTS so this migration is idempotent across
-- environments where some indexes were already added manually. Each is
-- documented with the consumer that benefits.

-- ============================================================================
-- round_correlations: FK lookup speedup
-- ============================================================================
-- The composite UNIQUE on (r1_round_id, r2_round_id) helps lookups that
-- filter both, but `_find_nearby_correlation_id` and `merge_round_correlation`
-- do single-column scans by r1 OR r2. Without these, those reads are full
-- table scans on a steadily-growing correlation table.
CREATE INDEX IF NOT EXISTS idx_round_correlations_r1_round_id
    ON round_correlations (r1_round_id)
    WHERE r1_round_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_round_correlations_r2_round_id
    ON round_correlations (r2_round_id)
    WHERE r2_round_id IS NOT NULL;

-- ============================================================================
-- player_comprehensive_stats: per-player aggregation speedup
-- ============================================================================
-- The existing UNIQUE on (round_id, player_guid) helps lookups that scope
-- by round_id first. Many of our hot endpoints (records, leaderboards,
-- skill ratings, team manager) GROUP BY player_guid across rounds — those
-- need the inverse leading column.
--
-- Partial index on round_number > 0 (R1+R2 only, excludes R0 aggregate rows)
-- because every audit-aware query filters R0 out anyway. The trailing
-- round_number column lets the planner short-circuit on R0 without re-scanning.
CREATE INDEX IF NOT EXISTS idx_pcs_player_guid_round_number
    ON player_comprehensive_stats (player_guid, round_number)
    WHERE round_number > 0;

-- ============================================================================
-- rounds: file_tracker existence check
-- ============================================================================
-- The audit's draft index (round_date, map_name, round_number) was redundant
-- with the existing `idx_rounds_map_round_date_time` (migration 014) which
-- covers (map_name, round_number, round_date, round_time) and matches the
-- full predicate of file_tracker._session_exists_in_db (which also filters
-- on round_time). PostgreSQL's planner uses that index regardless of the
-- ordering of equality columns in the WHERE clause. No new index needed.
