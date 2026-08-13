-- canonical_guid(guid): Phase 3 identity-merge resolution. When a player opts to
-- MERGE a sick-leave alt into their main (player_identity_links.link_type =
-- 'merged'), aggregations that GROUP BY canonical_guid(player_guid) count the
-- two guids as ONE identity. For every other guid (no merged link) it returns
-- the input unchanged, so nothing else moves.
--
-- STABLE (reads a table) + tiny indexed lookup on the UNIQUE alt_guid. 'sick_leave'
-- and 'alias' links are deliberately NOT folded — only an explicit 'merged'
-- opt-in changes any number.

BEGIN;

CREATE OR REPLACE FUNCTION canonical_guid(p_guid TEXT) RETURNS TEXT AS $$
  SELECT COALESCE(
    (SELECT l.primary_guid FROM player_identity_links l
     WHERE l.alt_guid = p_guid AND l.link_type = 'merged' LIMIT 1),
    p_guid
  );
$$ LANGUAGE sql STABLE;

-- Both roles execute it from their queries (grant only if the role exists, so a
-- fresh CI/test DB without website_app still applies — mirrors migration 073).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
    GRANT EXECUTE ON FUNCTION canonical_guid(TEXT) TO website_app;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etlegacy_user') THEN
    GRANT EXECUTE ON FUNCTION canonical_guid(TEXT) TO etlegacy_user;
  END IF;
END $$;

COMMIT;
