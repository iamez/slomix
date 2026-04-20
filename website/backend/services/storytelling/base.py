"""
Smart Storytelling Stats — Kill Impact Score (KIS) Engine

Computes contextual kill impact scores by combining:
- proximity_kill_outcome (what happened after each kill)
- proximity_carrier_kill (carrier interceptions)
- proximity_team_push (team push context)
- proximity_crossfire_opportunity (coordinated attacks)
- proximity_spawn_timing (spawn wave denial)
- proximity_reaction_metric (target class info)
"""

import asyncio
import traceback  # re-exported for mixin method bodies via __all__
from datetime import date, datetime

from shared.guid_utils import short_guid
from website.backend.logging_config import get_app_logger
from website.backend.utils.et_constants import strip_et_colors, weapon_name

# Legacy alias: existing call sites use `_safe_short`.
_safe_short = short_guid

logger = get_app_logger("storytelling")

# Per-session locks to prevent concurrent TOCTOU races on lazy compute
class _BoundedLockDict:
    """Bounded dict of asyncio.Lock — evicts oldest when full."""
    def __init__(self, maxsize: int = 64):
        self._locks: dict[str, asyncio.Lock] = {}
        self._order: list[str] = []
        self._maxsize = maxsize

    def get(self, key: str) -> asyncio.Lock:
        if key in self._locks:
            return self._locks[key]
        if len(self._locks) >= self._maxsize:
            oldest = self._order.pop(0)
            self._locks.pop(oldest, None)
        lock = asyncio.Lock()
        self._locks[key] = lock
        self._order.append(key)
        return lock

_compute_locks = _BoundedLockDict()

# Competitive ET:Legacy multipliers (calibrated for pro play)
CARRIER_KILL_MULTIPLIER = 3.0       # Killed flag/doc carrier
CARRIER_CHAIN_MULTIPLIER = 5.0      # Carrier kill + teammate returned within 10s
PUSH_QUALITY_THRESHOLD = 0.9          # Minimum push_quality to earn bonus
PUSH_BUFFER_MS = 2000                 # Tighter window (was 5000ms)
PUSH_TOWARD_EXCLUDE = frozenset(('NO', 'N/A', ''))  # Not a real objective push
CROSSFIRE_MULTIPLIER = 1.5          # Kill as part of crossfire setup
SPAWN_TIMING_BONUS = 1.0            # Added to 1.0 (so range 1.0-2.0 based on score 0-1)
OUTCOME_GIBBED = 1.3                # Kill was permanent (gibbed, no revive possible)
OUTCOME_REVIVED = 0.5               # Kill was undone by medic
OUTCOME_TAPPED = 1.0                # Normal (tapped out)
CLASS_WEIGHTS = {
    "MEDIC": 1.5,       # Removing healer = devastating
    "ENGINEER": 1.3,    # Removing objective player = opens path
    "FIELDOPS": 1.1,    # Removing supplier
    "SOLDIER": 1.0,     # Baseline
    "COVERTOPS": 1.0,   # Context-dependent
}
DISTANCE_LONG_RANGE = 1.2           # Kill at >800u (sniper pick)
DISTANCE_NORMAL = 1.0               # 100-800u
DISTANCE_MELEE = 0.9                # <100u (knife/close)

# Oksii adoption multipliers
LOW_HEALTH_THRESHOLD = 30           # HP threshold for clutch kill
LOW_HEALTH_MULTIPLIER = 1.3         # Kill with <30 HP = clutch
SOLO_CLUTCH_THRESHOLD = 3           # Enemies alive for solo clutch
SOLO_CLUTCH_MULTIPLIER = 2.0        # 1v3+ kill
OUTNUMBERED_MULTIPLIER = 1.5        # Kill while outnumbered
REINF_PENALTY_THRESHOLD = 0.75      # victim_reinf > 75% of spawn interval = bonus (legacy binary mode)

# Graduated reinforcement multiplier tiers (UTRO-inspired, 2026-04-20).
# Each tier is (max_reinf_seconds_exclusive, multiplier). The first tier
# whose max is greater than victim_reinf wins; the final tier uses infinity.
# Monotonic ramp from 0.70 (quick respawn — kill removed little time) up
# to 1.40 (full wave — kill caught them at max penalty).
#
# Replaces the binary 1.0 / 1.2 split used in KIS v2. Wider range and
# finer resolution better reflect the time-value of each kill, matching
# Stiba's UTRO formula philosophy while staying calibrated for KIS's
# multiplicative soft-cap at 5.0.
REINF_MULT_TIERS: tuple[tuple[float, float], ...] = (
    (2.0,  0.70),
    (5.0,  0.85),
    (10.0, 1.00),
    (15.0, 1.10),
    (20.0, 1.20),
    (25.0, 1.30),
    (float("inf"), 1.40),
)

# ── Team Synergy Score constants ────────────────────────────────
SYNERGY_WEIGHTS = {
    'crossfire': 0.25,
    'trade': 0.25,
    'cohesion': 0.20,
    'push': 0.15,
    'medic': 0.15,
}
COHESION_MAX_DISPERSION = 1500      # Game units; above this = 0 cohesion

# ── Timing windows (milliseconds) ─────────────────────────────────
# Previously magic numbers scattered across loaders, detectors, and SQL.
# Consolidated here so query tuning is one edit instead of ~20.
CARRIER_RETURN_WINDOW_MS = 10000    # Teammate must return the flag within 10s of the carrier kill
CROSSFIRE_TIMING_WINDOW_MS = 3000   # Crossfire teammate must have dealt damage within 3s of the kill
SPAWN_TIMING_WINDOW_MS = 2000       # Spawn-wave score keyed to kills within 2s of a spawn event
OBJECTIVE_EVENT_WINDOW_MS = 15000   # Kill is "objective-related" if within 15s of an obj event
KILL_STREAK_WINDOW_MS = 10000       # 3 kills within this window count as a streak
MULTIKILL_SHORT_WINDOW_MS = 5000    # 2-kill multikill requires this tight spacing
MULTIKILL_EXTENDED_WINDOW_MS = 8000 # 3+ kills allow a slightly longer spacing
TRADE_KILL_DELTA_MS = 5000          # Avenger must kill within 5s of teammate's death
LURKER_MIN_DURATION_MS = 2000       # player_track segments shorter than this are not "lurks"
DEATH_TRADE_WINDOW_MS = 10000       # Window after a death in which a trade counts

def _to_date(val: str | date) -> date:
    """Normalize to datetime.date for asyncpg DATE params (proximity tables use DATE type)."""
    if isinstance(val, date):
        return val
    return datetime.strptime(val, "%Y-%m-%d").date()


def _to_date_str(val: str | date) -> str:
    """Normalize to YYYY-MM-DD string for TEXT columns (player_comprehensive_stats.round_date)."""
    if isinstance(val, date):
        return val.isoformat()
    datetime.strptime(val, "%Y-%m-%d")  # validate
    return val


def _format_time_ms(ms: int) -> str:
    """Format milliseconds from round start as MM:SS."""
    if not ms or ms <= 0:
        return "0:00"
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


# Explicit export list so `from .base import *` is visible to ruff and mypy.
__all__ = [
    # stdlib / third-party re-exports used by mixin method bodies
    "asyncio",
    "traceback",
    "date",
    "datetime",
    "strip_et_colors",
    "weapon_name",
    "short_guid",
    # module-level helpers
    "_BoundedLockDict",
    "_compute_locks",
    "_safe_short",
    "_to_date",
    "_to_date_str",
    "_format_time_ms",
    "logger",
    # multipliers
    "CARRIER_KILL_MULTIPLIER",
    "CARRIER_CHAIN_MULTIPLIER",
    "PUSH_QUALITY_THRESHOLD",
    "PUSH_BUFFER_MS",
    "PUSH_TOWARD_EXCLUDE",
    "CROSSFIRE_MULTIPLIER",
    "SPAWN_TIMING_BONUS",
    "OUTCOME_GIBBED",
    "OUTCOME_REVIVED",
    "OUTCOME_TAPPED",
    "CLASS_WEIGHTS",
    "DISTANCE_LONG_RANGE",
    "DISTANCE_NORMAL",
    "DISTANCE_MELEE",
    "LOW_HEALTH_THRESHOLD",
    "LOW_HEALTH_MULTIPLIER",
    "SOLO_CLUTCH_THRESHOLD",
    "SOLO_CLUTCH_MULTIPLIER",
    "OUTNUMBERED_MULTIPLIER",
    "REINF_PENALTY_THRESHOLD",
    "REINF_MULT_TIERS",
    "SYNERGY_WEIGHTS",
    "COHESION_MAX_DISPERSION",
    # timing windows
    "CARRIER_RETURN_WINDOW_MS",
    "CROSSFIRE_TIMING_WINDOW_MS",
    "SPAWN_TIMING_WINDOW_MS",
    "OBJECTIVE_EVENT_WINDOW_MS",
    "KILL_STREAK_WINDOW_MS",
    "MULTIKILL_SHORT_WINDOW_MS",
    "MULTIKILL_EXTENDED_WINDOW_MS",
    "TRADE_KILL_DELTA_MS",
    "LURKER_MIN_DURATION_MS",
    "DEATH_TRADE_WINDOW_MS",
]


