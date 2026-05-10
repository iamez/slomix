-- Migration 052: Composite (session_date, *_guid_canonical) indexes
--
-- See docs/research/MEGA_AUDIT_V6_2026-05-10.md (E-2/E-3/E-8) for context.
--
-- Migration 035 added *_guid_canonical columns and SINGLE-column indexes,
-- but every session-scoped analytic query (skill ratings, KIS, advanced
-- metrics, win contribution) filters on (session_date, *_guid_canonical)
-- TOGETHER. Without the composite, those reads plan as bitmap-AND of two
-- single-column indexes, which loses to a true two-column seek as data
-- accumulates. Migration 041 added the equivalent for storytelling_kill_impact
-- on (session_date, killer_guid) but missed the canonical variant + the
-- proximity tables.
--
-- All four indexes use IF NOT EXISTS so this migration is idempotent.
-- Partial WHERE *_guid_canonical IS NOT NULL keeps the index lean — the
-- column was backfilled by migration 035 and is populated for new rows by
-- the application, but the partial predicate is defensive against legacy
-- rows and matches the WHERE clauses in the consuming queries.

BEGIN;

-- storytelling_kill_impact: ~14k rows; consumed by KIS leaderboards,
-- win-contribution, advanced metrics (gravity/space/enabler) — all
-- session-scoped via (session_date, killer_guid_canonical).
CREATE INDEX IF NOT EXISTS idx_ski_session_killer_canonical
    ON storytelling_kill_impact (session_date, killer_guid_canonical)
    WHERE killer_guid_canonical IS NOT NULL;

-- proximity_kill_outcome: ~16k rows; consumed by skill_rating session
-- scope (kill_quality, kill_permanence) via (session_date, killer_guid_canonical).
CREATE INDEX IF NOT EXISTS idx_pko_session_killer_canonical
    ON proximity_kill_outcome (session_date, killer_guid_canonical)
    WHERE killer_guid_canonical IS NOT NULL;

-- proximity_spawn_timing: ~20k rows; consumed by skill_rating session
-- scope (spawn_timing_eff) via (session_date, killer_guid_canonical).
CREATE INDEX IF NOT EXISTS idx_pst_session_killer_canonical
    ON proximity_spawn_timing (session_date, killer_guid_canonical)
    WHERE killer_guid_canonical IS NOT NULL;

-- proximity_combat_position: ~16k rows; consumed by skill_rating clutch
-- factor (low-HP kills) via (session_date, attacker_guid_canonical).
CREATE INDEX IF NOT EXISTS idx_pcp_session_attacker_canonical
    ON proximity_combat_position (session_date, attacker_guid_canonical)
    WHERE attacker_guid_canonical IS NOT NULL;

-- Note: schema_migrations row is inserted by scripts/apply_migrations.py
-- (with checksum + execution_ms), so no manual INSERT here.

COMMIT;
