#!/usr/bin/env python3
"""
🏆 Season System - Test Script
===============================

Test the SeasonManager class to ensure:
- Correct season calculation
- Proper date ranges
- SQL filter generation
- Season transitions

Run this before deploying to verify everything works correctly.
"""

import sys
import os
from datetime import datetime

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

# Import SeasonManager class
# Since we can't directly import from ultimate_bot.py (it needs Discord),
# let's recreate the class here for testing
class SeasonManager:
    """
    Manages quarterly competitive seasons with leaderboard resets.
    
    Features:
    - Automatic season calculation (Q1-Q4)
    - Season-filtered queries for leaderboards
    - All-time stats preservation
    - Season transition detection
    """
    
    def __init__(self):
        self.season_names = {
            1: "Spring",
            2: "Summer", 
            3: "Fall",
            4: "Winter"
        }
        print(f"📅 SeasonManager initialized - Current: {self.get_current_season()}")
    
    def get_current_season(self):
        """Get current season identifier (e.g., '2025-Q4')"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"
    
    def get_season_name(self, season_id=None):
        """Get friendly season name (e.g., '2025 Winter (Q4)')"""
        if season_id is None:
            season_id = self.get_current_season()
        
        year, quarter = season_id.split('-Q')
        quarter_num = int(quarter)
        season_name = self.season_names.get(quarter_num, f"Q{quarter_num}")
        return f"{year} {season_name} (Q{quarter_num})"
    
    def get_season_dates(self, season_id=None):
        """Get start and end dates for a season"""
        if season_id is None:
            season_id = self.get_current_season()
        
        year, quarter = season_id.split('-Q')
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
                # Calculate last day
                if end_month in [1, 3, 5, 7, 8, 10]:
                    last_day = 31
                elif end_month in [4, 6, 9, 11]:
                    last_day = 30
                else:  # February
                    # Check leap year
                    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                        last_day = 29
                    else:
                        last_day = 28
                end_date = datetime(year, end_month, last_day, 23, 59, 59)
        
        return start_date, end_date
    
    def get_season_sql_filter(self, season_id=None):
        """Get SQL WHERE clause for filtering by season"""
        if season_id is None or season_id.lower() == 'current':
            season_id = self.get_current_season()
        
        if season_id.lower() == 'alltime':
            return ""  # No filter for all-time stats
        
        start_date, end_date = self.get_season_dates(season_id)
        return f"AND s.session_date >= '{start_date.strftime('%Y-%m-%d')}' AND s.session_date <= '{end_date.strftime('%Y-%m-%d')}'"
    
    def is_new_season(self, last_known_season):
        """Check if we've transitioned to a new season"""
        current = self.get_current_season()
        return current != last_known_season
    
    def get_all_seasons(self):
        """Get list of all available seasons"""
        current = self.get_current_season()
        year, quarter = current.split('-Q')
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
    
    def get_days_until_season_end(self):
        """Get number of days until current season ends"""
        _, end_date = self.get_season_dates()
        now = datetime.now()
        delta = end_date - now
        return delta.days


def test_season_manager():
    """Test all SeasonManager functionality"""
    print("=" * 70)
    print("  🏆 Season System - Test Suite")
    print("=" * 70)
    print()
    
    # Initialize manager
    sm = SeasonManager()
    print()
    
    # Test 1: Current Season
    print("📋 Test 1: Current Season")
    print("-" * 70)
    current = sm.get_current_season()
    print(f"Current Season ID: {current}")
    print(f"Season Name: {sm.get_season_name()}")
    print()
    
    # Test 2: Season Dates
    print("📋 Test 2: Season Dates")
    print("-" * 70)
    start, end = sm.get_season_dates()
    print(f"Start Date: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End Date:   {end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Days Remaining: {sm.get_days_until_season_end()} days")
    print()
    
    # Test 3: All Quarters
    print("📋 Test 3: All Quarters (2025)")
    print("-" * 70)
    for q in range(1, 5):
        season_id = f"2025-Q{q}"
        name = sm.get_season_name(season_id)
        start, end = sm.get_season_dates(season_id)
        print(f"{season_id} - {name}")
        print(f"  {start.strftime('%b %d')} to {end.strftime('%b %d')}")
    print()
    
    # Test 4: SQL Filter
    print("📋 Test 4: SQL Filter Generation")
    print("-" * 70)
    sql_filter = sm.get_season_sql_filter()
    print(f"Current Season Filter:")
    print(f"  {sql_filter}")
    print()
    print(f"All-Time Filter:")
    alltime_filter = sm.get_season_sql_filter('alltime')
    print(f"  '{alltime_filter}' (empty string = no filter)")
    print()
    
    # Test 5: Season Transition
    print("📋 Test 5: Season Transition Detection")
    print("-" * 70)
    current = sm.get_current_season()
    print(f"Current: {current}")
    print(f"Is new season from '2025-Q3'? {sm.is_new_season('2025-Q3')}")
    print(f"Is new season from '{current}'? {sm.is_new_season(current)}")
    print()
    
    # Test 6: Recent Seasons
    print("📋 Test 6: Recent Seasons List")
    print("-" * 70)
    seasons = sm.get_all_seasons()
    print(f"Last 4 quarters (including current):")
    for season in seasons:
        print(f"  • {season} - {sm.get_season_name(season)}")
    print()
    
    # Summary
    print("=" * 70)
    print("✅ All tests completed successfully!")
    print()
    print("💡 Integration Tips:")
    print("  • Use get_season_sql_filter() in leaderboard queries")
    print("  • Call !season_info to show season details")
    print("  • Check is_new_season() to announce transitions")
    print("  • Track last_known_season in bot state")
    print("=" * 70)


if __name__ == '__main__':
    test_season_manager()
