"""Fail-closed roster ownership/schema admission; mutations require a team lock."""


class TeamIdentityConflict(RuntimeError):
    """Date-only team ownership cannot safely be attributed to this session ID."""


# A date is evidence of possible overlap, never proof of session ownership.
# Include all recorded session days, not just the caller's date (midnight).
UNRESOLVED_TEAM_IDENTITY_SQL = """
    SELECT EXISTS (
        SELECT 1 FROM session_teams
        WHERE gaming_session_id IS NULL AND map_name = 'ALL'
          AND (
            LEFT(session_start_date, 10) = $2
            OR LEFT(session_start_date, 10) IN (
                SELECT LEFT(round_date, 10) FROM rounds
                WHERE gaming_session_id = $1
            )
          )
    )
"""


def require_resolved_team_identity(unresolved: bool) -> None:
    """Only an explicit false result admits an ID-scoped writer."""
    if unresolved is not False:
        raise TeamIdentityConflict('Date-only team ownership requires explicit session resolution')


async def has_modern_team_identity(conn) -> bool:
    """Require the same usable identity key for legacy setup and runtime workers."""
    result = await conn.fetchval("""
            SELECT
              (SELECT count(*)=2 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='session_teams'
                 AND column_name IN ('gaming_session_id','session_identity'))
              AND EXISTS (
                SELECT 1 FROM pg_index i
                JOIN pg_class t ON t.oid=i.indrelid
                JOIN pg_class ix ON ix.oid=i.indexrelid
                JOIN pg_namespace n ON n.oid=t.relnamespace
                WHERE n.nspname='public' AND t.relname='session_teams'
                  AND ix.relname='session_teams_identity_unique'
                  AND i.indisunique AND i.indisvalid AND i.indisready AND i.indimmediate
                  AND i.indpred IS NULL AND i.indexprs IS NULL AND i.indnatts=3
                  AND ARRAY(SELECT a.attname::text
                            FROM unnest(i.indkey) WITH ORDINALITY k(attnum,position)
                            JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
                            ORDER BY k.position)
                      = ARRAY['session_identity','map_name','team_name']::text[]
              )
        """)
    return result is True
