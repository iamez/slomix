"""storytelling package — split from the monolithic storytelling_service.py in Sprint 6.

Public API is the StorytellingService class in .service, re-exported here.
All module-level constants and helpers live in .base (re-exported too for backward compat).
"""
from .base import *  # noqa: F401, F403  (constants + helpers; keeps legacy imports working)
from .service import StorytellingService  # noqa: F401
