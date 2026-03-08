-- Migration 016: Add subject_name and subject_guid to round_vs_stats
-- =============================================================================
-- Background:
--   endstats.lua loops over each player and writes their VS opponent rows to
--   the endstats file, but never wrote which player the rows belonged to.
--   The parser therefore stored all opponent rows without a "subject" context,
--   making aggregation impossible (kills/deaths could not be attributed).
--
--   Fix: endstats.lua now writes a VS_HEADER\t<player_name> line before each
--   player's VS block. The parser reads this and populates subject_name on
--   every row that follows.
--
-- Schema change:
--   - subject_name: display name of the player these stats belong to
--   - subject_guid: guid resolved from player_aliases (may be NULL)
--   - Existing rows keep NULL in these new columns (old data was unusable anyway)
-- =============================================================================

ALTER TABLE round_vs_stats
    ADD COLUMN IF NOT EXISTS subject_name TEXT,
    ADD COLUMN IF NOT EXISTS subject_guid TEXT;

-- Index for efficient per-player lookups (easiest prey, worst enemy queries)
CREATE INDEX IF NOT EXISTS idx_round_vs_stats_subject ON round_vs_stats(subject_guid);
CREATE INDEX IF NOT EXISTS idx_round_vs_stats_subject_round
    ON round_vs_stats(subject_guid, round_id);
