"""StorytellingService facade — inherits all mixins.

Client code still imports StorytellingService from the parent module:
    from website.backend.services.storytelling_service import StorytellingService
which re-exports this class via the shim file.
"""
from __future__ import annotations

from .advanced_metrics import _AdvancedMetricsMixin
from .archetypes import _ArchetypesMixin
from .base import *  # noqa: F401, F403  (constants + helpers)
from .kis import _KisMixin
from .loaders import _LoadersMixin
from .moments import _MomentsMixin
from .momentum import _MomentumMixin
from .narrative import _NarrativeMixin
from .synergy import _SynergyMixin
from .win_contribution import _WinContributionMixin


class StorytellingService(
    _KisMixin,
    _LoadersMixin,
    _MomentsMixin,
    _ArchetypesMixin,
    _SynergyMixin,
    _WinContributionMixin,
    _MomentumMixin,
    _NarrativeMixin,
    _AdvancedMetricsMixin,
):
    """Smart Storytelling Stats — facade for all storytelling computations.

    Split from monolithic storytelling_service.py in Sprint 6 via mixin pattern.
    """

    # PWC v2 weights (must sum to 1.0). Used by _WinContributionMixin.
    # Were lost during Sprint 6 mixin split — restored here as class attrs so
    # all mixins resolve via MRO.
    _PWC_W_KILLS = 0.22
    _PWC_W_DAMAGE = 0.10
    _PWC_W_OBJECTIVES = 0.20
    _PWC_W_REVIVES = 0.12
    _PWC_W_SURVIVAL = 0.08
    _PWC_W_CROSSFIRE = 0.10   # Crossfire kills share (team coordination)
    _PWC_W_TRADE = 0.10       # Trade kills share (avenging teammates)
    _PWC_W_CLUTCH = 0.08      # Clutch kills share (low HP / outnumbered)

    def __init__(self, db):
        self.db = db
