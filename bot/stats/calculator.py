"""
Statistics Calculator - Centralized stat calculations for ET:Legacy

This module provides a single source of truth for all game statistics calculations,
eliminating duplicate code across parsers, cogs, and database modules.

All methods are NULL-safe and handle edge cases (zero division, None values).
"""

from typing import Optional, Union


class StatsCalculator:
    """
    Centralized statistics calculator for ET:Legacy game stats.

    All methods are static and thread-safe.
    """

    @staticmethod
    def calculate_dpm(damage: Optional[int], time_seconds: Optional[Union[int, float]],
                      default: float = 0.0) -> float:
        """
        Calculate Damage Per Minute (DPM).

        Formula: (damage * 60) / time_seconds

        Args:
            damage: Total damage dealt
            time_seconds: Time played in seconds
            default: Value to return on error or invalid input

        Returns:
            DPM as float, or default if calculation fails

        Examples:
            >>> StatsCalculator.calculate_dpm(1200, 300)
            240.0  # (1200 * 60) / 300
            >>> StatsCalculator.calculate_dpm(0, 0)
            0.0
            >>> StatsCalculator.calculate_dpm(None, 100)
            0.0
        """
        try:
            if damage is None or time_seconds is None or time_seconds == 0:
                return default
            return (damage * 60) / time_seconds
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def calculate_kd(kills: Optional[int], deaths: Optional[int],
                     default: float = 0.0) -> float:
        """
        Calculate Kill/Death ratio (K/D).

        Formula: kills / deaths (or kills if deaths == 0)

        Args:
            kills: Number of kills
            deaths: Number of deaths
            default: Value to return on error

        Returns:
            K/D ratio as float. If deaths is 0, returns kills as float.

        Examples:
            >>> StatsCalculator.calculate_kd(20, 10)
            2.0
            >>> StatsCalculator.calculate_kd(15, 0)
            15.0  # Perfect K/D returns kills
            >>> StatsCalculator.calculate_kd(None, 10)
            0.0
        """
        try:
            if kills is None:
                return default
            if deaths is None or deaths == 0:
                return float(kills)
            return kills / deaths
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def calculate_accuracy(hits: Optional[int], shots: Optional[int],
                          as_percentage: bool = True, default: float = 0.0) -> float:
        """
        Calculate weapon accuracy.

        Formula: (hits / shots) * 100 (if as_percentage=True)

        Args:
            hits: Number of shots that hit
            shots: Total shots fired
            as_percentage: If True, returns 0-100. If False, returns 0.0-1.0
            default: Value to return on error

        Returns:
            Accuracy as percentage (0-100) or ratio (0.0-1.0)

        Examples:
            >>> StatsCalculator.calculate_accuracy(50, 100)
            50.0  # 50% accuracy
            >>> StatsCalculator.calculate_accuracy(50, 100, as_percentage=False)
            0.5  # 0.5 ratio
            >>> StatsCalculator.calculate_accuracy(0, 0)
            0.0
        """
        try:
            if hits is None or shots is None or shots == 0:
                return default
            ratio = hits / shots
            return (ratio * 100) if as_percentage else ratio
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def calculate_efficiency(kills: Optional[int], deaths: Optional[int],
                           as_percentage: bool = True, default: float = 0.0) -> float:
        """
        Calculate efficiency score (kills vs total engagements).

        Formula: (kills / (kills + deaths)) * 100

        Args:
            kills: Number of kills
            deaths: Number of deaths
            as_percentage: If True, returns 0-100. If False, returns 0.0-1.0
            default: Value to return on error

        Returns:
            Efficiency as percentage (0-100) or ratio (0.0-1.0)

        Examples:
            >>> StatsCalculator.calculate_efficiency(15, 5)
            75.0  # 15/(15+5) * 100
            >>> StatsCalculator.calculate_efficiency(10, 0)
            100.0  # Perfect efficiency
            >>> StatsCalculator.calculate_efficiency(0, 0)
            0.0
        """
        try:
            if kills is None:
                kills = 0
            if deaths is None:
                deaths = 0

            total = kills + deaths
            if total == 0:
                return default

            ratio = kills / total
            return (ratio * 100) if as_percentage else ratio
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def calculate_headshot_percentage(headshots: Optional[int], kills: Optional[int],
                                     default: float = 0.0) -> float:
        """
        Calculate headshot percentage.

        Formula: (headshots / kills) * 100

        Args:
            headshots: Number of headshot kills
            kills: Total kills
            default: Value to return on error

        Returns:
            Headshot percentage (0-100)

        Examples:
            >>> StatsCalculator.calculate_headshot_percentage(5, 20)
            25.0  # 25% of kills were headshots
            >>> StatsCalculator.calculate_headshot_percentage(0, 10)
            0.0
        """
        try:
            if headshots is None or kills is None or kills == 0:
                return default
            return (headshots / kills) * 100
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def safe_divide(numerator: Optional[Union[int, float]],
                   denominator: Optional[Union[int, float]],
                   default: float = 0.0) -> float:
        """
        Safe division with NULL and zero handling.

        Generic division method for custom calculations.

        Args:
            numerator: Value to divide
            denominator: Value to divide by
            default: Value to return on error

        Returns:
            numerator / denominator, or default if division fails

        Examples:
            >>> StatsCalculator.safe_divide(100, 4)
            25.0
            >>> StatsCalculator.safe_divide(10, 0)
            0.0
            >>> StatsCalculator.safe_divide(None, 5)
            0.0
        """
        try:
            if numerator is None or denominator is None or denominator == 0:
                return default
            return numerator / denominator
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def safe_percentage(part: Optional[Union[int, float]],
                       total: Optional[Union[int, float]],
                       default: float = 0.0) -> float:
        """
        Calculate percentage with NULL and zero handling.

        Formula: (part / total) * 100

        Args:
            part: Partial value
            total: Total value
            default: Value to return on error

        Returns:
            Percentage (0-100), or default if calculation fails

        Examples:
            >>> StatsCalculator.safe_percentage(25, 100)
            25.0
            >>> StatsCalculator.safe_percentage(3, 4)
            75.0
            >>> StatsCalculator.safe_percentage(5, 0)
            0.0
        """
        result = StatsCalculator.safe_divide(part, total, default)
        return result * 100 if result != default else default
