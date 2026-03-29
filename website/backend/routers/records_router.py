"""Records router -- thin aggregator that includes all records sub-routers.

main.py includes this router, so existing route registration is preserved.
All endpoint logic lives in the records_*.py sub-router modules.
"""

from fastapi import APIRouter

from website.backend.routers.records_awards import router as awards_router
from website.backend.routers.records_maps import router as maps_router
from website.backend.routers.records_matches import router as matches_router
from website.backend.routers.records_overview import router as overview_router
from website.backend.routers.records_player import router as player_router
from website.backend.routers.records_seasons import router as seasons_router
from website.backend.routers.records_trends import router as trends_router
from website.backend.routers.records_weapons import router as weapons_router

router = APIRouter()

router.include_router(overview_router)
router.include_router(seasons_router)
router.include_router(maps_router)
router.include_router(weapons_router)
router.include_router(matches_router)
router.include_router(awards_router)
router.include_router(player_router)
router.include_router(trends_router)
