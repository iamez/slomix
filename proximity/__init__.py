"""
Proximity Tracker v4 - Full Player Tracking & Combat Analytics

Import the parser:
    from proximity.parser import ProximityParserV4
    # Or use the legacy alias:
    from proximity.parser import ProximityParserV3
"""

from proximity.parser.parser import ProximityParserV3, ProximityParserV4

# Export both the legacy alias (V3) and the current implementation (V4) for clarity.
__all__ = ['ProximityParserV3', 'ProximityParserV4']
__version__ = '4.0'
