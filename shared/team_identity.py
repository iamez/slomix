"""Fail-closed date-only roster admission; callers must hold the team writer lock."""


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
