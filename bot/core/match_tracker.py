#!/usr/bin/env python3
"""
Match Tracking System - Centralized match ID generation and pairing logic

This module provides the core logic for:
1. Generating consistent match IDs from filenames (date + map, NO timestamp)
2. Pairing Round 1 and Round 2 files
3. Tracking match completeness
4. Ensuring R1, R2, and R0 all share the same match_id

Author: ET:Legacy Stats System
Date: November 7, 2025
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class MatchTracker:
    """
    Centralized match tracking logic.

    This ensures ALL code paths use the same match_id generation algorithm.
    """

    @staticmethod
    def extract_match_components(filename: str) -> Dict[str, str]:
        """
        Extract date, time, map, and round from filename.

        Input: 2025-11-06-234153-etl_frostbite-round-2.txt
        Returns: {
            'date': '2025-11-06',
            'time': '234153',
            'map': 'etl_frostbite',
            'round': '2',
            'base_match_id': '2025-11-06-etl_frostbite'
        }
        """
        # Remove .txt extension
        base = filename.replace('.txt', '')

        # Pattern: YYYY-MM-DD-HHMMSS-mapname-round-N
        pattern = r'^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+?)-round-(\d+)$'
        match = re.match(pattern, base)

        if not match:
            # Fallback for non-standard names
            return {
                'date': 'unknown',
                'time': 'unknown',
                'map': 'unknown',
                'round': '1',
                'base_match_id': base
            }

        date = match.group(1)
        time = match.group(2)
        map_name = match.group(3)
        round_num = match.group(4)

        return {
            'date': date,
            'time': time,
            'map': map_name,
            'round': round_num,
            'base_match_id': f"{date}-{map_name}"  # The KEY for matching R1 and R2!
        }

    @staticmethod
    def generate_match_id(filename: str) -> str:
        """
        Generate consistent match_id for database storage.

        This is the CRITICAL function that ensures R1 and R2 get same match_id!

        Input:  2025-11-06-234153-etl_frostbite-round-2.txt
        Output: 2025-11-06-etl_frostbite

        The timestamp (234153) is stripped so R1 and R2 have identical match_id.
        """
        components = MatchTracker.extract_match_components(filename)
        return components['base_match_id']

    @staticmethod
    def find_round_pair(target_file: str, all_files: List[str]) -> Optional[str]:
        """
        Find the paired round file (R1 for R2, or R2 for R1).

        Args:
            target_file: The file we want to find a pair for
            all_files: List of all available files

        Returns:
            The paired filename, or None if not found
        """
        components = MatchTracker.extract_match_components(target_file)
        base_match_id = components['base_match_id']
        current_round = components['round']

        # Determine what we're looking for
        target_round = '1' if current_round == '2' else '2'

        # Look for file with same base_match_id but different round
        for file in all_files:
            other_components = MatchTracker.extract_match_components(file)
            if (other_components['base_match_id'] == base_match_id and
                other_components['round'] == target_round):
                return file

        return None

    @staticmethod
    def find_round_1_for_round_2(round_2_file: str, search_dir: Path) -> Optional[Path]:
        """
        Find the Round 1 file for a given Round 2 file.

        This recreates the parser's logic for finding R1 when processing R2.
        """
        components = MatchTracker.extract_match_components(round_2_file)

        if components['round'] != '2':
            return None

        # Look for Round 1 with same date and map
        date = components['date']
        map_name = components['map']

        # Pattern for Round 1 file: YYYY-MM-DD-*-mapname-round-1.txt
        pattern = f"{date}-*-{map_name}-round-1.txt"

        matches = list(search_dir.glob(pattern))

        if not matches:
            return None

        # If multiple matches, use the one closest in time
        if len(matches) > 1:
            r2_time = datetime.strptime(components['time'], '%H%M%S')

            closest = None
            min_diff = timedelta(hours=24)  # Max difference

            for match in matches:
                r1_components = MatchTracker.extract_match_components(match.name)
                r1_time = datetime.strptime(r1_components['time'], '%H%M%S')

                diff = abs(r2_time - r1_time)
                if diff < min_diff:
                    min_diff = diff
                    closest = match

            return closest

        return matches[0]

    @staticmethod
    def validate_match_id(match_id: str) -> bool:
        """
        Check if match_id follows expected format.

        Valid: 2025-11-06-etl_frostbite
        Invalid: 2025-11-06-234153-etl_frostbite-round-1
        Invalid: 2025-11-06-234153-etl_frostbite
        """
        # Should NOT contain timestamp (6 digits) or 'round'
        if re.search(r'-\d{6}-', match_id):
            return False
        if re.search(r'-\d{6}$', match_id):  # Ends with 6 digits
            return False
        if 'round' in match_id.lower():
            return False

        # Should match pattern: YYYY-MM-DD-mapname
        pattern = r'^\d{4}-\d{2}-\d{2}-.+$'
        return bool(re.match(pattern, match_id))


# Singleton instance for easy import
match_tracker = MatchTracker()
