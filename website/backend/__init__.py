"""
Website Backend Package
=======================

FastAPI backend for the ET:Legacy Statistics Website.

Structure:
    main.py: FastAPI application entry point
    dependencies.py: Dependency injection (database, auth)
    local_database_adapter.py: Database access layer (PostgreSQL)
    init_db.py: Database initialization utilities

Routers:
    routers/api.py: Stats API endpoints (/api/stats, /api/leaderboard, etc.)
    routers/auth.py: Authentication endpoints (Discord OAuth)
    routers/predictions.py: Prediction system endpoints

Services:
    services/website_session_data_service.py: Session data aggregation

Security Notes:
    - SESSION_SECRET must be set (no defaults allowed)
    - CORS restricted to specific origins
    - All SQL uses parameterized queries
    - Input validation on all endpoints

Running:
    cd website
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

__all__ = []
