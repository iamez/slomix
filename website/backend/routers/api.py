"""
Legacy API router stub.

All endpoints have been extracted to domain-specific routers:
  - players_router.py  (11 endpoints: search, link, profile, compare, leaderboard, matches, form, rounds)
  - records_router.py  (23 endpoints: overview, seasons, maps, weapons, matches, records, awards, hall-of-fame, trends, viz)
  - sessions_router.py (9 endpoints: session lists, details, graphs)
  - diagnostics_router.py (diagnostics/monitoring endpoints)
  - proximity_router.py (proximity analytics endpoints)

This file is kept as a stub so existing main.py imports don't break.
The router has no endpoints of its own.
"""

from fastapi import APIRouter

router = APIRouter()
