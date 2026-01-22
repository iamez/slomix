"""Proximity Parser Module"""
from .parser import ProximityParserV3, ProximityParserV4

# Export both the legacy alias (V3) and the current implementation (V4) for clarity.
__all__ = ['ProximityParserV3', 'ProximityParserV4']
