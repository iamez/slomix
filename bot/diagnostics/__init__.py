"""
Bot Diagnostics Package
=======================

This package contains diagnostic and debugging scripts for the ET:Legacy Discord Bot.
These are standalone utilities meant to be run manually for troubleshooting.

WARNING: These scripts may read from/write to the database. Use with caution.

Available Diagnostics:
    check_all_rounds: Verify all rounds are properly imported
    check_duplicates: Find duplicate player entries
    check_playtime_issue: Debug playtime calculation problems
    check_session_boundary: Verify gaming session boundaries (60-min gaps)
    check_sessions: List and analyze gaming sessions
    reimport_missing: Re-import rounds that failed initial import
    remove_duplicates: Clean up duplicate entries (destructive!)
    test_import: Test the import pipeline with sample files

Usage:
    cd /home/samba/share/slomix_discord
    python -m bot.diagnostics.check_sessions
    python -m bot.diagnostics.check_duplicates

Note:
    These scripts are NOT meant to be imported by the bot itself.
    They are standalone CLI tools for debugging.
"""

# These are standalone scripts, not meant for import
# Keep this file minimal
__all__ = []
