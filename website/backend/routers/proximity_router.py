"""Proximity router — thin aggregator that includes all proximity sub-routers.

main.py includes this router, so existing route registration is preserved.
All endpoint logic lives in the proximity_*.py sub-router modules.
"""

from fastapi import APIRouter

from website.backend.routers.proximity_combat import router as combat_router
from website.backend.routers.proximity_dashboard import router as dashboard_router
from website.backend.routers.proximity_events import router as events_router
from website.backend.routers.proximity_movement import router as movement_router
from website.backend.routers.proximity_objectives import router as objectives_router
from website.backend.routers.proximity_player import router as player_router
from website.backend.routers.proximity_positions import router as positions_router
from website.backend.routers.proximity_round import router as round_router
from website.backend.routers.proximity_scoring import router as scoring_router
from website.backend.routers.proximity_support import router as support_router
from website.backend.routers.proximity_teamplay import router as teamplay_router
from website.backend.routers.proximity_trades import router as trades_router

router = APIRouter()

router.include_router(dashboard_router)
router.include_router(combat_router)
router.include_router(teamplay_router)
router.include_router(trades_router)
router.include_router(player_router)
router.include_router(round_router)
router.include_router(scoring_router)
router.include_router(objectives_router)
router.include_router(positions_router)
router.include_router(support_router)
router.include_router(events_router)
router.include_router(movement_router)
