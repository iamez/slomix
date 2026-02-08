"""
Website Backend Routers
=======================

FastAPI routers for the ET:Legacy Statistics Website.

Available Routers:
    api: Statistics API endpoints
        - GET /api/stats/{player_guid}: Player statistics
        - GET /api/leaderboard: Top players by various metrics
        - GET /api/sessions: Recent gaming sessions
        - GET /api/records: All-time records

    auth: Authentication endpoints
        - GET /auth/discord: Discord OAuth login
        - GET /auth/callback: OAuth callback handler
        - GET /auth/logout: Session logout

    predictions: Match prediction endpoints
        - GET /api/predictions: List recent predictions
        - GET /api/predictions/{id}: Get specific prediction

    greatshot: Greatshot upload + analysis endpoints
        - POST /api/greatshot/upload
        - GET /api/greatshot
        - GET /api/greatshot/{id}
        - GET /api/greatshot/{id}/report.json
        - GET /api/greatshot/{id}/report.txt

Usage:
    from website.backend.routers import api, auth, predictions, greatshot

    app.include_router(api.router, prefix="/api")
    app.include_router(auth.router, prefix="/auth")
    app.include_router(predictions.router, prefix="/api")
"""

from website.backend.routers import api
from website.backend.routers import auth
from website.backend.routers import predictions
from website.backend.routers import greatshot

__all__ = ['api', 'auth', 'predictions', 'greatshot']
