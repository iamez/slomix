"""
Statistics calculation module for ET:Legacy Stats Bot

Centralizes all stat calculations (DPM, K/D, accuracy, efficiency)
to eliminate code duplication and ensure consistency.
"""

from .calculator import StatsCalculator

__all__ = ['StatsCalculator']
