"""
FIVEEYES Analytics Package
Player synergy and team chemistry analysis
"""

__version__ = "1.0.0"
__author__ = "FIVEEYES Project"

from .synergy_detector import SynergyDetector, SynergyMetrics, PlayerPerformance

__all__ = ['SynergyDetector', 'SynergyMetrics', 'PlayerPerformance']
