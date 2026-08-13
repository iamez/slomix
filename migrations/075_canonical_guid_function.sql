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

-- Follows a chain of 'merged' links to its ROOT: A→B→C resolves to C for every
-- guid in the chain, so aggregation stays consistent no matter which member is
-- queried. Depth is capped (16) so a mistaken cycle (A→B→A) terminates instead
-- of looping forever. A guid with no merged link resolves to itself (depth 0).
CREATE OR REPLACE FUNCTION canonical_guid(p_guid TEXT) RETURNS TEXT AS $$
  WITH RECURSIVE chain(guid, depth) AS (
    SELECT p_guid, 0
    UNION ALL
    SELECT l.primary_guid, c.depth + 1
    FROM chain c
    JOIN player_identity_links l
      ON l.alt_guid = c.guid AND l.link_type = 'merged'
    WHERE c.depth < 16
  )
  SELECT guid FROM chain ORDER BY depth DESC LIMIT 1;
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
