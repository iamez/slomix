"""
Season Manager - Quarterly Competition System
==============================================
Extracted from: bot/ultimate_bot.py (Lines 125-223)
Extraction Date: 2025-11-01
Part of: Option B Refactoring (Extraction #2)

Manages quarterly competitive seasons with automatic leaderboard resets.
Provides season calculation, date ranges, and transition detection.

Season Format: "YYYY-QN" (e.g., "2025-Q4")
Quarters: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
"""

import logging
from datetime import datetime
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


class SeasonManager:
    """
    Manages quarterly competitive seasons with leaderboard resets.

    Features:
    - Automatic season calculation (Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec)
    - Season-filtered queries for leaderboards
    - All-time stats preservation
    - Season transition detection

    Season Format: "2025-Q4" (Year-Quarter)

    Usage:
        sm = SeasonManager()
        current = sm.get_current_season()  # "2025-Q4"
        start, end = sm.get_season_dates(current)
        is_new = sm.is_new_season("2025-Q3")

    Attributes:
        season_names (dict): Mapping of quarter numbers to season names
    """

    def __init__(self):
        """Initialize the SeasonManager with season name mappings."""
        self.season_names = {1: "Spring", 2: "Summer", 3: "Fall", 4: "Winter"}
        logger.info(
            f"📅 SeasonManager initialized - Current: {self.get_current_season()}"
        )

    def get_current_season(self) -> str:
        """
        Get current season identifier.

        Returns:
            str: Current season in format "YYYY-QN" (e.g., "2025-Q4")

        Example:
            >>> sm = SeasonManager()
            >>> sm.get_current_season()
            '2025-Q4'
        """
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"

    def get_season_name(self, season_id: Optional[str] = None) -> str:
        """
        Get friendly season name.

        Args:
            season_id: Season identifier (e.g., "2025-Q4").
                      If None, uses current season.

        Returns:
            str: Friendly name like "2025 Winter (Q4)"

        Example:
            >>> sm = SeasonManager()
            >>> sm.get_season_name("2025-Q4")
            '2025 Winter (Q4)'
        """
        if season_id is None:
            season_id = self.get_current_season()

        year, quarter = season_id.split("-Q")
        quarter_num = int(quarter)
        season_name = self.season_names.get(quarter_num, f"Q{quarter_num}")
        return f"{year} {season_name} (Q{quarter_num})"

    def get_season_dates(self, season_id: Optional[str] = None) -> Tuple[datetime, datetime]:
        """
        Get start and end dates for a season.

        Args:
            season_id: Season identifier (e.g., "2025-Q4").
                      If None, uses current season.

        Returns:
            tuple: (start_date, end_date) as datetime objects
                  start_date: First moment of the quarter (00:00:00)
                  end_date: Last moment of the quarter (23:59:59)

        Example:
            >>> sm = SeasonManager()
            >>> start, end = sm.get_season_dates("2025-Q4")
            >>> print(f"{start} to {end}")
            2025-10-01 00:00:00 to 2025-12-31 23:59:59
        """
        if season_id is None:
            season_id = self.get_current_season()

        year, quarter = season_id.split("-Q")
        year = int(year)
        quarter = int(quarter)

        # Calculate start month
        start_month = (quarter - 1) * 3 + 1

        # Start: First day of first month
        start_date = datetime(year, start_month, 1)

        # End: Last day of last month in quarter
        if quarter == 4:
            end_date = datetime(year, 12, 31, 23, 59, 59)
        else:
            end_month = start_month + 2
            # Get last day of end month
            if end_month == 12:
                end_date = datetime(year, 12, 31, 23, 59, 59)
            else:
                # First day of next month minus 1 second
                next_month = datetime(year, end_month + 1, 1)
                end_date = datetime(
                    year,
                    end_month,
                    (next_month - datetime(year, end_month, 1)).days,
                    23,
                    59,
                    59,
                )

        return start_date, end_date

    def get_season_sql_filter(self, season_id: Optional[str] = None) -> str:
        """
        Get SQL WHERE clause for filtering by season.

        Args:
            season_id: Season identifier (e.g., "2025-Q4").
                      "current" or None uses current season.
                      "alltime" returns empty string (no filter).

        Returns:
            str: SQL WHERE clause fragment (includes "AND" prefix)
                Empty string for all-time stats.

        Example:
            >>> sm = SeasonManager()
            >>> sm.get_season_sql_filter("2025-Q4")
            "AND s.session_date >= '2025-10-01' AND s.session_date <= '2025-12-31'"
            >>> sm.get_season_sql_filter("alltime")
            ""
        """
        if season_id is None or season_id.lower() == "current":
            season_id = self.get_current_season()

        if season_id.lower() == "alltime":
            return ""  # No filter for all-time stats

        start_date, end_date = self.get_season_dates(season_id)
        # Note: rounds table uses round_date column, not session_date
        return f"AND s.round_date >= '{start_date.strftime('%Y-%m-%d')}' AND s.round_date <= '{end_date.strftime('%Y-%m-%d')}'"

    def is_new_season(self, last_known_season: str) -> bool:
        """
        Check if we've transitioned to a new season.

        Args:
            last_known_season: Previous season identifier (e.g., "2025-Q3")

        Returns:
            bool: True if current season is different from last known season

        Example:
            >>> sm = SeasonManager()
            >>> sm.is_new_season("2025-Q3")  # If current is Q4
            True
        """
        current = self.get_current_season()
        return current != last_known_season

    def get_all_seasons(self) -> List[str]:
        """
        Get list of all available seasons for selection.

        Returns:
            list: Last 4 quarters (1 year) of season identifiers,
                 most recent first (e.g., ["2025-Q4", "2025-Q3", "2025-Q2", "2025-Q1"])

        Note:
            In future, could query database for actual seasons with data.

        Example:
            >>> sm = SeasonManager()
            >>> sm.get_all_seasons()
            ['2025-Q4', '2025-Q3', '2025-Q2', '2025-Q1']
        """
        current = self.get_current_season()
        year, quarter = current.split("-Q")
        year = int(year)
        quarter = int(quarter)

        seasons = []
        # Generate last 4 quarters (1 year of seasons)
        for i in range(4):
            q = quarter - i
            y = year
            if q <= 0:
                q += 4
                y -= 1
            seasons.append(f"{y}-Q{q}")

        return seasons

    def get_days_until_season_end(self) -> int:
        """
        Get number of days until current season ends.

        Returns:
            int: Days remaining in current season (can be negative if calculation error)

        Example:
            >>> sm = SeasonManager()
            >>> sm.get_days_until_season_end()
            60  # 60 days left in Q4
        """
        _, end_date = self.get_season_dates()
        now = datetime.now()
        delta = end_date - now
        return delta.days
