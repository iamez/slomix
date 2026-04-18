"""Backward-compat shim — storytelling_service.py delegates to the storytelling/ package.

Split in Sprint 6 (Mega Audit v3 / D.1): the previously monolithic 3302-line
file is now organized into mixin modules under website/backend/services/storytelling/.

All public symbols (StorytellingService class, constants, helpers) are
re-exported from here so existing imports like
`from website.backend.services.storytelling_service import StorytellingService`
keep working unchanged.
"""
from website.backend.services.storytelling import (  # noqa: F401
    StorytellingService,
)
from website.backend.services.storytelling.base import *  # noqa: F401, F403
