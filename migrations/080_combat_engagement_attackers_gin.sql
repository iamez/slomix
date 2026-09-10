-- ================================================================
-- 080: GIN index for attacker containment on combat_engagement
-- ================================================================
-- Created: 2026-09-02
-- Purpose: /api/proximity/player/{guid}/profile spent 3.4 s of its
--   3.5 s warm latency in a jsonb_array_elements EXISTS scan over
--   90 days of engagements (measured via EXPLAIN ANALYZE). The
--   kill-count predicate is a containment test in disguise, and
--   containment is what GIN jsonb_path_ops indexes answer.
--   Predicate equivalence was proven on live data before the
--   rewrite (two active guids: 2046=2046, 3429=3429 rows).
-- ================================================================

-- ⚠️ No ANALYZE here: the runner's role need not own the table (079's
-- convention). Run it once as the owner after applying:
--   PGPASSWORD=... psql -h 127.0.0.1 -U etlegacy_user -d etlegacy \
--     -c "ANALYZE combat_engagement;"   (done on dev, 2026-09-02)

CREATE INDEX IF NOT EXISTS idx_combat_engagement_attackers_gin
    ON combat_engagement USING gin (attackers jsonb_path_ops);
