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
        - POST /auth/logout: Session logout

    predictions: Match prediction endpoints
        - GET /api/predictions: List recent predictions
        - GET /api/predictions/{id}: Get specific prediction

    greatshot: Greatshot upload + analysis endpoints
        - POST /api/greatshot/upload
        - GET /api/greatshot
        - GET /api/greatshot/{id}
        - GET /api/greatshot/{id}/report.json
        - GET /api/greatshot/{id}/report.txt

    uploads: Community file upload library
        - POST /api/uploads: Upload a file
        - GET /api/uploads: Browse/search uploads
        - GET /api/uploads/{id}: Get upload details
        - GET /api/uploads/{id}/download: Download file
        - DELETE /api/uploads/{id}: Delete upload (owner only)
        - GET /api/uploads/tags/popular: Popular tags

    availability: Date-based availability API
        - GET /api/availability?from=...&to=...
        - POST /api/availability
        - GET /api/availability/me
        - GET/POST /api/availability/settings
        - GET/POST /api/availability/subscriptions

    planning: Planning room API
        - GET /api/planning/today
        - POST /api/planning/today/create
        - POST /api/planning/today/join
        - POST /api/planning/today/suggestions
        - POST /api/planning/today/vote
        - POST /api/planning/today/teams

Usage:
    from website.backend.routers import api, auth, predictions, greatshot, uploads, availability, planning

    app.include_router(api.router, prefix="/api")
    app.include_router(auth.router, prefix="/auth")
    app.include_router(predictions.router, prefix="/api")
    app.include_router(uploads.router, prefix="/api/uploads")
    app.include_router(availability.router, prefix="/api/availability")
    app.include_router(planning.router, prefix="/api/planning")
"""
__all__ = ["api", "auth", "predictions", "greatshot", "greatshot_topshots", "uploads", "availability", "planning"]
