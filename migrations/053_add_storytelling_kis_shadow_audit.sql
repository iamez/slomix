-- Migration 053: KIS server-side jsonb_agg shadow audit table (Phase 1 of A5).
--
-- Captures row-by-row deltas between the Python `_score_kill` path and a
-- SQL-only re-implementation. While shadow mode is enabled, the Python
-- path remains authoritative (writes to storytelling_kill_impact); this
-- table only records the top-N worst deltas per session for human review.
--
-- Phase 2 (cutover) is gated on the user reviewing this audit and
-- confirming that the rounding divergence is acceptable.
--
-- Rollback: DROP TABLE storytelling_kis_shadow_audit;

BEGIN;

CREATE TABLE IF NOT EXISTS storytelling_kis_shadow_audit (
    id              SERIAL PRIMARY KEY,
    session_date    DATE NOT NULL,
    kill_outcome_id INTEGER NOT NULL,
    python_impact   REAL NOT NULL,
    sql_impact      REAL NOT NULL,
    delta           REAL NOT NULL,
    captured_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Lookup by session for the diagnostics endpoint.
CREATE INDEX IF NOT EXISTS idx_kis_shadow_audit_session_date
    ON storytelling_kis_shadow_audit(session_date);

-- Ordered scans surface the worst divergences first per session.
CREATE INDEX IF NOT EXISTS idx_kis_shadow_audit_session_delta
    ON storytelling_kis_shadow_audit(session_date, ABS(delta) DESC);

COMMENT ON TABLE storytelling_kis_shadow_audit IS
    'Phase 1 shadow audit for A5 (server-side KIS jsonb_agg). Top-N worst per-kill deltas between Python _score_kill and SQL re-implementation.';

COMMIT;
