-- player_identity_links: maps a secondary ("alt") player_guid to a primary
-- identity, so a cl_guid change (new PC, reinstall) or a self-declared
-- "sick leave" (bolniška — a player logging an injury / off-form stretch under
-- a fresh guid so it does not spoil their main record) can be ATTRIBUTED
-- without necessarily merging the underlying stats.
--
-- link_type semantics:
--   'sick_leave' — kept SEPARATE in aggregates (its own leaderboard row), but
--                  the profile attributes it to primary and a 🩹 badge is shown.
--                  This is the default and does NOT change any existing number.
--   'merged'     — folded into primary everywhere via canonical-guid resolution
--                  (TOK F Phase 3); a player's own choice after recovery.
--   'alias'      — a plain guid-change link (same person, no injury framing).
--
-- Guid-anchored (primary_guid, not a Discord user_id) so it works for players
-- who never linked their Discord (e.g. carniee). One alt_guid belongs to at
-- most one identity (UNIQUE). See TOK F in the master plan (2026-08-13).
--
-- Deliberately transactional: the runner rejects live/non-transactional DDL.

BEGIN;

CREATE TABLE IF NOT EXISTS player_identity_links (
    id            SERIAL PRIMARY KEY,
    primary_guid  TEXT NOT NULL,
    alt_guid      TEXT NOT NULL UNIQUE,
    link_type     TEXT NOT NULL DEFAULT 'sick_leave'
                  CHECK (link_type IN ('sick_leave', 'merged', 'alias')),
    reason        TEXT,
    period_start  DATE,
    period_end    DATE,
    created_by    BIGINT,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    notes         TEXT,
    CONSTRAINT player_identity_links_no_self CHECK (primary_guid <> alt_guid)
);

-- Reverse lookup: find a primary identity's alts (the UNIQUE on alt_guid already
-- indexes the forward lookup).
CREATE INDEX IF NOT EXISTS idx_player_identity_links_primary
    ON player_identity_links (primary_guid);

-- Both roles need access: the website API reads (profile/leaderboard badge) and
-- the web self-service flow writes; the bot (etlegacy_user) writes via the
-- !bolniska command (Phase 2). Whichever role owns the table (website_app on
-- dev, the owner role on prod) makes the grant to the OTHER a real GRANT and to
-- itself a harmless no-op, so listing both is environment-agnostic.
GRANT SELECT, INSERT, UPDATE, DELETE ON player_identity_links TO website_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON player_identity_links TO etlegacy_user;
GRANT USAGE, SELECT ON SEQUENCE player_identity_links_id_seq TO website_app;
GRANT USAGE, SELECT ON SEQUENCE player_identity_links_id_seq TO etlegacy_user;

COMMIT;
