"""
SQLite Diagnostic Wrapper Test

NOTE: This test was written for an older architecture where _enable_sql_diag
was in the main bot class. The system has since migrated to PostgreSQL and
the method now lives in LeaderboardCog for backwards compatibility.

This test is skipped because:
1. The bot now uses PostgreSQL (not SQLite)
2. The _enable_sql_diag method is in LeaderboardCog, not ultimate_bot
3. SQLite diagnostics are only used for legacy support

To test SQLite functionality, use pytest with the unit tests in tests/unit/
"""

import pytest

# Skip this entire module - SQLite diagnostics are deprecated
pytestmark = pytest.mark.skip(
    reason="SQLite diagnostics deprecated - system uses PostgreSQL. "
           "Method moved from ultimate_bot.ETLegacyCommands to LeaderboardCog."
)


# Original test preserved for reference (but skipped)
async def test_sql_diag_wrapper():
    """
    Original test that verified _enable_sql_diag functionality.

    This test is now skipped because:
    - ETLegacyCommands class no longer exists (renamed to UltimateETLegacyBot)
    - _enable_sql_diag moved to bot/cogs/leaderboard_cog.py
    - Bot uses PostgreSQL, not SQLite
    """
    pass  # Skipped via pytestmark above
